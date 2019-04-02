#!/dls/science/groups/b21/PYTHON/bin/python
'''
Created on Dec 4th, 2018

@author: nathan
'''
from datetime import datetime
import logging
from optparse import OptionParser
from optparse import OptionGroup
import os
import shutil
import sys

class Archive(object):
    """Moves the current pipeline, mask or calibration files to archive folder 
    
    When you create a new pipeline, mask or calibration nxs file
    via DAWN you have to remove the previous current file or DAWN
    cannot write the new file. We have been appending the date onto
    the end of the file and moving it to an archive folder in the 
    /dls_sw/b21/scripts/TEMPLATES folder. This script automates that. 

    """
    
    '''
    Constructor
    '''
    def __init__(self):
        #set some parameters
        self.templates_directory = '/dls_sw/b21/scripts/TEMPLATES/'
        self.archive_directories = {'mask': 'processing_mask_archive/',
                                    'pipeline': 'processing_pipeline_archive/',
                                    'calibration': 'processing_calibration_archive/'
                                    }
        self.jobtype = None
        ###start a log file
        self.logger = logging.getLogger('Archive')
        self.logger.setLevel(logging.DEBUG)
        formatter = logging.Formatter('%(asctime)s: %(levelname)s: %(module)s: %(message)s',"[%Y-%m-%d %H:%M:%S]")
        streamhandler = logging.StreamHandler()
        streamhandler.setFormatter(formatter)
        self.logger.addHandler(streamhandler)

    def setJobType(self, jobtype=None):
        if jobtype in self.archive_directories.keys():
            self.jobtype=jobtype
            self.logger.info('Set job type to: '+jobtype)
            return True
        else:
            self.logger.error('Job type should be: mask, calibration or pipeline. Not: '+str(jobtype))

    def returnArchiveFileName(self):
        filename = self.templates_directory+self.archive_directories[self.jobtype]+self.jobtype+datetime.now().strftime('_%Y_%m_%d_')
        index = 1
        while os.path.isfile(filename+str(index)+'.nxs'):
            index += 1
        filename = filename+str(index)+'.nxs'
        self.logger.info('Archive file will be: '+filename)
        return filename

    def returnFileToBeArchived(self):
        return self.templates_directory+'current_'+self.jobtype+'.nxs'

    def moveFile(self, infile=None, outfile=None):
        if os.path.isfile(infile) and os.path.isdir(os.path.dirname(os.path.abspath(outfile))):
            try:
                shutil.move(infile, outfile)
                self.logger.info('Moved '+self.jobtype+' file to archive')
            except:
                self.logger.error('Could not move '+self.jobtype+' file to archive, could be permissions')
        else:
            self.logger.error('Could not archive '+self.jobtype+' file, either file or archive folder do not exist')

    def archive(self):
        self.moveFile(self.returnFileToBeArchived(), self.returnArchiveFileName())

if __name__ == '__main__':
    if len(sys.argv) < 2:
        sys.argv.append('-h')

    parser = OptionParser()
    required = OptionGroup(parser, "Required Arguments")
    optional = OptionGroup(parser, "Optional Arguments")
    required.add_option("-a", "--archive", action="store", type="string", dest="archive", default="None", help="The type of file you want to archive, can be mask, pipeline or calibration.")
    required.add_option("-u", "--unarchive", action="store", type="string", dest="unarchive", default="None", help="The file you want to recover from the archive, must be a file in one of the archive folders.")

    parser.add_option_group(required)
    parser.add_option_group(optional)
    (options, args) = parser.parse_args()

    job = Archive()
    if job.setJobType(options.archive.lower()):
        job.archive()
        job.logger.info('Finished successfully')
    else:
        job.logger.error('Finished in error')
