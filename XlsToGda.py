#!/dls/science/groups/b21/PYTHON/bin/python
'''
Created on Oct 16, 2017

@author: nathan
'''

import logging
from optparse import OptionParser
from optparse import OptionGroup
import os
import re
import sys
import xlrd
import xml.etree.ElementTree as ET
from xml.dom import minidom

class xlsReadWrite():
    """Parse a main-in xlsx input file to a measurement array and output again to an xlsx file
    
    The xlsReadWrite class contains methods to parse the input xlsx file that
    users provide for mail in at B21 to an array of measurements that could be
    used as input for the xmlReadWrite class. The class can also output an array 
    of measurements back to an xlsx file
    """
    
    '''
    Constructor
    '''
    def __init__(self):
        ###start a log file
        self.logger = logging.getLogger('xlsToGda')
        self.logger.setLevel(logging.DEBUG)
        formatter = logging.Formatter('%(asctime)s: %(levelname)s: %(module)s: %(message)s',"[%Y-%m-%d %H:%M:%S]")
        streamhandler = logging.StreamHandler()
        streamhandler.setFormatter(formatter)
        self.logger.addHandler(streamhandler)
        self.logger.info('Starting a new xlsToGda job')        

        #Create some parameters
        self.measurements = []
        self.input_file = None
        self.output_file = None
        self.output_type = None
        self.positions = [str(x)+str(y) for x in [2,3] for y in ['A','B','C','D']]

    def appendMeasurements(self, measurement_array):
        if type(measurement_array) == type([]):
            for measurement in measurement_array:
                if type(measurement) == type(()):
                    if measurement[0] == 'measurement':
                        self.measurements.append(measurement)
                    else:
                        self.logger.error('Measurements tuples in the measurement array should have "measurement" as the first term')
                self.logger.error('Measurements in the measurement array should be tuples')
        else:
            self.logger.error('appendMeasurement function expects an array as an argument')
                    
    def returnMeasurements(self):
        return self.measurements
    
    def returnNextPosition(self):
        try:
            curr_posn = dict(dict(self.measurements[-1][1])['location'])['plate']+dict(dict(self.measurements[-1][1])['location'])['row']
            if curr_posn in self.positions:
                index = self.positions.index(curr_posn)
                try:
                    return self.positions[index+1]
                except:
                    self.logger.error('Robot seems to be full!')
                    return '2A'
            else:
                self.logger.error('Failed to find next position')
                return '2A'
        except:
            return '2A'
                    

    
    def setOutputType(self, output_type):
        if output_type in ['hplc', 'biosaxs']:
            self.output_type = output_type
            self.logger.info('Set output type to: '+output_type)
        else:
            self.logger.error('Output type must be either biosaxs or hplc, not: '+str(output_type))

            
    def inputFile(self, filename):
        try:
            filename = os.path.abspath(filename)
            if not os.path.isfile(filename):
                raise IOError(str(filename)+' does not exist')
            elif not filename[-4:] == 'xlsx' or filename[-3:] == 'xls':
                raise TypeError(str(filename)+' is not an excel file')
            else:
                self.logger.info('Set '+str(filename)+' as the input file')
                self.input_file = filename
                return True
        except Exception as ex:
            template = "An exception of type {0} occured. {1!r}"
            message = template.format(type(ex).__name__, ex.args)
            self.logger.error(message)
            return False


    def outputFile(self, filename):
        try:
            filename = os.path.abspath(filename)
            if not os.path.isdir(os.path.split(filename)[0]):
                raise IOError('Output directory does not exist')
            if not os.access(os.path.split(filename)[0], os.W_OK):
                raise IOError('Cannot write to output directory')
            if filename[-4:] == 'xlsx' or filename[-3:] == 'xls':
                self.output_file = filename
                self.logger.info('Set output excel file to: '+self.output_file)
                return True
            else:
                raise TypeError('Output file should be of type hplc or biosaxs')
        except Exception as ex:
            template = "An exception of type {0} occured. {1!r}"
            message = template.format(type(ex).__name__, ex.args)
            self.logger.error(message)
            return False
                                 
    def parseXlsx(self, xls_file):
        if self.inputFile(xls_file):
            if self.output_type == 'hplc':
                self.logger.info('Parsing excel file for HPLC info')
                output = self.parseHplcXlsx()
            elif self.output_type == 'biosaxs':
                self.logger.info('Parsing excel file for biosaxs info')
                output = self.parseBiosaxsXlsx()
            else:
                self.logger.error('Output type was not set before parsing excel sheet')
                output = None
            return output
        else:
            self.logger.error('Did not parse, problem with input file')
    
    def returnCurrentStaffVisit(self):
        return 'cm16775-4'
    
    def parseHplcXlsx(self):
        output_list = []
        
        book = xlrd.open_workbook(self.input_file)
        sheet = book.sheet_by_index(0)
        visit_pattern = re.compile('[sSmMcCiInN][mMwWxXnNtT][0-9]{5}-[0-9]{1,2}')
        visit_cell = sheet.cell(1, 0)
        search = re.search(visit_pattern, visit_cell.value)
        if search:
            self.logger.info('Found valid visit ID in spreadsheet')
            visit = visit_cell.value[search.start():search.end()].lower()
        else:
            self.logger.info('Did not find valid visit in spreadsheet, using staff visit')
            visit = self.returnCurrentStaffVisit()
        #for row in sheet.rows 

    def parseBiosaxsXlsx(self):
        book = xlrd.open_workbook(self.input_file)
        sheet = book.sheet_by_index(0)
        #VISIT
        visit_pattern = re.compile('[sSmMcCiInN][mMwWxXnNtT][0-9]{5}-[0-9]{1,2}')
        visit_cell = sheet.cell(1, 0)
        search = re.search(visit_pattern, visit_cell.value)
        if search:
            self.logger.info('Found valid visit ID in spreadsheet')
            visit = visit_cell.value[search.start():search.end()].lower()
        else:
            self.logger.info('Did not find valid visit in spreadsheet, using staff visit')
            visit = self.returnCurrentStaffVisit()
        holder_id = sheet.row(23)[0].value
        next_posn = self.returnNextPosition()
        self.logger.info('Insert samples from holder: '+holder_id+' into plate: '+next_posn[0]+' and position: '+next_posn[1]+', wells 1-8 and buffer in 9.')
        well = 1
        for row_index in range(23,32):
            measurement = []
            sampleName = sheet.cell(row_index,2).value
            if sampleName:
                #location
                measurement.append(('location', [('plate', next_posn[0]),('row', next_posn[1]),('column',str(well))]))
                #sampleName
                measurement.append( ('sampleName', sampleName) )
                #concentration
                try:
                    concentration = float(''.join([x for x in sheet.cell(row_index,5).value if x.isdigit() or x == '.']))
                except:
                    self.logger.info('Failed to get concentration for '+sampleName+': will use 0.0')
                    concentration = 0.0
                measurement.append( ('concentration', str(concentration)) )
                #viscosity
                measurement.append( ('viscosity', 'medium') )
                #molecularWeight
                try:
                    molecularWeight = float(''.join([x for x in sheet.cell(row_index,7).value if x.isdigit() or x == '.']))
                except:
                    self.logger.info('Failed to get molecular weight for '+sampleName+': will use 0.0')
                    molecularWeight = 0.0
                measurement.append( ('molecularWeight', str(molecularWeight)) )
                #buffer
                if re.search('true', str(sheet.cell(row_index,3).value).lower()):
                    measurement.append( ('buffer', 'true') )
                    measurement.append( ('buffers', 'None') )
                else:
                    measurement.append( ('buffer', 'false') )
                    buffer_well = int(''.join([x for x in str(sheet.cell(row_index,3).value) if x.isdigit() or x == '.']))
                    if not buffer_well in range(1,10):
                        buffer_well = 9
                        self.logger.error('Failed to get buffer position for '+sampleName+' will use 9')
                    measurement.append( ('buffers', next_posn+str(buffer_well)) )
                #yellowSample
                measurement.append( ('yellowSample', 'true') )
                #timePerFrame
                measurement.append( ('timePerFrame', '0.5') )
                #frames
                measurement.append( ('frames', '30') )
                #exposureTemperature
                try:
                    temp = float(''.join([x for x in sheet.cell(row_index,9).value if x.isdigit() or x == '.']))
                    if not 4 <= temp <= 60:
                        self.logger.error('Exposure temperature was out of range will use 15')
                        temp = 15
                except:
                    self.logger.info('Unable to get exposure temperature, will use 15')
                    temp = 15
                measurement.append( ('exposureTemperature', str(temp)) )
                #key
                measurement.append( ('key', 'move') )
                #mode
                measurement.append( ('mode', 'BS') )
                #visit
                measurement.append( ('visit', visit) )
                #username
                measurement.append( ('username', 'b21user') )
                #add the measurement to the main array
                self.measurements.append( ('measurement', measurement) )
            else:
                self.logger.info('No sample in position: '+str(well))
            well += 1

                

                    
                    
        
    def writeHplcXml(self):
        root = ET.Element('HplcSessionBean')
        measurement = ET.SubElement(root, 'measurement')




