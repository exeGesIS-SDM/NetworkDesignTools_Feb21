from qgis.core import QgsProject, QgsProcessingFeatureSourceDefinition, QgsFeatureRequest, QgsVectorLayerUtils, NULL
from qgis.PyQt.QtWidgets import QMessageBox, QDialog
import processing
from network_design_tools import common

def createNodeCable(iface, startPoint, startLayerName, startFid, endPoint, endLayerName, endFid):
    layers = common.prerequisites['layers']
    ductLyr = common.getLayerByName(iface, QgsProject.instance(), layers['Duct']['name'])
    if ductLyr is None: return

    btDuctLyr = common.getLayerByName(iface, QgsProject.instance(), layers['BTDuct']['name'])
    if btDuctLyr is None: return

    try:
        result = processing.run("native:mergevectorlayers", { 'CRS' : ductLyr.crs(), \
                            'LAYERS' : [btDuctLyr, ductLyr], 'OUTPUT' : 'TEMPORARY_OUTPUT' })
        mergedDuctLyr = result['OUTPUT']
    except Exception as e:
        print(type(e), e)
        QMessageBox.critical(iface.mainWindow(),"Merge Failure", "Failed to merge the duct layers.")
    
    cableLyr = common.getLayerByName(iface, QgsProject.instance(), layers['Cable']['name'])
    if cableLyr is None: return

    startLyr = common.getLayerByName(iface, QgsProject.instance(), layers[startLayerName]['name'])
    if startLyr is None: return
    for feat in startLyr.getFeatures(QgsFeatureRequest(startFid)):
        startPt = feat

    endLyr = common.getLayerByName(iface, QgsProject.instance(), layers[endLayerName]['name'])
    if endLyr is None: return
    for feat in endLyr.getFeatures(QgsFeatureRequest(endFid)):
        endPt = feat

    # Get fields for the relevant layer
    for layer in layers:
        if layer == startLayerName:
            startFields = layers[layer]['fields']
        if layer == endLayerName:
            endFields = layers[layer]['fields']

    startID = startPt[startFields['id']]    
    endID = endPt[endFields['id']]
    cableName = '{}/{}'.format(startID, endID)

    cableFields = layers['Cable']['fields']

    cableLyr.startEditing() 
    try:
        # Select BT Ducts/110mm client ducts and route via duct
        expr = '"{}" = \'DUCT\' OR "{}" IS NOT NULL'.format(layers['BTDuct']['fields']['plantItem'], layers['Duct']['fields']['110mm'])
        mergedDuctLyr.selectByExpression(expr)
        QgsProject.instance().addMapLayer(mergedDuctLyr)
        selDuctLyr = QgsProcessingFeatureSourceDefinition(mergedDuctLyr.source(), selectedFeaturesOnly = True)

        start = '{}, {} [{}]'.format(startPoint.x(), startPoint.y(), QgsProject.instance().crs().authid())
        end = '{}, {} [{}]'.format(endPoint.x(), endPoint.y(), QgsProject.instance().crs().authid())
        result = processing.run("native:shortestpathpointtopoint", { 'DEFAULT_DIRECTION' : 2, 'DEFAULT_SPEED' : 50, 'DIRECTION_FIELD' : '', \
                        'START_POINT' : start, 'END_POINT' : end, 'INPUT' : selDuctLyr, 'OUTPUT' : 'TEMPORARY_OUTPUT', \
                        'SPEED_FIELD' : '', 'STRATEGY' : 0, 'TOLERANCE' : 0.2, 'VALUE_BACKWARD' : '', 'VALUE_BOTH' : '', 'VALUE_FORWARD' : '' })

        for c in result['OUTPUT'].getFeatures():
            feat = QgsVectorLayerUtils.createFeature(cableLyr)
            feat.setGeometry(c.geometry())
            feat.setAttribute(cableFields['feed'], 1) #U/G
            feat.setAttribute(cableFields['name'], cableName)
            cableLyr.addFeature(feat)
            result = iface.openFeatureForm(cableLyr, feat, False, showModal = True)

        if result:
            cableLyr.commitChanges()
    except Exception as e:
        print(e)
        QMessageBox.warning(iface.mainWindow(), 'Cable not created', 'Cable from {}: {} to {}: {} could not be calculated'.format(startLayerName, startID, endLayerName, endID))
    finally:
        cableLyr.rollBack()
        QgsProject.instance().removeMapLayer(mergedDuctLyr)
        del mergedDuctLyr
        del cableLyr