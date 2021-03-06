
"""
 :::: MEMINI ::::
 Receive and store timestamps of button presses on Pebble
"""

import struct
import time
import logging
import uuid
import os
import sys
import csv
import datetime
from struct import unpack_from
import msgpack

from serial.serialutil import SerialException
from libpebble2.communication import PebbleConnection
from libpebble2.communication.transports.serial import SerialTransport
from libpebble2.services.appmessage import AppMessageService, CString, Uint8
from libpebble2.protocol.apps import AppRunStateStart
from libpebble2.protocol.apps import AppRunState
import libpebble2.exceptions
from libpebble2.protocol import *

import rNTPTime
import socket
from gpio_utils import *
from Constants import *


#logging.basicConfig(level=logging.INFO)

#file_path = os.environ.get('PEBBLE_DATA_LOC')
file_path = "/media/card/memini/"
if file_path is None:
    print("DID NOT FIND PEBBLE_DATA_LOC")
    #print(os.environ)
    exit(1)
if not os.path.exists(file_path):
    os.mkdir(file_path)
#
meminifilename = str(file_path) + "memini_data.csv"


#KEY_MARKER_COUNT_TO_PHONE = 3
#KEY_MARKER_ID_TO_PHONE = 16
#KEY_RESPONSE_COUNT_TO_PHONE = 3
#KEY_RESPONSE_ID_TO_PHONE = 4
#KEY_MARKER_TIME_TO_PHONE = 32
#KEY_RESPONSE_TIME_TO_PHONE = 160
#BATTERY_FROM_WATCH = 7
#BATTERY_TIME_TO_PHONE = 9
#NOTIFICATION_TO_WATCH = 8

KEY_MARKER_COUNT_TO_PHONE= 3
KEY_MARKER_ID_TO_PHONE= 16
KEY_MARKER_TIME_TO_PHONE= 72

KEY_RESPONSE_COUNT_TO_PHONE= 4 
KEY_RESPONSE_ID_TO_PHONE= 128
KEY_RESPONSE_TIME_TO_PHONE= 184

BATTERY_VALUE_TO_PHONE= 1
BATTERY_TIME_TO_PHONE= 2

NOTIFICATION_TO_WATCH= 1

#COMMUNICATION_KEY_CONFIG = 200
#COMMUNICATION_KEY_PING = 100
#KEY_COUNT_TO_PHONE = 255
#KEY_DATA_TO_PHONE = 32
APP_UUID = "37ebe0947fd84161b712d31de6ee9163"

#running = True
notifyCounter = 0
batteryStatus = 0
#filename = ""

def decode_click_id(clickId):
    # clickIds = [11,12,13,14,21,22,23,31,32,33,34]
    clickTypes = ["Single","Long","Multi"]
    buttonIds = ["Up","Down","Select","Back"]
    clickTypeIndex = int((clickId-10) / 10)
    buttonIdIndex = int((clickId) % 10)-1
    clickType = clickTypes[clickTypeIndex]
    buttonId = buttonIds[buttonIdIndex]
    return buttonId,clickType
    #for press_key in ["UP", "DOWN", "SELECT"]:
    #    for press_type in ["SINGLE", "LONG", "MULTI"]:
    #        yield (press_key, press_type)



