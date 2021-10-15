#!/dls/science/groups/b21/PYTHON3/bin/python
from datetime import datetime
import glob
import logging
from math import ceil
import os.path
import time
import sys

YEAR_RANGE = 5
BASE_FOLDER = '/dls/b21/data/'
PATTERN = '*.nxs'

class UserTracking(object):
    """Analyses user visit folders

    Looks through a user visit and counts the number of various
    kinds of files and how long the experiment lasted for etc.
    """
    __version__ = '1.00'
    def __init__(self):
        self.headers = []
        self.visit_folder = None
        self.year = datetime.now().year
        self.visit_info = {}
        self.file_list = []

        #CREATE A LOGGER
        self.logger = logging.getLogger('UserTracking')
        self.logger.setLevel(logging.DEBUG)
        formatter = logging.Formatter('%(asctime)s: %(levelname)s: %(module)s: %(message)s',"[%Y-%m-%d %H:%M:%S]")
        streamhandler = logging.StreamHandler()
        streamhandler.setFormatter(formatter)
        if len(self.logger.handlers) == 0:
            self.logger.addHandler(streamhandler)
        self.logger.debug('UserTracking was instantiated')

    @property
    def number_of_files(self):
        return len(self.file_list)

    def find_visit(self, visit):
        for d in [f'{BASE_FOLDER}{y}/' for y in range(self.year,self.year-YEAR_RANGE,-1)]:
            if os.path.isdir(f'{d}{visit}'):
                self.visit_folder = f'{d}{visit}/'
                self.logger.info(f'Found visit folder: {self.visit_folder}')
                return True
            else:
                self.logger.error(f'Failed to find visit {visit} in last {YEAR_RANGE} years')
                return False

    def set_filelist(self, filelist):
        if type(filelist) == list:
            self.file_list = filelist
            self.logger.debug('Set file list')
        else:
            self.logger.error('setFileList method requires a list as input')

    def get_fileList(self):
        return self.file_list

    def find_files(self):
        if self.visit_folder:
            fl = sorted(glob.glob(f'{self.visit_folder}{PATTERN}'))
            self.logger.debug(f'Found {len(fl)} nxs files in visit')
            return fl
        else:
            self.logger.error('getFileList method called with no visit folder')
            return []

    def timestamp_first_file(self):
        ts = None
        try:
            ts = datetime.fromtimestamp(os.path.getctime(self.file_list[0]))
            self.logger.debug(f'First file timestamp: {ts}')
        except:
            self.logger.error('Failed to get time stamp from first file')
        return ts

    def timestamp_last_file(self):
        ts = None
        try:
            ts = datetime.fromtimestamp(os.path.getmtime(self.file_list[-1]))
            self.logger.debug(f'Last file timestamp: {ts}')
        except:
            self.logger.error('Failed to get time stamp from last file')
        return ts

    def collate_data(self):
        #timestamp first file
        ts_first = self.timestamp_first_file()
        if type(ts_first) == datetime:
            self.visit_info['timestamp first file'] = ts_first.strftime("%Y-%m-%d_%H:%M:%S")

        #timestamp last file
        ts_last = self.timestamp_last_file()
        if type(ts_last) == datetime:
            self.visit_info['timestamp last file'] = ts_last.strftime("%Y-%m-%d_%H:%M:%S")

        #duration
        if type(ts_last) == type(ts_first) == datetime:
            duration = ts_last - ts_first
            self.visit_info['duration (hours)'] = duration.total_seconds()/60**2
            self.visit_info['duration (shifts)'] = ceil(duration.total_seconds()/60**2/8)

        #gaps
        all_gaps = []
        for i, f in enumerate(self.file_list[1:]):
            all_gaps.append(
                (
                    datetime.fromtimestamp(os.path.getmtime(self.file_list[i+1])) -
                    datetime.fromtimestamp(os.path.getmtime(self.file_list[i]))
                    ).total_seconds())
        print(all_gaps)
        print(self.file_list[1])


if __name__ == '__main__':
    for v in sys.argv[1:]:
        job =  UserTracking()
        if job.find_visit(v):
            job.set_filelist(job.find_files())
            job.collate_data()
        print(job.visit_info)