class xmlReadWrite():
    """Read and write xml files for biosaxs or hplc experiments
    
    The xmlReadWrite class allows you to parse a hplc or biosaxs xml file
    such as are used at the B21 beamline at Diamond as hold the list of 
    measurements as an array of dictionaries where they can be modified
    before writing them out to a new xml file.
    """
    
    '''
    Constructor
    '''
    def __init__(self):
        ###start a log file
        self.logger = logging.getLogger('xmlReadWrite')
        self.logger.setLevel(logging.DEBUG)
        formatter = logging.Formatter('%(asctime)s: %(levelname)s: %(module)s: %(message)s',"[%Y-%m-%d %H:%M:%S]")
        streamhandler = logging.StreamHandler()
        streamhandler.setFormatter(formatter)
        self.logger.addHandler(streamhandler)
        self.logger.info('Starting a new xmlReadWrite instance')        

        #Create some parameters
        self.measurements = []
        self.output_type = None
        self.xml_file = None

    def appendMeasurements(self, measurement_array):
        if type(measurement_array) == type([]):
            for measurement in measurement_array:
                if type(measurement) == type(()):
                    if measurement[0] == 'measurement':
                        self.measurements.append(measurement)
                    else:
                        self.logger.error('Measurements tuples in the measurement array should have "measurement" as the first term')
                self.logger.error('Measurements in the measurement array should be tuples')
        else:
            self.logger.error('appendMeasurement function expects an array as an argument')
                    
    def returnMeasurements(self):
        return self.measurements

    def setOutputType(self, output_type):
        if output_type in ['hplc', 'biosaxs']:
            self.output_type = output_type
            self.logger.info('Set output type to: '+output_type)
        else:
            self.logger.error('Output type must be either biosaxs or hplc, not: '+str(output_type))
        
    def returnType(self):
        return self.output_type
    
    def inputFile(self, filename):
        try:
            filename = os.path.abspath(filename)
            if not os.path.isdir(os.path.split(filename)[0]):
                raise IOError('Output directory does not exist')
            if not os.access(os.path.split(filename)[0], os.W_OK):
                raise IOError('Cannot write to output directory')
            if filename[-7:] == 'biosaxs':
                self.output_type = 'biosaxs'
                self.xml_file = filename
                self.logger.info('Set output type to biosaxs')
                return True
            elif filename[-4:] == 'hplc':
                self.output_type = 'hplc'
                self.xml_file = filename
                self.logger.info('Set output file to: '+filename)
                self.logger.info('Set output type to hplc')
                return True
            else:
                raise TypeError('Output file should be of type hplc or biosaxs')
        except Exception as ex:
            template = "An exception of type {0} occured. {1!r}"
            message = template.format(type(ex).__name__, ex.args)
            self.logger.error(message)
            return False
        
    def parseFromXml(self, filename):
        output_array = []
        if self.inputFile(filename):
            try:
                root = ET.parse(filename).getroot()
            except:
                if self.output_type == 'hplc':
                    root = ET.Element('HplcSessionBean')
                else:
                    root = ET.Element('BSSCSessionBean')
            for measurement in root.getchildren():
                measurement_array = []
                for field in measurement.getchildren():
                    if field.tag == 'location':
                        location_array = []
                        for subfield in field.getchildren():
                            location_array.append( (str(subfield.tag),str(subfield.text)) )
                        measurement_array.append( (str(field.tag),location_array) )
                    else:
                        if field.text == None:
                            measurement_array.append( (str(field.tag),'') )
                        else:
                            measurement_array.append( (str(field.tag),str(field.text)) )
                output_array.append( ('measurement', measurement_array) )
            self.measurements = output_array
            return True
        else:
            return False
            
    def parseToXml(self, measurement_array):
        if self.output_type == 'hplc':
            root = ET.Element('HplcSessionBean')
        else:
            root = ET.Element('BSSCSessionBean')
        for sample in measurement_array:
            measurement = ET.SubElement(root, sample[0])
            for attribute in sample[1]:
                submeasurement = ET.SubElement(measurement, attribute[0])
                if attribute[0] == 'location' and not self.output_type == 'hplc':
                    for position_attribute in attribute[1]:
                        subsubmeasurement = ET.SubElement(submeasurement, position_attribute[0])
                        subsubmeasurement.text = position_attribute[1]
                else:
                    submeasurement.text = attribute[1]
        return minidom.parseString(ET.tostring(root)).toprettyxml(indent="    ", encoding="UTF-8")

                    



    