class AppMsgHandler:
    """ Class for handling the incoming app-messages - commands - from the pebble """
    def __init__(self, strUUID=APP_UUID):
        self.appID = strUUID
        self.markerCount = 0
        self.responseCount = 0
        self.batteryCharge = -1


    def message_log(self,data):
        global batteryStatus
        global meminifilename
        #global filename
        #print("markerCount = {}, responseCount = {}".format(self.markerCount,self.responseCount))
        dataTypes = []
        buttonIds = []
        clickTypes = []
        timeStamps = []
        batteryStatuses = []
        if self.markerCount>0:
            markerIds = []
            #markerTimes = []
            for k in range(self.markerCount):
                dataTypes.append( "MARKER" )
                batteryStatuses.append(batteryStatus)
                if (KEY_MARKER_ID_TO_PHONE+k) in data:
                    markerId = data[KEY_MARKER_ID_TO_PHONE+k]
                    markerIds.append(markerId)
                    buttonId,clickType = decode_click_id(markerId)
                    #print("click:{},{}".format(buttonId,clickType))
                    buttonIds.append(buttonId)
                    clickTypes.append(clickType)
                if (KEY_MARKER_TIME_TO_PHONE+k) in data:
                    timeStamps.append(data[KEY_MARKER_TIME_TO_PHONE+k])
                #print("timestamps:{}".format(timeStamps))        
        if self.responseCount>0:
            responseIds = []
            for k in range(self.responseCount):
                dataTypes.append( "RESPONSE" )
                batteryStatuses.append(batteryStatus)
                if (KEY_RESPONSE_ID_TO_PHONE+k) in data:
                    responseId = data[KEY_RESPONSE_ID_TO_PHONE+k]
                    responseIds.append(responseId)
                    buttonId,clickType = decode_click_id(responseId)
                    buttonIds.append(buttonId)
                    clickTypes.append(clickType)
                if (KEY_RESPONSE_TIME_TO_PHONE+k) in data:
                    timeStamps.append(data[KEY_RESPONSE_TIME_TO_PHONE+k])
                #print("timestamps:{}".format(timeStamps))

        if self.batteryCharge>=0:
            dataTypes.append( "BATTERY" )
            batteryStatus = self.batteryCharge
            batteryStatuses.append(batteryStatus)
            buttonIds.append("-")
            clickTypes.append("-")
            timeStamps.append(data[BATTERY_TIME_TO_PHONE])            
        try:
            print(dataTypes)
            print(timeStamps)
            print(buttonIds)
            print(clickTypes)
            print(batteryStatuses)
            with open(meminifilename,'a') as dataFile:
                for k in range(len(dataTypes)):
                    dataFile.write("{0},{1},{2},{3},{4}\n" \
                        .format(dataTypes[k],timeStamps[k],buttonIds[k],clickTypes[k],batteryStatuses[k]))
            return True
        except:
            print("Error in writing!")
            return False
        

    def message_received_event(self, transaction_id, uuid, data):
        global notifyCounter
        print("in message received")
        if uuid.get_hex() != self.appID:
            print("Ignoring appdata from unknown sender {}".format(uuid.get_hex()))
            return
        print("Msg Received: {}".format(data))
        if KEY_MARKER_COUNT_TO_PHONE in data:
            self.markerCount = data[KEY_MARKER_COUNT_TO_PHONE] 
            #dataType = "MARKER"
            print("got {} markers".format(self.markerCount))
            #del data[KEY_COUNT_TO_PHONE]
        if KEY_RESPONSE_COUNT_TO_PHONE in data:
            self.responseCount = data[KEY_RESPONSE_COUNT_TO_PHONE]
            #dataType = "RESPONSE"
            print("got {} responses".format(self.responseCount))
        if BATTERY_VALUE_TO_PHONE in data:
            #dataType = "BATTERY"
            self.batteryCharge = data[BATTERY_VALUE_TO_PHONE]
            print("Battery status: {}%".format(self.batteryCharge))
        

        if (self.markerCount>0 or self.responseCount>0 or self.batteryCharge>=0):
            loggingStatus = self.message_log(data)
            notifyCounter += 1
            if loggingStatus:
                self.markerCount = 0
                self.responseCount = 0 
                self.batteryCharge = -1
                print("Logging Success!")
            else: print("Logging Error!")
        return
        
                 


class CommunicationKeeper:
    #""" Class for handling re-sending of NACK-ed messages """
    NACK_COUNT_LIMIT = 5

    def __init__(self, strUUID, appMsgService):
        self.uuid = uuid.UUID(strUUID)
        self.pending = {}
        self.nack_count = 0
        self.appMsgService = appMsgService
        self.error = None
        print("in Communication Keeper")

    def check_uuid(self, uuid):
        output = True
        if uuid != self.uuid:
            print("Ignoring appdata from unknown sender {}".format(uuid))
            output = False
        return output

    def nack_received(self, transaction_id, uuid):
        #""" Callback functions for the library call when receiving nack """
        if self.check_uuid(uuid) == False:
            return
        if transaction_id not in self.pending:
            raise SerialException("Invalid transaction ID received")
        # We got nack from the watch
        print("NACK received for packet!")
        self.nack_count += 1
        if self.nack_count > self.NACK_COUNT_LIMIT:
            # we are inside the receive thread here, exception will kill only that
            self.error = "Nack count limit reached, something is wrong."
            self.nack_count = 0
            return
        # self.send_message( self.pending[transaction_id] )
        #del self.pending[transaction_id]

    def ack_received(self, transaction_id, uuid):
        print("ACK received for packet!")
        if self.check_uuid(uuid) == False:
            return
        if transaction_id not in self.pending:
            raise SerialException("Invalid transaction ID received")
        del self.pending[transaction_id]

    def send_message(self, data):
        #""" Send message and retry sending if it gets nacked """
        transaction_id = self.appMsgService.send_message(self.uuid, data)
        self.pending[transaction_id] = data


