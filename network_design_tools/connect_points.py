from qgis.core import QgsProject, QgsFeatureRequest, QgsVectorLayerUtils, QgsGeometry
from qgis.PyQt.QtWidgets import QMessageBox
import processing
from network_design_tools import common

def createNodeCable(iface, routingType, startPoint, startLayerName, startFid, endPoint, endLayerName, endFid):
    layers = common.prerequisites['layers']
    ductLyr = common.getLayerByName(iface, QgsProject.instance(), layers['Duct']['name'])
    if ductLyr is None:
        return

    btDuctLyr = common.getLayerByName(iface, QgsProject.instance(), layers['BTDuct']['name'])
    if btDuctLyr is None:
        return

    try:
        result = processing.run("native:mergevectorlayers", { 'CRS' : ductLyr.crs(), \
                            'LAYERS' : [btDuctLyr, ductLyr], 'OUTPUT' : 'TEMPORARY_OUTPUT' })
        mergedDuctLyr = result['OUTPUT']
    except Exception as e:
        print(type(e), e)
        QMessageBox.critical(iface.mainWindow(),"Merge Failure", "Failed to merge the duct layers.")

    cableLyr = common.getLayerByName(iface, QgsProject.instance(), layers['Cable']['name'])
    if cableLyr is None:
        return

    startLyr = common.getLayerByName(iface, QgsProject.instance(), layers[startLayerName]['name'])
    if startLyr is None:
        return
    for feat in startLyr.getFeatures(QgsFeatureRequest(startFid)):
        startPt = feat

    endLyr = common.getLayerByName(iface, QgsProject.instance(), layers[endLayerName]['name'])
    if endLyr is None:
        return
    for feat in endLyr.getFeatures(QgsFeatureRequest(endFid)):
        endPt = feat

    # Get fields for the relevant layer
    for layer in layers:
        if layer == startLayerName:
            startFields = layers[layer]['fields']
        if layer == endLayerName:
            endFields = layers[layer]['fields']

    startId = startPt[startFields['id']]
    endIdSplit = endPt[endFields['id']].split('-')
    endId = []
    for word in endIdSplit:
        if word not in startId:
            endId.append(word)

    cableName = '{}/{}'.format(startId, '-'.join(endId))

    cableFields = layers['Cable']['fields']

    cableLyr.startEditing()
    try:
        if routingType == 'UG':
            QgsProject.instance().addMapLayer(mergedDuctLyr)

            start = '{}, {} [{}]'.format(startPoint.x(), startPoint.y(), QgsProject.instance().crs().authid())
            end = '{}, {} [{}]'.format(endPoint.x(), endPoint.y(), QgsProject.instance().crs().authid())
            print('start: ', start, ' end: ', end)
            result = processing.run("native:shortestpathpointtopoint", { 'DEFAULT_DIRECTION' : 2, 'DEFAULT_SPEED' : 50, 'DIRECTION_FIELD' : None, \
                            'START_POINT' : start, 'END_POINT' : end, 'INPUT' : mergedDuctLyr, 'OUTPUT' : 'TEMPORARY_OUTPUT', \
                            'SPEED_FIELD' : None, 'STRATEGY' : 0, 'TOLERANCE' : 0.1, 'VALUE_BACKWARD' : '', 'VALUE_BOTH' : '', 'VALUE_FORWARD' : '' })

            for c in result['OUTPUT'].getFeatures():
                feat = QgsVectorLayerUtils.createFeature(cableLyr)
                feat.setGeometry(c.geometry())
                feat.setAttribute(cableFields['feed'], 1) # U/G
                feat.setAttribute(cableFields['use'], 2) # Distribution
                feat.setAttribute(cableFields['type'], 4) # 48F
                feat.setAttribute(cableFields['name'], cableName)
                cableLyr.addFeature(feat)
        else:
            feat = QgsVectorLayerUtils.createFeature(cableLyr)
            c = QgsGeometry.fromPolylineXY([startPoint, endPoint])
            feat.setGeometry(c)
            feat.setAttribute(cableFields['feed'], 2) # Aerial
            feat.setAttribute(cableFields['use'], 2) # Distribution
            feat.setAttribute(cableFields['type'], 4) # 48F
            feat.setAttribute(cableFields['name'], cableName)
            cableLyr.addFeature(feat)
        result = iface.openFeatureForm(cableLyr, feat, False, showModal = True)
        if result:
            cableLyr.commitChanges()

    except Exception as e:
        print(e)
        QMessageBox.warning(iface.mainWindow(), 'Cable not created', \
            'Cable from {}: {} to {}: {} could not be calculated'.format(startLayerName, startId, endLayerName, '-'.join(endIdSplit)))
    finally:
        cableLyr.rollBack()
        QgsProject.instance().removeMapLayer(mergedDuctLyr)
        del mergedDuctLyr
        del cableLyr
