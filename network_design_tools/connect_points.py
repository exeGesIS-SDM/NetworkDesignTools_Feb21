from PyQt5.QtCore import pyqtSignal, QObject
from qgis.core import QgsProject, QgsVectorLayer, QgsPoint, QgsProcessingFeatureSourceDefinition, \
                      QgsFeatureRequest, QgsVectorLayerUtils, QgsGeometry, QgsSpatialIndex, NULL, \
                      QgsRectangle, QgsProcessingException, QgsPointXY
from qgis.PyQt.QtWidgets import QMessageBox
import processing
from network_design_tools import common
from .mm_processing import MastermapProcessing
from .map_tools import UGDropMapTool

def createNodeCable(iface, routingType, startPoint, startLayerName, startFid, endPoint, endLayerName, endFid):
    layers = common.prerequisites['layers']
    duct_lyr = common.getLayerByName(iface, QgsProject.instance(), layers['Duct']['name'])
    if duct_lyr is None:
        return

    bt_duct_lyr = common.getLayerByName(iface, QgsProject.instance(), layers['BTDuct']['name'])
    if bt_duct_lyr is None:
        return

    try:
        result = processing.run("native:mergevectorlayers", { 'CRS' : duct_lyr.crs(), \
                            'LAYERS' : [bt_duct_lyr, duct_lyr], 'OUTPUT' : 'TEMPORARY_OUTPUT' })
        merged_duct_lyr = result['OUTPUT']
    except Exception as e:
        print(type(e), e)
        QMessageBox.critical(iface.mainWindow(),"Merge Failure", "Failed to merge the duct layers.")

    cable_lyr = common.getLayerByName(iface, QgsProject.instance(), layers['Cable']['name'])
    if cable_lyr is None:
        return

    start_lyr = common.getLayerByName(iface, QgsProject.instance(), startLayerName)
    if start_lyr is None:
        return
    for feat in start_lyr.getFeatures(QgsFeatureRequest(startFid)):
        startPt = feat

    end_lyr = common.getLayerByName(iface, QgsProject.instance(), endLayerName)
    if end_lyr is None:
        return
    for feat in end_lyr.getFeatures(QgsFeatureRequest(endFid)):
        endPt = feat

    # Get fields for the relevant layer
    for params in layers.values():
        if params['name'] == startLayerName:
            startFields = params['fields']
        if params['name'] == endLayerName:
            endFields = params['fields']

    startId = startPt[startFields['id']]
    if endPt[endFields['id']] != NULL:
        endIdSplit = endPt[endFields['id']].split('-')
        endId = endIdSplit[-1]
    else:
        endId = endPt[endFields['id']]

    cableName = '{}/{}'.format(startId, endId)

    cable_fields = layers['Cable']['fields']

    cable_lyr.startEditing()
    try:
        if routingType == 'UG':
            QgsProject.instance().addMapLayer(merged_duct_lyr)

            start = '{}, {} [{}]'.format(startPoint.x(), startPoint.y(), QgsProject.instance().crs().authid())
            end = '{}, {} [{}]'.format(endPoint.x(), endPoint.y(), QgsProject.instance().crs().authid())
            result = processing.run("native:shortestpathpointtopoint", { 'DEFAULT_DIRECTION' : 2, 'DEFAULT_SPEED' : 50, 'DIRECTION_FIELD' : None, \
                            'START_POINT' : start, 'END_POINT' : end, 'INPUT' : merged_duct_lyr, 'OUTPUT' : 'TEMPORARY_OUTPUT', \
                            'SPEED_FIELD' : None, 'STRATEGY' : 0, 'TOLERANCE' : 0.1, 'VALUE_BACKWARD' : '', 'VALUE_BOTH' : '', 'VALUE_FORWARD' : '' })

            for c in result['OUTPUT'].getFeatures():
                feat = QgsVectorLayerUtils.createFeature(cable_lyr)
                feat.setGeometry(c.geometry())
                feat.setAttribute(cable_fields['feed'], 1) # U/G
                feat.setAttribute(cable_fields['use'], 2) # Distribution
                feat.setAttribute(cable_fields['type'], 4) # 48F
                feat.setAttribute(cable_fields['name'], cableName)
                cable_lyr.addFeature(feat)
        else:
            feat = QgsVectorLayerUtils.createFeature(cable_lyr)
            c = QgsGeometry.fromPolylineXY([startPoint, endPoint])
            feat.setGeometry(c)
            feat.setAttribute(cable_fields['feed'], 2) # Aerial
            feat.setAttribute(cable_fields['use'], 2) # Distribution
            feat.setAttribute(cable_fields['type'], 4) # 48F
            feat.setAttribute(cable_fields['name'], cableName)
            cable_lyr.addFeature(feat)
        result = iface.openFeatureForm(cable_lyr, feat, False, showModal = True)
        if result:
            cable_lyr.commitChanges()

    except Exception as e:
        print(e)
        QMessageBox.warning(iface.mainWindow(), 'Cable not created', \
            'Cable from {}: {} to {}: {} could not be calculated. '.format(startLayerName, startId, endLayerName, '-'.join(endIdSplit)) + \
            'Please check ducts are snapped and there are no invalid geometries in BT Duct / Duct layers.')
    finally:
        cable_lyr.rollBack()
        QgsProject.instance().removeMapLayer(merged_duct_lyr)
        del merged_duct_lyr
        del cable_lyr

