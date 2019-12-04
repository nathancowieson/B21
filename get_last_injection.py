#!/dls/science/groups/b21/PYTHON3/bin/python
'''
Created on Nov 18th, 2019

@author: nathan
'''
from datetime import datetime
import logging
import pickle
import redis

class getLastInjectionSignal(object):
    """Gets the last injection signal from redis
    
    The epics_daemon.py process running on the ws005 machine under 
    supervisor control saves a time stamp of the previous last HPLC
    injection. This script returns it.

    """
    '''
    Constructor
    '''
    def __init__(self):
        #set some parameters
        self.type = 'getLastInjectionSignal'
        self.redis = redis.StrictRedis(host='b21-ws005.diamond.ac.uk', port=6379, db=0)

        ###start a log file
        self.logger = logging.getLogger(self.type)
        self.logger.setLevel(logging.DEBUG)
        formatter = logging.Formatter('%(asctime)s: %(levelname)s: %(module)s: %(message)s',"[%Y-%m-%d %H:%M:%S]")
        streamhandler = logging.StreamHandler()
        streamhandler.setFormatter(formatter)
        self.logger.addHandler(streamhandler)

        #some runtime parameters
        self.asDatetime = True
        self.redis_key='lastInjectionSignal'

    def getFromRedis(self):
        self.logger.debug('getFromRedis function was run')
        try:
            return self.redis.get(self.redis_key)
        except:
            self.logger.error('Failed to get last injection signal from redis')
            return False

    def getTimestamp(self, pickled=True):
        timestamp = self.getFromRedis()
        if not pickled:
            if timestamp:
                return pickle.loads(self.getFromRedis())
            else:
                return False
        else:
            return timestamp

if __name__ == '__main__':
    from optparse import OptionParser
    from optparse import OptionGroup
    parser = OptionParser()
    required = OptionGroup(parser, "Required Arguments")
    optional = OptionGroup(parser, "Optional Arguments")
    optional.add_option("-t", "--text", action="store_true", dest="astext", default=False, help="Return the time stamp as a plain text string rather than a pickled datetime object, default is pickled")
    parser.add_option_group(required)
    parser.add_option_group(optional)
    (options, args) = parser.parse_args()

    job = getLastInjectionSignal()
    if options.astext:
        print(job.getTimestamp(pickled=False))
    else:
        print(job.getTimestamp(pickled=True))
    job.logger.info('Finished normally')

