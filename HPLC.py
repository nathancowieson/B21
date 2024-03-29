'''
Created on April 28th, 2017

@author: nathan
'''
from uk.ac.gda.devices.hplc.beans import HplcSessionBean
from gda.commandqueue import JythonScriptProgressProvider
from gdascripts.pd.epics_pds import DisplayEpicsPVClass, SingleEpicsPositionerClass
from gda.data.metadata import GDAMetadataProvider
from gda.jython.commands.GeneralCommands import pause
from gda.jython import JythonServerFacade
from gda.scan import StaticScan
import gdaserver
from tfgsetup import fs
from time import sleep
import logging
import pickle
#import gda.factory.Finder
import gda.factory.Finder.find as find
import re
import sys
from cStringIO import StringIO
from math import ceil
from datetime import datetime
import subprocess

class HPLC(object):
    """Handles collection of HPLC SAXS data in GDA/Jython

    The class is called via the 'Queue Experiment' button on the
    <filename.hplc> xml file in the HPLC setup perspective in GDA.
    The class has various functions to check shutters etc on the 
    beamline as well as measuring the data.
    """
    __version__ = '1.03'
    skip_checks = False
    def __init__(self, filename):
        self.hplcFile = filename
        self.bean = HplcSessionBean.createFromXML(filename)
        #finder = gda.factory.Finder.getInstance()
        #find = finder.find
        self.shutter = find('shutter')
        self.bsdiode = find('bsdiode')
        self.sample_type = find('sample_type')
        self.sampleName = find("samplename")
        self.environment = find("sample_environment")
        self.tfg = gdaserver.Tfg
        self.ncddetectors = find('ncddetectors')#finder.listAllLocalObjects("uk.ac.gda.server.ncd.detectorsystem.NcdDetectorSystem")[0]
        self.jsf = JythonServerFacade.getInstance()
        self.readout_time = 0.1

        #CREATE A LOGGER
        self.logger = logging.getLogger('HPLC')
        self.logger.setLevel(logging.INFO)
        formatter = logging.Formatter('%(asctime)s: %(levelname)s: %(module)s: %(message)s',"[%Y-%m-%d %H:%M:%S]")
        streamhandler = logging.StreamHandler()
        streamhandler.setFormatter(formatter)
        if len(self.logger.handlers) == 0:
            self.logger.addHandler(streamhandler)
        self.logger.info('HPLC class version '+self.__version__+' was instantiated')
        
    def setupTfg(self, frames, tpf):
        self.tfg.clearFrameSets()
        self.tfg.addFrameSet(frames, self.readout_time * 1000, tpf * 1000, int('00000100', 2), int('11111111', 2), 0, 0)#note, byte order is reversed!
        self.tfg.loadFrameSets()
        return frames * (tpf + self.readout_time)
    
    def setTitle(self, title):
        GDAMetadataProvider.getInstance().setMetadataValue("title", title)
        
    def setSampleType(self, type='sample'):
        if type in self.sample_type.positionsList:
            self.sample_type(type)
        else:
            self.logger.error('Invalid sample type')
            
    def setEnvironment(self, type='HPLC'):
        if type in ['BSSC', 'HPLC', 'Manual']:
            self.environment(type)
        else:
            self.logger.error('Environment type should be one of: HPLC, BSSC, Manual.')

    def setGdaStatus(self, status='HPLC'):
        statuses = {'Idle': 0, 'HPLC': 1, 'BSSC': 2, 'Manual': 3, 'Other': 4}
        try:
            gdaStatus.getPosition()
        except:
            gdaStatus = SingleEpicsPositionerClass('fv1', 'BL21B-CS-IOC-01:GDASTATUS', 'BL21B-CS-IOC-01:GDASTATUS', 'BL21B-VA-FVALV-01:CON', 'BL21B-VA-FVALV-01:CON', 'mm', '%d')
        if status in statuses.keys():
            gdaStatus(statuses[status])

    def getGdaStatus(self):
        statuses = {0: 'Idle', 1: 'HPLC', 2: 'BSSC', 3: 'Manual', 4: 'Other'}
        position = 4
        try:
            position = gdaStatus.getPosition()
        except:
            gdaStatus = SingleEpicsPositionerClass('fv1', 'BL21B-CS-IOC-01:GDASTATUS', 'BL21B-CS-IOC-01:GDASTATUS', 'BL21B-VA-FVALV-01:CON', 'BL21B-VA-FVALV-01:CON', 'mm', '%d')
            position = gdaStatus.getPosition()
        return statuses[position]

    def armFastValve(self):
        try:
            fv1.getPosition()
        except:
            fv1 = SingleEpicsPositionerClass('fv1', 'BL21B-VA-FVALV-01:CON', 'BL21B-VA-FVALV-01:STA', 'BL21B-VA-FVALV-01:STA', 'BL21B-VA-FVALV-01:CON', 'mm', '%d')
        if not fv1.getPosition() == 3.0:
            fv1(3.0)

    def sendSms(self, message=""):
        fedids = {'Nathan': 'xaf46449', 'Nikul': 'rvv47355', 'Rob': 'xos81802', 'Katsuaki': 'vdf31527', 'Charlotte': 'nue65926'}
        for key in fedids.keys():
            subprocess.call(['/dls_sw/prod/tools/RHEL6-x86_64/defaults/bin/dls-sendsms.py', fedids[key], message])
        self.logger.info('Sent an SMS')

    def killHplc(self, state=False):
        try:
            kill_hplc.getPosition()
        except:
            kill_hplc = SingleEpicsPositionerClass('kill_hplc', 'BL21B-EA-HPLC-01:MOD1:SHUTDOWN', 'BL21B-EA-HPLC-01:MOD1:SHUTDOWN', 'BL21B-EA-HPLC-01:MOD1:SHUTDOWN', 'BL21B-EA-HPLC-01:MOD1:SHUTDOWN', 'mm', '%d')

        if state:
            kill_hplc(1)
        else:
            kill_hplc(0)

    def getMachineStatus(self):
        try:
            machine_status.getPosition()
        except:
            machine_status=DisplayEpicsPVClass('beam_status', 'FE21B-PS-SHTR-01:STA', 'units', '%d')
        if machine_status.getPosition() == 1.0:
            return True
        else:
            return False
        
    def getSearchStatus(self):
        try:
            eh_search_status.getPosition()
        except:
            eh_search_status=DisplayEpicsPVClass('eh_search_status', 'BL21B-PS-IOC-01:M11:LOP', 'units', '%d')

        if eh_search_status.getPosition() != 0.0:
            return False
        else:
            return True

    def getSafetyShutter(self):
        if self.shutter.getPosition() == 'Open':
            return True
        else:
            return False

    def setSafetyShutter(self, command='Open'):
        levels = ['Open', 'Close']
        if command in levels:
            self.shutter(command)
            self.logger.info('Setting safety shutter to '+command)
        else:
            self.logger.error("setSafetyShutter function requires either 'Open' or 'Close' as input")

            
    def getHplcValve(self):
        try:
            hplcvalve_status.getPosition()
        except:
            hplcvalve_status=DisplayEpicsPVClass('hplcvalve_status', 'BL21B-EA-HPLC-01:MOD1:VALVE:CTRL', 'units', '%d')
        if hplcvalve_status.getPosition() == 1.0:
            return True
        else:
            return False
                                  
    def getFastShutter(self):
        old_stdout = sys.stdout
        sys.stdout = mystdout = StringIO()
        fs()
        sys.stdout = old_stdout
        if mystdout.getvalue() == 'fs: Open\n':
            self.logger.info('Fast shutter is open')
            return True
        else:
            self.logger.info('Fast shutter is closed')
            return False

    def setFastShutter(self, command='Open'):
        if command in ['Open', 'Close']:
            self.logger.info('Setting fast shutter to '+command)
            fs(command)
            
        else:
            self.logger.error('setFastValve function requires either Close or Open as input')

    def getInjectSignal(self):
        cutoff = 2.5
        signal = 2.75
        try:
            signal = inject_signal.getPosition()
        except:
            inject_signal=DisplayEpicsPVClass('inject_signal', 'BL21B-EA-ENV-01:HPLC:TRIG', 'units', '%.3e')
            signal = inject_signal.getPosition()
            
        if signal < cutoff:
            return True
        else:
            return False
            
    def NumberOfImages(self, duration_mins=32.0, exposure_time_secs=3.0):
        run_list = []
        number_of_images = int(ceil(duration_mins * 60.0 / ( self.readout_time + exposure_time_secs)))
        while number_of_images > 1000:
            run_list.append( (1000,exposure_time_secs) )
            number_of_images -= 1000
        if number_of_images > 0:
            run_list.append( (number_of_images,exposure_time_secs) )
        self.logger.info('Will collect: '+str(sum([x[0] for x in run_list]))+' images across '+str(len(run_list))+' nxs file')
        return run_list

    def testForBeam(self):
        self.setFastShutter('Open')
        sleep(1)
        beamstop_diode_reading = self.bsdiode.getPosition()
        self.setFastShutter('Close')
        if beamstop_diode_reading > 10E6:
            return True
        else:
            return False

    def preRunCheck(self):
        status = False
        message = "HPLC run aborted due to: "
        if self.skip_checks:
            message = 'Skipping all pre-run checks'
            status = True
        elif not self.getMachineStatus():
            message += 'Machine is down'
        elif not self.getSafetyShutter():
            message += 'Safety shutter is closed'
        elif not self.getHplcValve():
            message += 'HPLC valve is closed'
        elif not self.testForBeam():
            message += 'no beam on the beamstop diode'
        else:
            status = True
            message = 'Pre-run check passed successfully'
        return (status, message)

    def run(self, processing=True):
        try:
            self.setGdaStatus('HPLC')
            if self.skip_checks:
                self.logger.info('Skipping checks for safety shutter, HPLC valve and fast shutter')
            else:
                if not self.getSafetyShutter():
                    if self.getSearchStatus():
                        self.setSafetyShutter('Open')
                    else:
                        self.logger.error('Search the hutch you crazy fool!')
                        raise EnvironmentError('The script terminated early because the hutch is not searched.')
                
                if not self.getHplcValve():
                    self.logger.error('The HPLC static/flow valve is in static position, this may be caused by a loss of vacuum in the sample section.')
                    raise EnvironmentError('The script terminated early because the HPLC static/flow valve is in the static position')
            
                if self.getFastShutter():
                    self.logger.info('Fast shutter was open, closing it so the tfg can take care of it during collection')
                    self.setFastShutter('Close')
                
            self.setEnvironment('HPLC')
            self.setSampleType('sample')
            
            self.isError = False
            previous_runtime = 0
            for i, b in enumerate(self.bean.measurements):
                pause()
                my_check = self.preRunCheck()
                if not my_check[0]:
                    self.sendSms(my_check[1])
                    self.logger.error(my_check[1])
                    self.killHplc(True)
                    self.isError = True
                    break
                else:
                    self.logger.info(my_check[1])
                
                self.logger.info('---- STARTING RUN '+str(i+1)+' of '+str(len(self.bean.measurements))+': SAMPLE: '+b.getSampleName()+' ----')
                exposure_time = b.getTimePerFrame()
                
                #GET THE RUN TIME
                try:
                    runtime = int(b.getTotalDuration())
                except:
                    self.logger.error('The run time of the experiment must be an integer and is in minutes, using 30 mins as a default')
                    runtime = 32

                #Set up run parameters
                self.setTitle(b.getSampleName())
                
                #Work out if we missed an injection signal
                try:
                    last_injection = pickle.loads(eval(subprocess.check_output(['/dls/science/groups/b21/B21/get_last_injection.py'], shell=True).decode('utf-8').rstrip()))
                    time_since_injection = (datetime.now()-last_injection).seconds
                    if re.match('no check missed injection',b.getComment()):
                        time_since_injection = 1E8
                        self.logger.error('Setting time since last injection to 1E8')
                    if time_since_injection < (previous_runtime*60):
                        runtime = ((runtime*60.0) - (datetime.now()-last_injection).seconds ) / 60.0
                        pre_run_delay = 0
                        found_signal = True
                        self.logger.info('Missed injection signal, run time adjusted to '+str(runtime)+' mins')
                    else:
                        pre_run_delay = 120
                        found_signal = False
                        self.logger.info('We have not missed an injection, will wait for one')
                except:
                    pre_run_delay = 120
                    found_signal = False
                    self.logger.error('Failed to get the time of last hplc injection, check redis on ws005!')
                finally:
                    number_of_images = self.NumberOfImages(runtime, exposure_time)
                previous_runtime = runtime
                if re.match('skip delay',b.getComment()):
                    pre_run_delay = 0
                    self.logger.info('Skipping pre run delay because of comment')

                #wait for injection signal
                starttime = datetime.now()
                elapsed_time = 0
                while elapsed_time < pre_run_delay:
                    if self.getInjectSignal():
                        self.logger.info('Found injection signal')
                        found_signal = True
                        break
                    else:
                        elapsed_time = (datetime.now() - starttime).seconds
                    sleep(0.1)

                if not found_signal:
                    self.logger.info('Did not find the inject signal, will proceed anyway.')
                    self.sendSms(str(i+1)+' of '+str(len(self.bean.measurements))+': missed the injection signal')

                #Start the data collection
                self.logger.info('Starting data collection')
                for index,run in enumerate(number_of_images):
                    self.setupTfg(run[0], run[1])
                    self.logger.info('NXS file '+str(index+1)+' of '+str(len(number_of_images))+' for '+b.getSampleName())
                    StaticScan([self.ncddetectors]).run()
                self.logger.info('Finished collecting '+b.getSampleName())
            self.setSafetyShutter('Close')
            if self.isError:
                self.logger.error('SCRIPT WAS TERMINATED PREMATURELY')
            else:
                self.logger.info('SCRIPT FINISHED NORMALLY')
            #namespace:
            #b.getLocation().getRow()
            #b.getLocation().getColumn()
            #b.getSampleName()
            #b.getConcentration()
            #b.getMolecularWeight()
            #b.getTimePerFrame()
            #b.getBuffers()
            #b.getComment()
            #b.getVisit()
            #b.getUsername()
            #JythonScriptProgressProvider.sendProgress(100*i/float(len(self.bean.measurements)))
        except:
            self.logger.error('SCRIPT TERMINATED IN ERROR')
        finally:
            self.setEnvironment('Manual')
            self.setSampleType('none')
            self.getGdaStatus() == 'Idle'

