import os.path
import json
import csv
from qgis.PyQt.QtWidgets import QMessageBox
from qgis.core import QgsProject, QgsSnappingConfig

prerequisites = {}

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
        QMessageBox.critical(iface.mainWindow(), 'Prerequisites not found or invalid', \
            'The prerequisites file ({}) could not be found or is not valid. Please check and try again.'.format(json_path))


def getLayerByName(iface, project, layerName, showMessage = True):
    try:
        layer = project.mapLayersByName(layerName)[0]
        return layer
    except:
        if showMessage:
            QMessageBox.critical(iface.mainWindow(), 'Layer not found', 'The {0} layer could not be found. Please ensure the layer is open.'.format(layerName))
        return None

def set_snap_layers(layer_names, snap_types, snap_tolerance, snap_units):
    snap_config = QgsSnappingConfig(QgsProject.instance())
    snap_config.setEnabled(True)
    snap_config.setMode(QgsSnappingConfig.SnappingMode.AdvancedConfiguration)

    disabled_layer_settings = QgsSnappingConfig.IndividualLayerSettings(False, QgsSnappingConfig.SnappingType.Vertex, snap_tolerance, snap_units)
    if len(snap_types) == 0:
        return False

    if len(snap_types) == 1 or len(snap_types) < len(layer_names):
        per_layer_snap = False
        snap_layer_settings = QgsSnappingConfig.IndividualLayerSettings(True, snap_types[0], snap_tolerance, snap_units)
    else:
        per_layer_snap = True

    snap_layer_found = False
    all_layer_settings = snap_config.individualLayerSettings()
    for layer in all_layer_settings.keys():
        if layer.name() in layer_names:
            # Enable specified snap settings
            if per_layer_snap:
                index = layer_names.index(layer.name())
                snap_layer_settings = QgsSnappingConfig.IndividualLayerSettings(True, snap_types[index], snap_tolerance, snap_units)
            snap_config.setIndividualLayerSettings(layer, snap_layer_settings)
            snap_layer_found = True
        else:
            if all_layer_settings[layer].enabled():
                snap_config.setIndividualLayerSettings(layer, disabled_layer_settings)

    if snap_layer_found:
        QgsProject.instance().setSnappingConfig(snap_config)

    return snap_layer_found

def writeToCSV(iface, csvfilename, headers, data):
    try:
        with open(csvfilename, 'w', newline='') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=headers)
            writer.writeheader()
            for row in data:
                writer.writerow(row)
        return True
    except:
        QMessageBox.critical(iface.mainWindow(), 'File in use', \
                             'The {0} file could not be opened for write access. Please close the file and try again.'.format(csvfilename))
        return False
