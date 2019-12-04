#!/dls/science/groups/b21/PYTHON3/bin/python
'''
Created on Nov 18th, 2019

@author: nathan
'''
import sys
from epics import PV, poll
from epics.ca import CAThread
from datetime import datetime
import logging
import pickle
import redis
import sys
from time import sleep
sys.path.insert(0, '/dls/science/groups/b21/PYTHON3/libraries/beamline/')
from devices.valve import Valve
from devices.vacuum_measurement import MksGauge, Gauge

class epicsDaemon(object):
    """Control valve positions in the B21 vacuum system
    
    Runs as a daemon to automatically control various valve
    positions in the B21 endstation vacuum system.

    """
    #ADD THE EPICS DEVICES
    dwell_time = 2
    eh_search_status = PV('BL21B-PS-IOC-01:M11:LOP')
    sample_vacuum = MksGauge('BL21B-VA-PIRG-32')
    camera_vacuum = MksGauge('BL21B-VA-PIRG-81')
    upstream_vacuum = MksGauge('BL21B-VA-PIRG-70')
    hplc_injection = PV('BL21B-EA-ENV-01:HPLC:TRIG')
    v31 = Valve('BL21B-VA-VALVE-31')
    v32 = Valve('BL21B-VA-VALVE-32')
    v33 = Valve('BL21B-VA-VALVE-33')
    gdastat = PV('BL21B-CS-IOC-01:GDASTATUS')
    threads = {'onHutchClose':[], 'onHutchOpen':[], 'onInjectionSignalChange':[]}
    '''
    Constructor
    '''
    def __init__(self):
        #set some parameters
        self.type = 'vacuumDaemon'
        self.redis = redis.StrictRedis(host='b21-ws005.diamond.ac.uk', port=6379, db=0)

        ###start a log file
        self.logger = logging.getLogger(self.type)
        self.logger.setLevel(logging.DEBUG)
        formatter = logging.Formatter('%(asctime)s: %(levelname)s: %(module)s: %(message)s',"[%Y-%m-%d %H:%M:%S]")
        streamhandler = logging.StreamHandler()
        streamhandler.setFormatter(formatter)
        self.logger.addHandler(streamhandler)

        #some runtime parameters
        self.default_status = True
        self.injection_underway = False

        #add callbacks
        self.eh_search_status.add_callback(self.onEHSearchStatusChange)
        self.hplc_injection.add_callback(self.onInjectionSignalChange)

    def setWorking(self, state=True):
        if state == True:
            self.redis.set('vacuumDaemon', 'On')
            self.logger.debug('Set daemon functions to active')
        elif state == False:
            self.redis.set('vacuumDaemon', 'Off')
            self.logger.debug('Set daemon function to inactive')

    def getWorking(self):
        try:
            i = self.redis.get('vacuumDaemon').decode('utf-8')
            if i == 'On':
                self.logger.debug('Found vacuum daemon functions to be active')
                return True
            elif i == 'Off':
                self.logger.debug('Found vacuum daemon functions to be inactive')
                return False
            else:
                self.logger.error('Unexpected status for vacuum functions, returning default')
                return self.default_status
        except:
            self.logger.error('Could not get vacuum daemon state from redis')
            return True

    def prepareForDataCollection(self):
        self.logger.debug('Preparing for data collection mode')
        try:
            self.v33.close()
            self.v31.reset_interlocks()
            self.v32.reset_interlocks()
            self.v32.open()
            self.v31.open()
        except:
            self.logger.error('prepareForDataCollection function threw an error')
        finally:
            self.logger.debug('prepareForDataCollection function terminated normally')
            self.threads['onHutchClose'].pop()

    def onHutchClose(self):
        '''method to set valve positions when hutch is searched and secured'''
        self.logger.debug('onHutchClose method was called')
        if len(self.threads['onHutchClose']) > 0:
            self.logger.error('There is already an onHutchClose thread running, will not start a new one')
        else:
            new_thread = CAThread(target=self.prepareForDataCollection)
            self.threads['onHutchClose'].append(new_thread)
            new_thread.start()

    def prepareForHutchOpen(self):
        self.logger.debug('Preparing for hutch opening')
        try:
            self.v33.reset_interlocks()
            self.v33.open()
        except:
            self.logger.error('prepareForHutchOpen function threw an error')
        finally:
            self.logger.debug('prepareForHutchOpen function terminated normally')
            self.threads['onHutchOpen'].pop()

    def onHutchOpen(self):
        '''method to set valve positions when hutch is opened'''
        self.logger.debug('onHutchOpen method was called')
        if len(self.threads['onHutchOpen']) > 0:
            self.logger.error('There is already an onHutchOpen thread running, will not start a new one')
        else:
            new_thread = CAThread(target=self.prepareForHutchOpen)
            self.threads['onHutchOpen'].append(new_thread)
            new_thread.start()

    def onEHSearchStatusChange(self, pvname=None, value=None, host=None, **kws):
        self.logger.info(f'value={value}')
        if self.eh_search_status.get() == 0.0:
            self.onHutchClose()
        else:
            self.onHutchOpen()

    def injectionUnderway(self):
        self.logger.debug('injectionUnderway method called')
        try:
            self.logger.info('Found injection signal')
            self.injection_underway = True
            self.redis.set('lastInjectionSignal', pickle.dumps(datetime.now(), protocol=2))#protocol 2 is so it can be read in jython and python2.7
            sleep(3)
            self.injection_underway = False
        except:
            self.logger.error('There was an error with the injectionUnderway function')
        finally:
            self.logger.debug('injectionUnderway function terminated normally')
            self.threads['onInjectionSignalChange'].pop()

    def onInjectionSignalChange(self, pvname=None, value=None, host=None, **kws):
        cutoff = 2.5
        if value < cutoff and not self.injection_underway:
            new_thread = CAThread(target=self.injectionUnderway)
            self.threads['onInjectionSignalChange'].append(new_thread)
            new_thread.start()
            


if __name__ == '__main__':
    job = epicsDaemon()
#    print(job.eh_search_status.get())
#    print(job.v31.status())
#    job.onHutchClose()
#    job.v33.open()
#    job.onHutchOpen()
    while True:
        poll(evt=1.e-5, iot=0.1)

