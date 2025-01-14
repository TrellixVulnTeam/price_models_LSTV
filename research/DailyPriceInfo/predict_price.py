import numpy as np
import os
import six.moves.urllib as urllib
import sys
import tarfile
import tensorflow as tf
import zipfile
import xlwt
import shutil

from collections import defaultdict
from io import StringIO
#from matplotlib import pyplot as plt
from PIL import Image

from object_detection.utils import label_map_util

from object_detection.utils import visualization_utils as vis_util

PATH_TO_PREDICTION_DIR = '/home/davidcui/Documents/price/prediction'
if not os.path.exists(PATH_TO_PREDICTION_DIR):
    print 'Directory not exist:',PATH_TO_PREDICTION_DIR
    exit(0)

# Path to frozen detection graph. This is the actual model that is used for the object detection.
PATH_TO_CKPT = os.path.join(PATH_TO_PREDICTION_DIR,'frozen_inference_graph.pb')
if not os.path.exists(PATH_TO_CKPT):
    print 'File not exist:',PATH_TO_CKPT
    exit(0)

# List of the strings that is used to add correct label for each box.
PATH_TO_LABELS = '/home/davidcui/Documents/price/label_map.pbtxt'
if not os.path.exists(PATH_TO_LABELS):
    print 'File not exist:', PATH_TO_LABELS
    exit(0)

PATH_TO_TEST_IMAGES_DIR = os.path.join(PATH_TO_PREDICTION_DIR, 'test_image')
if not os.path.exists(PATH_TO_TEST_IMAGES_DIR):
    print 'Directory not exist:', PATH_TO_TEST_IMAGES_DIR
    exit(0)

PATH_TO_RESULT_DIR = os.path.join(PATH_TO_PREDICTION_DIR, 'result')
#PATH_TO_UP_IMAGE_DIR = os.path.join(PATH_TO_RESULT_DIR, 'up')
#PATH_TO_DOWN_IMAGE_DIR = os.path.join(PATH_TO_RESULT_DIR, 'down')

if os.path.exists(PATH_TO_RESULT_DIR):
    shutil.rmtree(PATH_TO_RESULT_DIR)
    print 'Delete exisint directory ',PATH_TO_RESULT_DIR

os.mkdir(PATH_TO_RESULT_DIR)
#os.mkdir(PATH_TO_UP_IMAGE_DIR)
#os.mkdir(PATH_TO_DOWN_IMAGE_DIR)
print 'Create directory', PATH_TO_RESULT_DIR
#print 'Create directory', PATH_TO_UP_IMAGE_DIR
#print 'Create directory', PATH_TO_DOWN_IMAGE_DIR


RESULT_EXCEL_FILE_PATH = os.path.join(PATH_TO_RESULT_DIR,'result.xls')

NUM_CLASSES = 10

#load the frozen inference graph
detection_graph = tf.Graph()
with detection_graph.as_default():
  od_graph_def = tf.GraphDef()
  with tf.gfile.GFile(PATH_TO_CKPT, 'rb') as fid:
    serialized_graph = fid.read()
    od_graph_def.ParseFromString(serialized_graph)
    tf.import_graph_def(od_graph_def, name='')

#load label map
label_map = label_map_util.load_labelmap(PATH_TO_LABELS)
categories = label_map_util.convert_label_map_to_categories(label_map, max_num_classes=NUM_CLASSES, use_display_name=True)
category_index = label_map_util.create_category_index(categories)

for cat_idx in category_index:
    cat_name = category_index[cat_idx]['name']
    cat_dir = os.path.join(PATH_TO_RESULT_DIR, cat_name)
    os.mkdir(cat_dir)
    print 'Create directory', cat_dir

#helper code
def load_image_into_numpy_array(image):
  (im_width, im_height) = image.size
  return np.array(image.getdata()).reshape(
      (im_height, im_width, 3)).astype(np.uint8)

#load test image
# use all the jpeg images in test_image
files = os.listdir(PATH_TO_TEST_IMAGES_DIR)
jpeg_files = []
for file in files:
    if os.path.splitext(file)[1] == '.jpeg':
        jpeg_files.append(file)

