import tushare
import xlwt
import xlrd
from xlutils.copy import copy
import os
import time
from utils import insert_log
#from utils import first_date_of_last_month
import utils
import sys
import shutil
import PIL.Image
import requests
import traceback
from generate_tf_record import generate_tf_record

#UP = 0
#DOWN = 1
#category = ['up', 'down']
#qualified = []

#for i in range(2):
#    qualified.append([])

def comp(x, y):
    id1 = x[0]
    id2 = y[0]
    if id1 < id2:
        return -1
    if id1 > id2:
        return 1
    if id1 == id2:
        return 0


date = time.strftime('%Y-%m-%d',time.localtime(time.time()))
REFERENCE_DIR = os.path.join(utils.get_path_to_data_dir(), 'reference_' + date)

LOG_FILE = ''
#
# important do not delete the directory, because the call of tushare.get_hist_data() is very
# slow and tend of fail somtimes, it's important to keep the reference.xls and resume from
# there
#
def init():
    if not os.path.exists(REFERENCE_DIR):
        os.mkdir(REFERENCE_DIR)

    timestamp = time.strftime('%Y-%m-%d_%H-%M-%S', time.localtime(time.time()))
    log_fp = os.path.join(REFERENCE_DIR, 'log'+timestamp+'.txt')
    # create log file, overwrite mode
    global LOG_FILE
    LOG_FILE = open(log_fp, 'wb')

def generate_reference_xls():
    existing_rows = []

    #open the reference.xls file
    global date
    excel_fp = os.path.join(REFERENCE_DIR, 'reference_'+ date +'.xls')

    #create the xls file and the read_worksheet if it doesn't yet exist
    if not os.path.exists(excel_fp):
        write_workbook = xlwt.Workbook()
        write_workbook.add_sheet('all')
        write_workbook.save(excel_fp)

    #get the baseline existing_rows from the xls file
    read_workbook = xlrd.open_workbook(excel_fp)
    read_worksheet = read_workbook.sheet_by_name('all')
    rows = read_worksheet.nrows
    for i in range(0, rows):
        existing_rows.append(read_worksheet.row_values(i))
        #existing_rows.sort(comp)
    insert_log(LOG_FILE, 'Read ' + format(read_worksheet.nrows, "") + ' rows from file ' + excel_fp)

    write_workbook = copy(read_workbook)
    write_worksheet = write_workbook.get_sheet('all')

    #to skip the existing data we need to have the existing_rows of ID in existing_rows
    #we already know the format of existing_rows is [[id1, x, y, z, ...], [id2, x, y, z, ...] ...]
    ids_in_worksheet =[]
    for i in existing_rows:
        ids_in_worksheet.append(i[0])

    #get all stock info
    stock_info = tushare.get_stock_basics()
    insert_log (LOG_FILE, 'There are ' + format(len(stock_info), "") + ' items from tushare.get_stock_basics()')

    count = 0

    for id in stock_info.index:
        count += 1
        insert_log(LOG_FILE, 'processing ' + format(count, "") + ': ' + id)

        if id in ids_in_worksheet:
            insert_log(LOG_FILE, 'Already has ' + id + ' skip it')
            continue

        #test code
        #if count > 100:
        #     break

        month = utils.last_month()
        try:
            history_data = tushare.get_hist_data(id, start=utils.first_date_of_last_month(), retry_count=5, pause=1)
            #print history_data.columns
            #print history_data[0:4]
            close_price = history_data[u'close']
            print history_data
        except Exception:
            ##  nothing to handle
            insert_log(LOG_FILE, 'Exception when handling ' + id)
            info = sys.exc_info()
            print (info[0], ':', info[1])
            continue

        continous_up = False
        continous_down = False

        #only need to analyze if we have at least 4 sample
        if(len(close_price) >= 4):
            continous_up = True
            continous_down = True

            from trend_analysis_utils import get_trend_type
            trend = get_trend_type(close_price)

        #row = read_worksheet.nrows
        #read_worksheet.write(row, 0, id)
        try:
            record = []

            last_date = close_price.keys()[0]

            three_days_ago = 'NA'
            if len(close_price.keys()) >= 4:
                three_days_ago = close_price.keys()[3]

            open_price = history_data[u'open'][0]
            high = history_data[u'high'][0]
            low = history_data[u'low'][0]
            price_change = history_data[u'price_change'][0]
            volume = history_data[u'volume'][0]
            p_change = history_data[u'p_change'][0]
            ma5 = history_data[u'ma5'][0]
            ma10 = history_data[u'ma10'][0]
            ma20 = history_data[u'ma20'][0]
            v_ma5 = history_data[u'v_ma5'][0]
            v_ma10 = history_data[u'v_ma10'][0]
            v_ma20 = history_data[u'v_ma20'][0]
            turnover = history_data[u'turnover'][0]


            #
            #[id, 3_day_trend, date, open price, close price, high, low, volume, price_change, p_change, ma5, ma10, ma20, v_ma5, v_ma10, v_ma20, turnover]
            #

            record.append(id)
            record.append(trend)
            record.append(last_date)
            record.append(three_days_ago)
            record.append(open_price)
            record.append(close_price[0])
            record.append(high)
            record.append(low)
            record.append(volume)
            record.append(price_change)
            record.append(p_change)
            record.append(ma5)
            record.append(ma10)
            record.append(ma20)
            record.append(v_ma5)
            record.append(v_ma10)
            record.append(v_ma20)
            record.append(turnover)

            for i in range(len(record)):
                write_worksheet.write(rows, i, record[i])

            rows += 1

            write_workbook.save(excel_fp)
            insert_log(LOG_FILE, 'written to file ' + excel_fp)

        except Exception, e:
            insert_log(LOG_FILE, 'Exception when handling id ' + id)
            info = sys.exc_info()
            print traceback.print_exc()
            continue

        #existing_rows.append([id, trend, date, open_price, close_price[0], high, low, price_change, ma5, ma10, ma20, v_ma5, v_ma10, v_ma20, turnover])
        insert_log(LOG_FILE, id + ' 3 day trend is ' + trend)


    insert_log(LOG_FILE, 'Finished populating reference.xls')

