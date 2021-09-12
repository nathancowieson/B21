#!/dls/science/groups/b21/PYTHON3/bin/python
'''
Created on Dec 8th, 2016
Last update May 4 2021

@author: nathan
'''
import logging
import numpy
from optparse import OptionParser
from optparse import OptionGroup
import os
from datetime import datetime
import sys
import getpass
import paramiko
import re
import redis
import subprocess
from glob import glob
from shutil import copyfile
import h5py
import json
from epics import ca
sys.path.insert(0, '/dls/science/groups/b21/B21')
from XlsToGda import xmlReadWrite
from reportlab.pdfgen.canvas import Canvas
from reportlab.lib.pagesizes import A4

class UserSetup(object):
    """Sets the currently logged in users directories for a visit
    
    Puts a nxs format processing file into the visit processing directory
    Puts a json template file into the users xml/templates directory
    Copies desktop icons to the users desktop
    Puts a current scatter into the visits processing directory

    """
    
    '''
    Constructor
    '''
    def __init__(self):
        #set some parameters
        self.visit_id = None
        self.year = str(datetime.now().year)
        self.visit_directory = f'/dls/b21/data/{self.year}/'
        self.username = getpass.getuser()
        self.home_directory = f'{os.path.expanduser("~")}/'
        self.template_dir = '/dls_sw/b21/scripts/TEMPLATES/'
        self.mask_file = f'{self.template_dir}current_mask.nxs'
        self.calibration_file = f'{self.template_dir}current_calibration.nxs'
        self.pipeline_file = f'{self.template_dir}current_pipeline.nxs'
        self.output_pipeline_file = False
        self.redis = redis.StrictRedis(host='b21-ws005.diamond.ac.uk', port=6379, db=0)
        ###start a log file
        self.logger = logging.getLogger('UserSetup')
        self.logger.setLevel(logging.DEBUG)
        if len(self.logger.handlers) == 0:
            formatter = logging.Formatter('%(asctime)s: %(levelname)s: %(module)s: %(message)s',"[%Y-%m-%d %H:%M:%S]")
            streamhandler = logging.StreamHandler()
            streamhandler.setFormatter(formatter)
            self.logger.addHandler(streamhandler)

    def set_year(self, year=None):
        '''set the year to look for the visit folder in'''
        self.logger.debug('the set_year method was called')
        if type(year) == int:
            self.year = str(year)
            self.visit_directory = f'/dls/b21/data/{self.year}/'
            self.logger.debug(f'Set year to {self.year}')
        else:
            self.logger.error('set_year method requires an integer')

    def get_year(self):
        return self.year

    def get_visit_stats(self, visit):
        visit_stats = {
            'visit': visit,
            'visit_dir': '',
            'start_time': 'null',
            'end_time': datetime.now().strftime('%Y-%m-%d_%H:%M:%S'),
            'first_file': 'null',
            'last_file': 'null',
            'total_exposure_time': 0,
            'bssc_samples': 0,
            'hplc_samples': 0,
            'manual_samples': 0,
            'median_file_gap': 0,
            'longest_file_gap': 0
            }
        visit_dir = None
        visit_dirs = [
            f'{self.visit_directory}{visit}/',
            f'/dls/b21/data/{str(int(self.get_year())-1)}/{visit}/'
            ]
        for vd in visit_dirs:
            if os.path.isdir(vd):
                visit_dir = vd
                visit_stats['visit_dir'] = visit_dir
                self.logger.debug('Found previous visit dir for get_visit_stats')
                break
        if visit_dir:
            #Get time user_setup was run
            pattern = visit_dir+'processing/processing_pipeline_*.nxs'
            pipeline_files = glob(pattern)
            pipeline_files.sort(key=os.path.getctime)
            setup_time = datetime.fromtimestamp(os.path.getctime(pipeline_files[-1]))
            visit_stats['start_time'] = setup_time.strftime('%Y-%m-%d_%H:%M:%S')

            #Get first and last image time
            pattern = visit_dir+'*.nxs'            
            data_files = glob(pattern)
            data_files.sort(key=os.path.getctime)
            first_file = datetime.fromtimestamp(os.path.getctime(pipeline_files[0]))
            visit_stats['first_file'] = first_file.strftime('%Y-%m-%d_%H:%M:%S')
            last_file = datetime.fromtimestamp(os.path.getctime(pipeline_files[-1]))
            visit_stats['last_file'] = last_file.strftime('%Y-%m-%d_%H:%M:%S')

            #Gaps between files
            gaps = []
            for i,f in enumerate(data_files):
                if i > 0:
                    gaps.append(os.path.getctime(data_files[i])-os.path.getmtime(data_files[i-1]))
            ngaps = numpy.array(gaps)
            
            visit_stats['median_file_gap'] = numpy.median(ngaps)
            visit_stats['longest_file_gap'] = ngaps.max()

            #Divide nxs files by type
            for f in data_files:
                with h5py.File(f, "r") as fh:
                    try:
                        e = fh['/entry1/environment/type'][()][0].decode('utf-8')
                        if e == 'BSSC':
                            visit_stats['bssc_samples'] += 1
                        elif e == 'HPLC':
                            visit_stats['hplc_samples'] += 1
                        else:
                            visit_stats['manual_samples'] += 1
                    except:
                        self.logger.error(f'Could not get type from nxs file: {f}')
                        visit_stats['manual_samples'] += 1
                    try:
                        visit_stats['total_exposure_time'] += fh['entry1/instrument/Scalers/count_time'][...].sum()
                    except:
                        self.logger.debug('Failed to get exposure time from nxs, prob a scan')
                        visit_stats['total_exposure_time'] += 20
            return visit_stats

    def getVisit(self):
        try:
            chid = ca.create_channel('BL21B-EA-EXPT-01:ID', connect=True)
            visit = ca.get(chid)
            pattern = '[cmisnl][wmbxnt][0-9]{5}-[0-9]+'
            if re.match(pattern, visit):
                self.logger.debug('Found the current visit from epics')
                return visit
            else:
                self.logger.error('Visit from epics has an expected format')
                return visit
        except:
            self.logger.error('Could not get visit from epics')
            return False

    def setVisit(self, visit):
        if str(visit) in os.listdir(self.visit_directory):
            self.visit_id = str(visit)
            self.visit_directory = self.visit_directory+self.visit_id+'/'
            self.logger.info(f'Set the visit to: {self.visit_id}')
            command = ['groups', self.username]

            my_env = os.environ.copy()
            child = subprocess.Popen(command, env=my_env, stderr=subprocess.PIPE, stdout=subprocess.PIPE)
            users_experiments = [x.decode('utf-8') for x in child.communicate()[0].split()[1:]]
            exit_status = child.returncode
            if 'b21_staff' in users_experiments or self.username in users_experiments:
                self.logger.info('Current user has permissions on this visit')
                try:
                    ###connect to epics
                    chid = ca.create_channel('BL21B-EA-EXPT-01:ID', connect=True)
                    ca.put(chid, self.visit_id)
                    self.logger.info('Set the new visit in epics for the autoprocessing to pick up')
                    return True
                except:
                    self.logger.error('Epics is not on the path, will try accessing explicitly')
                    try:
                        my_env = os.environ.copy()
                        epics_path = '/dls_sw/epics/R3.14.12.3/base/bin/linux-x86_64'
                        my_env["PATH"] = epics_path + ':'+ my_env["PATH"]
                        child = subprocess.Popen(['caput', 'BL21B-EA-EXPT-01:ID', self.visit_id], env=my_env, stderr=subprocess.PIPE, stdout=subprocess.PIPE, bufsize=1)
                        epics_output = child.communicate()
                        epics_status = child.returncode
                        if epics_status == 0:
                            self.logger.info('Successfully put visit ID to epics via command line')
                            return True
                        else:
                            self.logger.error('Failed to put visit ID to epics, the processing pypline will not work')
                            self.logger.error(f'To fix this open a terminal window on another workstation and run the command: caput BL21B-EA-EXPT-01:ID {self.visit_id}')
                            return False
                    except:
                        self.logger.error('Failed to put visit ID to epics, the processing pypline will not work')
                        self.logger.error(f'To fix this open a terminal window on another workstation and run the command: caput BL21B-EA-EXPT-01:ID {self.visit_id}')
                        return False

            else:
                self.logger.error('Current user has no permissions on this visit')
                return False
        else:
            self.logger.error(f'{visit} was not found in the filesystem')
            return False

    def CopyIcons(self):
        self.logger.info('Copying desktop icons to Desktop')
        for launcher in glob(self.template_dir+'*.desktop'):
            if not os.path.isfile(self.home_directory+'Desktop/'+os.path.split(launcher)[-1]):
                self.logger.info('copied '+os.path.split(launcher)[-1]+' to desktop')
                copyfile(launcher, self.home_directory+'Desktop/'+os.path.split(launcher)[-1])
                os.chmod(self.home_directory+'Desktop/'+os.path.split(launcher)[-1], int('755', 8))
            else:
                self.logger.info(f'{os.path.split(launcher)[-1]} is already on desktop')  

    def CopyScatter(self):
        scatter_in = self.template_dir+'scatterIV.jar'
        scatter_out = self.visit_directory+'processing/scatterIV.jar'
        scatter_config = self.visit_directory+'processing/scatter.config'
        config_contents = [
            datetime.now().strftime('#%a %b %d %H:%M:%S BST %Y'),
            'workingDirectory=X\:\\\\'+str(datetime.now().year)+'\\\\'+self.visit_id+'\\\\processing',
            'atsasDirectory=C\:\\\\atsas',
            'beamlineOrManufacturer=B21',
            'xraysource=0',
            'threshold=0.35',
            'subtractionDirectory=X\:\\\\'+str(datetime.now().year)+'\\\\'+self.visit_id+'\\\\processing']
        with open(scatter_config, 'w') as f:
            f.write('\r\n'.join(config_contents))
            
        if os.path.isfile(scatter_in):
            if not os.path.isfile(scatter_out):
                copyfile(scatter_in, scatter_out)
                self.logger.info('copied scatterIV.jar to the processing directory')
                
            else:
                copyfile(scatter_in, scatter_out)
                self.logger.info('Replaced a version of scatter in the processing directory')
        else:
            self.logger.error('did not copy scatter to the processing directory, could not find jar file in /dls_sw/b21/scripts/TEMPLATES')


    def CopyBSA(self):
        bsa_in = self.template_dir+'BSA.pdb'
        bsa_out = self.visit_directory+'processing/BSA.pdb'
            
        if os.path.isfile(bsa_in):
            if not os.path.isfile(bsa_out):
                copyfile(bsa_in, bsa_out)
                self.logger.info('copied BSA.pdb to the processing directory')
            else:
                self.logger.info('BSA.pdb already exists in the processing dir.')
        else:
            self.logger.error('did not copy BSA.pdb to the processing directory, did not exist in /dls_sw/b21/scripts/TEMPLATES')

    def CopyJupyterNotebook(self):
        output_dir = self.visit_directory+'xml/templates/'
        notebook_file = 'report.ipynb'
        nbk_in = self.template_dir+notebook_file
        nbk_out = output_dir+notebook_file

        if not os.path.isdir(output_dir):
            os.makedirs(output_dir)
            
        if os.path.isfile(nbk_in):
            if not os.path.isfile(nbk_out):
                copyfile(nbk_in, nbk_out)
                self.logger.info('copied report.ipynb to the xml/template directory')
            else:
                self.logger.info('report.ipynb already exists in the xml/template dir.')
        else:
            self.logger.error('did not copy report.ipynb to the xml/template directory, did not exist in /dls_sw/b21/scripts/TEMPLATES')

    def GetCurrentProcessingFile(self):
        processing_file = self.template_dir+'current_pipeline.nxs'
        #processing_files = filter(os.path.isfile, glob(self.template_dir+'processing_pipeline_*.nxs'))
        #processing_files.sort(key=os.path.getmtime)
        #if len(processing_files) > 0:
        #    return processing_files[-1]
        if os.path.isfile(processing_file):
            return processing_file
        else:
            self.logger.error('There are no files called processing_pipeline_<date>.nxs in '+self.template_dir)
            sys.exit()

    def WriteMaskFile(self):
        output_file = self.visit_directory+'processing/mask_file_'+datetime.now().strftime('%d%m%y')+'.nxs'
        if os.path.isfile(self.mask_file) and self.mask_file[-4:] == '.nxs':
            copyfile(self.mask_file, output_file)
            self.logger.info('Wrote mask file to: '+output_file)
            return output_file
        else:
            self.logger.error("Mask file: "+self.mask_file+" does not exist")
            return False

    def WriteCalibrationFile(self):
        output_file = self.visit_directory+'processing/calibration_file_'+datetime.now().strftime('%d%m%y')+'.nxs'
        if os.path.isfile(self.calibration_file) and self.calibration_file[-4:] == '.nxs':
            copyfile(self.calibration_file, output_file)
            self.logger.info('Wrote calibration file to: '+output_file)
            return output_file
        else:
            self.logger.error("Calibration file: "+self.calibration_file+" does not exist")
            return False

    def WriteDefaultXmlFiles(self):
        biosaxs_outfile = self.visit_directory+'xml/default.biosaxs'
        hplc_outfile = self.visit_directory+'xml/default.hplc'

        default_biosaxs = [('measurement', [('location', [('plate', '2'), ('row', 'A'), ('column', '9')]), ('sampleName', 'my buffer'), ('concentration', '0.0'), ('viscosity', 'medium'), ('molecularWeight', '0.0'), ('buffer', 'true'), ('buffers', ''), ('yellowSample', 'true'), ('timePerFrame', '1.0'), ('frames', '21'), ('exposureTemperature', '15.0'), ('key', ''), ('mode', 'BS'), ('move', 'true'), ('sampleVolume', '35'), ('visit', self.visit_id), ('username', 'b21user')]), ('measurement', [('location', [('plate', '1'), ('row', 'A'), ('column', '1')]), ('sampleName', 'my sample'), ('concentration', '1.0'), ('viscosity', 'medium'), ('molecularWeight', '66.0'), ('buffer', 'false'), ('buffers', '2a9'), ('yellowSample', 'true'), ('timePerFrame', '1.0'), ('frames', '21'), ('exposureTemperature', '15.0'), ('key', ''), ('mode', 'BS'), ('move', 'true'), ('sampleVolume', '35'), ('visit', self.visit_id), ('username', 'b21user')])]
        default_hplc = [('measurement', [('location', 'A1'), ('sampleName', 'my sample'), ('concentration', '5.0'), ('molecularWeight', '66.0'), ('timePerFrame', '3.0'), ('visit', self.visit_id), ('username', 'b21user'), ('comment', 'None'), ('buffers', '25 mM Tris pH 7.5, 200 mM NaCl'), ('mode', 'HPLC'), ('columnType', 'KW403'), ('duration', '32.0')])]
        myxml = xmlReadWrite()
        myxml.setOutputType('biosaxs')
        open(biosaxs_outfile, 'w').write(myxml.parseToXml(default_biosaxs).decode('utf-8'))
        self.logger.info('Wrote default.biosaxs to xml directory')
        myxml.setOutputType('hplc')
        open(hplc_outfile, 'w').write(myxml.parseToXml(default_hplc).decode('utf-8'))
        self.logger.info('Wrote default.hplc to xml directory')        

    def WriteProcessingPipeline(self, output_file = None, low_q = None, high_q = None, abs_cal = None):
        #GET PIPELINE OUTPUT NAME, SET DEFAULT IF NONE
        if output_file == None:
            output_file = self.visit_directory+'processing/processing_pipeline_'+datetime.now().strftime('%d%m%y')+'.nxs'
        else:
            try:
                output_file = os.path.abspath(output_file)
                if not os.path.isdir(os.path.split(output_file)[0]):
                    raise IOError('Output file must point to an extant directory')
                if not output_file[-4:] == '.nxs':
                    raise IOError('Output file must be of type .nxs')
                self.logger.info('Pipeline output file set manually to: '+str(output_file))
            except:
                output_file = self.visit_directory+'processing/processing_pipeline_'+datetime.now().strftime('%d%m%y')+'.nxs'
                self.logger.error('Error setting pipeline output file name, will write to default')
        #SET LOW AND HIGH Q LIMITS AND SET TO DEFAULT IF FORMAT WRONG
        if not low_q == None:
            try:
                low_q = float(low_q)
            except:
                low_q = None
                self.logger.error('low_q needs to be of type: float, will ignore user input')

        if not high_q == None:
            try:
                high_q = float(high_q)
            except:
                high_q = None
                self.logger.error('high_q needs to be of type: float, will ignore user input')


        #SET ABSOLUTE CALIBRATION MULTIPLIER
        if not abs_cal == None:
            try:
                abs_cal = float(abs_cal)
            except:
                abs_cal = None
                self.logger.error('Factor for absolute calibration must be of type float, will leave as is')

        if os.path.isfile(self.pipeline_file) and self.pipeline_file[-4:] == '.nxs':
            copyfile(self.pipeline_file, output_file)
            self.logger.info(f'Copied: {self.pipeline_file} to: {output_file}')
            self.logger.info('Parsing pipeline nxs file')
            mynxs = h5py.File(output_file, 'r+')
            location = '/entry/process/'
            proc = mynxs[location]
            #this seems like a strange way to do it but its because
            #the entries in the nxs file that are named with just an
            #integer are the processing steps and they are the only
            #entries we want so we use this method to ignore the other
            #entries.
            for i in range(len(proc)):
                if str(i) in proc:
                    if proc[f'{i}/name'][()] == 'Export to Text File':
                        mydata = json.loads(proc[f'{i}/data'][()])
                        mydata['outputDirectoryPath'] = self.visit_directory+'processed'
                        proc[f'{i}/data'][()] = json.dumps(mydata).encode('utf-8')
                    elif proc[f'{i}/name'][()] == u'Import Detector Calibration':
                        calibration_file = self.WriteCalibrationFile()
                        if calibration_file:
                            proc[f'{i}/data'][()] = json.dumps({"filePath":calibration_file}).encode('utf-8')
                            self.logger.info(f"Using detector calibration file: {json.loads(proc[f'{i}/data'][()])['filePath']}")
                        else:
                            self.logger.error('Unable to set the calibration file in pipeline nxs')
                    elif proc[f'{i}/name'][()] == u'Import Mask From File':
                        mask_file = self.WriteMaskFile()
                        if mask_file:
                            proc[f'{i}/data'][()] = json.dumps({"filePath":mask_file}).encode('utf-8')
                            self.logger.info(f"Using detector mask file: {json.loads(proc[f'{i}/data'][()])['filePath']}")
                    elif proc[f'{i}/name'][()] == u'Azimuthal Integration':
                        mydata = json.loads(proc[f'{i}/data'][()])
                        if low_q == None:
                            low_q = mydata['radialRange'][0]
                        if high_q == None:
                            high_q = mydata['radialRange'][1]
                        mydata['radialRange'] = [low_q, high_q]
                        proc[f'{i}/name'][()] = json.dumps(mydata).encode('utf-8')
                    elif proc[f'{i}/name'][()] == u'Multiply by Scalar':
                        if not abs_cal == None:
                            mydata = json.loads(proc[f'{i}/name'][()])
                            mydata['value'] = abs_cal
                            proc[f'{i}/name'][()] = json.dumps(mydata).encode('utf-8')
                        else:
                            pass

                    else:
                        pass
            self.output_pipeline_file = output_file
            self.logger.info('Set the output data directory in the pipeline file to: '+self.visit_directory+'processed')
        else:
            self.logger.error(str(self.pipeline_file)+' does not exist or is not of type nxs')
                    
    def WriteJsonTemplate(self, activeMQ=False):
        self.logger.info('Making xml/templates and processing/log directories')
        log_dir = self.visit_directory+'processing/log/'
        template_dir = self.visit_directory+'xml/templates/'
        notebook_file = template_dir+'report.ipynb'



        for mydir in [log_dir, template_dir]:
            if not os.path.isdir(mydir):
                os.makedirs(mydir)

        if not self.output_pipeline_file:
            self.logger.error('Run WriteProcessingPipeline before WriteJsonTemplate')
        else:
            template_dict = {
                "name": "Reduction to 2D dat file",
                "runDirectory": log_dir,
                "filePath": "",
                "dataDimensions": [-2, -1],
                "processingPath": self.output_pipeline_file,
                "outputFilePath": "",
                "deleteProcessingFile": 'false',
                "datasetPath": "/entry1/detector/data",
                "notebook": notebook_file
                }
            if activeMQ:
                template_dict['publisherURI'] = 'tcp://b21-control:61616'
            with open(template_dir+'template.json', 'w') as json_file:
                json_file.write(json.dumps(template_dict))
            self.logger.info('Wrote JSON template file in: '+template_dir+'template.json')
            self.logger.info('JSON template points to: '+self.output_pipeline_file)

    def setHplcSymLinkLocation(self, location=None):
        try:
            old_location = self.redis.get('hplc_symlink')
            try:
                os.unlink(old_location)
                self.logger.info('Unlinked old symlink location')
            except:
                self.logger.info('Did not unlink old symlink location')
            if os.path.isdir(os.path.split(location)[0]):
                self.redis.set('hplc_symlink', location)
                self.logger.info('Setting hplc_symlink to: '+location)
        except:
            self.logger.error('Failed to set hplc symlink to: '+str(location))

    def getHplcSymLink(self):
        return self.redis.get('hplc_symlink')

    def MakeHplcSymLink(self):
        #Set some parameters
        user = 'b21user'
        host = 'localhost'
        #target_dir = '/dls/b21/data/2019/cm22953-2/processing/hplc_forwarding_link'
        target_dir = self.getHplcSymLink()
        source_dir = self.visit_directory+'processing/hplc/'

        #If you are already b21user you can go ahead directly
        if getpass.getuser() == user:
            self.logger.info(f'Making symlink {target_dir} pointing to: {source_dir}')
            try:
                if os.path.islink(target_dir):
                    os.unlink(target_dir)
                if not os.path.isdir(source_dir):
                    os.mkdir(source_dir)
                os.chdir(os.path.split(target_dir)[0])
                os.symlink(os.path.relpath(source_dir), os.path.split(target_dir)[1])
            except:
                self.logger.error('Failed to make the HPLC symlink, prob a permissions issue')
        #If you are not b21user you need to switch
        else:
            self.logger.info('To create the HPLC link we switch to b21user')

            #Give three chances to get the password right
            tries = 0
            success = False
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            while not success and tries < 3:
                mypass = getpass.getpass('Enter b21user password: ')
                try:
                    client.connect(host, username=user, password=mypass)
                    success = True
                except:
                    self.logger.error('Failed to login as b21user, prob wrong password, try again')
                    tries += 1


            if success:
                self.logger.info('Unlinking the old dir')
                command = 'unlink '+target_dir
                chan = client.get_transport().open_session()
                chan.exec_command(command)
                if chan.recv_exit_status() == 0:
                    self.logger.info('Successfully unlinked the old directory.')
                else:
                    self.logger.error('Failed to unlink the old dir, will try to link the new one anyway.')
                self.logger.info('Linking the new directory')
                command = 'cd '+os.path.split(target_dir)[0]+';ln -s '+os.path.relpath(source_dir)+' '+os.path.split(target_dir)[1]
                chan = client.get_transport().open_session()
                chan.exec_command(command)
                if chan.recv_exit_status() == 0:
                    self.logger.info('Linked the new directory')
                else:
                    self.logger.error('Failed to link the new directory, you will have to do this manually')
            else:
                self.logger.error('Failed to login as b21user after three tries, you will have to make the HPLC link manually')
            client.close()

    def MakeProcessingDirSymLink(self):
        #Set some parameters
        user = 'b21user'
        host = 'localhost'
        target_dir = '/home/b21user/Documents/current_visit'
        source_dir = self.visit_directory+'processing'

        #If you are already b21user you can go ahead directly
        if getpass.getuser() == user:
            self.logger.info('Making symlink '+target_dir+': pointing to: '+source_dir)
            try:
                if os.path.islink(target_dir):
                    os.unlink(target_dir)
                os.symlink(source_dir, target_dir)
            except:
                self.logger.error('Failed to make the processing dir symlink, this is only a shortcut for scatter so no dramas')
        #If you are not b21user you need to switch
        else:
            self.logger.info('To create the processing dir link we switch to b21user')

            #Give three chances to get the password right
            tries = 0
            success = False
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            while not success and tries < 3:
                mypass = getpass.getpass('Enter b21user password: ')
                try:
                    client.connect(host, username=user, password=mypass)
                    success = True
                except:
                    self.logger.error('Failed to login as b21user, prob wrong password, try again')
                    tries += 1


            if success:
                self.logger.info('Unlinking the old dir')
                command = 'unlink '+target_dir
                chan = client.get_transport().open_session()
                chan.exec_command(command)
                if chan.recv_exit_status() == 0:
                    self.logger.info('Successfully unlinked the old directory.')
                else:
                    self.logger.error('Failed to unlink the old dir, will try to link the new one anyway.')
                self.logger.info('Linking the new directory')
                command = 'ln -s '+source_dir+' '+target_dir
                chan = client.get_transport().open_session()
                chan.exec_command(command)
                if chan.recv_exit_status() == 0:
                    self.logger.info('Linked the new directory')
                else:
                    self.logger.error('Failed to link the new directory, you will have to do this manually')
            else:
                self.logger.error('Failed to login as b21user after three tries, you will have to make the HPLC link manually')
            client.close()

    def make_pdf_report(self):
        page_size = ps = A4
        output_file = self.visit_directory+'processing/beamline_parameters.pdf'
        self.logger.info(f'Outputting beamline info to {output_file}')
        c = Canvas(output_file, pagesize=ps)
        #HEADER
        c.setStrokeColorRGB(0,0,0)
        c.setFillColorRGB(0,0.1,0.4)
        logo_x = ps[0]/6
        logo_y = logo_x/1.5
        c.rect(10,ps[1]-logo_y-10,logo_x,logo_y, fill=1)

        c.setFillColorRGB(1,1,1)
        c.setFont('Helvetica', 48)
        c.drawString(20,ps[1]-24-logo_y/2, "B21")

        c.setFillColorRGB(0,0.1,0.4)
        c.setFont('Helvetica', 24)
        c.drawString(20+logo_x,ps[1]-5-(1*24), "AUTOMATED")
        c.drawString(20+logo_x,ps[1]-2.5-(2*24), "BEAMLINE AND USEAGE")
        c.drawString(20+logo_x,ps[1]-(3*24), "REPORT")

        c.setFont('Helvetica', 14)
        c.drawString(ps[0]-120,ps[1]-20, datetime.now().strftime('%a %d %b %Y'))
        c.drawString(ps[0]-120,ps[1]-20-14, self.visit_id)

        c.setStrokeColorRGB(0,0.1,0.4)
        c.line(0,ps[1]-76,ps[0],ps[1]-76)

        #CALIBRATION STUFF
        c.drawString(10,ps[1]-100,"CALIBRATION INFORMATION")

        try:
            with h5py.File(self.calibration_file, "r") as fh:
                wavelength = round(fh['/entry1/calibration_sample/beam/incident_wavelength'][()],4)
                energy = round(12.398/fh['/entry1/calibration_sample/beam/incident_wavelength'][()],1)
                sample_to_dect = round(fh['/entry1/instrument/detector/distance'][()],1)
                beam_position_x_mm = round(fh['/entry1/instrument/detector/beam_center_x'][()],2)
                beam_position_y_mm = round(fh['/entry1/instrument/detector/beam_center_y'][()],2)
                self.logger.debug('Got parameters from calibration file')
        except:
            self.logger.error('Failed to get into from calibration file, will use defaults')
            wavelength = 0.9524
            energy = 13.0
            sample_to_dect = 3703.5
            beam_postion_x_mm = 129.3
            beam_postion_y_mm = 19.87
        try:
            with h5py.File(self.pipeline_file, "r") as fh:
                location = '/entry/process/'
                proc = fh[location]
                for i in range(len(proc)):
                    if str(i) in proc:
                        if proc[f'{i}/name'][()] == u'Azimuthal Integration':
                            mydata = json.loads(proc[f'{i}/data'][()])
                            q_range = mydata['radialRange']
            self.logger.debug('Got info from pipeline file')
        except:
            self.logger.error('Failed to get info from pipeline file, using defaults')
            q_range = [0.0045,0.34]

        tabs = (30,200)
        line_spacing = 15
        csr = ps[1]-115
        c.setFont('Helvetica', 12)
        c.drawString(tabs[0],csr, "Wavelength:")
        c.drawString(tabs[1],csr, f"{wavelength} \u00C5")
        csr-=line_spacing
        c.drawString(tabs[0],csr, "Energy:")
        c.drawString(tabs[1],csr, f"{energy} keV")
        csr-=line_spacing
        c.drawString(tabs[0],csr, "Beam centre X:")
        c.drawString(tabs[1],csr, f"{beam_position_x_mm} mm")
        csr-=line_spacing
        c.drawString(tabs[0],csr, "Beam centre Y:")
        c.drawString(tabs[1],csr, f"{beam_position_y_mm} mm")
        csr-=line_spacing
        c.drawString(tabs[0],csr, "Sample to detector distance:")
        c.drawString(tabs[1],csr, f"{sample_to_dect} mm")
        csr-=line_spacing
        c.drawString(tabs[0],csr, "Detector:")
        c.drawString(tabs[1],csr, f"EigerX 4M (Dectris)")
        csr-=line_spacing
        c.drawString(tabs[0],csr, "Source:")
        c.drawString(tabs[1],csr, f"bending magnet")
        csr-=line_spacing
        c.drawString(tabs[0],csr, "Flux:")
        c.drawString(tabs[1],csr, f"2x10")
        c.setFont('Helvetica', 8)
        c.drawString(tabs[1]+27,csr+5, f"4")
        c.setFont('Helvetica', 12)
        c.drawString(tabs[1]+35,csr, f"photons.s")
        c.setFont('Helvetica', 8)
        c.drawString(tabs[1]+88,csr+5, f"-1")
        c.setFont('Helvetica', 12)
        csr-=line_spacing
        c.drawString(tabs[0],csr, "Q range:")
        c.drawString(tabs[1],csr, f"{q_range[0]}-{q_range[1]} \u00C5")
        c.setFont('Helvetica', 8)
        c.drawString(tabs[1]+76,csr+5, f"-1")
        c.setFont('Helvetica', 12)
        csr-=line_spacing
        c.drawString(tabs[0],csr, "Q definition:")
        c.drawString(tabs[1],csr, f"4π*sin(θ)/λ")
        csr-=line_spacing
        c.drawString(tabs[0],csr, "Intensity units:")
        c.drawString(tabs[1],csr, f"cm")
        c.setFont('Helvetica', 8)
        c.drawString(tabs[1]+17,csr+5, f"-1")
        c.setFont('Helvetica', 12)
        c.drawString(tabs[1]+25,csr, f"(absolute intensity scaled to water scatter at 0.0163)")
        csr-=line_spacing
        c.drawString(tabs[0],csr, "Capillary diameter:")
        c.drawString(tabs[1],csr, "1.5 mm")
        csr-=line_spacing
        c.drawString(tabs[0],csr, "Default exposure temperature:")
        c.drawString(tabs[1],csr, "15 \u00B0C (used unless otherwise specified per sample)")
        csr-=line_spacing
        c.drawString(tabs[0],csr, "Beam size at sample:")
        c.drawString(tabs[1],csr, "1.0 x 0.25 mm")
        csr-=line_spacing
        c.drawString(tabs[0],csr, "Beam size at detector (focus):")
        c.drawString(tabs[1],csr, "0.05 x 0.05 mm (FWHM)")
        c.save()

