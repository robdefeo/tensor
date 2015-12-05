from os import mkdir
from os import path
from pymongo import MongoClient
from cv2 import IMREAD_COLOR
from cv2 import imdecode
from cv2 import imwrite
import requests
import numpy as np
import improc.features.preprocess as preprocess
from StringIO import StringIO
from PIL import Image


def is_corrupted(stream):
    try:
        img = Image.open(StringIO(stream.content))
        check = img.verify()
        del img
        return False
    except IOError:
        return True


def image_raw_preprocessing(img_stream):
    image_squared = None
    image_decoded = imdecode(np.fromstring(img_stream.content, np.uint8), flags=IMREAD_COLOR)
    if image_decoded is not None:
        try:
            image_autocropped = preprocess.autocrop(image_decoded)
        except AttributeError:
            return image_squared
        if image_autocropped is not None:
            image_scaled_max = preprocess.scale_max(image_autocropped)
            image_squared = preprocess.make_square(image_scaled_max)
    return image_squared


def update_product(data, prd_id):
    if any(data):
            collection.update(
                {"_id": prd_id},
                {"$set": data},
                upsert=False
            )

out_dir = 'out'

# Initializing MongoDB client
client = MongoClient('localhost', 27017)
test_db = client.jemboo_test
collection = test_db.shoes

if not(path.exists(out_dir)):
    mkdir(out_dir)
    print "Created output folder"

products = collection.find()

print "Downloading images..."
print_interval = products.count()/20
num_processed_products = 0
num_processed_imgs = 0
num_corrupted_imgs = 0
num_failed_crop = 0


for prd_index, product in enumerate(products):
    product_status = "ok"
    product_id = product['_id']

    if prd_index % print_interval == 0:
        print(str(prd_index / print_interval * 4) + "% of products scanned")

    set_data = {}
    for img_index, img in enumerate(product['images']):
        img_status = None
        url = img['url']
        img_id = img['_id']
        img_filename = out_dir + "/" + str(product_id) + "_" + str(img_id) + ".jpg"

        if "image_processed_status" not in img:  # check if image already exist

            img_data = requests.get(url, stream=True)

            if img_data.status_code == 200:
                processed_img = None

                if not is_corrupted(img_data):
                    processed_img = image_raw_preprocessing(img_data)
                else:
                    img_status = "image_corrupted"
                    product_status = "failed"
                    num_corrupted_imgs += 1

                if processed_img is not None:
                    imwrite(img_filename, processed_img)  # save image
                    img_status = "ok"
                else:
                    img_status = "autocropped_failed"
                    product_status = "failed"
                    num_failed_crop += 1

            else:
                img_status = "http_fail"
                product_status = "failed"
                print("Unable to retrieve image " + str(img_index) + "/" + str(prd_index))

            set_data["images.%s.image_processed_status" % img_index] = img_status  # update img status

        update_product(set_data, product_id)
        num_processed_imgs += 1

    set_data["processed_status"] = product_status  # update_product_status
    update_product(set_data, product_id)
    num_processed_products += 1

print "100% of products scanned\n"
print "Total number of processed products: %i" % num_processed_products
print "Total number of processed images: %i" % num_processed_imgs
print "Number of images failed to crop: %i" % num_failed_crop
print "Number of corrupted images: %i" % num_corrupted_imgs
