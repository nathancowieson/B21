#!/dls/science/groups/b21/PYTHON/bin/python
'''
Created on May 1, 2018

@author: nathan
'''
import logging
from os.path import isfile
import sys
import time
import zmq

sys.path.append('/dls/science/groups/b21/B21')
from integrateNxs import integrateNxs


mylogger = logger = logging.getLogger('zmqServer')
mylogger.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s: %(levelname)s: %(module)s: %(message)s',"[%Y-%m-%d %H:%M:%S]")
filehandler = logging.FileHandler('/home/b21user/nathanc/intnxs.txt')
filehandler.setFormatter(formatter)
streamhandler = logging.StreamHandler()
streamhandler.setFormatter(formatter)
mylogger.addHandler(filehandler)
mylogger.addHandler(streamhandler)
mylogger.info('Started the zmqServer')


context = zmq.Context()
socket = context.socket(zmq.REP)
socket.bind("tcp://*:5555")


while True:
    #  Wait for next request from client
    message = socket.recv()
    mylogger.info(str(message))

    #  Do some 'work'
    if message[-4:] == '.nxs' and isfile(message):
        mylogger.info('Found a valid nxs file, will run a processing job')
        job = integrateNxs()
        job.setCores(4)
        if job.setNxsFile(message):
            if job.setVisitDirectory():
                if job.setProcessingPipeline():
                    if job.writeJsonFile():
                        if job.createTempPipeline():
                            job.runDawn()
                            job.cleanUp()
    else:
        mylogger.error(message+' is not a valid nxs file')

    #  Send reply back to client
    socket.send(b"Got it")