TEST_IMAGE_PATHS = [ os.path.join(PATH_TO_TEST_IMAGES_DIR, name) for name in jpeg_files ]

#create result file work book
result_data = xlwt.Workbook()
# create worksheets and populate first row
for sheet_name in category_index:
    sheet = result_data.add_sheet(category_index[sheet_name]['name'])
    row0 = ['ID', 'Score']
    for col in range(len(row0)):
        sheet.write(0, col, row0[col])

# Size, in inches, of the output images.
IMAGE_SIZE = (24, 16)

cursor = [1, 1]

with detection_graph.as_default():
  with tf.Session(graph=detection_graph) as sess:
    # Definite input and output Tensors for detection_graph
    image_tensor = detection_graph.get_tensor_by_name('image_tensor:0')
    # Each box represents a part of the image where a particular object was detected.
    detection_boxes = detection_graph.get_tensor_by_name('detection_boxes:0')
    # Each score represent how level of confidence for each of the objects.
    # Score is shown on the result image, together with the class label.
    detection_scores = detection_graph.get_tensor_by_name('detection_scores:0')
    detection_classes = detection_graph.get_tensor_by_name('detection_classes:0')
    num_detections = detection_graph.get_tensor_by_name('num_detections:0')
    for image_path in TEST_IMAGE_PATHS:
      image = Image.open(image_path)
      # the array based representation of the image will be used later in order to prepare the
      # result image with boxes and labels on it.
      image_np = load_image_into_numpy_array(image)
      # Expand dimensions since the model expects images to have shape: [1, None, None, 3]
      image_np_expanded = np.expand_dims(image_np, axis=0)
      # Actual detection.
      (boxes, scores, classes, num) = sess.run(
          [detection_boxes, detection_scores, detection_classes, num_detections],
          feed_dict={image_tensor: image_np_expanded})

      squeeze_classes = np.squeeze(classes).astype(np.int32)
      squeeze_scores = np.squeeze(scores)

      result_str = ''
      for i in range(boxes.shape[0]):
          if squeeze_classes[i] in category_index.keys():
            class_name = category_index[squeeze_classes[i]]['name']
          else:
            class_name = 'N/A'
          score_str = display_str = '{}=>{}%'.format(
              class_name,
              int(100*squeeze_scores[i]))
          result_str = result_str + score_str + '; '

          #populate excel sheet
          sheet = result_data.get_sheet(class_name)
          #sheet = result_data.Worksheet(class_name)
          sheet.write(cursor[squeeze_classes[i] - 1], 0, os.path.basename(image_path))
          sheet.write(cursor[squeeze_classes[i] - 1], 1, format(int(100*squeeze_scores[i])))
          cursor[squeeze_classes[i] - 1] += 1

      print(image_path + ': ' + result_str)
      # Visualization of the results of a detection.
      vis_util.visualize_boxes_and_labels_on_image_array(
          image_np,
          np.squeeze(boxes),
          np.squeeze(classes).astype(np.int32),
          np.squeeze(scores),
          category_index,
          use_normalized_coordinates=True,
          line_thickness=8)
      #plt.figure(figsize=IMAGE_SIZE)
      #plt.imshow(image_np)
      #if(class_name == 'up'):
      #    up_image_file = os.path.join(PATH_TO_UP_IMAGE_DIR, score_str+'_'+os.path.basename(image_path))
      #    Image.fromarray(image_np).save(up_image_file)
      #    print 'Save file ',up_image_file
      #elif(class_name == 'down'):
      #    down_image_file = os.path.join(PATH_TO_DOWN_IMAGE_DIR, score_str+'_'+os.path.basename(image_path))
      #    Image.fromarray(image_np).save(down_image_file)
      #    print 'Save file ', down_image_file

      #Save image to path according to class_name
      path_to_save = os.path.join(PATH_TO_RESULT_DIR, class_name)
      image_file = os.path.join(path_to_save, score_str+'_'+os.path.basename(image_path))
      Image.fromarray(image_np).save(image_file)
      print 'Save file ', image_file

# save the results in Excel file
result_data.save(RESULT_EXCEL_FILE_PATH)