def restart_app_on_watch(pebble,appUUID):
    current_app_uuid = pebble.send_and_read(AppRunState(data=AppRunStateRequest()), AppRunState).data.uuid
    #print(current_app_uuid)
    if current_app_uuid != uuid.UUID(appUUID):
        # Re-start the watchapp
        pebble.send_packet(AppRunState(command = 0x01, data=AppRunStateStop(uuid = uuid.UUID(appUUID))))
        print("Pebble App Closed!")
        time.sleep(5)
        pebble.send_packet(AppRunState(command = 0x01, data=AppRunStateStart(uuid = uuid.UUID(appUUID))))
        time.sleep(2)
    return


def memini_main(mainMsgService,mainCommHandler,mainMsgHandler):
    #""" Main function for the communicatior, loops here """
    #print("in main")
    #print("Connection ok, entering to active state..")

    notification_type = "Warning"
    location_info = "Kitchen"
    envir_param = "Light"

    global notifyCounter
    print("Notify Counter = {}".format(notifyCounter))
    if notifyCounter>=3:
        notification = notification_type + "\n" + location_info + "\n" + envir_param  
        mainCommHandler.send_message({NOTIFICATION_TO_WATCH: CString(notification)})
        notifyCounter = 0
    time.sleep(10)



# if __name__ == "__main__":

def meminiSense(startDateTime,hostIP,BASE_PORT,streaming=True,logging=True):
    global meminifilename
    #logging.basicConfig(level=logging.INFO)
    #file_path = "/media/card/memini/"
    #if file_path is None:
    #    print("DID NOT FIND PEBBLE_DATA_LOC")
    #    #print(os.environ)
    #    exit(1)
    #if not os.path.exists(file_path):
    #    os.mkdir(file_path) 
    #
    #filename = str(file_path) + "memini_data.csv"
    running = True
    #pebble = PebbleConnection(SerialTransport("/dev/rfcomm0"))
    #pebble.connect()
    
    while True:
        try:
            pebble = PebbleConnection(SerialTransport("/dev/rfcomm0"))
            pebble.connect()
            #print "connection try 0!"
            appUUID = APP_UUID[:]
            while running:
                try:
                    print "Attempt to Connect"
                    #logging.info("Attempting to connect to pebble")
                    pebble.run_async()
                    print "Connection Success"
                    #logging.info("Pebble connection success")
                    break
                except libpebble2.exceptions.TimeoutError:
                    print "Pebble timeouted, retrying.."
                    continue
            #print "Opening file!"
            #with open(meminifilename,'a') as dataFile:
            #    dataFile.write("message,timestamp,button_id,click_type,battery_charge\n") 
            if pebble.connected:
                restart_app_on_watch(pebble,appUUID)
                with open(meminifilename,'a') as dataFile:
                    dataFile.write("message,timestamp,button_id,click_type,battery_charge\n")
                
                # Register service for app messages
                mainMsgService = AppMessageService(pebble)
                mainCommHandler = CommunicationKeeper(appUUID, mainMsgService)
                mainMsgService.register_handler("nack", mainCommHandler.nack_received)
                mainMsgService.register_handler("ack", mainCommHandler.ack_received)
                mainMsgHandler = AppMsgHandler(appUUID)
                mainMsgService.register_handler("appmessage", mainMsgHandler.message_received_event)

            while pebble.connected:
                # time.sleep(10) 
                memini_main(mainMsgService,mainCommHandler,mainMsgHandler)
        except SerialException:
            print("Error: Pebble Disconnected!")
            time.sleep(30)
            exit(2)
