#!/dls/science/groups/b21/PYTHON/bin/python
'''
Created on Dec 8th, 2016

@author: nathan
'''
import logging
from optparse import OptionParser
from optparse import OptionGroup
from nexusformat import nexus as nx#import nxload, nxsave
import json
import os
import sys

class AbsCal(object):
    """Sets the multiplier for absolute calibration
    
    Given a water and empty capillary shot sets the multiplier for
    outputing absolutely calibrated dat files into the reduction
    pipeline.

    """
    
    '''
    Constructor
    '''
    def __init__(self):
        #set some parameters
        self.water = None
        self.empty = None
        self.qmin = 0.34 # window for calculating
        self.qmax = 0.36 # scattering
        self.target = 0.0163
        self.master_pipeline = '/dls_sw/b21/scripts/TEMPLATES/current_pipeline.nxs'

        ###start a log file
        self.logger = logging.getLogger('AbsCal')
        self.logger.setLevel(logging.DEBUG)
        formatter = logging.Formatter('%(asctime)s: %(levelname)s: %(module)s: %(message)s',"[%Y-%m-%d %H:%M:%S]")
        streamhandler = logging.StreamHandler()
        streamhandler.setFormatter(formatter)
        self.logger.addHandler(streamhandler)

    def SetWater(self, water):
        intensities = []
        if os.path.isfile(water) and water[-4:] == '.dat':
            with open(water, 'r') as waterfile:
                for line in waterfile.readlines():
                    line = line.split()
                    try:
                        q = float(line[0])
                        i = float(line[1])
                        e = float(line[2])
                        if self.qmin < q < self.qmax:
                            intensities.append(i)
                    except:
                        pass
            if len(intensities) > 10:
                self.water = sum(intensities)/len(intensities)
            else:
                self.logger.error('Insufficient points within high Q window to calculate water scatter')
        else:
            self.logger.error('Water dat file does not exist or is not of type .dat')

    def SetEmpty(self, empty):
        intensities = []
        if os.path.isfile(empty) and empty[-4:] == '.dat':
            with open(empty, 'r') as emptyfile:
                for line in emptyfile.readlines():
                    line = line.split()
                    try:
                        q = float(line[0])
                        i = float(line[1])
                        e = float(line[2])
                        if self.qmin < q < self.qmax:
                            intensities.append(i)
                    except:
                        pass
            if len(intensities) > 10:
                self.empty = sum(intensities)/len(intensities)
            else:
                self.logger.error('Insufficient points within high Q window to calculate empty scatter')
        else:
            self.logger.error('Empty dat file does not exist or is not of type .dat')

    def MeasuredScatter(self):
        if self.empty and self.water:
            return self.water - self.empty
        else:
            self.logger.error('Cannot return scatter until dat files have been parsed')
            return False

    def Ratio(self, scatter):
        try:
            return self.MeasuredScatter() / self.target
        except:
            self.logger.error('Cannot return ratio without first parsing dat files')
            return False

    def GetMultiplier(self):
        if os.path.isfile(self.master_pipeline) and self.master_pipeline[-4:] == '.nxs':
            self.logger.info('Parsing pipeline nxs file')
            mynxs = nx.tree.NXFile(self.master_pipeline, 'rw')
            tree = mynxs.readfile()
            for item in tree.entry.process._entries.iteritems():
                try:
                    if item[1].name.nxdata == u'Multiply by Scalar':
                        mydata = json.loads(item[1].data.nxdata)
                        return mydata['value']
                except:
                    pass
        else:
            self.logger.error('Could not return multiplier from current nxs pipeline')

    def SetMultiplier(self, multiplier):
        if os.path.isfile(self.master_pipeline) and self.master_pipeline[-4:] == '.nxs':
            self.logger.info('Setting Multiplier in pipeline nxs file')
            mynxs = nx.tree.NXFile(self.master_pipeline, 'rw')
            tree = mynxs.readfile()
            for item in tree.entry.process._entries.iteritems():
                try:
                    if item[1].name.nxdata == u'Multiply by Scalar':
                        mydata = json.loads(item[1].data.nxdata)
                        mydata['value'] = multiplier
                        item[1].data.nxdata = unicode(json.dumps(mydata), 'utf-8')
                    else:
                        pass
                except:
                    pass
        else:
            self.logger.error('Cannot get pipeline nxs file')

    def CalculateNewMultiplier(self, old_multiplier, ratio):
        try:
            return old_multiplier / ratio
        except:
            self.logger.error('Could not calculate the new multiplier')
            return False

if __name__ == '__main__':
    if len(sys.argv) < 2:
        sys.argv.append('-h')

    parser = OptionParser()
    required = OptionGroup(parser, "Required Arguments")
    optional = OptionGroup(parser, "Optional Arguments")
    required.add_option("-w", "--water", action="store", type="string", dest="water", default="None", help="An unsubtracted water shot. Recommend a single 2 min exposure.")
    required.add_option("-m", "--empty", action="store", type="string", dest="empty", default="None", help="An unsubtracted empty capillary shot. Recommend a single 2 min exposure.")

    parser.add_option_group(required)
    parser.add_option_group(optional)
    (options, args) = parser.parse_args()

    if options.water == "None" or options.empty == None:
        sys.exit('Useage: set_absolute_cal.py -w <water shot.dat> -m <empty cap shot.dat>')


    job = AbsCal()
    job.SetWater(options.water)
    job.SetEmpty(options.empty)
    print 'Multiplier in current pipeline is: '+str(job.GetMultiplier())
    print 'Giving a water intensity of: '+str(job.MeasuredScatter())
    print 'Need to set multiplier to :'+str(job.CalculateNewMultiplier(job.GetMultiplier(), job.Ratio((job.MeasuredScatter()))))
    print 'To give water intensity of: '+str(job.target)
    var = raw_input('Set multiplier in the master pipeline file? (y/n): ')
    if var in ['y', 'Y', 'Yes', 'yes']:
        job.SetMultiplier(job.CalculateNewMultiplier(job.GetMultiplier(), job.Ratio((job.MeasuredScatter()))))
        job.logger.info('Set the multiplier in the master file')
    job.logger.info('Finished successfully')
