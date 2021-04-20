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
from PyQt5.QtGui import QCursor, QPixmap, QColor
from PyQt5.QtWidgets import QApplication, QMessageBox

from qgis.core import QgsProject, QgsWkbTypes, QgsFeatureRequest, QgsRectangle
from qgis.gui import QgsMapToolEmitPoint, QgsMapToolEdit, QgsRubberBand, QgsMapCanvasSnappingUtils
from network_design_tools import common


class SelectDCMapTool(QgsMapToolEmitPoint):
        
    dcSelected = pyqtSignal('QgsFeatureId', 'QgsFeatureId')
    
    def __init__(self, iface, canvas):
        QgsMapToolEmitPoint.__init__(self, canvas)

        """ The user should select a pole object. Then select a Boundary  """
         

        self.setCursor(Qt.CrossCursor)
        self.iface = iface
        self.canvas = canvas
        # self.snapper = QgsMapCanvasSnappingUtils(self.canvas)
        self.poleLayerName = common.prerequisites['layers']['Poles']['name']
        self.poleLayer = None
        self.bndLayerName = common.prerequisites['layers']['Boundaries']['name']
        self.bndLayer = None
        self.bndFields = common.prerequisites['layers']['Boundaries']['fields']
        self.poleSelected = False
        self.poleId = -1
        self.bndID = -1
        self.crs = ''
        self.reset()  

    def reset(self):
        self.poleSelected = False
        self.poleId = -1
                
    def canvasReleaseEvent(self, event):
        # Get the click and emit the point in source crs

        if self.poleSelected:

            self.poleSelected = False
            
            # Get the click and check they clicked on a SN
            if self.bndLayer == None:
                self.bndLayer = common.getLayerByName(self.iface, QgsProject.instance(), self.bndLayerName)
                if self.bndLayer != None:
                    self.crs = self.bndLayer.crs().authid()
                else:
                    self.deactivate()

            point = event.mapPoint()
            request = QgsFeatureRequest(QgsRectangle(point.x()-1,point.y()-1, point.x()+1, point.y()+1))
            # Get ID of the bound, of type SN
            
            for bnd in self.bndLayer.getFeatures(request):
                if bnd['Type'] == '2' or bnd['Type'] == '3': # UGSN or PMSN
                    self.bndID = bnd.id()
                    self.dcSelected.emit(self.poleId, self.bndID)
            
            self.reset()
        else:

 
            if self.poleLayer == None:
                self.poleLayer = common.getLayerByName(self.iface, QgsProject.instance(), self.poleLayerName)
                if self.poleLayer == None:
                    self.deactivate()

            point = event.mapPoint()
            request = QgsFeatureRequest(QgsRectangle(point.x()-1,point.y()-1, point.x()+1, point.y()+1))
            # Get ID of first feature with DP type
            for pole in self.poleLayer.getFeatures(request):
                #print(pole['Use'])
                #any pole will do
                #if pole['Use'] == 'Carrier' or pole['Use'] == 'PMCE' or pole['Use'] == 'PMSN':
                self.poleSelected = True
                self.poleId = pole.id()
                reply = QMessageBox.information(self.iface.mainWindow(),'Network Design Toolkit', '{0} object selected, now select an object from the {1} layer, to create cables to all properties within the area'.format(self.poleLayerName,self.bndLayerName) , QMessageBox.Ok)
                return
    
            reply = QMessageBox.information(self.iface.mainWindow(),'Network Design Toolkit', 'First select an object from the {} layer'.format(self.poleLayerName) , QMessageBox.Ok)

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
        self.layerNames = ['Cabinet','Node','Joint']
        self.layers = {}
        self.reset()

    def deactivate(self):
        self.reset()
        QgsMapToolEmitPoint.deactivate(self)

    def reset(self):
        self.startPtSelected = False
        self.startLayerName = None
        self.startFid = None
        self.startPt = None

    def canvasReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            """ Generate Cable """
            # Get the click and emit the point in source crs
            if not self.startPtSelected:
                if len(self.layers) == 0:
                    self.initialiseLayers()

                point = event.mapPoint()
                request = QgsFeatureRequest(QgsRectangle(point.x()-1,point.y()-1, point.x()+1, point.y()+1))               
                for layerName, layer in self.layers.items():
                    for feat in layer.getFeatures(request):
                        self.startLayerName = layerName
                        self.startFid = feat.id()
                        break

                if self.startFid is not None:
                    self.startPt = point
                    self.startPtSelected = True
                else:
                    self.iface.messageBar().pushInfo('No Infrastructure', 'No Cabinet, Node or Joint at that location')
            else:
                point = event.mapPoint()
                request = QgsFeatureRequest(QgsRectangle(point.x()-1,point.y()-1, point.x()+1, point.y()+1))

                endFid = None
                for layerName, layer in self.layers.items():
                    for feat in layer.getFeatures(request):
                        endLayerName = layerName
                        endFid = feat.id()
                        break

                if endFid is not None:
                    startPt = self.startPt
                    startLayerName = self.startLayerName
                    startFid = self.startFid
                    self.startPt = point

                    # Initialise start point for next cable
                    self.startLayerName = endLayerName
                    self.startFid = endFid
                    self.pointsClicked.emit(startPt, startLayerName, startFid, point, endLayerName, endFid)
                else:
                    self.iface.messageBar().pushInfo('No Infrastructure', 'No Cabinet, Node or Joint at that location')
        elif event.button() == Qt.RightButton:
            self.reset()

    def initialiseLayers(self):
        for layerName in self.layerNames:
            if not layerName in self.layers:
                self.layers[layerName] = common.getLayerByName(self.iface, QgsProject.instance(), self.layerParams[layerName]['name'], False)

        if len(self.layers) == 0:
            self.iface.messageBar().pushInfo('Layers not open', 'None of the Cabinet, Node or Joint layers are open.')
            self.deactivate()

    def isZoomTool(self):
        return False

    def isTransient(self):
        return False

    def isEditTool(self):
        return False