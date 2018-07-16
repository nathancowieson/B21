#!/dls_sw/prod/tools/RHEL6-x86_64/Python/2-7-3/prefix/bin/python
import logging
from PyQt4 import QtGui
from PyQt4 import QtCore
import sys
from time import sleep
sys.path.append('/dls_sw/prod/tools/RHEL6-x86_64/pyepics/3-2-0/prefix/lib/python2.7/site-packages')

from epics import PV, poll

class Window(QtGui.QWidget):
    """This class provides the GUI interface for the cell_changer

    This class only provides the GUI interface, there is no logic or
    interaction with the beamline. These functions are contained in
    a Worker class that will be run by the Window class as a QThread.
    """

    def __init__(self, parent = None):
        #CREATE A LOGGER
        self.logger = logging.getLogger('cellChanger')
        self.logger.setLevel(logging.DEBUG)
        formatter = logging.Formatter('%(asctime)s: %(levelname)s: %(module)s: %(message)s',"[%Y-%m-%d %H:%M:%S]")
        streamhandler = logging.StreamHandler()
        streamhandler.setFormatter(formatter)
        if len(self.logger.handlers) == 0:
            self.logger.addHandler(streamhandler)
            self.logger.info('cellChanger was started')

        QtGui.QWidget.__init__(self, parent)
        self.thread = Worker()

        self.button = QtGui.QPushButton('toggle', self)
        self.button.setCheckable(True)
        self.button.move(10, 10)
        self.button.clicked[bool].connect(self.onButtonPress)

        self.square = QtGui.QFrame(self)
        self.square.setGeometry(120, 10, 130, 30)
        self.setStatusColour(self.thread.returnStatus())
            

        self.status = QtGui.QLabel(self.thread.returnStatus(), self)
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
        self.hivac = QtGui.QFrame(self)
        self.hivac.setGeometry(212,70, 25,25)
        

        #LABELS AND INDICATORS FOR V33 STATE
        self.v33_label = QtGui.QLabel('V33 Status:', self)
        self.v33_label.move(20, 137)
        self.v33_open_label = QtGui.QLabel('Open', self)
        self.v33_open_label.move(145, 110)
        self.v33_closed_label = QtGui.QLabel('Closed', self)
        self.v33_closed_label.move(200, 110)

        self.clv33 = QtGui.QFrame(self)
        self.clv33.setGeometry(212,130,25,25)
        self.opv33 = QtGui.QFrame(self)
        self.opv33.setGeometry(152,130,25,25)
        self.setGeometry(400, 600, 260, 180)
        self.setWindowTitle('Cell Changer')

        #WARNING ABOUT GOING TO DATA MODE WHILE AT ATMOSPHERE
        self.manual_vent_label = QtGui.QLabel('MANUAL VENTING FIRST!', self)
        self.manual_vent_label.move(5,160)
        self.manual_vent_label.setStyleSheet('color: red')
        font = QtGui.QFont()
        font.setPointSize(10)
        font.setBold(True)
        font.setWeight(75)
        self.manual_vent_label.setFont(font)
        self.manual_vent_label.hide()


        self.show()
        

        

        self.connect(self.thread, QtCore.SIGNAL('Ioc'), self.onIocChange)
        self.connect(self.thread, QtCore.SIGNAL('Vac'), self.onVacChange)
        self.connect(self.thread, QtCore.SIGNAL('V33'), self.onV33Change)
        self.connect(self.thread, QtCore.SIGNAL('Status'), self.onStatusChange)
        self.connect(self.thread, QtCore.SIGNAL('Manual Vent'), self.onManualVent)
        self.thread.onVacChange()
        self.thread.onV33Change()

    def onManualVent(self, signal=True):
        self.logger.debug('GUI: ran onManualVent function')
        self.showManualVent()
        try:
            if self.timer:
                self.timer.stop()
                self.timer.deleteLater()
        except:
            pass
        self.timer = QtCore.QTimer()
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.hideManualVent)
        self.timer.start(5000)
        
    def hideManualVent(self):
        self.manual_vent_label.hide()
        self.logger.debug('GUI: hideManualVent function ran')

    def showManualVent(self):
        self.manual_vent_label.show()
        self.logger.debug('GUI: showManualVent function ran')

        #for index in range(1,4):
        #    self.manual_vent_label.show()
        #    sleep(1)
        #    self.manual_vent_label.hide()
        #    sleep(0.5)
        
    def onIocChange(self, signal):
        self.logger.debug('GUI:onIocChange: '+signal)

    def onVacChange(self, signal):
        self.logger.debug('GUI:onVacChange: '+signal)
        if signal == 'Low':
            self.lovac.setStyleSheet("QWidget { border: 2px solid black; background-color: %s }" %  QtGui.QColor(0, 0, 0).name())
            self.hivac.setStyleSheet("QWidget { border: 2px solid black; background-color: %s }" %  QtGui.QColor(255, 255, 255).name())
        elif signal == 'High':
            self.lovac.setStyleSheet("QWidget { border: 2px solid black; background-color: %s }" %  QtGui.QColor(255, 255, 255).name())
            self.hivac.setStyleSheet("QWidget { border: 2px solid black; background-color: %s }" %  QtGui.QColor(0, 0, 0).name())
        else:
            self.lovac.setStyleSheet("QWidget { border: 2px solid black; background-color: %s }" %  QtGui.QColor(255, 255, 255).name())
            self.hivac.setStyleSheet("QWidget { border: 2px solid black; background-color: %s }" %  QtGui.QColor(255, 255, 255).name())

    def onV33Change(self, signal):
        self.logger.debug('GUI:onV33Change: '+signal)
        if signal == 'Open':
            self.opv33.setStyleSheet("QWidget { border: 2px solid black; background-color: %s }" %  QtGui.QColor(0, 0, 0).name())
            self.clv33.setStyleSheet("QWidget { border: 2px solid black; background-color: %s }" %  QtGui.QColor(255, 255, 255).name())
        elif signal == 'Closed':
            self.opv33.setStyleSheet("QWidget { border: 2px solid black; background-color: %s }" %  QtGui.QColor(255, 255, 255).name())
            self.clv33.setStyleSheet("QWidget { border: 2px solid black; background-color: %s }" %  QtGui.QColor(0, 0, 0).name())
        else:
            self.opv33.setStyleSheet("QWidget { border: 2px solid black; background-color: %s }" %  QtGui.QColor(255, 255, 255).name())
            self.clv33.setStyleSheet("QWidget { border: 2px solid black; background-color: %s }" %  QtGui.QColor(255, 255, 255).name())

            
    def onStatusChange(self, signal):
        self.logger.debug('GUI:onStatusChange: '+signal)
        self.setStatus(signal)
        #self.show()


    def onButtonPress(self):
        self.logger.debug('Ran GUI:onButtonPress')
        self.thread.buttonPress()

    def setStatusColour(self, status='Unknown'):
        if status == 'Data Mode':
            self.square.setStyleSheet("QFrame { background-color: %s }" % QtGui.QColor(0, 255, 0).name())
        elif status == 'Vent Mode':
            self.square.setStyleSheet("QFrame { background-color: %s }" % QtGui.QColor(255, 0, 0).name())
        else:
            self.square.setStyleSheet("QFrame { background-color: %s }" % QtGui.QColor(255, 255, 255).name())

    def setStatusText(self, status='Unknown'):
        if status in ['Data Mode', 'Vent Mode']:
            self.status.setText(status)
        else:
            self.logger.error('Invalid status received by GUI:setStatusText')
            self.status.setText('Unknown')

    def setStatus(self, status='Unknown'):
        self.setStatusColour(status)
        self.setStatusText(status)
    

