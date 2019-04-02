#!/dls/science/groups/b21/PYTHON/bin/python
'''
Created on Jul 4, 2018

@author: nathan
'''
import datetime
from epics import Device
import logging
from time import sleep
import redis
import sys
from optparse import OptionParser
from optparse import OptionGroup
class toggleHplcBiosaxs(object):
    """Allows toggling of the cell position between HPLC mode and biosaxs mode
    
    """
    
    '''
    Constructor
    '''
    def __init__(self):
        #set some parameters
        self.type = 'toggleHplcBiosaxs'
        self.motor_x = Device('BL21B-MO-TABLE-02:X.', attrs=('VAL', 'RBV', 'DESC'))
        self.motor_y = Device('BL21B-MO-TABLE-02:Y.', attrs=('VAL', 'RBV', 'DESC'))
        self.redis = redis.StrictRedis(host='b21-ws005.diamond.ac.uk', port=6379, db=0)
        self.rkey = 'toggle_hplc_biosaxs'
        self.deadband = 0.01

        ###start a log file
        self.logger = logging.getLogger('toggleHplcBiosaxs')
        self.logger.setLevel(logging.INFO)
        formatter = logging.Formatter('%(asctime)s: %(levelname)s: %(module)s: %(message)s',"[%Y-%m-%d %H:%M:%S]")
        streamhandler = logging.StreamHandler()
        streamhandler.setFormatter(formatter)
        self.logger.addHandler(streamhandler)
        self.logger.info('Running the toggleHplcBiosaxs script')

    def getFromRedis(self, key='biosaxs_table_x'):
        keys = ['biosaxs_table_x', 'biosaxs_table_y', 'hplc_table_x', 'hplc_table_y', 'gelcell_table_x', 'gelcell_table_y']
        if key in keys:
            if self.redis.exists(key):
                return float(self.redis.get(key))
            else:
                self.logger.error(key+' does not exist in redis, needs to be set first')
                return None
        else:
            self.logger.error('getFromRedis takes one of: '+','.join(keys)+' as input')
            return None

    def setHplcPosition(self):
        try:
            motor_x = self.motor_x.get('RBV')
            self.redis.set('hplc_table_x', motor_x)
            self.logger.info('Set HPLC motor_x position to: '+str(motor_x))
            motor_y = self.motor_y.get('RBV')
            self.redis.set('hplc_table_y', motor_y)
            self.logger.info('Set HPLC motor_y position to: '+str(motor_y))
            return True
        except:
            self.logger.error('Could not set the HPLC position, check redis, check epics')
            return False
        
    def gotoHplcPosition(self):
        motor_x = self.getFromRedis('hplc_table_x')
        motor_y = self.getFromRedis('hplc_table_y')
        if None in [motor_x, motor_y]:
            self.logger.error('Cannot go to HPLC position, not set in redis')
            return False
        else:
            self.motor_x.put('VAL', motor_x, wait=True)
            self.motor_y.put('VAL', motor_y, wait=True)
            self.logger.info('Set saxs cell to the HPLC position')
            return True
        
    def setBiosaxsPosition(self):
        try:
            motor_x = self.motor_x.get('RBV')
            self.redis.set('biosaxs_table_x', motor_x)
            self.logger.info('Set BIOSAXS motor_x position to: '+str(motor_x))
            motor_y = self.motor_y.get('RBV')
            self.redis.set('biosaxs_table_y', motor_y)
            self.logger.info('Set BIOSAXS motor_y position to: '+str(motor_y))
            return True
        except:
            self.logger.error('Could not set the BIOSAXS position, check redis, check epics')

    def gotoBiosaxsPosition(self):
        motor_x = self.getFromRedis('biosaxs_table_x')
        motor_y = self.getFromRedis('biosaxs_table_y')
        if None in [motor_x, motor_y]:
            self.logger.error('Cannot go to BIOSAXS position, not set in redis')
            return False
        else:
            self.motor_x.put('VAL', motor_x, wait=True)
            self.motor_y.put('VAL', motor_y, wait=True)
            self.logger.info('Set saxs cell to the BIOSAXS position')
            return True

    def setGelcellPosition(self):
        try:
            motor_x = self.motor_x.get('RBV')
            self.redis.set('gelcell_table_x', motor_x)
            self.logger.info('Set GELCELL motor_x position to: '+str(motor_x))
            motor_y = self.motor_y.get('RBV')
            self.redis.set('gelcell_table_y', motor_y)
            self.logger.info('Set GELCELL motor_y position to: '+str(motor_y))
            return True
        except:
            self.logger.error('Could not set the BIOSAXS position, check redis, check epics')

    def gotoGelcellPosition(self):
        motor_x = self.getFromRedis('gelcell_table_x')
        motor_y = self.getFromRedis('gelcell_table_y')
        if None in [motor_x, motor_y]:
            self.logger.error('Cannot go to GELCELL position, not set in redis')
            return False
        else:
            self.motor_x.put('VAL', motor_x, wait=True)
            self.motor_y.put('VAL', motor_y, wait=True)
            self.logger.info('Set saxs cell to the BIOSAXS position')
            return True

    def returnStatus(self):
        if self.getFromRedis('biosaxs_table_x')+self.deadband > self.motor_x.get('RBV') > self.getFromRedis('biosaxs_table_x')-self.deadband and self.getFromRedis('biosaxs_table_y')+self.deadband > self.motor_y.get('RBV') > self.getFromRedis('biosaxs_table_y')-self.deadband:
            return 'biosaxs'
        elif self.getFromRedis('hplc_table_x')+self.deadband > self.motor_x.get('RBV') > self.getFromRedis('hplc_table_x')-self.deadband and self.getFromRedis('hplc_table_y')+self.deadband > self.motor_y.get('RBV') > self.getFromRedis('hplc_table_y')-self.deadband:
            return 'hplc'
        elif self.getFromRedis('gelcell_table_x')+self.deadband > self.motor_x.get('RBV') > self.getFromRedis('gelcell_table_x')-self.deadband and self.getFromRedis('gelcell_table_y')+self.deadband > self.motor_y.get('RBV') > self.getFromRedis('gelcell_table_y')-self.deadband:
            return 'gelcell'
        else:
            return 'None'
                  
