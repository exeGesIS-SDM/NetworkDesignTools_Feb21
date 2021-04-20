from qgis.PyQt.QtWidgets import QMessageBox
import configparser as cp
import os.path
import uuid
import requests
import json
import csv

def initPrerequisites(iface):
    """ Fetch prerequisites from webservice or file or show error if not available """
    global prerequisites
    # Initialise so always available 
    prerequisites = {}
    
    # File implementation
    json_path = os.path.join(os.path.dirname(__file__), 'prerequisites.json') 
    
    try:
        with open(json_path) as json_file:
            prerequisites = json.load(json_file)
    except:
        QMessageBox.critical(iface.mainWindow(), 'Prerequisites not found or invalid', 'The prerequisites file ({}) could not be found or is not valid. Please check and try again.'.format(json_path))


def getLayerByName(iface, project, layerName, showMessage = True):
    try:
        layer = project.mapLayersByName(layerName)[0]
        return layer
    except:
        if showMessage:
            QMessageBox.critical(iface.mainWindow(), 'Layer not found', 'The {0} layer could not be found. Please ensure the NetworkDesignTool project is open.'.format(layerName))
        return None

def writeToCSV(iface, csvfilename, writeThis, isFirstRow = False):
    #try:
    #print(writeThis)
    if isFirstRow:
        attrib = 'w'
    else:
        attrib = 'a'
    with open(csvfilename,attrib, newline='') as csvfile:
        fieldnames = ['Item', 'Quantity']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        if isFirstRow:
            writer.writeheader()
        #for items in writeThis
        #    writer.writerow(items)
        writer.writerow(writeThis)
        #txwriter = csv.writer(csvfile, delimiter=',')
        #txwriter.writerow(writeThis)
    return True
    #except:
    #    return False