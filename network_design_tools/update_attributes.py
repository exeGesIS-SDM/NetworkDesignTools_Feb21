from math import ceil
from qgis.core import QgsProject, QgsVectorLayer, QgsSpatialIndex, QgsPoint, NULL, \
                      QgsFeatureRequest, QgsRectangle, QgsVectorLayerUtils, \
                      QgsGeometry, QgsExpression
from PyQt5.QtWidgets import QMessageBox
import processing
from network_design_tools import common

def updateCableCounts(iface):
    """ For each duct:
        - get the middle node or centre of line if 2 vertices
        - count the number of cables at that location
        - insert into cable count layer
    """

    layers = common.prerequisites['layers']

    bt_duct_lyr = common.getLayerByName(iface, QgsProject.instance(), layers['BTDuct']['name'], True)
    if bt_duct_lyr is None:
        return

    duct_lyr = common.getLayerByName(iface, QgsProject.instance(), layers['Duct']['name'], True)
    if duct_lyr is None:
        return

    cable_lyr = common.getLayerByName(iface, QgsProject.instance(), layers['Cable']['name'], True)
    if cable_lyr is None:
        return
    cable_fields = layers['Cable']['fields']

    count_lyr = common.getLayerByName(iface, QgsProject.instance(), layers['CableCount']['name'], True)
    if count_lyr is None:
        return
    count_fields = layers['CableCount']['fields']

    count_lyr.startEditing()
    # Delete all existing cable counts
    id_list = [feat.id() for feat in count_lyr.getFeatures()]
    count_lyr.deleteFeatures(id_list)

    request = QgsFeatureRequest()
    bt_duct_lyr.startEditing()
    for duct in bt_duct_lyr.getFeatures():
        geom = duct.geometry()
        # Get central nodes
        vertices = list(geom.vertices())
        if len(vertices) < 2:
            continue

        mid = (len(vertices) // 2) - 1
        rem = len(vertices) % 2
        v1 = vertices[mid]
        v2 = vertices[mid + 1]

        if rem == 0:
            pt = QgsPoint((v1.x() + v2.x())/2, (v1.y() + v2.y())/2)
        else:
            pt = vertices[mid]
        azimuth = v1.azimuth(v2)

        aoi = QgsRectangle(pt.x()-0.1, pt.y()-0.1, pt.x()+0.1, pt.y()+0.1)
        request.setFilterRect(aoi)
        counts = {'1': 0, '2': 0, '3': 0}
        for cable in cable_lyr.getFeatures(request):
            if cable[cable_fields['feed']] == "1":
                cable_use = cable[cable_fields['use']]
                counts[cable_use] += 1

        label_count = 0
        for cable_type, count in counts.items():
            if count > 0:
                label_count += 1
                label = QgsVectorLayerUtils.createFeature(count_lyr)
                #TODO: Offset if count > 1
                if duct.geometry().length() > 5:
                    pt_b = pt.project(5, azimuth)
                    label.setGeometry(QgsGeometry.fromPolyline([pt, pt_b]))
                else:
                    label.setGeometry(duct.geometry())
                label.setAttribute(count_fields['feed'], 1) # UG
                label.setAttribute(count_fields['type'], int(cable_type))
                label.setAttribute(count_fields['count'], count)
                count_lyr.addFeature(label)

    for duct in duct_lyr.getFeatures():
        geom = duct.geometry()
        # Get central nodes
        vertices = list(geom.vertices())
        if len(vertices) < 2:
            continue

        mid = (len(vertices) // 2) - 1
        rem = len(vertices) % 2
        v1 = vertices[mid]
        v2 = vertices[mid + 1]

        if rem == 0:
            pt = QgsPoint((v1.x() + v2.x())/2, (v1.y() + v2.y())/2)
        else:
            pt = vertices[mid]
        azimuth = v1.azimuth(v2)

        aoi = QgsRectangle(pt.x()-0.1, pt.y()-0.1, pt.x()+0.1, pt.y()+0.1)
        request.setFilterRect(aoi)
        counts = {'1': 0, '2': 0, '3': 0}
        for cable in cable_lyr.getFeatures(request):
            if cable[cable_fields['feed']] == 1:
                cable_use = cable[cable_fields['use']]
                counts[cable_use] += 1

        label_count = 0
        for cable_type, count in counts.items():
            if count > 0:
                label_count += 1
                label = QgsVectorLayerUtils.createFeature(count_lyr)
                #TODO: Offset if count > 1
                if duct.geometry().length() > 5:
                    pt_b = pt.project(5, azimuth)
                    label.setGeometry(QgsGeometry.fromPolyline([pt, pt_b]))
                else:
                    label.setGeometry(duct.geometry())
                label.setAttribute(count_fields['feed'], 1) # UG
                label.setAttribute(count_fields['type'], int(cable_type))
                label.setAttribute(count_fields['count'], count)
                count_lyr.addFeature(label)

    unique_cables = []
    request = QgsFeatureRequest(QgsExpression('"{}" = \'2\' AND NOT "{}" = \'1\''.format(cable_fields['feed'], cable_fields['use'])))
    for cable in cable_lyr.getFeatures(request):
        is_unique = True
        for cab in unique_cables:
            if cab['geometry'].isGeosEqual(cable.geometry()):
                cable_use = cable[cable_fields['use']]
                cab['counts'][cable_use] += 1
                is_unique = False
                break

        if is_unique:
            counts = {'1': 0, '2': 0, '3': 0}
            cable_use = cable[cable_fields['use']]
            counts[cable_use] += 1
            unique_cables.append({'geometry': cable.geometry(), 'counts': counts})

    for cable in unique_cables:
        geom = cable['geometry']
        vertices = list(geom.vertices())
        if len(vertices) < 2:
            continue

        mid = (len(vertices) // 2) - 1
        rem = len(vertices) % 2
        v1 = vertices[mid]
        v2 = vertices[mid + 1]

        if rem == 0:
            pt = QgsPoint((v1.x() + v2.x())/2, (v1.y() + v2.y())/2)
        else:
            pt = vertices[mid]
        azimuth = v1.azimuth(v2)

        label_count = 0
        for cable_type, count in cable['counts'].items():
            if count > 0:
                label_count += 1
                label = QgsVectorLayerUtils.createFeature(count_lyr)
                #TODO: Offset if count > 1
                if cable['geometry'].length() > 5:
                    pt_b = pt.project(5, azimuth)
                    label.setGeometry(QgsGeometry.fromPolyline([pt, pt_b]))
                else:
                    label.setGeometry(geom)
                label.setAttribute(count_fields['feed'], 1) # UG
                label.setAttribute(count_fields['type'], int(cable_type))
                label.setAttribute(count_fields['count'], count)
                count_lyr.addFeature(label)
    count_lyr.commitChanges()
    count_lyr.rollBack()

def updateNodeAttributes(iface):
    """ For each node:
        - select the corresponding boundary and populate premises
        - select the nearest premises and populate address
    """

    layers = common.prerequisites['layers']

    premisesLyr = common.getLayerByName(iface, QgsProject.instance(), layers['Premises']['name'], True)
    if premisesLyr is None:
        return

    index = QgsSpatialIndex(premisesLyr.getFeatures())
    premisesFields = premisesLyr.fields().names()

    failed_layers = []
    ### Update cabinet/joints layers ###
    for lyr_name in ['Cabinet', 'Joint', 'NewPole']:
        lyr = common.getLayerByName(iface, QgsProject.instance(), layers[lyr_name]['name'], False)
        if lyr is None:
            failed_layers.append(layers[lyr_name]['name'])
            break

        fields = layers[lyr_name]['fields']
        lyr.startEditing()
        for obj in lyr.getFeatures():
            try:
                geom = obj.geometry()
                premises_ids = index.nearestNeighbor(geom, 1)
                premises = premisesLyr.getFeature(premises_ids[0])
                address = getPremisesAddress(premises, premisesFields)
                if address != NULL:
                    obj[fields['address']] = address
                lyr.updateFeature(obj)
            except Exception as e:
                print(type(e), e)
        lyr.commitChanges()
        lyr.rollBack()

    ### Update Nodes Layer ###
    nodeLyr = common.getLayerByName(iface, QgsProject.instance(), layers['Node']['name'], True)
    if nodeLyr is None:
        failed_layers.append(layers['Node']['name'])
    else:
        # Get the intersecting nodes
        bdryLyr = common.getLayerByName(iface, QgsProject.instance(), layers['Boundaries']['name'], True)
        if bdryLyr is None:
            failed_layers.append(layers['Node']['name'])
        else:
            nodeFields = layers['Node']['fields']
            bdryFields = layers['Boundaries']['fields']

            nodeLyr.startEditing()
            for node in nodeLyr.getFeatures():
                nodeId = node[nodeFields['id']]

                bdryLyr.selectByExpression('\"{}\" = \'{}\''.format(bdryFields['name'], nodeId))
                if bdryLyr.selectedFeatureCount() == 1:
                    bdry = bdryLyr.selectedFeatures()[0]
                    node[nodeFields['premises']] = bdry[bdryFields['premises']]

                geom = node.geometry()
                premises_ids = index.nearestNeighbor(geom, 1)
                premises = premisesLyr.getFeature(premises_ids[0])
                address = getPremisesAddress(premises, premisesFields)

                if address != NULL:
                    node[nodeFields['address']] = address

                nodeLyr.updateFeature(node)

            nodeLyr.commitChanges()
            nodeLyr.rollBack()
            nodeLyr.removeSelection()
            bdryLyr.removeSelection()

    if len(failed_layers) > 0:
        QMessageBox.warning(iface.mainWindow(), "Attribute update failure", "The following layers were not updated: {}".format('; '.join(failed_layers)))
    else:
        iface.messageBar().pushSuccess('Nodes updated', 'Node attribute update completed')

def updatePremisesAttributes(iface, bdryLyr, bdryFeat):
    '''
        select all customer premises in selected boundary
        update each addresspoint with AC??? SN TN LOC?
        Set the Length field to the length of the supply drop cable ?
        add these fields if not exist already?
        can this be done automatically?
    '''

    layers = common.prerequisites['layers']
    AddressLayerName = layers['Premises']['name']

    tempLyr = QgsVectorLayer("Polygon?crs=EPSG:27700", "Temp_Boundary", "memory")
    tempLyr.dataProvider().addFeature(bdryFeat)

    cpLyr = common.getLayerByName(iface, QgsProject.instance(), AddressLayerName, True)
    if cpLyr is None:
        return

    cableLayerName = layers['Cable']['name']
    cableLyr = common.getLayerByName(iface, QgsProject.instance(), cableLayerName, True)
    if cableLyr is None:
        return

    #get the intersecting properties
    processing.run("qgis:selectbylocation", {'INPUT':cpLyr, 'INTERSECT':tempLyr, 'METHOD':0, 'PREDICATE':[0]})
    processing.run("qgis:selectbylocation", {'INPUT':bdryLyr, 'INTERSECT':tempLyr, 'METHOD':0, 'PREDICATE':[0]})

    cpLyr.startEditing()

    for cpfeat in cpLyr.selectedFeatures(): #set all to No first, then ignore any n/a=6
        cpfeat.setAttribute('LOC', 'N')
        cpfeat.setAttribute('LOC_TYPE', NULL)
        cpLyr.updateFeature(cpfeat)

    for bdryfeat in bdryLyr.selectedFeatures():
        for cpfeat in cpLyr.selectedFeatures():
            if cpfeat.geometry().intersects(bdryfeat.geometry()):

                bdryType = bdryfeat['Type']
                if bdryType == '1': # UGPN
                    cpfeat.setAttribute('PN', bdryfeat['Name'])
                elif bdryType in ('2', '3', '10'): # UGSN, PMSN, MSN
                    cpfeat.setAttribute('SN', bdryfeat['Name'])
                elif bdryType in ('4', '5', '11'): # UGCE, PMCE, MCE
                    cpfeat.setAttribute('TN', bdryfeat['Name'])
                elif bdryType == '8': # AC
                    cpfeat.setAttribute('AC', bdryfeat['Name'])

                LOC = bdryfeat['LOC']
                if LOC != 'N/A': # = 'N/A' Set the LOC to true if inside an LOC polygon, Set LOCType to the LOC type value
                    cpfeat.setAttribute('LOC', 'Y')

                    if cpfeat['LOC_TYPE'] == NULL:
                        cpfeat.setAttribute('LOC_TYPE', LOC)
                    else:
                        if LOC is not None:
                            # Append to existing value
                            cpfeat.setAttribute('LOC_TYPE', '{}; {}'.format(cpfeat['LOC_TYPE'], LOC))

                # update CP with length of cable
                cableLyr.selectByExpression('"UPRN" = \'{}\''.format(cpfeat['UPRN']))
                if cableLyr.selectedFeatureCount() > 0:
                    clength = cableLyr.selectedFeatures()[0].geometry().length()
                    cpfeat.setAttribute('Distance', ceil(clength))

                cpLyr.updateFeature(cpfeat)

    cpLyr.commitChanges()
    cpLyr.rollBack()

    cpLyr.removeSelection()
    bdryLyr.removeSelection()

    iface.messageBar().pushSuccess('Premises updated', 'Premises attribute update completed')

def getPremisesAddress(premises, fields):
    addressFields = common.prerequisites['settings']['premisesAddressFields']
    address = []
    for field in addressFields:
        if field in fields:
            val = premises[field]
            if val != NULL:
                val = str(val)
                if len(val) > 0:
                    address.append(val)

    if len(address) == 0:
        return NULL
    else:
        return ', '.join(address)
