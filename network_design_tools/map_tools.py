# -*- coding: utf-8 -*-
"""
/***************************************************************************
 Fibre Network Toolkit
                                 A QGIS plugin
 Tools for automating the design of new fibre networks
                              -------------------
        begin                : 2012-11-11
        copyright            : (C) 2020 by exeGesIS SDM Ltd
        email                : xginfo@esdm.co.uk
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""

from PyQt5.QtCore import pyqtSignal, Qt
from PyQt5.QtWidgets import QMessageBox
from qgis.core import QgsProject, QgsFeatureRequest, QgsRectangle, QgsPointLocator, \
                      QgsSnappingConfig, QgsTolerance
from qgis.gui import QgsMapToolEmitPoint, QgsSnapIndicator
from network_design_tools import common

class SelectDCMapTool(QgsMapToolEmitPoint):

    dcSelected = pyqtSignal('QgsFeatureId', 'QgsFeatureId')

    def __init__(self, iface, canvas):
        """The user should select a SN/TN node object"""

        QgsMapToolEmitPoint.__init__(self, canvas)

        self.setCursor(Qt.CrossCursor)
        self.iface = iface
        self.canvas = canvas
        # self.snapper = QgsMapCanvasSnappingUtils(self.canvas)
        self.nodeLayerName = common.prerequisites['layers']['Node']['name']
        self.nodeLayer = None
        self.nodeFields = common.prerequisites['layers']['Node']['fields']
        self.nodeUseLUT = common.prerequisites['settings']['nodeUseBdryTypeLUT']
        self.bndLayerName = common.prerequisites['layers']['Boundaries']['name']
        self.bndLayer = None
        self.bndFields = common.prerequisites['layers']['Boundaries']['fields']
        self.nodeSelected = False
        self.nodeId = -1
        self.nodeFeat = None
        self.crs = ''
        self.reset()

    def reset(self):
        self.nodeSelected = False
        self.nodeId = -1
        self.nodeFeat = None

    def canvasReleaseEvent(self, event):
        # Get the click and emit the point in source crs
        if self.nodeLayer is None:
            self.nodeLayer = common.getLayerByName(self.iface, QgsProject.instance(), self.nodeLayerName)
            if self.nodeLayer is None:
                self.deactivate()

        point = event.mapPoint()
        self.nodeLayer.selectByExpression('\"Position\" in (\'1\',\'2\')')
        request = QgsFeatureRequest(QgsRectangle(point.x()-1,point.y()-1, point.x()+1, point.y()+1))
        # Get ID of first feature with DP type
        for node in self.nodeLayer.getSelectedFeatures(request):
            self.nodeSelected = True
            self.nodeId = node.id()
            self.nodeFeat = node
            break

        if self.nodeSelected:
            self.nodeSelected = False

            # Get the click and check they clicked on a SN
            if self.bndLayer is None:
                self.bndLayer = common.getLayerByName(self.iface, QgsProject.instance(), self.bndLayerName)
                if self.bndLayer is not None:
                    self.crs = self.bndLayer.crs().authid()
                else:
                    self.deactivate()

            for bnd in self.bndLayer.getFeatures(request):
                bndType = bnd[self.bndFields['type']]
                if  bndType != 1 and bndType == self.nodeUseLUT[self.nodeFeat[self.nodeFields['use']]]: # UGSN or PMSN
                    self.dcSelected.emit(self.nodeId, bnd.id())
                    break

            self.reset()
        else:
            QMessageBox.information(self.iface.mainWindow(), 'Network Design Toolkit', \
                'First select an aerial or underground node from the {} layer'.format(self.nodeLayerName) , QMessageBox.Ok)

    def isZoomTool(self):
        return False

    def isTransient(self):
        return False

    def isEditTool(self):
        return False


class ConnectNodesMapTool(QgsMapToolEmitPoint):

    pointsClicked = pyqtSignal('QgsPointXY', str, 'QgsFeatureId', 'QgsPointXY', str, 'QgsFeatureId')

    def __init__(self, iface, canvas):
        QgsMapToolEmitPoint.__init__(self, canvas)
        self.setCursor(Qt.CrossCursor)
        self.iface = iface
        self.canvas = canvas
        self.layerParams = common.prerequisites['layers']
        self.layerNames = common.prerequisites['settings']['snapLayers']['connectNodes']
        self.layers = {}
        self.startPtSelected = False
        self.startLayerName = None
        self.startFid = None
        self.startPt = None
        self.snapper = self.canvas.snappingUtils()
        self.snap_indicator = QgsSnapIndicator(self.canvas)
        self.snap_configured = False

    def deactivate(self):
        self.reset()
        QgsMapToolEmitPoint.deactivate(self)

    def reset(self):
        self.startPtSelected = False
        self.startLayerName = None
        self.startFid = None
        self.startPt = None

    def canvasMoveEvent(self, event):
        # Enable snapping to snap_layers only
        if not self.snap_configured and len(self.layerNames) > 0:
            self.snap_configured = common.set_snap_layers(self.layerNames, [QgsSnappingConfig.SnappingType.Vertex], 12, QgsTolerance.UnitType.Pixels)
            if not self.snap_configured:
                self.iface.messageBar().pushCritical('Snap layer(s) unavailable', 'Could not configure the specified snapping layers: {}'.format(', '.join(self.layerNames)))
                self.deactivate()
        snapped_point = self.snapper.snapToMap(event.mapPoint())
        self.snap_indicator.setMatch(snapped_point)

    def canvasReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            ### Generate Cable ###
            # Get the click and emit the point in source crs
            if self.snap_configured:
                snapped_point = self.snapper.snapToMap(event.mapPoint())
                if snapped_point.isValid():
                    if not self.startPtSelected:
                        self.startLayerName = snapped_point.layer().name()
                        self.startFid = snapped_point.featureId()
                        self.startPt = snapped_point.point()
                        self.startPtSelected = True
                    else:
                        endLayerName = snapped_point.layer().name()
                        endFid = snapped_point.featureId()

                        startPt = self.startPt
                        startLayerName = self.startLayerName
                        startFid = self.startFid

                        # Initialise start point for next cable
                        self.startPt = snapped_point.point()
                        self.startLayerName = endLayerName
                        self.startFid = endFid
                        self.pointsClicked.emit(startPt, startLayerName, startFid, snapped_point.point(), endLayerName, endFid)
                else:
                    self.iface.messageBar().pushInfo('No Infrastructure', 'No Cabinet, Node or Joint at that location')
        elif event.button() == Qt.RightButton:
            self.reset()

    def isZoomTool(self):
        return False

    def isTransient(self):
        return False

    def isEditTool(self):
        return False

class UGDropMapTool(QgsMapToolEmitPoint):
    """ Map tool for getting a snapped point click """
    canvasClickSnapped = pyqtSignal('QgsPointXY', str, 'QgsPointLocator::Match')

    def __init__(self, iface, canvas):
        QgsMapToolEmitPoint.__init__(self, canvas)
        self.iface = iface
        self.canvas = canvas
        self.snapper = self.canvas.snappingUtils()
        self.snap_indicator = QgsSnapIndicator(self.canvas)
        self.snap_layers = common.prerequisites['settings']['snapLayers']['ugDrop']
        self.snap_configured = False

    def deactivate(self):
        self.reset()
        QgsMapToolEmitPoint.deactivate(self)

    def reset(self):
        self.snap_configured = False
        self.snap_indicator.setMatch(QgsPointLocator.Match())

    def canvasMoveEvent(self, event):
        # Enable snapping to snap_layers only
        if not self.snap_configured and len(self.snap_layers) > 0:
            self.snap_configured = common.set_snap_layers(self.snap_layers, [QgsSnappingConfig.SnappingType.VertexAndSegment], 12, QgsTolerance.UnitType.Pixels)
            if not self.snap_configured:
                self.iface.messageBar().pushCritical('Snap layer(s) unavailable', 'Could not configure the specified snapping layers: {}'.format(', '.join(self.snap_layers)))
                self.deactivate()
        snapped_point = self.snapper.snapToMap(event.mapPoint())
        self.snap_indicator.setMatch(snapped_point)

    def canvasReleaseEvent(self, event):
        # Get the click and emit the point in source crs
        if self.snap_configured:
            snapped_point = self.snapper.snapToMap(event.mapPoint())
            crs = self.canvas.mapSettings().destinationCrs().authid()
            if snapped_point.isValid():
                self.canvasClickSnapped.emit(snapped_point.point(), crs, snapped_point)
                self.reset()

    def isZoomTool(self):
        return False

    def isTransient(self):
        return False

    def isEditTool(self):
        return False