#
# this function creates directory JPEGImages and downloads all the k line images to it
# if the JPEGImages directory already exists, it will be deleted so every time it's a
# full download of all images
#
def download_daily_image():
    JPEG_DIR = os.path.join(REFERENCE_DIR, 'JPEGImages')

    if os.path.exists(JPEG_DIR):
        shutil.rmtree(JPEG_DIR)
    os.mkdir(JPEG_DIR)

    stock_info = tushare.get_stock_basics()

    # download gif and save as jpeg for each id from tushare
    for id in stock_info.index:
        # if id != '002270': continue

        # insert prefix
        if ((id.find('300') == 0 or id.find('00') == 0)):
            id = 'sz' + id
        elif (id.find('60') == 0):
            id = 'sh' + id
        else:
            LOG_ID_NOT_HANDLED = 'Don\'t know how to handle ID:' + id + ', skip and continue'
            insert_log(LOG_FILE, LOG_ID_NOT_HANDLED)
            continue

        insert_log(LOG_FILE, 'Start downloading gif for ' + id)

        # download the gif file
        url = 'http://image.sinajs.cn/newchart/daily/n/' + id + '.gif'
        gif = requests.get(url)

        try:
            # save gif file to folder IMAGE_DATA_DIR
            gif_file_name = os.path.join(JPEG_DIR, id + '.gif')
            gif_fp = open(gif_file_name, 'wb')
            gif_fp.write(gif.content)
            gif_fp.close()
            insert_log(LOG_FILE, 'Complete downloading ' + id + '.gif')

            # save the gif to jpeg
            # need the convert otherwise will report raise IOError("cannot write mode %s as JPEG" % im.mode)
            im = PIL.Image.open(gif_file_name)
            im = im.convert('RGB')
            jpeg_file = os.path.join(JPEG_DIR, id + '.jpeg')
            im.save(jpeg_file)
            insert_log(LOG_FILE, 'Saved file ' + os.path.realpath(jpeg_file))
            # delete the gif file
            os.remove(gif_file_name)

        except IOError, err:
            insert_log(LOG_FILE, 'IOError when handling ' + id)
            info = sys.exc_info()
            print (info[0], ':', info[1])
            continue
        except Exception, e:
            insert_log(LOG_FILE, 'Exception when handling ' + id)
            info = sys.exc_info()
            print (info[0], ':', info[1])
            continue

    insert_log(LOG_FILE, 'Finished downloading jpeg files')