class Worker(QtCore.QThread):
    def __init__(self, parent=None):
        #CREATE A LOGGER
        self.logger = logging.getLogger('cellChanger')
        self.logger.info('worker joined cellChanger logger')
        
        QtCore.QThread.__init__(self, parent)

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
            self.logger.debug(key+': '+self.pvs[key].get(as_string=True))

        self.pvs['status_ioc'].add_callback(self.onIocChange)
        self.pvs['status_v33'].add_callback(self.onV33Change)
        self.pvs['sample_vac'].add_callback(self.onVacChange)

        self.status = 'Unknown'
        self.deduceStatus()

    def onIocChange(self, pvname=None, value=None, host=None, **kws):
        if value == 0:
            status = 'On'
        elif value == 1:
            status = 'Off'
        else:
            status = 'Unknown'
        self.emit(QtCore.SIGNAL('Ioc'), status)
        self.logger.debug('worker:onIocChange status: '+status)

    def onV33Change(self, pvname=None, value=None, host=None, **kws):
        if value == None:
            value = self.pvs['status_v33'].get()
        if value == 3:
            status = 'Closed'
        elif value == 1:
            status = 'Open'
        else:
            status = 'Changing'
        self.emit(QtCore.SIGNAL('V33'), status)
        self.logger.debug('worker:onV33Change status: '+status)

    def onVacChange(self, pvname=None, value=None, host=None, **kws):
        if value == None:
            value=self.pvs['sample_vac'].get()
        if value < 1E-1:
            status = 'Low'
        elif value > 7.5E2:
            status = 'High'
        else:
            status = 'Intermediate'
        self.emit(QtCore.SIGNAL('Vac'), status)
        self.logger.debug('worker:onVacChange status: '+status)

    def getVacStatus(self):
        status = self.pvs['sample_vac'].get()
        if status < 1E-1:
            return 'Low'
        elif status > 7.5E2:
            return 'High'
        else:
            return 'Intermediate'

    def getIocStatus(self):
        status = self.pvs['status_ioc'].get()
        if status == 0:
            return 'On'
        elif status == 1:
            return 'Off'
        else:
            return 'Unknown'

    def setIocStatus(self, status='Off'):
        if status == 'Off':
            self.pvs['stop_ioc'].put(1)
        elif status == 'On':
            self.pvs['start_ioc'].put(1)
        else:
            self.error('setIocStatus needs off or on as a command')

    def getV33Status(self):
        status = self.pvs['status_v33'].get()
        if status == 3:
            return 'Closed'
        elif status == 1:
            return 'Open'
        else:
            return 'Moving'

    def setV33Status(self, status='close'):
        if status == 'close':
            self.logger.info('Closing V33')
            self.pvs['control_v33'].put(1)
        elif status == 'open':
            self.logger.info('Opening V33')
            self.pvs['control_v33'].put(0)
        else:
            self.logger.error('setV33Status needs open or close as a command')

    def deduceStatus(self):
        if self.getVacStatus() == 'Low' and self.getIocStatus() == 'On':
            self.status = 'Data Mode'
        elif self.getV33Status() == 'Closed' and self.getIocStatus() == 'Off':
            self.status = 'Vent Mode'
        else:
            self.status = 'Unknown'

    def returnStatus(self):
        return self.status

    def buttonPress(self):
        if self.status == 'Vent Mode':
            if not self.getVacStatus() == 'Low':
                self.emit(QtCore.SIGNAL('Manual Vent'), 'True')
            else:
                self.status = 'Data Mode'
                self.logger.info('Worker: Changing to Data Mode')
                self.setIocStatus('On')
        else:
            self.status = 'Vent Mode'
            self.logger.info('Worker: Changing to Vent Mode')
            self.setIocStatus('Off')
            self.setV33Status('close')
        self.logger.info('Button press toggled status to: '+self.status)
        self.emit(QtCore.SIGNAL('Status'), self.status)

if __name__ == '__main__':
    app = QtGui.QApplication(sys.argv)
    window = Window()
    window.show()
    sys.exit(app.exec_())
