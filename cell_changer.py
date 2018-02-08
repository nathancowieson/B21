#!/dls_sw/prod/tools/RHEL6-x86_64/Python/2-7-3/prefix/bin/python
import logging
from PyQt4 import QtGui
from PyQt4 import QtCore
import sys

sys.path.append('/dls_sw/prod/tools/RHEL6-x86_64/pyepics/3-2-0/prefix/lib/python2.7/site-packages')

from epics import PV


class cellChanger(QtGui.QWidget):
    """Prepare for venting sample cell

    This class checks the status of the python IOC that controls the
    valves and also the status of V33. It provides a small GUI that
    can toggle between the IOC being off and the valve closed in which
    state the sample area can be vented with the needle valve and the
    cell changed.
    """

    def __init__(self):
        #CREATE A LOGGER
        self.logger = logging.getLogger('cellChanger')
        self.logger.setLevel(logging.INFO)
        formatter = logging.Formatter('%(asctime)s: %(levelname)s: %(module)s: %(message)s',"[%Y-%m-%d %H:%M:%S]")
        streamhandler = logging.StreamHandler()
        streamhandler.setFormatter(formatter)
        if len(self.logger.handlers) == 0:
            self.logger.addHandler(streamhandler)
            self.logger.info('cellChanger was started')


        self.status = 'Unknown'
        self.pvs = {
            'start_ioc': PV('BL21B-PY-IOC-02:START'),
            'stop_ioc': PV('BL21B-PY-IOC-02:STOP'),
            'status_ioc': PV('BL21B-PY-IOC-02:STATUS'),
            'status_v33': PV('BL21B-VA-VALVE-33:STA'),
            'control_v33': PV('BL21B-VA-VALVE-33:CON'),
            'sample_vac': PV('BL21B-VA-SPACE-10:P'),
            'camera_vac': PV('BL21B-VA-SPACE-11:P')
            }
        for key in self.pvs.keys():
            self.logger.info(key+': '+self.pvs[key].get(as_string=True))
            if key in ['status_ioc', 'status_v33']:
                self.pvs[key].add_callback(self.onValueChange)
            else:
                pass

        self.col = QtGui.QColor(255, 255, 255)
        super(cellChanger, self).__init__()

        self.initUI()
        self.onValueChange()
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.update)
        self.timer.start(2000)

        self.timer.timeout.connect(self.onVacChange)

    def setStatusColour(self, colour='green'):
        if colour == 'green':
            self.square.setStyleSheet("QFrame { background-color: %s }" % QtGui.QColor(0, 255, 0).name())
        elif colour == 'red':
            self.square.setStyleSheet("QFrame { background-color: %s }" % QtGui.QColor(255, 0, 0).name())
        elif colour == 'yellow':
            self.square.setStyleSheet("QFrame { background-color: %s }" % QtGui.QColor(255, 255, 0).name())
        elif colour == 'white':
            self.square.setStyleSheet("QFrame { background-color: %s }" % QtGui.QColor(255, 255, 255).name())
        else:
            self.logger.error(str(colour)+' is not a colour we can set')

    def checkVacuum(self):
        if self.pvs['sample_vac'].get() < 1.0E-1:
            return 'low'
        elif self.pvs['sample_vac'].get() > 9.9E2:
            return 'high'
        else:
            return 'intermediate'

    def onValueChange(self, pvname=None, value=None, host=None, **kws):
        if self.getIocStatus() == 'Off' and self.getV33Status() == 'Closed':
            status_text = 'vent it!'
            self.logger.info('status: '+status_text)
            self.setStatusColour('red')
            self.status.setText(status_text)
        elif self.getIocStatus() == 'On' and self.getV33Status() == 'Open':
            status_text = 'IOC on!'
            print status_text
            self.setStatusColour('green')
            self.status.setText(status_text)
        else:
            status_text = 'changing...'
            print status_text
            self.setStatusColour('white')
            self.status.setText(status_text)

        if self.getV33Status() == 'Closed':
            self.logger.info('Found V33 Closed')
            self.clv33.setStyleSheet("QWidget { border: 2px solid black; background-color: %s }" %  QtGui.QColor(0, 0, 0).name())
            self.opv33.setStyleSheet("QWidget { border: 2px solid black; background-color: %s }" %  QtGui.QColor(255, 255, 255).name())
        elif self.getV33Status() == 'Open':
            self.logger.info('Found V33 Open')
            self.opv33.setStyleSheet("QWidget { border: 2px solid black; background-color: %s }" %  QtGui.QColor(0, 0, 0).name())
            self.clv33.setStyleSheet("QWidget { border: 2px solid black; background-color: %s }" %  QtGui.QColor(255, 255, 255).name())
        else:
            self.logger.error('Found V33 in an intermediate state')
            self.opv33.setStyleSheet("QWidget { border: 2px solid black; background-color: %s }" %  QtGui.QColor(255, 255, 255).name())
            self.clv33.setStyleSheet("QWidget { border: 2px solid black; background-color: %s }" %  QtGui.QColor(255, 255, 255).name())

    def onVacChange(self):
        value = self.pvs['sample_vac'].get()
        if value < 1E-1:
            self.lovac.setStyleSheet("QWidget { border: 2px solid black; background-color: %s }" %  QtGui.QColor(0, 0, 0).name())
            self.hivac.setStyleSheet("QWidget { border: 2px solid black; background-color: %s }" %  QtGui.QColor(255, 255, 255).name())
        elif value > 9.9E2:
            self.hivac.setStyleSheet("QWidget { border: 2px solid black; background-color: %s }" %  QtGui.QColor(0, 0, 0).name())
            self.lovac.setStyleSheet("QWidget { border: 2px solid black; background-color: %s }" %  QtGui.QColor(255, 255, 255).name())
        else:
            self.lovac.setStyleSheet("QWidget { border: 2px solid black; background-color: %s }" %  QtGui.QColor(255, 255, 255).name())
            self.hivac.setStyleSheet("QWidget { border: 2px solid black; background-color: %s }" %  QtGui.QColor(255, 255, 255).name())
            
    def getIocStatus(self):
        try:
            if self.pvs['status_ioc'].get() == 1:
                return 'Off'
            else:
                return 'On'
        except:
            return False

    def setIocStatus(self, status='Off'):
        if status == 'off':
            self.pvs['stop_ioc'].put(1)
        elif status == 'on':
            self.pvs['start_ioc'].put(1)
        else:
            self.error('setIocStatus needs off or on as a command')

    def getV33Status(self):
        try:
            if self.pvs['status_v33'].get() == 3:
                return 'Closed'
            else:
                return 'Open'
        except:
            return False

    def setV33Status(self, status='close'):
        if status == 'close':
            self.logger.info('Closing V33')
            self.pvs['control_v33'].put(1)
        elif status == 'open':
            self.logger.info('Opening V33')
            self.pvs['control_v33'].put(0)
        else:
            self.logger.error('setV33Status needs open or close as a command')
            
    def getStatus(self):
        if self.getV33Status() == 'Closed' and self.getIocStatus() == 'Off':
            return 'vent mode'
        elif self.getV33Status() == 'Open' and self.getIocStatus() == 'On':
            return 'data mode'
        else:
            return 'changing'
    
    def initUI(self):
        button = QtGui.QPushButton('toggle', self)
        button.setCheckable(True)
        button.move(10, 10)

        button.clicked[bool].connect(self.buttonPress)

        self.square = QtGui.QFrame(self)
        self.square.setGeometry(120, 10, 130, 30)
        self.square.setStyleSheet("QWidget { border: 2px solid black; background-color: %s }" %  QtGui.QColor(255, 255, 255).name())
            

        self.status = QtGui.QLabel('unknown', self)
        self.status.move(125,15)

        #LABELS AND INDICATORS FOR VACUUM STATE
        self.vac_label = QtGui.QLabel('Sample vacuum:', self)
        self.vac_label.move(20, 76)
        self.vac_low_label = QtGui.QLabel('<1E-1', self)
        self.vac_low_label.move(140, 50)
        self.vac_high_label = QtGui.QLabel('~1E3', self)
        self.vac_high_label.move(200, 50)

        self.lovac = QtGui.QFrame(self)
        self.lovac.setGeometry(152,70,25,25)
        self.lovac.setStyleSheet("QWidget { border: 2px solid black; background-color: %s }" %  QtGui.QColor(255, 255, 255).name())
        self.hivac = QtGui.QFrame(self)
        self.hivac.setGeometry(212,70, 25,25)
        self.hivac.setStyleSheet("QWidget { border: 2px solid black; background-color: %s }" %  QtGui.QColor(255, 255, 255).name())

        #LABELS AND INDICATORS FOR V33 STATE
        self.v33_label = QtGui.QLabel('V33 Status:', self)
        self.v33_label.move(20, 137)
        self.v33_open_label = QtGui.QLabel('Open', self)
        self.v33_open_label.move(145, 110)
        self.v33_closed_label = QtGui.QLabel('Closed', self)
        self.v33_closed_label.move(200, 110)

        self.clv33 = QtGui.QFrame(self)
        self.clv33.setGeometry(212,130,25,25)
        self.clv33.setStyleSheet("QWidget { border: 2px solid black; background-color: %s }" %  QtGui.QColor(255, 255, 255).name())
        self.opv33 = QtGui.QFrame(self)
        self.opv33.setGeometry(152,130,25,25)
        self.opv33.setStyleSheet("QWidget { border: 2px solid black; background-color: %s }" %  QtGui.QColor(255, 255, 255).name())

        self.setGeometry(400, 600, 260, 180)
        self.setWindowTitle('Cell Changer')
        self.show()
        
        
    def buttonPress(self, pressed):
        #source = self.sender()
        
        if self.getStatus() == 'vent mode':
            self.logger.info('changing to data mode')
            self.setIocStatus('on')
        elif self.getStatus() == 'data mode':
            self.logger.info('changing to vent mode')
            self.setIocStatus('off')
            self.setV33Status('close')
        else:
            self.logger.error('neither in vent or data mode, changing to vent mode')
            self.setIocStatus('off')
            self.setV33Status('close')
            
        
def main():
    
    app = QtGui.QApplication(sys.argv)
    ex = cellChanger()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()    

