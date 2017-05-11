#!/dls/science/groups/b21/PYTHON/bin/python
'''
Created on Dec 8th, 2016

@author: nathan
'''
import logging
from epics import caget
from optparse import OptionParser
from optparse import OptionGroup
from datetime import datetime
import yaml
#from nexusformat import nexus as nx#import nxload, nxsave
#import json
import os.path
import sys

class Snapshot(object):
    """Takes a snapshot of beamline settings
    
    Imports PVs from pvs.yaml and dumps a snapshot of positions
    to a csv file.

    """
    
    '''
    Constructor
    '''
    def __init__(self):
        #set some parameters
        self.pv_array = [('TIMESTAMP', datetime.now().strftime('%Y/%m/%d_%H:%M:%S'))]
        config_file = '/dls/science/groups/b21/B21/pvs.yml'
        with open(config_file, 'r') as ymlfile:
            self.myconfig = yaml.load(ymlfile)

        ###start a log file
        self.logger = logging.getLogger('Snapshot')
        self.logger.setLevel(logging.DEBUG)
        formatter = logging.Formatter('%(asctime)s: %(levelname)s: %(module)s: %(message)s',"[%Y-%m-%d %H:%M:%S]")
        streamhandler = logging.StreamHandler()
        streamhandler.setFormatter(formatter)
        self.logger.addHandler(streamhandler)

    def GetFromEpics(self):
        categories = self.myconfig.keys()
        categories.remove('SETTINGS')
        starttime = datetime.now()
        for category in categories:
            for item in self.myconfig[category].keys():
                try:
                    self.pv_array.append( (category+':'+item, str(caget(self.myconfig[category][item]))) )
                    
                except:
                    self.pv_array.append( (category+':'+item, 'ERROR') )
                    self.logger.error('Problem getting PV: '+self.myconfig[category][item])
        self.logger.info('Finished getting all PVs in '+str((datetime.now()-starttime).seconds)+' seconds')

    def AddMessage(self, message=""):
        message = '"'+''.join(str(message).split(','))+'"'
        self.pv_array.append( ('MESSAGE',str(message)) )

    def ReturnPVString(self, option='data'):
        header = []
        data = []
        for item in self.pv_array:
            header.append(str(item[0]))
            data.append(str(item[1]))
        if option == 'header':
            return ','.join(header)+'\n'
        elif option == 'data':
            return ','.join(data)+'\n'
        else:
            self.logger.error('ReturnPVString takes either data or header as an option.')
            return ','.join(data)+'\n'
                    

if __name__ == '__main__':
    parser = OptionParser()
    required = OptionGroup(parser, "Required Arguments")
    optional = OptionGroup(parser, "Optional Arguments")
    required.add_option("-m", "--message", action="store", type="string", dest="message", default="", help="A message to add to the snapshot line i.e. 'beam was off!' or 'beam was good'")

    parser.add_option_group(required)
    parser.add_option_group(optional)
    (options, args) = parser.parse_args()


    job = Snapshot()
    job.AddMessage(options.message)
    
    job.GetFromEpics()
    if os.path.isfile(job.myconfig['SETTINGS']['OUTFILE']):
        with open(job.myconfig['SETTINGS']['OUTFILE'], 'a') as outfile:
            outfile.write(job.ReturnPVString('data'))
            job.logger.info('Wrote snapshot to file')
    else:
        with open(job.myconfig['SETTINGS']['OUTFILE'], 'w') as outfile:
            outfile.write(job.ReturnPVString('header'))
            outfile.write(job.ReturnPVString('data'))
            job.logger.info('Wrote snapshot to a new file: '+job.myconfig['SETTINGS']['OUTFILE'])

    job.logger.info('Finished successfully')
