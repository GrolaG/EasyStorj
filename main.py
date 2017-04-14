# -*- coding: utf-8 -*-
import base64
import hashlib
import hmac
import json
from PyQt4 import Qt

import magic
import os
import operator
import socket
import sys
import threading
import time
from PyQt4 import QtCore, QtGui

#import pycountry
import requests
import storj
from PyQt4.QtCore import QAbstractTableModel, SIGNAL
from PyQt4.QtCore import QVariant
from PyQt4.QtGui import *
#from ipwhois import IPWhois
from storj import exception
from storj import model

#from bucket_manage_ui import Ui_BucketManager
#from client_configuration_ui import Ui_ClientConfiguration
#from create_bucket_ui import Ui_BucketCreate
from file_crypto_tools import FileCrypto  # file ancryption and decryption lib
#from file_manager_ui import Ui_FileManager
#from file_mirrors_list_ui import Ui_FileMirrorsList
#from initial_window_ui import Ui_InitialWindow
#from main_menu_ui import Ui_MainMenu
#from node_details_ui import Ui_NodeDetails
#from single_file_downloader_ui import Ui_SingleFileDownload
#from single_file_upload_ui import Ui_SingleFileUpload
#from storj_login_ui import Ui_Login
#from storj_register_ui import Ui_Register
from sharder import ShardingTools
from tools import Tools
#from backend_config import Configuration
from account_manager import AccountManager

# UI
#from UI.login import LoginUI
#from UI.registration import RegisterUI
from UI.mainUI import MainUI
from UI.initial_window import InitialWindowUI

# CONSIDER A BETTER PLACE WHERE TO MOVE THIS
from UI.engine import StorjEngine

# ext libs

# Define CONSTANS


global SHARD_MULTIPLES_BACK, MAX_SHARD_SIZE

MAX_SHARD_SIZE = 4294967296  # 4Gb
SHARD_MULTIPLES_BACK = 4

global html_format_begin, html_format_end
html_format_begin = "<html><head/><body><p><span style=\" font-size:12pt; font-weight:600;\">"
html_format_end = "</span></p></body></html>"



class ProgressBar(QProgressBar):

    def __init__(self, value, parent=None):
        QProgressBar.__init__(self)
        self.setMinimum(1)
        self.setMaximum(100)
        self.setValue(value)
        self.setFormat('{0:.5f}'.format(value))
        #style = ''' QProgressBar{max-height: 15px;text-align: center;}'''
        #self.setStyleSheet(style)

class ProgressWidgetItem(QTableWidgetItem):

    def __lt__(self, other):
        return self.data(Qt.UserRole) < other.data(Qt.UserRole)

    def updateValue(self, value):
        self.setData(Qt.UserRole, value)


class MyTableModel(QtCore.QAbstractTableModel):
    def __init__(self,data,parent=None):
        QtCore.QAbstractTableModel.__init__(self,parent)
        self.__data=data     # Initial Data

    def rowCount( self, parent ):
        return len(self.__data)

    def columnCount( self , parent ):
        return len(self.__data)

    def data ( self , index , role ):
        if role == QtCore.Qt.DisplayRole:
            row = index.row()
            column = index.column()
            value = self.__data[row][column]
            return QtCore.QString(str(value))

    def setData(self, index, value):
        self.__data[index.row()][index.column()] = value
        return True

    def flags(self, index):
        return QtCore.Qt.ItemIsEnabled|QtCore.Qt.ItemIsEditable|QtCore.Qt.ItemIsSelectable

    def insertRows(self , position , rows , item , parent=QtCore.QModelIndex()):
        # beginInsertRows (self, QModelIndex parent, int first, int last)
        self.beginInsertRows(QtCore.QModelIndex(),len(self.__data),len(self.__data)+1)
        self.__data.append(item) # Item must be an array
        self.endInsertRows()
        return True


######################################################################################################################################
####################### FILE MANAGER UI ##################################