if __name__ == '__main__':
    if len(sys.argv) < 2:
        sys.argv.append('-h')

    parser = OptionParser()
    optional = OptionGroup(parser, "Optional Arguments")
    optional.add_option("-s", "--set", action="store", type="string", dest="set", default="None", help="Use the current table position to be the setpoint for either biosaxs, hplc or gelcell, takes 'hplc', 'gelcell or 'biosaxs' as argument")
    optional.add_option("-g", "--goto", action="store", type="string", dest="goto", default="None", help="Goto a set position, takes 'hplc', 'gellcell' or 'biosaxs' as argument")
    optional.add_option("-x", "--status", action="store_true", dest="status", default=False, help="Returns the current position of the cell and exits.")

    parser.add_option_group(optional)
    (options, args) = parser.parse_args()

    job = toggleHplcBiosaxs()
    if options.status:
        print 'Current cell position: '+job.returnStatus()
    if options.set.lower() == 'hplc':
        job.setHplcPosition()
    elif options.set.lower() == 'biosaxs':
        job.setBiosaxsPosition()
    elif options.set.lower() == 'gelcell':
        job.setGelcellPosition()
    else:
        pass
    if options.goto.lower() == 'hplc':
        job.gotoHplcPosition()
    elif options.goto.lower() == 'biosaxs':
        job.gotoBiosaxsPosition()
    elif options.goto.lower() == 'gelcell':
        job.gotoGelcellPosition()
    else:
        pass
    job.logger.info('FINISHED NORMALLY!')

    
    