if __name__ == '__main__':
    if len(sys.argv) < 2:
        sys.argv.append('-h')

    parser = OptionParser()
    required = OptionGroup(parser, "Required Arguments")
    optional = OptionGroup(parser, "Optional Arguments")
    required.add_option("-v", "--visit_id", action="store", type="string", dest="visit_id", default="None", help="The visit ID of the experiment i.e. mx9537-84. If none is given will attempt to retrieve visit ID from database.")
    optional.add_option("-n", "--q_min", action="store", type="float", dest="lo_q", default=None, help="Set the low Q limit for the radial integration")
    optional.add_option("-x", "--q_max", action="store", type="float", dest="hi_q", default=None, help="Set the high Q limit for the radial integration")
    optional.add_option("-a", "--abs_cal", action="store", type="float", dest="abs_cal", default=None, help="Multiplier for setting absolute calibration, default is to leave it as is.")
    optional.add_option("-y", "--year", action="store", type="int", dest="year", default=None, help="Manually set the year to look for the visit folder, default is current year.")
    optional.add_option("-o", "--output_file", action="store", type="string", dest="output_file", default=None, help="The location of the pipeline nxs output file. The default is into current visit processing dir with name processing_pipeline_<todays date>.nxs ")
    optional.add_option("-m", "--mq", action="store_true", dest="activemq", default=False, help="Turn on activeMQ communication, default is False.")
    optional.add_option("-p", "--pdf", action="store_false", dest="makepdf", default=True, help="Skip output of calibration and beamline info as a pdf file, default is to output the file.")
    optional.add_option("-l", "--hplc_link", action="store", type="string", dest="hplc_link", default="None", help="Set a new location for the HPLC symlink.")
    parser.add_option_group(required)
    parser.add_option_group(optional)
    (options, args) = parser.parse_args()

    if options.visit_id == "None":
        sys.exit('Useage: user_setup.py -v <visit id>')
    

    job = UserSetup()
    if options.year:
        job.set_year(options.year)
    if job.setVisit(options.visit_id):
        job.CopyIcons()
        job.CopyScatter()
        job.CopyBSA()
        job.CopyJupyterNotebook()
        job.WriteProcessingPipeline(output_file = options.output_file, low_q = options.lo_q, high_q = options.hi_q, abs_cal = options.abs_cal)
        job.WriteJsonTemplate(activeMQ=options.activemq)
        if not options.hplc_link == 'None':
            job.setHplcSymLinkLocation(options.hplc_link)
        job.MakeHplcSymLink()
        job.WriteDefaultXmlFiles()
        if options.makepdf:
            job.make_pdf_report()
        job.logger.info('Finished successfully')
