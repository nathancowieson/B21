#!/dls/science/groups/b21//PYTHON3/bin/python
'''
Created on Nov 18th, 2019

@author: nathan
'''
from epics import Motor, PV
import json
import logging
import matplotlib.pyplot as plt
import numpy
from optparse import OptionParser
from optparse import OptionGroup
import pickle
import redis
import sys

class EnergyChange(object):
    """Change energy via the B21 DMM
    
    The position of various axes in the DMM are optimised across the energy
    range from 8 to 15 KeV. Third order polynomial functions are fitted to
    each motor position. The polynomials are then used so that motor positions
    can be derived for a required energy. Polynomials are stored in redis.

    """
    
    '''
    Constructor
    '''
    def __init__(self):
        #set some parameters
        self.type = 'energyChange'
        #self.redis = redis.StrictRedis(host='b21-ws005.diamond.ac.uk', port=6379, db=0, decode_responses=True)
        self.redis = redis.StrictRedis(host='b21-ws005.diamond.ac.uk', port=6379, db=0)
        self.pvs = None
        self.d = 24 #d spacing for substrates in mono
        self.mono_offset = 18
        self.invert_bragg = True
        self.dmm_points = None

        ###start a log file
        self.logger = logging.getLogger(self.type)
        self.logger.setLevel(logging.DEBUG)
        formatter = logging.Formatter('%(asctime)s: %(levelname)s: %(module)s: %(message)s',"[%Y-%m-%d %H:%M:%S]")
        streamhandler = logging.StreamHandler()
        streamhandler.setFormatter(formatter)
        self.logger.addHandler(streamhandler)

    def getDmmPoints(self):
        dmm_points = []
        try:
            if 'dmm_points' in [i.decode('utf-8') for i in self.redis.keys()]:
                dmm_points = json.loads(self.redis.get('dmm_points'))
                self.logger.debug(f'Got {len(dmm_points)} DMM points from redis')
            else:
                self.logger.info('No DMM points in redis, starting from blank')
        except:
            self.logger.error('Could not access redis, starting from blank')
        return dmm_points

    def addNewDmmPoint(self, point=None):
        '''
        point should be a dictionary of the type 
        returned by the getPosition function.
        '''
        if type(point) == type({}):
            has_right_entries = True
            for i in self.pvs.keys():
                if not i in point.keys():
                    has_right_entries = False
                    self.logger.debug(f'The point given to addNewDmmPoint lacks the entry {i}')
            if has_right_entries:
                point['Wavelength (A)'] = self.getWavelength(point['dmm_p1'])
                point['Energy (KeV)'] = self.getEnergy(point['dmm_p1'])
                current_points = self.getDmmPoints()
                current_points.append(point)
                self.redis.set('dmm_points', json.dumps(current_points))
                self.logger.info(f'Added point: ')
                return True
            else:
                self.logger.error('Could not addNewDmmPoint, incorrect entries')
                return False
        else:
            self.logger.error('Could not addNewDmmPoint, needs a dictionary as input')
            return False
        

    def clearDmmPoints(self):
        try:
            if self.redis.set('dmm_points', json.dumps([])):
                self.logger.info('Cleared DMM points in redis')
            else:
                self.logger.error('There was an error clearing DMM points in redis')
        except:
            self.logger.error('There was an error accessing redis')

    def getDspacing(self):
        self.logger.debug('getDspacing function called')
        return self.d

    def setDspacing(self, d=None):
        try:
            self.d = float(d)
            self.logger.info(f'Set d spacing to: {self.d}')
        except:
            self.logger.error(f'Could not set d spacing to: {d}')

    def getPVs(self):
        try:
            self.pvs = {'dmm_z': Motor('BL21B-OP-DMM-01:Z'),
                        'dmm_y1': Motor('BL21B-OP-DMM-01:Y1'),
                        'dmm_y2': Motor('BL21B-OP-DMM-01:Y2'),
                        'dmm_p1': Motor('BL21B-OP-DMM-01:PITCH1'),
                        'dmm_p2': Motor('BL21B-OP-DMM-01:PITCH2'),
                        'dmm_r2': Motor('BL21B-OP-DMM-01:ROLL2'),
                        'd3d2': PV('BL21B-DI-PHDGN-03:PHD2:I'),
                        'bsdiode': PV('BL21B-DI-PHDGN-07:PHD1:I'),
                        'xrayeye_y': PV('BL21B-DI-PHDGN-08:CAM:STAT:CentroidY_RBV'),
                        'xrayeye_x': PV('BL21B-DI-PHDGN-08:CAM:STAT:CentroidX_RBV')}
            self.logger.info('Got PVs')
            return True
        except:
            self.logger.error('Failed to get PVs')
            return False

    def getPosition(self, axis='all'):
        if self.pvs:
            if axis in self.pvs.keys():
                self.logger.debug(f'Got position for axis {self.pvs[axis].DESC}')
                return self.pvs[axis].RBV
            elif axis == 'all':
                output_array = {}
                for a in self.pvs.keys():
                    if self.pvs[a].__class__ == Motor:
                        output_array[a] = self.pvs[a].RBV
                    elif self.pvs[a].__class__ == PV:
                        output_array[a] = self.pvs[a].get()
                    else:
                        self.logger.error(f'{a} is of unknown type')
            else:
                self.logger.error('Unknown option for get position')
            return output_array
        else:
            self.logger.error('You need to run the getPVs function first')

    def saveRedisPoint(self, point=None):
        '''
        takes the output array from the getPosition function and writes it to
        redis for fitting later on.
        '''
        pass                         

    def getWavelength(self, bragg=None):
        '''
        Will calculate from current DMM P1 position or can
        take an optional bragg angle which should be supplied
        in mrad.
        '''
        if bragg:
            try:
                if self.invert_bragg:
                    return numpy.sin(-1*float(bragg)*0.001)*2*self.d
                else:
                    return numpy.sin(float(bragg)*0.001)*2*self.d
            except:
                self.logger.error('getWavelength requires a float as input')
                return 0
        else:
            if self.pvs:
                if 'dmm_p1' in self.pvs.keys():
                    try:
                        if self.invert_bragg:
                            return numpy.sin(-1*self.pvs['dmm_p1'].RBV*0.001)*2*self.d
                        else:
                            return numpy.sin(self.pvs['dmm_p1'].RBV*0.001)*2*self.d
                    except:
                        self.logger.error('getWavelength function failed')
                        return 0
                else:
                    self.logger.error('getWavelength function failed, no dmm_p1 in pv list')
                    return 0
            else:
                self.logger.error('You need to run the getPVs function first')
                return 0

    def getEnergy(self, bragg=None):
        if bragg:
            try:
                return 12.39852/self.getWavelength(float(bragg))
            except:
                self.logger.error('getEnergy function requires a float as input')
                return 0
        else:
            if self.pvs:
                try:
                    return 12.39852/self.getWavelength()
                except:
                    self.logger.error('getEnergy function failed because getWavelength failed')
                    return 0
            else:
                self.logger.error('You need to run the getPVs function first')

    def setPolynomial(self, axis=None, polynomial=None):
        if axis in ['dmm_y2', 'dmm_r2', 'dmm_p2']:
            try:
                a,b,c,d = [float(i) for i in polynomial[:]]
                axis_name = 'polynomial_'+axis
                self.redis.set(axis_name, pickle.dumps(polynomial))
                self.logger.info(f'Set {axis_name} in redis')
            except:
                self.logger.error('setPolynomial function needs a numpy polynomial')
        else:
            self.logger.error('setPolynomial function needs axis as: dmm_y2, dmm_r2 or dmm_p2')

    def gotoEnergy(self, energy=13):
        setpoints = {}
        try:
            setpoints['energy'] = float(energy)
            if 9.5 < energy < 14.001:
                setpoints['wavelength'] = 12.39852/setpoints['energy']
                dmm_p1 = numpy.arcsin(setpoints['wavelength']/(2*self.d))#rad
                setpoints['dmm_z'] = self.mono_offset/numpy.tan(dmm_p1*2)
                if self.invert_bragg:
                    setpoints['dmm_p1'] = -1000*dmm_p1#mrad
                else:
                    setpoints['dmm_p1'] = 1000*dmm_p1#mrad
            for axis in ['dmm_y2', 'dmm_p2', 'dmm_r2']:
                z = pickle.loads(self.redis.get('polynomial_'+axis))
                p = numpy.poly1d(z)
                setpoints[axis] = p(energy)
            for i in setpoints.keys():
                self.logger.info(f'Will set {i} to: {setpoints[i]}')
            proceed = input('Confirm that we are ok to proceed (y/n):')
            if proceed.upper() in ['Y', 'YES']:
                for axis in ['dmm_z', 'dmm_p1', 'dmm_y2', 'dmm_r2', 'dmm_p2']:
                    self.pvs[axis].move(setpoints[axis], wait=True)
                self.logger.info('Now do a p2 scan in GDA: rscan dmm_pitch2 -0.1 0.1 0.01 d3d2')
            else:
                self.logger.info('Will not set any DMM positions')
        except:
            self.logger.error('Error getting motor positions')

    def calculatePolynomial(self, axis=None):
        '''
        Calculate a third order polynomial function from the motor
        positions stored in redis, axis should be dmm_y2, dmm_r2,
        dmm_p2.
        '''
        x = []
        y = []
        if axis in ['dmm_y2', 'dmm_r2', 'dmm_p2']:
            for i in self.getDmmPoints():
                try:
                    x.append(i['energy (KeV)'])
                    y.append(i[axis])
                except:
                    self.logger.error(f'Error getting energy and {axis} from a point in redis: skipping')
            z = numpy.polyfit(numpy.array(x), numpy.array(y), 3)
            p = numpy.poly1d(z)
            xp = numpy.linspace(min(x), max(x), 100)
            plt.plot(x, y, '.', xp, p(xp), '-')
            self.logger.info('Check the fit then close the window to be prompted further')
            plt.show()
            apply = input('Set current fit values in redis (y/n)?')
            if apply.upper() in ['Y', 'YES']:
                self.setPolynomial(axis, z)
            else:
                self.logger.info('Will not set this fit')

        else:
            self.logger.error('calculatePolynomial function needs either dmm_r2, dmm_p2 or dmm_y2 as an argument')

