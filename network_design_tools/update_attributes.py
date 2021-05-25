from qgis.core import QgsProject, QgsVectorLayer, QgsSpatialIndex, NULL
from PyQt5.QtWidgets import QMessageBox
import processing
from network_design_tools import common

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
    for lyr_name in ['Cabinet', 'Joint']:
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
        QMessageBox.warning("Attribute update failure", "The following layers were not updated: {}".format('; '.join(failed_layers)))

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
                elif bdryType in ('2', '3'): # UGSN, PMSN
                    cpfeat.setAttribute('SN', bdryfeat['Name'])
                elif bdryType in ('4', '5'): # UGCE, PMCE
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
                    cpfeat.setAttribute('Distance', clength)

                cpLyr.updateFeature(cpfeat)

    cpLyr.commitChanges()
    cpLyr.rollBack()

    cpLyr.removeSelection()
    bdryLyr.removeSelection()

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