#
# generate files in directory training_data, including two sub-dirs
# JPEGImages and annotations.
# It reads the reference_<date>.xls file to determine what JPEG files
# should be copied to sub-dir JPEGImages. Then it generates the xml files in the annotations sub-dir
#
def generate_training_data():
    excel_fp = os.path.join(REFERENCE_DIR, 'reference_' + date + '.xls')
    traing_data_dir = os.path.join(REFERENCE_DIR, 'training_data')
    if os.path.exists(traing_data_dir):
        shutil.rmtree(traing_data_dir)
    os.mkdir(traing_data_dir)
    insert_log(LOG_FILE, 'create dir ' + traing_data_dir)

    IMAGE_directory = os.path.join(traing_data_dir, 'JPEGImages')
    if not os.path.exists(IMAGE_directory):
        os.mkdir(IMAGE_directory)
        insert_log(LOG_FILE, 'create dir ' + IMAGE_directory)
    else:
        insert_log(LOG_FILE, 'dir ' + IMAGE_directory + ' already exists')

    annotation_directory = os.path.join(traing_data_dir, 'annotations')
    if not os.path.exists(annotation_directory):
        os.mkdir(annotation_directory)
        insert_log(LOG_FILE, 'create dir ' + annotation_directory)
    else:
        insert_log(LOG_FILE, 'dir ' + annotation_directory + ' already exist')

    insert_log(LOG_FILE, 'open ' + excel_fp)
    read_workbook = xlrd.open_workbook(excel_fp)
    read_worksheet = read_workbook.sheet_by_name('all')
    rows = []
    for i in range(0, read_worksheet.nrows):
        rows.append(read_worksheet.row_values(i))
    insert_log(LOG_FILE, 'read '+ format(len(rows),"") + ' rows from xls file')

    examples_fp = os.path.join(traing_data_dir, 'examples.txt')
    examples_file = open(examples_fp, 'w')

    model_bias_fp = os.path.join(traing_data_dir, 'model_bias_'+ date+'.xls')
    if os.path.exists(model_bias_fp):
        os.remove(model_bias_fp)
        insert_log(LOG_FILE, 'delete file ' + model_bias_fp)

    model_bias_workbook = xlwt.Workbook()
    model_bias_worksheet = model_bias_workbook.add_sheet('bias')

    #cursor of model_bias_worksheet
    model_bias_worksheet_cursor = 0

    for i in range(len(rows)):
        trend = rows[i][1]
        if (trend != 'NA'):
            id = rows[i][0]
            three_days_ago = rows[i][3]

            # insert prefix
            if ((id.find('300') == 0 or id.find('00') == 0)):
                id = 'sz' + id
            elif (id.find('60') == 0):
                id = 'sh' + id
            else:
                LOG_ID_NOT_HANDLED = 'Don\'t know how to handle ID:' + id + ', skip and continue'
                insert_log(LOG_FILE, LOG_ID_NOT_HANDLED)
                continue

            if three_days_ago == '':
                continue

            ref_directory = os.path.join(utils.get_path_to_data_dir(), 'reference_'+three_days_ago)
            if not os.path.exists(ref_directory):
                insert_log(LOG_FILE, ref_directory + ' does not exist for id ' + format(id, ""))
                continue

            source_JPEG_dir = os.path.join(ref_directory, 'JPEGImages')
            if not os.path.exists(source_JPEG_dir):
                insert_log(LOG_FILE, source_JPEG_dir + ' does not exist for id ' + format(id, ""))
                continue

            source_JPEG_file = os.path.join(source_JPEG_dir, id+'.jpeg')
            if not os.path.exists(source_JPEG_file):
                insert_log(LOG_FILE, source_JPEG_file + ' does not exist for id ' + format(id, ""))
                continue

            insert_log(LOG_FILE, source_JPEG_file + ' found')
            shutil.copy(source_JPEG_file, IMAGE_directory)

            JPEG_file = os.path.join(IMAGE_directory, id+'.jpeg')

            ##create XML for each jpeg file
            # < annotation >
            #   < folder > data_image < / folder >
            #   < filename > sh600055.jpeg < / filename >
            #   < path > /home/davidcui/PycharmProjects/test01/data_image/sh600055.jpeg < / path >
            #   < source >
            #       < database > Unknown < / database >
            #   < / source >
            #   < size >
            #       < width > 545 < / width >
            #       < height > 300 < / height >
            #       < depth > 3 < / depth >
            #   < / size >
            #   < segmented > 0 < / segmented >
            #   < object >
            #       < name > up < / name >
            #       < pose > Unspecified < / pose >
            #       < truncated > 0 < / truncated >
            #       < difficult > 0 < / difficult >
            #       < bndbox >
            #           < xmin > 50 < / xmin >
            #           < ymin > 17 < / ymin >
            #           < xmax > 532 < / xmax >
            #           < ymax > 287 < / ymax >
            #       < / bndbox >
            #   < / object >
            # < / annotation >
            ##


            import xml.dom.minidom

            doc = xml.dom.minidom.Document()
            # root node
            root = doc.createElement('annotation')
            doc.appendChild(root)

            folder = doc.createElement('folder')
            folder.appendChild(doc.createTextNode(IMAGE_directory))
            root.appendChild(folder)

            filename = doc.createElement('filename')
            filename.appendChild(doc.createTextNode(os.path.basename(JPEG_file)))
            root.appendChild(filename)

            path = doc.createElement('path')
            path.appendChild(doc.createTextNode(os.path.realpath(JPEG_file)))
            root.appendChild(path)

            source = doc.createElement('source')
            database = doc.createElement('database')
            database.appendChild(doc.createTextNode('Unknown'))
            source.appendChild(database)
            root.appendChild(source)

            size = doc.createElement('size')
            width = doc.createElement('width')
            width.appendChild(doc.createTextNode('545'))
            height = doc.createElement('height')
            height.appendChild(doc.createTextNode('300'))
            depth = doc.createElement('depth')
            depth.appendChild(doc.createTextNode('3'))
            size.appendChild(width)
            size.appendChild(height)
            size.appendChild(depth)
            root.appendChild(size)

            segmented = doc.createElement('segmented')
            segmented.appendChild(doc.createTextNode('0'))
            root.appendChild(segmented)

            object = doc.createElement('object')
            name = doc.createElement('name')
            name.appendChild(doc.createTextNode(trend))
            pose = doc.createElement('pose')
            pose.appendChild(doc.createTextNode('Unspecified'))
            truncated = doc.createElement('truncated')
            truncated.appendChild(doc.createTextNode('0'))
            difficult = doc.createElement('difficult')
            difficult.appendChild(doc.createTextNode('0'))
            bndbox = doc.createElement('bndbox')
            xmin = doc.createElement('xmin')
            xmin.appendChild(doc.createTextNode('50'))
            bndbox.appendChild(xmin)
            ymin = doc.createElement('ymin')
            ymin.appendChild(doc.createTextNode('17'))
            bndbox.appendChild(ymin)
            xmax = doc.createElement('xmax')
            xmax.appendChild(doc.createTextNode('532'))
            bndbox.appendChild(xmax)
            ymax = doc.createElement('ymax')
            ymax.appendChild(doc.createTextNode('287'))
            bndbox.appendChild(ymax)

            object.appendChild(name)
            object.appendChild(pose)
            object.appendChild(truncated)
            object.appendChild(difficult)
            object.appendChild(bndbox)
            root.appendChild(object)

            xml_fp = open(os.path.join(annotation_directory, id + '.xml'), 'wb')
            doc.writexml(xml_fp, indent='\t', addindent='\t', newl='\n', encoding="utf-8")
            # print('Saved file '+ os.path.realpath(xml_fp))
            insert_log(LOG_FILE, 'Saved file ' + id + '.xml for trend ' + trend)

            examples_file.write(id + ' 1\n')
            insert_log(LOG_FILE, id + ' written to file ' + examples_fp)

            #[id, date, trend, weight]
            model_bias_worksheet.write(model_bias_worksheet_cursor, 0, id)
            model_bias_worksheet.write(model_bias_worksheet_cursor, 1, date)
            model_bias_worksheet.write(model_bias_worksheet_cursor, 2, trend)
            if trend == 'up':
                model_bias_worksheet.write(model_bias_worksheet_cursor, 3, 1.0)
            elif trend == 'down':
                model_bias_worksheet.write(model_bias_worksheet_cursor, 3, -1.0)
            insert_log(LOG_FILE, 'insert row '+ format(model_bias_worksheet_cursor,"") +' [' + id + ',' + date + ','+ trend + ',' + '+/- 1.0] to ' + model_bias_fp)
            model_bias_worksheet_cursor += 1

    examples_file.close()
    model_bias_workbook.save(model_bias_fp)

    insert_log(LOG_FILE, 'Finished generating annotations')

if __name__ == "__main__":
    init()
    generate_reference_xls()
    generate_training_data()

    download_daily_image()

    training_data_dir = os.path.join(REFERENCE_DIR, 'training_data')
    output_path = os.path.join(training_data_dir, 'price.record')
    label_map_path = '/home/davidcui/Documents/price/label_map.pbtxt'
    generate_tf_record(training_data_dir, output_path, label_map_path)

    LOG_FILE.close()