class DownloadTaskQtThread(QtCore.QThread):
    tick = QtCore.pyqtSignal(int, name="upload_changed")

    def __init__(self, url, path_to_save, options_chain, progress_bar):
        QtCore.QThread.__init__(self)
        self.obj_thread = QtCore.QThread()
        self.url = url
        self.path_to_save = path_to_save
        self.options_chain = options_chain
        self.progress_bar = progress_bar

        # def run(self):
        # self.client.create_download_connection(self, None, None, None, None)

    # def create_download_connection(self, url, path_to_save, options_chain, progress_bar):
    def run(self):
        print "test"
        local_filename = self.path_to_save
        if self.options_chain["handle_progressbars"] != "1":
            r = requests.get(self.url)
            # requests.
            with open(self.local_filename, 'wb') as f:
                for chunk in r.iter_content(chunk_size=1024):
                    if chunk:  # filter out keep-alive new chunks
                        f.write(chunk)
        else:
            r = requests.get(self.url, stream=True)
            f = open(local_filename, 'wb')
            if self.options_chain["file_size_is_given"] == "1":
                file_size = self.options_chain["shard_file_size"]
            else:
                file_size = int(r.headers['Content-Length'])

            chunk = 1
            num_bars = file_size / chunk
            t1 = file_size / (32 * 1024)
            i = 0
            print file_size
            for chunk in r.iter_content(32 * 1024):
                f.write(chunk)
                print str(i) + " " + str(t1)
                print round(float(i) / float(t1), 1)
                print str(int(round((100.0 * i) / t1))) + " %"
                percent_downloaded = int(round((100.0 * i) / t1))
                # Refactor for fix SIGSEGV
                # self.tick.emit(percent_downloaded)
                # self.emit(SIGNAL("setStatus"), percent_downloaded , "information")
                # Old
                # progress_bar.setValue (percent_downloaded)
                i += 1
            f.close()
            return


##################### CRYPTOGRAPHY TOOLS ################################
class CryptoTools():
    def calculate_hmac(self, base_string, key):
        """
        HMAC hash calculation and returning the results in dictionary collection
        FROM: <https://janusznawrat.wordpress.com/2015/04/08/wyliczanie-kryptograficznych-sum-kontrolnych-hmac-plikow-i-lancuchow-znakowych/>
        """
        hmacs = dict()
        # --- MD5 ---
        hashed = hmac.new(key, base_string, hashlib.md5)
        hmac_md5 = hashed.digest().encode("base64").rstrip('\n')
        hmacs['MD5'] = hmac_md5
        # --- SHA-1 ---
        hashed = hmac.new(key, base_string, hashlib.sha1)
        hmac_sha1 = hashed.digest().encode("base64").rstrip('\n')
        hmacs['SHA-1'] = hmac_sha1
        # --- SHA-224 ---
        hashed = hmac.new(key, base_string, hashlib.sha224)
        hmac_sha224 = hashed.digest().encode("base64").rstrip('\n')
        hmacs['SHA-224'] = hmac_sha224
        # --- SHA-256 ---
        hashed = hmac.new(key, base_string, hashlib.sha256)
        hmac_sha256 = hashed.digest().encode("base64").rstrip('\n')
        hmacs['SHA-256'] = hmac_sha256
        # --- SHA-384 ---
        hashed = hmac.new(key, base_string, hashlib.sha384)
        hmac_sha384 = hashed.digest().encode("base64").rstrip('\n')
        hmacs['SHA-384'] = hmac_sha384
        # --- SHA-512 ---
        hashed = hmac.new(key, base_string, hashlib.sha512)
        hmac_sha512 = hashed.digest().encode("base64").rstrip('\n')
        hmacs['SHA-512'] = hmac_sha512
        return hmacs

    def prepare_bucket_entry_hmac(self, shard_array):
        storj_keyring = storj.model.Keyring()
        encryption_key = storj_keyring.get_encryption_key("test")
        current_hmac = ""
        for shard in shard_array:
            base64_decoded = str(base64.decodestring(shard.hash)) + str(current_hmac)
            current_hmac = self.calculate_hmac(base64_decoded, encryption_key)

        print current_hmac
        return current_hmac


class StorjSDKImplementationsOverrides():
    def __init__(self, parent=None):
        self.storj_engine = StorjEngine()  # init StorjEngine