class DropCableBuilder(QObject):
    cablesCompleted = pyqtSignal()
    def __init__(self, iface):
        QObject.__init__(self)

        self.iface = iface
        self.is_valid = False
        self.layers = common.prerequisites['layers']

        self.node_lyr = None
        self.bdry_lyr = None
        self.cable_lyr = None
        self.cable_fields = self.layers['Cable']['fields']

        self.cp_lyr = None
        self.uprn_field = self.layers['Premises']['fields']['uprn']
        self.premises_list = {}
        self.premises_index = None
        self.premises_id = None

        self.subscriber_lyr = None
        self.sub_fields = self.layers['SubFeed']['fields']

        self.mp = None
        self.point_tool = UGDropMapTool(self.iface, self.iface.mapCanvas())
        self.snap_config = QgsProject.instance().snappingConfig()

    def check_layers(self):
        self.is_valid = False

        self.node_lyr = common.getLayerByName(self.iface, QgsProject.instance(), self.layers['Node']['name'])
        if self.node_lyr is None:
            return

        self.bdry_lyr = common.getLayerByName(self.iface, QgsProject.instance(), self.layers['Boundaries']['name'])
        if self.bdry_lyr is None:
            return

        self.cable_lyr = common.getLayerByName(self.iface, QgsProject.instance(), self.layers['Cable']['name'])
        if self.cable_lyr is None:
            return

        self.cp_lyr = common.getLayerByName(self.iface, QgsProject.instance(), self.layers['Premises']['name'])
        if self.cp_lyr is None:
            return

        self.subscriber_lyr = common.getLayerByName(self.iface, QgsProject.instance(), self.layers['SubFeed']['name'])
        if self.cp_lyr is None:
            return

        self.snap_config = QgsProject.instance().snappingConfig()

        self.is_valid = True

    def create_drop_cables(self, node_id, bdry_id, selected_only):
        if not self.is_valid:
            return

        self.node_lyr.removeSelection()
        self.node = self.node_lyr.getFeature(node_id)

        self.bdry_lyr.selectByIds([bdry_id])
        if self.bdry_lyr.selectedFeatureCount() == 0:
            return
        bdry_feat = self.bdry_lyr.selectedFeatures()[0]
        bdry_type = bdry_feat[self.layers['Boundaries']['fields']['type']]

        self.mp = MastermapProcessing(self.iface, 'TopoArea', self.bdry_lyr, bdry_id)

        # Get the intersecting properties
        bdry_sel_lyr = QgsProcessingFeatureSourceDefinition(self.bdry_lyr.source(), selectedFeaturesOnly = True)
        try:
            if selected_only:
                # Ensure selected properties are within the SN boundary
                processing.run("qgis:selectbylocation", {'INPUT':self.cp_lyr, 'INTERSECT':bdry_sel_lyr, 'METHOD':2, 'PREDICATE':[6]}) # 6 = Within
            else:
                processing.run("qgis:selectbylocation", {'INPUT':self.cp_lyr, 'INTERSECT':bdry_sel_lyr, 'METHOD':0, 'PREDICATE':[6]}) # 6 = Within
        except QgsProcessingException as e:
            QMessageBox.critical(self.iface.mainWindow(),'Selection Failure', \
                                'Failed to select Customer Premises. Please check geometries in Boundaries layer are valid.\nQGIS error: {}'.format(e), QMessageBox.Ok)
            return

        if bdry_type in ('2', '3'): # UGSN / PMSN
            processing.run("qgis:selectbylocation", {'INPUT':self.bdry_lyr, 'INTERSECT':bdry_sel_lyr, 'METHOD':0, 'PREDICATE':[5, 6]}) # 5 = Overlaps
            self.bdry_lyr.selectByExpression('\"{}\" in (\'4\', \'5\')'.format(self.layers['Boundaries']['fields']['type']), \
                QgsVectorLayer.SelectBehavior.IntersectSelection)

            if self.bdry_lyr.selectedFeatureCount() > 0:
                processing.run("qgis:selectbylocation", { 'INPUT' : self.cp_lyr, 'INTERSECT' : bdry_sel_lyr, 'METHOD' : 3, 'PREDICATE' : [6] }) # 3 = Remove from selection
        self.bdry_lyr.removeSelection()

        if self.cp_lyr.selectedFeatureCount() == 0:
            if selected_only:
                QMessageBox.critical(self.iface.mainWindow(),'No Premises', 'None of the selected premises are within the SN boundary.', QMessageBox.Ok)
            else:
                QMessageBox.critical(self.iface.mainWindow(),'No Premises', 'There are no premises are within the SN boundary.', QMessageBox.Ok)
            return

        message = '%s properties have been found within the SN area. Do you want to draw cables?' % (self.cp_lyr.selectedFeatureCount())
        reply = QMessageBox.question(self.iface.mainWindow(), 'Create Cables', message, QMessageBox.Yes, QMessageBox.No)
        if reply == QMessageBox.No:
            return

        if selected_only:
            msg_box = QMessageBox(QMessageBox.Question, 'Set Drop Cable Type', \
                              "How will these drop cables be installed?", parent = self.iface.mainWindow())
            aerial_btn = msg_box.addButton('Aerial', QMessageBox.YesRole)
            msg_box.addButton('Underground', QMessageBox.NoRole)
            msg_box.setDefaultButton(aerial_btn)
            msg_box.setEscapeButton(aerial_btn)

            reply = msg_box.exec_()
            if reply == 0:
                self.create_oh_drop_cables()
            elif reply == 1:
                self.create_ug_drop_cables()
        else:
            if bdry_type in ('3', '5'): # PMSN/PMCE
                self.create_oh_drop_cables()
            else: # UGSN/UGCE
                self.create_ug_drop_cables()

    def create_oh_drop_cables(self):
        self.cable_lyr.startEditing()
        for cpfeat in self.cp_lyr.selectedFeatures(): # Loop through the properties
            cable_pts = []
            cable_pts.append(QgsPoint(cpfeat.geometry().asPoint()))
            cable_pts.append(QgsPoint(self.node.geometry().asPoint()))

            new_cable = self.mp.clipGeometryByBuilding(cpfeat.geometry(), self.node.geometry(), QgsGeometry.fromPolyline(cable_pts))

            pc = QgsVectorLayerUtils.createFeature(self.cable_lyr)
            pc.setGeometry(new_cable)
            pc.setAttribute(self.cable_fields['feed'], '2') # Aerial
            pc.setAttribute(self.cable_fields['use'], '1') # Access
            pc.setAttribute(self.cable_fields['type'], '1') # 1F
            pc.setAttribute(self.cable_fields['uprn'], cpfeat[self.uprn_field])
            self.cable_lyr.addFeature(pc)
        self.cable_lyr.commitChanges()
        self.cable_lyr.rollBack()

        self.drop_cables_completed()

    def create_ug_drop_cables(self):
        # Create list of premises to process
        self.premises_index = QgsSpatialIndex(self.cp_lyr.getSelectedFeatures())
        for premises in self.cp_lyr.selectedFeatures():
            self.premises_list[premises.id()] = premises
        self.cp_lyr.removeSelection()

        # Configure map tool
        self.point_tool.deactivated.connect(self.reset_ug_drop_cable_builder)
        self.iface.mapCanvas().setMapTool(self.point_tool)

        self.next_ug_drop_cable()

    def drop_cables_completed(self):
        self.mp.removeSelection()
        self.cp_lyr.removeSelection()
        self.cable_lyr.triggerRepaint()
        self.cablesCompleted.emit()

    def insert_ug_drop_cable(self, end_point, crs, match):
        duct_lyr = common.getLayerByName(self.iface, QgsProject.instance(), self.layers['Duct']['name'])
        if duct_lyr is None:
            self.point_tool.deactivate()
            self.drop_cables_completed()
            return

        bt_duct_lyr = common.getLayerByName(self.iface, QgsProject.instance(), self.layers['BTDuct']['name'])
        if bt_duct_lyr is None:
            self.point_tool.deactivate()
            self.drop_cables_completed()
            return

        client_point = self.check_lead_in_duct(end_point, match)
        if end_point is not None:
            try:
                result = processing.run("native:mergevectorlayers", { 'CRS' : duct_lyr.crs(), \
                                    'LAYERS' : [bt_duct_lyr, duct_lyr], 'OUTPUT' : 'TEMPORARY_OUTPUT' })
                merged_duct_lyr = result['OUTPUT']
            except Exception as e:
                print(type(e), e)
                QMessageBox.critical(self.iface.mainWindow(),"Merge Failure", "Failed to merge the duct layers.")

            self.cable_lyr.startEditing()
            try:
                QgsProject.instance().addMapLayer(merged_duct_lyr)

                start_point = self.node.geometry().asPoint()
                start = '{}, {} [{}]'.format(start_point.x(), start_point.y(), QgsProject.instance().crs().authid())
                end = '{}, {} [{}]'.format(end_point.x(), end_point.y(), crs)
                result = processing.run("native:shortestpathpointtopoint", { 'DEFAULT_DIRECTION' : 2, 'DEFAULT_SPEED' : 50, 'DIRECTION_FIELD' : None, \
                            'START_POINT' : start, 'END_POINT' : end, 'INPUT' : merged_duct_lyr, 'OUTPUT' : 'TEMPORARY_OUTPUT', \
                            'SPEED_FIELD' : None, 'STRATEGY' : 0, 'TOLERANCE' : 0.1, 'VALUE_BACKWARD' : '', 'VALUE_BOTH' : '', 'VALUE_FORWARD' : '' })

                for c in result['OUTPUT'].getFeatures():
                    feat = QgsVectorLayerUtils.createFeature(self.cable_lyr)

                    if client_point is not None:
                        client_geom = c.geometry().asPolyline()
                        client_geom.append(QgsPointXY(client_point))
                        feat.setGeometry(QgsGeometry.fromPolylineXY(client_geom))
                    else:
                        feat.setGeometry(c.geometry())
                    feat.setAttribute(self.cable_fields['feed'], 1) # U/G
                    feat.setAttribute(self.cable_fields['use'], 1) # Access
                    feat.setAttribute(self.cable_fields['type'], 1) # 1F
                    feat.setAttribute(self.cable_fields['uprn'], self.premises_list[self.premises_id][self.uprn_field])
                    self.cable_lyr.addFeature(feat)
                self.cable_lyr.commitChanges()

            except Exception as e:
                print(e)
                QMessageBox.warning(self.iface.mainWindow(), 'Cable not created', \
                    'Cable from {} to UPRN {} could not be calculated. '.format(self.node[self.layers['Node']['fields']['id']], \
                                                                                self.premises_list[self.premises_id][self.uprn_field]) + \
                    'Please check nodes are snapped and there are no invalid geometries in BT Duct / Duct layers.')
            finally:
                self.cable_lyr.rollBack()
                QgsProject.instance().removeMapLayer(merged_duct_lyr)
                del merged_duct_lyr

        # Remove feature from index/list
        self.premises_index.deleteFeature(self.premises_list[self.premises_id])
        del self.premises_list[self.premises_id]
        self.premises_id = None
        self.next_ug_drop_cable()

    def check_lead_in_duct(self, end_point, match):
        self.point_tool.canvasClickSnapped.disconnect(self.insert_ug_drop_cable)
        split_duct = True
        split_lyr = match.layer()
        duct = split_lyr.getFeature(match.featureId())
        geom = duct.geometry()
        geom.convertToSingleType()

        if match.hasVertex():
            # Check if vertex is at start/end of duct
            vertices = list(geom.vertices())
            if match.vertexIndex() == 0 or match.vertexIndex() == (len(vertices) - 1):
                split_duct = False

        bt_lead_in = False
        if split_lyr.name() == self.layers['BTDuct']['name']:
            if duct[self.layers['BTDuct']['fields']['leadSpine']] == 'Lead in':
                bt_lead_in = True

        if split_duct:
            split_lyr.startEditing()
            try:
                att=duct.attributes()
                if match.hasVertex():
                    index = match.vertexIndex()
                else:
                    # Insert vertex if match = Edge
                    index = match.vertexIndex() + 1
                    geom.insertVertex(QgsPoint(end_point), index)

                geom_a=QgsGeometry.fromPolylineXY(geom.asPolyline()[:index+1])
                geom_b=QgsGeometry.fromPolylineXY(geom.asPolyline()[index:])

                if geom_a.length() > 0.01 and geom_b.length() > 0.01:
                    duct_a=QgsVectorLayerUtils.createFeature(split_lyr)
                    duct_a.setGeometry(geom_a)
                    duct_a.setAttributes(att)
                    split_lyr.addFeature(duct_a)

                    duct_b=QgsVectorLayerUtils.createFeature(split_lyr)
                    duct_b.setGeometry(geom_b)
                    duct_b.setAttributes(att)
                    split_lyr.addFeature(duct_b)

                    split_lyr.deleteFeature(duct.id())
                    split_lyr.commitChanges()

            except Exception as e:
                print(type(e), e)
            finally:
                split_lyr.rollBack()

        if bt_lead_in:
            return None

        premises_geom = self.premises_list[self.premises_id].geometry()

        # Insert subscriber feed
        self.insert_subscriber_feed(end_point, premises_geom.asPoint())

        # Calculate end of client cable where it meets building
        duct_pts = []
        duct_pts.append(QgsPoint(premises_geom.asPoint()))

        duct_pts.append(QgsPoint(end_point))
        lead_in_geom = self.mp.clipGeometryByBuilding(premises_geom, QgsGeometry.fromPointXY(end_point), QgsGeometry.fromPolyline(duct_pts))

        vertices = list(lead_in_geom.vertices())
        return vertices[0]

    def insert_subscriber_feed(self, point, premise):
        try:
            self.subscriber_lyr.startEditing()

            # Check if subscriber feed at point location
            existing_feed = False
            aoi = QgsRectangle(point.x()-0.1, point.y()-0.1, point.x()+0.1, point.y()+0.1)
            for feed in self.subscriber_lyr.getFeatures(QgsFeatureRequest(aoi)):
                feed.setAttribute(self.sub_fields['dropCount'], feed[self.sub_fields['dropCount']] + 1)
                self.subscriber_lyr.updateFeature(feed)
                existing_feed = True
                break

            if not existing_feed:
                max_id = self.subscriber_lyr.maximumValue(self.subscriber_lyr.fields().indexFromName(self.sub_fields['id']))
                if max_id == NULL:
                    max_id = 0

                sub_feed = QgsVectorLayerUtils.createFeature(self.subscriber_lyr)
                sub_feed.setGeometry(QgsGeometry.fromPointXY(point))
                sub_feed.setAttribute(self.sub_fields['id'], max_id + 1)
                sub_feed.setAttribute(self.sub_fields['dropCount'], 1)
                sub_feed.setAttribute(self.sub_fields['surface'], 'Footway')

                line =  QgsGeometry.fromPolyline([QgsPoint(self.node.geometry().asPoint()), QgsPoint(point)])
                s = line.closestSegmentWithContext(premise)
                if s[3] < 0:
                    sub_feed.setAttribute(self.sub_fields['orientation'], 1) # Left
                else:
                    sub_feed.setAttribute(self.sub_fields['orientation'], 2) # Right

                rotation = point.azimuth(premise)
                sub_feed.setAttribute(self.sub_fields['rotation'], rotation)

                self.subscriber_lyr.addFeature(sub_feed)
            self.subscriber_lyr.commitChanges()
        except Exception as e:
            print(type(e), e)
        finally:
            self.subscriber_lyr.rollBack()

    def next_ug_drop_cable(self):
        nearest_ids = self.premises_index.nearestNeighbor(self.node.geometry().asPoint(), 1)
        if len(nearest_ids) > 0:
            self.premises_id = nearest_ids[0]
            self.cp_lyr.selectByIds([self.premises_id], QgsVectorLayer.SetSelection)
            geom = self.premises_list[self.premises_id].geometry()
            self.iface.mapCanvas().setCenter(geom.asPoint())
            self.iface.messageBar().pushInfo("Link to duct", "Click on duct vertex/segment to connect premises to {}".format(self.node[self.layers['Node']['fields']['id']]))
            self.point_tool.canvasClickSnapped.connect(self.insert_ug_drop_cable)
        else:
            self.point_tool.deactivate()
            self.drop_cables_completed()

    def reset_ug_drop_cable_builder(self):
        self.cable_lyr.rollBack()
        self.premises_index = None
        self.premises_list = {}
        self.premises_id = None
        QgsProject.instance().setSnappingConfig(self.snap_config)
