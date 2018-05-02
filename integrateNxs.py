#!/dls/science/groups/b21/PYTHON/bin/python
'''
Created on May 1, 2018

@author: nathan
'''
import glob
import json
import logging
from nexusformat import nexus as nx
from optparse import OptionParser
from optparse import OptionGroup
import os
from shutil import copyfile
import subprocess
import time
import zmq
import sys

class integrateNxs(object):
    """Given a nxs file will run the integration via DAWN

    Class contains functions to take a nxs file, extract visit and
    processing pipeline info and run the integration of the nxs file
    to dat files via a headless DAWN interface.
    """

    def __init__(self):
        self.nxsfile = None
        self.visit_directory = None
        self.output_directory = None
        self.output_nxs_file = None
        self.pipeline_file = None
        self.creation_time = None
        self.json_file = '/tmp/temp.json'
        self.working_pipeline_file = '/tmp/temp_pipeline.nxs'
        self.cores = 1
        #SETUP LOG
        self.logger = logger = logging.getLogger('integrateNxs')
        self.logger.setLevel(logging.INFO)
        formatter = logging.Formatter('%(asctime)s: %(levelname)s: %(module)s: %(message)s',"[%Y-%m-%d %H:%M:%S]")
        streamhandler = logging.StreamHandler()
        streamhandler.setFormatter(formatter)
        self.logger.addHandler(streamhandler)
        self.logger.info('started a new nxs file integration job')

    def setCores(self, cores=1):
        if type(cores) == type(1):
            self.cores = cores
            self.logger.info('Set number of cores to: '+str(cores))
        else:
            self.logger.error('Cannot set number of cores to: '+str(cores))

    def setNxsFile(self, nxsfile=None):
        try:
            if not nxsfile:
                error_message = 'setNxsFile function requires an argument, got None'
                self.logger.error(error_message)
                raise IOError(error_message)
            if not os.path.isfile(nxsfile):
                error_message = str(nxsfile)+' does not exist'
                self.logger.error(error_message)
                raise IOError(error_message)
            if not nxsfile[-4:] == '.nxs':
                error_message = str(nxsfile)+' is not of type nxs'
                self.logger.error(error_message)
                raise IOError(error_message)
            self.nxsfile = nxsfile
            self.creation_time = os.path.getctime(nxsfile)
            self.logger.info('Set nxs file as: '+str(self.nxsfile))
            return True
        except:
            sys.exit('Fatal error: Failed to set the nxs file')
            return False

    def getNxsFile(self):
        return self.nxsfile

    def setVisitDirectory(self):
        if not self.nxsfile == None:
            try:
                self.visit_directory = os.path.split(os.path.realpath(self.nxsfile))[0]
                if os.path.isdir(self.visit_directory+'/processing'):
                    self.output_directory = self.visit_directory+'/processing/'
                    self.logger.info('Set output directory to: '+self.output_directory)
                    self.output_nxs_file = self.output_directory+os.path.splitext(os.path.split(self.nxsfile)[-1])[0]+'_processing.nxs'
                    return True
                else:
                    error_message = 'No processing subdirectory, not a valid visit directory'
                    self.logger.error(error_message)
                    raise IOError(error_message)
            except:
                return False

    def getVisitDirectory(self):
        return self.visit_directory
        
    def setProcessingPipeline(self):
        try:
            if not self.output_directory:
                error_message = 'No output directory, needed to get processing pipeline'
                self.logger.error(error_message)
                raise IOError(error_message)
            processing_pipelines = glob.glob(self.output_directory+'/processing_pipeline*.nxs')
            if len(processing_pipelines) == 0:
                error_message = 'No processing pipelines available in this visit'
                self.logger.error(error_message)
                raise IOError(error_message)
            elif len(processing_pipelines) == 1:
                self.pipeline_file = processing_pipelines[0]
                return True
            else:
                filedates = {}
                for file in processing_pipelines:
                    filedates[os.path.getctime(file)] = file
                for ctime in sorted(filedates.keys()):
                    if ctime < self.creation_time:
                        self.pipeline_file = filedates[ctime]
            if self.pipeline_file:
                self.logger.info('Set the processing pipeline to: '+self.pipeline_file)
                return True
            else:
                error_message = 'Could not find a pipeline file that predates this nxs file'
                self.logger.error(error_message)
                raise IOError(error_message)
        except:
            return False

    def getProcessingPipeline(self):
        return self.pipeline_file

    def createTempPipeline(self):
        try:
            copyfile(self.pipeline_file, self.working_pipeline_file)
            mynxs = nx.tree.NXFile(self.working_pipeline_file, 'rw')
            tree = mynxs.readfile()
            for item in tree.entry.process._entries.iteritems():
                try:
                    if item[1].name.nxdata == u'Export to Text File':
                        mydata = json.loads(item[1].data.nxdata)
                        mydata['outputDirectoryPath'] = self.output_directory
                        item[1].data.nxdata = unicode(json.dumps(mydata), 'utf-8')
                    else:
                        pass
                except:
                    pass
            self.logger.info('Created a temporary pipeline file with /processing output dir')
            return True
        except:
            self.logger.error('Unable to create a temporary pipeline file')
            return False

    def writeJsonFile(self):
        json_content = {
            'runDirectory': '/tmp',
            'name': 'b21_reduction',
            'filePath': self.nxsfile,
            'dataDimensions': [-1, -2],
            'processingPath': self.working_pipeline_file,
            'outputFilePath': self.output_nxs_file,
            'deleteProcessingFile': False,
            'datasetPath': '/entry1/detector',
            'numberOfCores': self.cores,
            'xmx': 1024
            }

        try:
            with open(self.json_file, 'w') as jsonfile:
                jsonfile.write(json.dumps(json_content))
            self.logger.info('Wrote the JSON template file to: '+self.json_file)
            return True
        except:
            self.logger.error('Could not write the JSON template file')
            return False

    def runDawn(self):
        self.logger.info('Setting up the dawn environment')
        dawn_executable = ['/dls_sw/apps/DawnDiamond/2.8/builds/release-linux64/dawn', '-noSplash', '-configuration', os.environ['HOME']+'/.eclipse', '-application', 'org.dawnsci.commandserver.processing.processing', '-data', '@none', '-path', self.json_file]
        
        #to make an updated dawn_environment file open a terminal, do: module load dawn
        #then start a python shell and run the following:
        #>>> import os, json
        #>>> outfile = open('/dls/science/groups/b21/B21/dawn_environment.json', 'w')
        #>>> outfile.write(json.dumps(os.environ.copy()))
        #>>> outfile.close()
        #>>> quit()
        my_env = json.loads(open('/dls/science/groups/b21/B21/dawn_environment.json').read())
        self.logger.info('Running Dawn, may take a few seconds')
        child = subprocess.Popen(dawn_executable, stderr=subprocess.PIPE, stdout=subprocess.PIPE)
        dawn_output = child.communicate()[0].split('\n')
        dawn_status = child.returncode
        self.logger.info('Dawn completed with status code: '+str(dawn_status))


    def cleanUp(self):
        for file in [self.json_file, self.working_pipeline_file]:
            os.remove(file)
        self.logger.info('Cleaned up temporary files')