if __name__ == '__main__':
    if len(sys.argv) < 2:
        sys.argv.append('-h')

    parser = OptionParser()
    required = OptionGroup(parser, "Required Arguments")
    optional = OptionGroup(parser, "Optional Arguments")
    optional.add_option("-a", "--add", action="store_true", dest="addpoint", default=False, help="Add the current DMM configuration to the points table, true/false flag, needs no argument")
    optional.add_option("-c", "--clear", action="store_true", dest="clear", default=False, help="Clear the DMM points saved in redis before doing anything else, needs no argument")
    optional.add_option("-p", "--poly", action="store", type="string", dest="polynomial", default=None, help="Fit a polynomial to stored motor positions, options are dmm_r2, dmm_p2, dmm_y2.")
    optional.add_option("-s", "--set", action="store", type="float", dest="setpoint", default=None, help="Set new energy for DMM, needs a float in the range 9.5 to 14 KeV.")
    parser.add_option_group(required)
    parser.add_option_group(optional)
    (options, args) = parser.parse_args()

    job = EnergyChange()
    if job.getPVs():
        if options.clear:
            job.clearDmmPoints()
        if options.addpoint:
            job.addNewDmmPoint(job.getPosition('all'))
        elif options.polynomial:
            job.calculatePolynomial(options.polynomial)
        elif options.setpoint:
            job.gotoEnergy(options.setpoint)
        else:
            pass
        
        #print('Energy (KeV),Wavelength (A),'+','.join([str(i) for i in job.getPosition('all').keys()]))
        #print(str(job.getEnergy())+','+str(job.getWavelength())+','+','.join([str(i) for i in job.getPosition('all').values()]))
    job.logger.info('Finished successfully')

    '''
    job.addNewDmmPoint({'energy (KeV)':14.0003152348502, 'Wavelength (A)':0.885588630828615, 'dmm_z':487.5515, 'dmm_y1':0.0011, 'dmm_y2':17.92, 'dmm_p1':-18.45081, 'dmm_p2':-18.49004, 'dmm_r2':-0.126, 'd3d2':0.062241829366958, 'bsdiode':-0.000769371679795, 'xrayeye_y':166.315533073593, 'xrayeye_x':146.194810967299})
    job.addNewDmmPoint({'energy (KeV)':13.5002794635802, 'Wavelength (A)':0.918389877294582, 'dmm_z':470.1204, 'dmm_y1':0.0011, 'dmm_y2':17.95995, 'dmm_p1':-19.13429, 'dmm_p2':-19.14479, 'dmm_r2':0.036, 'd3d2':0.062290677616816, 'bsdiode':-0.000711363497588, 'xrayeye_y':146.992555541905, 'xrayeye_x':150.229526699054})
    job.addNewDmmPoint({'energy (KeV)':13.0005499590986, 'Wavelength (A)':0.953691962186778, 'dmm_z':452.6892, 'dmm_y1':0.0011, 'dmm_y2':17.9799, 'dmm_p1':-19.86989, 'dmm_p2':-19.85298, 'dmm_r2':0.2338, 'd3d2':0.063029507395931, 'bsdiode':-0.00080295536423, 'xrayeye_y':165.208611234825, 'xrayeye_x':153.920562752229})
    job.addNewDmmPoint({'energy (KeV)':12.4994320852199, 'Wavelength (A)':0.991926666385167, 'dmm_z':435.2568, 'dmm_y1':0.0011, 'dmm_y2':18.02, 'dmm_p1':-20.66661, 'dmm_p2':-20.61437, 'dmm_r2':0.4966, 'd3d2':0.062876856615122, 'bsdiode':-0.000708310435367, 'xrayeye_y':164.592529227585, 'xrayeye_x':148.375773788695})
    job.addNewDmmPoint({'energy (KeV)':12.0002959129722, 'Wavelength (A)':1.03318452227476, 'dmm_z':417.8003, 'dmm_y1':0.0011, 'dmm_y2':18.05, 'dmm_p1':-21.52634, 'dmm_p2':-21.43605, 'dmm_r2':0.7018, 'd3d2':0.061893785586714, 'bsdiode':-0.000879281919766, 'xrayeye_y':171.68262109833, 'xrayeye_x':150.989812708215})
    job.addNewDmmPoint({'energy (KeV)':11.5003972177638, 'Wavelength (A)':1.07809493578612, 'dmm_z':400.3902, 'dmm_y1':0.0011, 'dmm_y2':18.0999, 'dmm_p1':-22.4622, 'dmm_p2':-22.32858, 'dmm_r2':0.9328, 'd3d2':0.05771420720817, 'bsdiode':-0.000726628808695, 'xrayeye_y':140.273128127906, 'xrayeye_x':145.145467912662})
    job.addNewDmmPoint({'energy (KeV)':11.0001189602387, 'Wavelength (A)':1.12712599243844, 'dmm_z':382.9537, 'dmm_y1':0.0011, 'dmm_y2':18.15, 'dmm_p1':-23.48395, 'dmm_p2':-23.29996, 'dmm_r2':1.1288, 'd3d2':0.051489108366789, 'bsdiode':-0.001065518715271, 'xrayeye_y':123.973681655106, 'xrayeye_x':144.724867266624})
    job.addNewDmmPoint({'energy (KeV)':10.5004011092072, 'Wavelength (A)':1.18076632226254, 'dmm_z':365.51725, 'dmm_y1':0.0011, 'dmm_y2':18.20005, 'dmm_p1':-24.60178, 'dmm_p2':-24.30347, 'dmm_r2':1.2714, 'd3d2':0.046650078615153, 'bsdiode':-0.001312816755205, 'xrayeye_y':124.313144001905, 'xrayeye_x':151.617634260286})
    job.addNewDmmPoint({'energy (KeV)':9.99981160304098, 'Wavelength (A)':1.23987535887472, 'dmm_z':348.0799, 'dmm_y1':0.00105, 'dmm_y2':18.2491, 'dmm_p1':-25.83361, 'dmm_p2':-25.49501, 'dmm_r2':1.5932, 'd3d2':0.040791341647712, 'bsdiode':-0.000860963546437, 'xrayeye_y':123.000545399147, 'xrayeye_x':137.535755636807})
    job.addNewDmmPoint({'energy (KeV)':9.49971294699231, 'Wavelength (A)':1.30514680487535, 'dmm_z':330.6399, 'dmm_y1':0.00105, 'dmm_y2':18.2991, 'dmm_p1':-27.19391, 'dmm_p2':-26.79682, 'dmm_r2':1.7634, 'd3d2':0.033809094933521, 'bsdiode':-0.000714416559809, 'xrayeye_y':159.29207468305, 'xrayeye_x':145.405360762442})
    job.addNewDmmPoint({'energy (KeV)':9.00024742978845, 'Wavelength (A)':1.37757546075502, 'dmm_z':313.1981, 'dmm_y1':0.0011, 'dmm_y2':18.3791, 'dmm_p1':-28.70343, 'dmm_p2':-28.23404, 'dmm_r2':1.9472, 'd3d2':0.255421392480422, 'bsdiode':-0.000641143066496, 'xrayeye_y':116.402668872171, 'xrayeye_x':144.06020867463})
    '''