################################################################# SINGLE FILE UPLOADER UI SECTION ###################################################################
class SingleFileUploadUI(QtGui.QMainWindow):
    def __init__(self, parent=None, bucketid=None, fileid=None):
        QtGui.QWidget.__init__(self, parent)
        self.ui_single_file_upload = Ui_SingleFileUpload()
        self.ui_single_file_upload.setupUi(self)
        QtCore.QObject.connect(self.ui_single_file_upload.start_upload_bt, QtCore.SIGNAL("clicked()"),
                               self.createNewUploadThread)  # open bucket manager
        QtCore.QObject.connect(self.ui_single_file_upload.file_path_select_bt, QtCore.SIGNAL("clicked()"),
                               self.select_file_path)  # open file select dialog
        QtCore.QObject.connect(self.ui_single_file_upload.tmp_path_select_bt, QtCore.SIGNAL("clicked()"),
                               self.select_tmp_directory)  # open tmp directory select dialog
        self.storj_engine = StorjEngine()  # init StorjEngine

        self.initialize_upload_queue_table()

        # set default paths

        self.ui_single_file_upload.tmp_path.setText(str("/tmp/"))


        # initialize variables
        self.shards_already_uploaded = 0
        self.uploaded_shards_count = 0
        self.upload_queue_progressbar_list = []

        self.connect(self, SIGNAL("addRowToUploadQueueTable"), self.add_row_upload_queue_table)

        self.connect(self, SIGNAL("incrementShardsProgressCounters"), self.increment_shards_progress_counters)
        self.connect(self, SIGNAL("updateUploadTaskState"), self.update_upload_task_state)
        self.connect(self, SIGNAL("updateShardUploadProgress"), self.update_shard_upload_progess)
        self.connect(self, SIGNAL("showFileNotSelectedError"), self.show_error_not_selected_file)
        self.connect(self, SIGNAL("showInvalidPathError"), self.show_error_invalid_file_path)
        self.connect(self, SIGNAL("showInvalidTemporaryPathError"), self.show_error_invalid_temporary_path)

        self.createBucketResolveThread() # resolve buckets and put to buckets combobox

        # file_pointers = self.storj_engine.storj_client.file_pointers("6acfcdc62499144929cf9b4a", "dfba26ab34466b1211c60d02")

        #self.emit(SIGNAL("addRowToUploadQueueTable"), "important", "information")
        #self.emit(SIGNAL("addRowToUploadQueueTable"), "important", "information")
        #self.emit(SIGNAL("incrementShardsProgressCounters"))

        self.max_retries_upload_to_same_farmer = 3
        self.max_retries_negotiate_contract = 10

        #
        # print self.config.max_retries_upload_to_same_farmer

        # self.initialize_shard_queue_table(file_pointers)
    def update_shard_upload_progess (self, row_position_index, value):
        self.upload_queue_progressbar_list[row_position_index].setValue(value)
        print "kotek"
        return 1

    def update_upload_task_state(self, row_position, state):
        self.ui_single_file_upload.shard_queue_table_widget.setItem(int(row_position), 3, QtGui.QTableWidgetItem(str(state)))

    def show_error_not_selected_file(self):
        QMessageBox.about(self, "Error", "Please select file which you want to upload!")

    def show_error_invalid_file_path(self):
        QMessageBox.about(self, "Error", "File path seems to be invalid!")

    def show_error_invalid_temporary_path(self):
        QMessageBox.about(self, "Error", "Temporary path seems to be invalid!")

    def createBucketResolveThread(self):
        bucket_resolve_thread = threading.Thread(target=self.initialize_buckets_select_list, args=())
        bucket_resolve_thread.start()

    def initialize_buckets_select_list(self):
        self.buckets_list = []
        self.bucket_id_list = []
        self.storj_engine = StorjEngine()  # init StorjEngine
        i = 0
        try:
            for bucket in self.storj_engine.storj_client.bucket_list():
                self.buckets_list.append(str(bucket.name))  # append buckets to list
                self.bucket_id_list.append(str(bucket.id))  # append buckets to list
                i = i + 1
        except storj.exception.StorjBridgeApiError, e:
            QMessageBox.about(self, "Unhandled bucket resolving exception", "Exception: " + str(e))

        self.ui_single_file_upload.save_to_bucket_select.addItems(self.buckets_list)


    def increment_shards_progress_counters(self):
        self.shards_already_uploaded += 1
        self.ui_single_file_upload.shards_uploaded.setText(html_format_begin + str(self.shards_already_uploaded) + html_format_end)

    def add_row_upload_queue_table(self, row_data):
        self.upload_queue_progressbar_list.append(QProgressBar())

        self.upload_queue_table_row_count = self.ui_single_file_upload.shard_queue_table_widget.rowCount()

        self.ui_single_file_upload.shard_queue_table_widget.setRowCount(self.upload_queue_table_row_count+1)

        self.ui_single_file_upload.shard_queue_table_widget.setCellWidget(self.upload_queue_table_row_count, 0, self.upload_queue_progressbar_list[self.upload_queue_table_row_count])
        self.ui_single_file_upload.shard_queue_table_widget.setItem(self.upload_queue_table_row_count, 1, QtGui.QTableWidgetItem(row_data["hash"]))
        self.ui_single_file_upload.shard_queue_table_widget.setItem(self.upload_queue_table_row_count, 2, QtGui.QTableWidgetItem(str(row_data["farmer_address"]) + ":" + str(row_data["farmer_port"])))
        self.ui_single_file_upload.shard_queue_table_widget.setItem(self.upload_queue_table_row_count, 3, QtGui.QTableWidgetItem(str(row_data["state"])))
        self.ui_single_file_upload.shard_queue_table_widget.setItem(self.upload_queue_table_row_count, 4, QtGui.QTableWidgetItem(str(row_data["token"])))
        self.ui_single_file_upload.shard_queue_table_widget.setItem(self.upload_queue_table_row_count, 5, QtGui.QTableWidgetItem(str(row_data["shard_index"])))

        self.upload_queue_progressbar_list[self.upload_queue_table_row_count].setValue(0)

        print row_data

    def select_tmp_directory(self):
        self.selected_tmp_dir = QtGui.QFileDialog.getExistingDirectory(None, 'Select a folder:', '',
                                                                       QtGui.QFileDialog.ShowDirsOnly)
        self.ui_single_file_upload.tmp_path.setText(str(self.selected_tmp_dir))

    def select_file_path(self):
        self.ui_single_file_upload.file_path.setText(QFileDialog.getOpenFileName())

    def createNewUploadThread(self):
        # self.download_thread = DownloadTaskQtThread(url, filelocation, options_chain, progress_bars_list)
        # self.download_thread.start()
        # self.download_thread.connect(self.download_thread, SIGNAL('setStatus'), self.test1, Qt.QueuedConnection)
        # self.download_thread.tick.connect(progress_bars_list.setValue)

        # Refactor to QtTrhead
        upload_thread = threading.Thread(target=self.file_upload_begin, args=())
        upload_thread.start()

    def initialize_upload_queue_table(self):

        # initialize variables
        self.shards_already_uploaded = 0
        self.uploaded_shards_count = 0
        self.upload_queue_progressbar_list = []

        self.upload_queue_table_header = ['Progress', 'Hash', 'Farmer', 'State', 'Token', 'Shard index']
        self.ui_single_file_upload.shard_queue_table_widget.setColumnCount(6)
        self.ui_single_file_upload.shard_queue_table_widget.setRowCount(0)
        horHeaders = self.upload_queue_table_header
        self.ui_single_file_upload.shard_queue_table_widget.setHorizontalHeaderLabels(horHeaders)
        self.ui_single_file_upload.shard_queue_table_widget.resizeColumnsToContents()
        self.ui_single_file_upload.shard_queue_table_widget.resizeRowsToContents()


        self.ui_single_file_upload.shard_queue_table_widget.horizontalHeader().setResizeMode(QtGui.QHeaderView.Stretch)

    def set_current_status(self, current_status):
        self.ui_single_file_upload.current_state.setText(html_format_begin + current_status + html_format_end)

    def createNewShardUploadThread(self, shard, chapters, frame, file_name):
        # another worker thread for single shard uploading and it will retry if download fail
        upload_thread = threading.Thread(target=self.upload_shard(shard=shard, chapters=chapters, frame=frame, file_name_ready_to_shard_upload=file_name), args=())
        upload_thread.start()

    def upload_shard(self, shard, chapters, frame, file_name_ready_to_shard_upload):

        self.uploadblocksize = 4096

        def read_in_chunks(file_object, shard_size, rowposition, blocksize=self.uploadblocksize, chunks=-1):
            """Lazy function (generator) to read a file piece by piece.
            Default chunk size: 1k."""

            i = 0
            while chunks:
                data = file_object.read(blocksize)
                if not data:
                    break
                yield data
                i += 1
                t1 = float(shard_size) / float((self.uploadblocksize))
                if shard_size <= (self.uploadblocksize):
                    t1 = 1

                percent_uploaded = int(round((100.0 * i) / t1))

                print i
                chunks -= 1
                self.emit(SIGNAL("updateShardUploadProgress"), int(rowposition),
                          percent_uploaded)  # update progress bar in upload queue table

        it = 0
        contract_negotiation_tries = 0
        while self.max_retries_negotiate_contract > contract_negotiation_tries:
            contract_negotiation_tries += 1

            # emit signal to add row to upload queue table
            # self.emit(SIGNAL("addRowToUploadQueueTable"), "important", "information")


            self.ui_single_file_upload.current_state.setText(
                html_format_begin + "Adding shard " + str(
                    chapters) + " to file frame and getting contract..." + html_format_end)

            try:
                frame_content = self.storj_engine.storj_client.frame_add_shard(shard, frame.id)

                # Add items to shard queue table view

                tablerowdata = {}
                tablerowdata["farmer_address"] = frame_content["farmer"]["address"]
                tablerowdata["farmer_port"] = frame_content["farmer"]["port"]
                tablerowdata["hash"] = str(shard.hash)
                tablerowdata["state"] = "Uploading..."
                tablerowdata["token"] = frame_content["token"]
                tablerowdata["shard_index"] = str(chapters)

                self.emit(SIGNAL("addRowToUploadQueueTable"), tablerowdata)  # add row to table

                rowcount = self.ui_single_file_upload.shard_queue_table_widget.rowCount()

                print frame_content
                print shard
                # frame_content.
                print frame_content["farmer"]["address"]

                farmerNodeID = frame_content["farmer"]["nodeID"]

                url = "http://" + frame_content["farmer"]["address"] + ":" + str(
                    frame_content["farmer"]["port"]) + "/shards/" + frame_content["hash"] + "?token=" + \
                      frame_content["token"]
                print url

                # files = {'file': open(file_path + '.part%s' % chapters)}
                # headers = {'content-type: application/octet-stream', 'x-storj-node-id: ' + str(farmerNodeID)}

                self.set_current_status("Uploading shard" + str(chapters + 1) + "to farmer...")

                # begin recording exchange report
                exchange_report = storj.model.ExchangeReport()

                current_timestamp = int(time.time())

                exchange_report.exchangeStart = str(current_timestamp)
                exchange_report.farmerId = str(farmerNodeID)
                exchange_report.dataHash = str(shard.hash)

                shard_size = int(shard.size)

                rowposition = rowcount

                farmer_tries = 0
                response = None
                while self.max_retries_upload_to_same_farmer > farmer_tries:
                    farmer_tries += 1
                    try:
                        with open(self.parametrs.tmpPath + file_name_ready_to_shard_upload + '-' + str(chapters + 1),
                                  'rb') as f:
                            response = requests.post(url, data=read_in_chunks(f, shard_size, rowposition), timeout=1)

                        j = json.loads(str(response.content))
                        if (j["result"] == "The supplied token is not accepted"):
                            raise storj.exception.StorjFarmerError(
                                storj.exception.StorjFarmerError.SUPPLIED_TOKEN_NOT_ACCEPTED)

                    except Exception, e:
                        self.emit(SIGNAL("updateUploadTaskState"), rowposition,
                                  "First try failed. Retrying...")  # update shard upload state
                        print str(e)
                        continue
                    else:
                        self.emit(SIGNAL("incrementShardsProgressCounters"))  # update already uploaded shards count
                        self.emit(SIGNAL("updateUploadTaskState"), rowposition,
                                  "Uploaded!")  # update shard upload state

                        print str(self.all_shards_count) + "wszystkie" + str(
                            self.shards_already_uploaded) + "wyslane"
                        if int(self.all_shards_count) == int(self.shards_already_uploaded+1):
                            self.emit(SIGNAL("finishUpload"))  # send signal to save to bucket after all files are uploaded
                        break

                print response.content

                j = json.loads(str(response.content))
                if (j["result"] == "The supplied token is not accepted"):
                    raise storj.exception.StorjFarmerError(storj.exception.StorjFarmerError.SUPPLIED_TOKEN_NOT_ACCEPTED)


                firstiteration = False
                it += 1

            except storj.exception.StorjBridgeApiError, e:
                # upload failed due to Storj Bridge failure
                print "Exception raised while trying to negitiate contract: " + str(e)
                continue
            except storj.exception.StorjFarmerError, e:
                # upload failed due to Farmer Failure
                print str(e)
                if str(e) == str(storj.exception.StorjFarmerError.SUPPLIED_TOKEN_NOT_ACCEPTED):
                    print "The supplied token not accepted"
                #print "Exception raised while trying to negitiate contract: " + str(e)
                continue
            except Exception, e:
                # now send Exchange Report
                # upload failed probably while sending data to farmer
                print "Error occured while trying to upload shard or negotiate contract. Retrying... " + str(e)
                current_timestamp = int(time.time())

                exchange_report.exchangeEnd = str(current_timestamp)
                exchange_report.exchangeResultCode = (exchange_report.FAILURE)
                exchange_report.exchangeResultMessage = (exchange_report.STORJ_REPORT_UPLOAD_ERROR)
                self.set_current_status("Sending Exchange Report for shard " + str(chapters + 1))
                # self.storj_engine.storj_client.send_exchange_report(exchange_report) # send exchange report
                continue
            else:
                # uploaded with success
                current_timestamp = int(time.time())
                # prepare second half of exchange heport
                exchange_report.exchangeEnd = str(current_timestamp)
                exchange_report.exchangeResultCode = (exchange_report.SUCCESS)
                exchange_report.exchangeResultMessage = (exchange_report.STORJ_REPORT_SHARD_UPLOADED)
                self.set_current_status("Sending Exchange Report for shard " + str(chapters + 1))
                # self.storj_engine.storj_client.send_exchange_report(exchange_report) # send exchange report
                break



    def file_upload_begin(self):

        # upload finish function #
        def finish_upload(self):
            self.crypto_tools = CryptoTools()
            self.ui_single_file_upload.current_state.setText(
                html_format_begin + "Generating SHA5212 HMAC..." + html_format_end)
            hash_sha512_hmac_b64 = self.crypto_tools.prepare_bucket_entry_hmac(shards_manager.shards)
            hash_sha512_hmac = hashlib.sha224(str(hash_sha512_hmac_b64["SHA-512"])).hexdigest()
            print hash_sha512_hmac
            # save

            # import magic
            # mime = magic.Magic(mime=True)
            # mime.from_file(file_path)

            print frame.id
            print "Now upload file"

            data = {
                'x-token': push_token.id,
                'x-filesize': str(file_size),
                'frame': frame.id,
                'mimetype': file_mime_type,
                'filename': str(bname),
                'hmac': {
                    'type': "sha512",
                    # 'value': hash_sha512_hmac["sha512_checksum"]
                    'value': hash_sha512_hmac
                },
            }
            self.ui_single_file_upload.current_state.setText(
                html_format_begin + "Adding file to bucket..." + html_format_end)

            success = False
            try:
                response = self.storj_engine.storj_client._request(
                    method='POST', path='/buckets/%s/files' % bucket_id,
                    # files={'file' : file},
                    headers={
                        'x-token': push_token.id,
                        'x-filesize': str(file_size),
                    },
                    json=data,
                )
                success = True
            except storj.exception.StorjBridgeApiError, e:
                QMessageBox.about(self, "Unhandled exception", "Exception: " + str(e))
            if success:
                self.ui_single_file_upload.current_state.setText(
                    html_format_begin + "Upload success! Waiting for user..." + html_format_end)


        self.connect(self, SIGNAL("finishUpload"), lambda: finish_upload(self))

        # end upload finishing function #

        self.validation = {}

        self.initialize_upload_queue_table()

        #item = ProgressWidgetItem()
        #self.ui_single_file_upload.shard_queue_table_widget.setItem(1, 1, item)
        #item.updateValue(1)

        #progress.valueChanged.connect(item.updateValue)


        encryption_enabled = True
        self.parametrs = storj.model.StorjParametrs()

        # get temporary files path
        if self.ui_single_file_upload.tmp_path.text() == "":
            self.parametrs.tmpPath = "/tmp/"
        else:
            self.parametrs.tmpPath = str(self.ui_single_file_upload.tmp_path.text())

        self.configuration = Configuration()

        # get temporary files path
        if self.ui_single_file_upload.file_path.text() == "":
            self.validation["file_path"] = False
            self.emit(SIGNAL("showFileNotSelectedError"))  # show error missing file path
        else:
            self.validation["file_path"] = True
            file_path = str(self.ui_single_file_upload.file_path.text())


        if self.validation["file_path"]:
            bucket_id = "dc4778cc186192af49475b49"
            bname = os.path.split(file_path)[1]

            print bname + "npliku"

            mime = magic.Magic(mime=True)
            file_mime_type = str(mime.from_file(str(file_path)))
            # file_mime_type = str("A")

            file_existence_in_bucket = False

            # if self.configuration.sameFileNamePrompt or self.configuration.sameFileHashPrompt:
            # file_existence_in_bucket = self.storj_engine.storj_client.check_file_existence_in_bucket(bucket_id=bucket_id, filepath=file_path) # chech if exist file with same file name

            if file_existence_in_bucket == 1:
                # QInputDialog.getText(self, 'Warning!', 'File with name ' + str(bname) + " already exist in bucket! Please use different name:", "test" )
                print "Same file exist!"

            if self.ui_single_file_upload.encrypt_files_checkbox.isChecked():
                # encrypt file
                self.set_current_status("Encrypting file...")
                file_crypto_tools = FileCrypto()
                file_crypto_tools.encrypt_file("AES", str(file_path), self.parametrs.tmpPath + "/" + bname + ".encrypted",
                                               "kotecze57")  # begin file encryption
                file_path_ready = self.parametrs.tmpPath + "/" + bname + ".encrypted" # get path to encrypted file in temp dir
                file_name_ready_to_shard_upload = bname + ".encrypted"
            else:
                file_path_ready = file_path
                file_name_ready_to_shard_upload = bname

            print self.parametrs.tmpPath
            print file_path_ready + "sciezka2"

            def get_size(file_like_object):
                return os.stat(file_like_object.name).st_size

            # file_size = get_size(file)
            file_size = os.stat(file_path).st_size
            self.ui_single_file_upload.current_state.setText(
                html_format_begin + "Resolving PUSH token..." + html_format_end)

            push_token = None

            try:
                push_token = self.storj_engine.storj_client.token_create(bucket_id,
                                                                         'PUSH')  # get the PUSH token from Storj Bridge
            except storj.exception.StorjBridgeApiError, e:
                QMessageBox.about(self, "Unhandled PUSH token create exception", "Exception: " + str(e))

            self.ui_single_file_upload.push_token.setText(
                html_format_begin + str(push_token.id) + html_format_end)  # set the PUSH Token

            print push_token.id

            self.ui_single_file_upload.current_state.setText(
                html_format_begin + "Resolving frame for file..." + html_format_end)
            try:
                frame = self.storj_engine.storj_client.frame_create()  # Create file frame
            except storj.exception.StorjBridgeApiError, e:
                QMessageBox.about(self, "Unhandled exception while creating file staging frame", "Exception: " + str(e))

            self.ui_single_file_upload.file_frame_id.setText(html_format_begin + str(frame.id) + html_format_end)

            print frame.id
            # Now encrypt file
            print file_path_ready + "sciezka"

            # Now generate shards
            self.set_current_status("Splitting file to shards...")
            shards_manager = model.ShardManager(filepath=str(file_path_ready), tmp_path=self.parametrs.tmpPath)



            # self.ui_single_file_upload.current_state.setText(html_format_begin + "Generating shards..." + html_format_end)
            # shards_manager._make_shards()
            shards_count = shards_manager.index
            # create file hash
            self.storj_engine.storj_client.logger.debug('file_upload() push_token=%s', push_token)

            # upload shards to frame
            print shards_count

            # set shards count
            self.ui_single_file_upload.shards_count.setText(str(shards_count))
            self.all_shards_count = shards_count

            chapters = 0
            firstiteration = True

            for shard in shards_manager.shards:
                self.createNewShardUploadThread(shard, chapters, frame, file_name_ready_to_shard_upload)
                chapters += 1



                # delete encrypted file



        # hash_sha512_hmac = self.storj_engine.storj_client.get_custom_checksum(file_path)
        hash_sha512_hmac = "dxjcdj"

        #self.emit(SIGNAL("finishUpload")) # send signal to save to bucket after all filea are uploaded

        #finish_upload(self)








if __name__ == "__main__":
    QtCore.QCoreApplication.setAttribute(QtCore.Qt.AA_X11InitThreads)
    app = QtGui.QApplication(sys.argv)

    myapp = MainUI()
    initial_window = InitialWindowUI()

    account_manager = AccountManager()
    if account_manager.if_logged_in():
        myapp.show()
    else:
        initial_window.show()

    sys.exit(app.exec_())