if __name__ == '__main__':
    if len(sys.argv) < 2:
        sys.argv.append('-h')

    parser = OptionParser()
    required = OptionGroup(parser, "Required Arguments")
    required.add_option("-n", "--nxs_file", action="store", type="string", dest="nxsfile", default="None", help="The nxs file you want to integrate.")
    optional = OptionGroup(parser, "Optional Arguments")
    optional.add_option("-l", "--local", action="store_true", dest="local", default=False, help="If included the nxs file will integrate on the local machine, default is to run on ws005.")

    parser.add_option_group(required)
    parser.add_option_group(optional)
    (options, args) = parser.parse_args()

    if options.nxsfile == "None":
        sys.exit('Useage: integrateNxs.py -n nxs_file.nxs')

    if options.local:
        job = integrateNxs()
        if job.setNxsFile(options.nxsfile):
            if job.setVisitDirectory():
                if job.setProcessingPipeline():
                    if job.writeJsonFile():
                        if job.createTempPipeline():
                            job.runDawn()
                            job.cleanUp()
                            job.logger.info('FINISHED NORMALLY')

    else:
        mylogger = logging.getLogger('remoteIntegrate')
        mylogger.setLevel(logging.INFO)
        formatter = logging.Formatter('%(asctime)s: %(levelname)s: %(module)s: %(message)s',"[%Y-%m-%d %H:%M:%S]")
        streamhandler = logging.StreamHandler()
        streamhandler.setFormatter(formatter)
        mylogger.addHandler(streamhandler)
        mylogger.info('Started a remote integration job')
        context = zmq.Context()
        try:
            mylogger.info('Connecting to zmq server')
            socket = context.socket(zmq.REQ)
            socket.connect("tcp://172.23.91.68:5555")
            message = str(options.nxsfile).encode('utf-8')
            mylogger.info('Sending the processing job to ws005, may take a few seconds')
            socket.send(message)
            reply = socket.recv()
            if reply == 'Got it':
                mylogger.info('Connection to zmq successful, processing complete')
                mylogger.info('COMPLETED NORMALLY')
            else:
                raise OSError('Could not connect to zmq server')
        except:
            mylogger.error('There was an issue connecting to zmq, check the server is running in supervisor on ws005')


