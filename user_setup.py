#!/dls/science/groups/b21/PYTHON/bin/python
'''
Created on Dec 8th, 2016

@author: nathan
'''
import logging
from optparse import OptionParser
from optparse import OptionGroup
import os
from datetime import datetime
import sys
import getpass
import paramiko
import subprocess
from glob import glob
from shutil import copyfile
from nexusformat import nexus as nx#import nxload, nxsave
import json
from epics import ca
sys.path.insert(0, '/dls/science/groups/b21/B21')
from XlsToGda import xmlReadWrite

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
        self.visit_directory = '/dls/b21/data/'+str(datetime.now().year)+'/'
        self.username = getpass.getuser()
        self.home_directory = os.path.expanduser("~")+'/'
        self.template_dir = '/dls_sw/b21/scripts/TEMPLATES/'
        self.mask_file = self.template_dir+'current_mask.nxs'
        self.calibration_file = self.template_dir+'current_calibration.nxs'
        self.pipeline_file = self.template_dir+'current_pipeline.nxs'
        self.output_pipeline_file = False

        ###start a log file
        self.logger = logging.getLogger('UserSetup')
        self.logger.setLevel(logging.DEBUG)
        formatter = logging.Formatter('%(asctime)s: %(levelname)s: %(module)s: %(message)s',"[%Y-%m-%d %H:%M:%S]")
        streamhandler = logging.StreamHandler()
        streamhandler.setFormatter(formatter)
        self.logger.addHandler(streamhandler)
           
    def SetVisit(self, visit):
        if str(visit) in os.listdir(self.visit_directory):
            self.visit_id = str(visit)
            self.visit_directory = self.visit_directory+self.visit_id+'/'
            self.logger.info('Set the visit to: '+self.visit_id)
            command = ['groups', self.username]

            my_env = os.environ.copy()
            child = subprocess.Popen(command, env=my_env, stderr=subprocess.PIPE, stdout=subprocess.PIPE)
            users_experiments = child.communicate()[0].split()[1:]
            exit_status = child.returncode
            if 'b21_staff' in users_experiments or self.username in users_experiments:
                self.logger.info('Current user has permissions on this visit')
                try:
                    ###connect to epics
                    self.chid = ca.create_channel('BL21B-EA-EXPT-01:ID', connect=True)
                    ca.put(self.chid, self.visit_id)
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
                            self.logger.error('To fix this open a terminal window on another workstation and run the command: caput BL21B-EA-EXPT-01:ID '+self.visit_id)
                            return False
                    except:
                        self.logger.error('Failed to put visit ID to epics, the processing pypline will not work')
                        self.logger.error('To fix this open a terminal window on another workstation and run the command: caput BL21B-EA-EXPT-01:ID '+self.visit_id)
                        return False

            else:
                self.logger.error('Current user has no permissions on this visit')
                return False
        else:
            self.logger.error(str(visit)+' was not found in the filesystem')
            return False

    def CopyIcons(self):
        self.logger.info('Copying desktop icons to Desktop')
        for launcher in glob(self.template_dir+'*.desktop'):
            if not os.path.isfile(self.home_directory+'Desktop/'+os.path.split(launcher)[-1]):
                self.logger.info('copied '+os.path.split(launcher)[-1]+' to desktop')
                copyfile(launcher, self.home_directory+'Desktop/'+os.path.split(launcher)[-1])
                os.chmod(self.home_directory+'Desktop/'+os.path.split(launcher)[-1], int('755', 8))
            else:
                self.logger.info(os.path.split(launcher)[-1]+' is already on desktop')  

    def CopyScatter(self):
        scatter_in = self.template_dir+'scatter3.jar'
        scatter_out = self.visit_directory+'processing/scatter3.jar'
        if os.path.isfile(scatter_in):
            if not os.path.isfile(scatter_out):
                copyfile(scatter_in, scatter_out)
                self.logger.info('copied scatter3.jar to the processing directory')
            else:
                copyfile(scatter_in, scatter_out)
                self.logger.info('Replaced a version of scatter in the processing directory')
        else:
            self.logger.error('did not copy scatter to the processing directory, could not find jar file in /dls_sw/b21/scripts/TEMPLATES')

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

        default_biosaxs = [('measurement', [('location', [('plate', '2'), ('row', 'A'), ('column', '9')]), ('sampleName', 'my buffer'), ('concentration', '0.0'), ('viscosity', 'medium'), ('molecularWeight', '0.0'), ('buffer', 'true'), ('buffers', ''), ('yellowSample', 'true'), ('timePerFrame', '1.0'), ('frames', '28'), ('exposureTemperature', '15.0'), ('key', ''), ('mode', 'BS'), ('move', 'true'), ('sampleVolume', '35'), ('visit', self.visit_id), ('username', 'b21user')]), ('measurement', [('location', [('plate', '1'), ('row', 'A'), ('column', '1')]), ('sampleName', 'my sample'), ('concentration', '1.0'), ('viscosity', 'medium'), ('molecularWeight', '66.0'), ('buffer', 'false'), ('buffers', '2a9'), ('yellowSample', 'true'), ('timePerFrame', '1.0'), ('frames', '28'), ('exposureTemperature', '15.0'), ('key', ''), ('mode', 'BS'), ('move', 'true'), ('sampleVolume', '35'), ('visit', self.visit_id), ('username', 'b21user')])]
        default_hplc = [('measurement', [('location', 'A1'), ('sampleName', 'my sample'), ('concentration', '5.0'), ('molecularWeight', '66.0'), ('timePerFrame', '3.0'), ('visit', self.visit_id), ('username', 'b21user'), ('comment', 'None'), ('buffers', '25 mM Tris pH 7.5, 200 mM NaCl'), ('mode', 'HPLC'), ('columnType', 'kw304'), ('duration', '30.0')])]
        myxml = xmlReadWrite()
        myxml.setOutputType('biosaxs')
        open(biosaxs_outfile, 'w').write(myxml.parseToXml(default_biosaxs))
        self.logger.info('Wrote default.biosaxs to xml directory')
        myxml.setOutputType('hplc')
        open(hplc_outfile, 'w').write(myxml.parseToXml(default_hplc))
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
            self.logger.info('Copied: '+self.pipeline_file+' to: '+output_file)
            self.logger.info('Parsing pipeline nxs file')
            mynxs = nx.tree.NXFile(output_file, 'rw')
            tree = mynxs.readfile()
            for item in tree.entry.process._entries.iteritems():
                try:
                    if item[1].name.nxdata == u'Export to Text File':
                        mydata = json.loads(item[1].data.nxdata)
                        mydata['outputDirectoryPath'] = self.visit_directory+'processed'
                        item[1].data.nxdata = unicode(json.dumps(mydata), 'utf-8')
                    elif item[1].name.nxdata == u'Import Detector Calibration':
                        calibration_file = self.WriteCalibrationFile()
                        if calibration_file:
                            item[1].data.nxdata = unicode(json.dumps({"filePath":calibration_file}), 'utf-8')
                            self.logger.info('Using detector calibration file: '+json.loads(item[1].data.nxdata)['filePath'])
                        else:
                            self.logger.error('Unable to set the calibration file in pipeline nxs')
                    elif item[1].name.nxdata == u'Import Mask From File':
                        mask_file = self.WriteMaskFile()
                        if mask_file:
                            item[1].data.nxdata = unicode(json.dumps({"filePath":mask_file}), 'utf-8')
                            self.logger.info('Using detector mask file: '+json.loads(item[1].data.nxdata)['filePath'])
                    elif item[1].name.nxdata == u'Azimuthal Integration':
                        mydata = json.loads(item[1].data.nxdata)
                        if low_q == None:
                            low_q = mydata['radialRange'][0]
                        if high_q == None:
                            high_q = mydata['radialRange'][1]
                        mydata['radialRange'] = [low_q, high_q]
                        item[1].data.nxdata = unicode(json.dumps(mydata), 'utf-8')
                    elif item[1].name.nxdata == u'Multiply by Scalar':
                        if not abs_cal == None:
                            mydata = json.loads(item[1].data.nxdata)
                            mydata['value'] = abs_cal
                            item[1].data.nxdata = unicode(json.dumps(mydata), 'utf-8')
                        else:
                            pass

                    else:
                        pass
                except:
                    pass
            self.output_pipeline_file = output_file
            self.logger.info('Set the output data directory in the pipeline file to: '+self.visit_directory+'processed')
        else:
            self.logger.error(str(self.pipeline_file)+' does not exist or is not of type nxs')
                    
    def WriteJsonTemplate(self):
        self.logger.info('Making xml/templates and processing/log directories')
        log_dir = self.visit_directory+'processing/log/'
        template_dir = self.visit_directory+'xml/templates/'
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
                "datasetPath": "/entry1/detector"
                }
            with open(template_dir+'template.json', 'w') as json_file:
                json_file.write(json.dumps(template_dict))
            self.logger.info('Wrote JSON template file in: '+template_dir+'template.json')
            self.logger.info('JSON template points to: '+self.output_pipeline_file)

    def MakeHplcSymLink(self):
        #Set some parameters
        user = 'b21user'
        host = 'localhost'
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        target_dir = '/dls/b21/data/2017/cm16775-4/processing/hplc_forwarding_link'
        source_dir = self.visit_directory+'hplc/saxs'

        #If you are already b21user you can go ahead directly
        if getpass.getuser() == user:
            self.logger.info('Making symlink '+target_dir+': pointing to: '+source_dir)
            try:
                if os.path.islink(target_dir):
                    os.unlink(target_dir)
                os.symlink(source_dir, target_dir)
            except:
                self.logger.error('Failed to make the HPLC symlink, prob a permissions issue')
        #If you are not b21user you need to switch
        else:
            self.logger.info('To create the HPLC link we switch to b21user')

            #Give three chances to get the password right
            tries = 0
            success = False
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
    optional.add_option("-o", "--output_file", action="store", type="string", dest="output_file", default=None, help="The location of the pipeline nxs output file. The default is into current visit processing dir with name processing_pipeline_<todays date>.nxs ")

    parser.add_option_group(required)
    parser.add_option_group(optional)
    (options, args) = parser.parse_args()

    if options.visit_id == "None":
        sys.exit('Useage: user_setup.py -v <visit id>')


    job = UserSetup()
    if job.SetVisit(options.visit_id):
        job.CopyIcons()
        job.CopyScatter()
        job.WriteProcessingPipeline(output_file = options.output_file, low_q = options.lo_q, high_q = options.hi_q, abs_cal = options.abs_cal)
        job.WriteJsonTemplate()
        job.MakeHplcSymLink()
        job.WriteDefaultXmlFiles()
        job.logger.info('Finished successfully')