if __name__ == '__main__':
    
    if len(sys.argv) < 2:
        sys.argv.append('-h')
        
    '''
    parse command line options
    '''
    
    parser = OptionParser()
    required = OptionGroup(parser, "Required Arguments")
    required.add_option("-e", "--excel", action="store", type="string", dest="excel_file", help="The excel file you want to parse")
    required.add_option("-x", "--xml", action="store", type="string", dest="xml_file", help="The xml file you want to use")
    
    optional = OptionGroup(parser, "Optional Arguments")
    optional.add_option("-d", "--delete", action="store_true", dest="delete", default=False, help="Overwrite the output file instead of appending (default is to append).")

    parser.add_option_group(required)
    parser.add_option_group(optional)
    (options, args) = parser.parse_args()
    
    '''
    fail if you didn't choose a valid input file
    '''
    if options.excel_file:
        if not os.path.isfile(options.excel_file):
            sys.exit('Specified input file: '+str(options.excel_file)+' does not exist')
    else:
        sys.exit('Useage: XlsToGda.py -e input_file.xlsx -x xml_file.biosaxs')

    if not options.xml_file:
        sys.exit('Useage: XlsToGda.py -e input_file.xlsx -x xml_file.biosaxs')
        
        

    #job = xlsToGda()
    #job.addOutput(options.out_file)
    #if job.addInput(options.xls_file):
    #    print job.parseXlsx()
    myxml = xmlReadWrite()
    if myxml.parseFromXml(options.xml_file):
        myxls = xlsReadWrite()
        myxls.setOutputType(myxml.returnType())
        myxls.appendMeasurements(myxml.returnMeasurements())
        myxls.parseXlsx(options.excel_file)
        open(options.xml_file, 'w').write(myxml.parseToXml(myxls.measurements))
    
