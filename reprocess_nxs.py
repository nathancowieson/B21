#!/dls/science/groups/b21/PYTHON/bin/python
import sys
import logging
from optparse import OptionParser
from optparse import OptionGroup
import os.path
import re

sys.path.insert(0, '/dls/science/groups/b21/PYTHON/packages/Pypline3/Pypline3')
from visit_id import VisitID
from database import Database


if __name__ == '__main__':
    ###start a log file
    logger = logging.getLogger('Reprocess')
    logger.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s: %(levelname)s: %(module)s: %(message)s',"[%Y-%m-%d %H:%M:%S]")
    streamhandler = logging.StreamHandler()
    streamhandler.setFormatter(formatter)
    logger.addHandler(streamhandler)

    if len(sys.argv) < 2:
        sys.argv.append('-h')

    parser = OptionParser()
    required = OptionGroup(parser, "Required Arguments")
    optional = OptionGroup(parser, "Optional Arguments")
    required.add_option("-n", "--nxs", action="store", type="string", dest="nxs_file", default="None", help="The full path to the nxs file you would like to reprocess. i.e. /dls/b21/data/2018/cm19678-1/b21-382321.nxs")

    parser.add_option_group(required)
    parser.add_option_group(optional)
    (options, args) = parser.parse_args()

    try:
        if not os.path.isfile(options.nxs_file) and options.nxs_file[-4:] == '.nxs':
            raise IOError('NXS file does not exist')
    except:
        logger.error('NXS file does not exist')
        sys.exit('Useage: user_setup.py -n full/path/to/nxsfile.nxs')


    #define visit
    visit_pattern = re.compile("[mncis][pmxwnt][0-9]{5}-[0-9]{1,3}")
    if visit_pattern.match(options.nxs_file.split('/')[5]):
        visit = VisitID(options.nxs_file.split('/')[5])
        logger.info('Set visit to: '+visit.ReturnVisitID())
    else:
        logger.error('The specified nxs file does not seem to be in the context of a visit directory')

    #connect to database
    database = Database()
    database.setDatabase(visit.ReturnDatabaseFileName())

    #remove the file
    try:
        if database.removeNxsFile(options.nxs_file, visit):
            logger.info(options.nxs_file+' has been removed from the database')
            logger.info('The pypline will reprocess this file in the next few seconds')
        else:
            logger.error('Failed to remove the nxs file from the database.')
    except:
        sys.exit('Failed to remove the nxs file from the database.')

    logger.info('FINISHED NORMALLY')
