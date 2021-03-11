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
from .common import getLayerByName

class PointMapTool(QgsMapToolEmitPoint):
    
    canvasClicked = pyqtSignal('QgsPointXY', str)
    
    def __init__(self, canvas):
        QgsMapToolEmitPoint.__init__(self,canvas)
        self.canvas = canvas
                
    def canvasReleaseEvent(self, event):
        # Get the click and emit the point in source crs
        crs = self.canvas.mapSettings().destinationCrs().authid()
        self.canvasClicked.emit(event.mapPoint(),crs)
    
    def isZoomTool(self):
        return False
    
    def isTransient(self):
        return False
      
    def isEditTool(self):
        return False

class MovePointMapTool(QgsMapToolEdit):
    
    pointMoved = pyqtSignal('QgsFeatureId', 'QgsPointXY', str)
    
    def __init__(self, iface, canvas, sourceLayerName, snapLayer):
        QgsMapToolEdit.__init__(self,canvas)
        self.setCursor(Qt.CrossCursor)
        self.iface = iface
        self.canvas = canvas
        self.rubberBand = self.createRubberBand(QgsWkbTypes.PointGeometry)
        self.rubberBand.setIcon(QgsRubberBand.IconType.ICON_FULL_BOX)
        self.snapper = QgsMapCanvasSnappingUtils(self.canvas)
        self.sourceLayerName = sourceLayerName
        self.sourceLayer = None
        self.snapLayer = snapLayer
        self.startID = None
        self.crs = ''
        self.isMoving = False
        self.reset()

    def reset(self):
        self.startID = self.endPoint = None
        self.isMoving = False
        self.rubberBand.reset(True)
                
    def canvasMoveEvent(self, event):
        # TODO: Enable snapping to snapLayer only
        if not self.isMoving:
            return

        self.endPoint = event.mapPoint()
        self.showPoint(self.endPoint)

    def canvasReleaseEvent(self, event):
        if self.isMoving:
            self.isMoving = False
            # Get the click and emit the start/end points in source crs
            self.pointMoved.emit(self.startID, event.mapPoint(), self.crs)
            self.reset()
        else:
            # TODO: Enable snapping to sourceLayer only
            if self.sourceLayer == None:
                self.sourceLayer = getLayerByName(self.iface, QgsProject.instance(), self.sourceLayerName)
                if self.sourceLayer == None:
                    self.deactivate()
                                
            if self.sourceLayer != None:
                self.crs = self.sourceLayer.crs().authid()
                point = event.mapPoint()
                request = QgsFeatureRequest(QgsRectangle(point.x()-1,point.y()-1, point.x()+1, point.y()+1))
                # Get ID of first feature
                for pt in self.sourceLayer.getFeatures(request):
                    self.startID = pt.id()
                    break

                if self.startID != None:
                    self.isMoving = True
    
    def showPoint(self, point):
        self.rubberBand.reset(QgsWkbTypes.PointGeometry)
        self.rubberBand.addPoint(point, True)
        self.rubberBand.show()

    def isZoomTool(self):
        return False
    
    def isTransient(self):
        return False
      
    def isEditTool(self):
        return True

class SelectCPTool(QgsMapToolEmitPoint):
        
    dpSelected = pyqtSignal('QgsFeatureId', list)
    
    def __init__(self, iface, canvas):
        QgsMapToolEmitPoint.__init__(self, canvas)
        self.setCursor(Qt.CrossCursor)
        self.iface = iface
        self.canvas = canvas
        # self.snapper = QgsMapCanvasSnappingUtils(self.canvas)
        self.bdryLayer = None
        self.dpLayer = None
        self.bdrySelected = False
        self.bdryId = -1
        self.crs = ''
        self.reset()

    def reset(self):
        self.bdrySelected = False
        self.bdryId = -1
                
    def canvasReleaseEvent(self, event):
        # Get the click and emit the point in source crs
        if self.bdrySelected:
            self.bdrySelected = False
            
            # Get the click and check they clicked on a DP
            if self.dpLayer == None:
                self.dpLayer = getLayerByName(self.iface, QgsProject.instance(), 'DistributionPoints')
                if self.dpLayer != None:
                    self.crs = self.dpLayer.crs().authid()
                else:
                    self.deactivate()

            point = event.mapPoint()
            request = QgsFeatureRequest(QgsRectangle(point.x()-1,point.y()-1, point.x()+1, point.y()+1))
            # Get name of DP features by concatenating Cabinet-FibreIndex.Branch.PFDPId
            dpNames = []
            for dp in self.dpLayer.getFeatures(request):
                dpNames.append('{}-{}.{}.{}'.format(dp['Cabinet'], dp['Fibre Inde'], dp['Branch'], dp['PFDP ID']))

            if len(dpNames) > 0:                
                self.dpSelected.emit(self.bdryId, dpNames)
            else:
                self.iface.messageBar().pushInfo('No Distribution Point', 'No Distribution Point at that location')
            self.reset()
        else:
            if self.bdryLayer == None:
                self.bdryLayer = getLayerByName(self.iface, QgsProject.instance(), 'Boundaries')
                if self.bdryLayer == None:
                    self.deactivate()

            point = event.mapPoint()
            request = QgsFeatureRequest(QgsRectangle(point.x()-1,point.y()-1, point.x()+1, point.y()+1))
            # Get ID of first feature with DP type
            for bdry in self.bdryLayer.getFeatures(request):
                if bdry['Type'] == 'DP':
                    self.bdrySelected = True
                    self.bdryId = bdry.id()
                    break
    
    def isZoomTool(self):
        return False
    
    def isTransient(self):
        return False
      
    def isEditTool(self):
        return False

class FreehandPolygonMapTool(QgsMapToolEdit):
    
    polyCompleted = pyqtSignal('QgsGeometry')

    def __init__(self, canvas):
        QgsMapToolEdit.__init__(self,canvas)
        self.canvas = canvas
        self.rubberBand = self.createRubberBand(QgsWkbTypes.PolygonGeometry)
        self.rubberBand.setColor(QColor(255, 0, 0, 50))
    
    def reset(self):
        self.rubberBand.reset(QgsWkbTypes.PolygonGeometry)

    def activate(self):
        self.reset()
        
    def deactivate(self):
        self.reset()
        
    def canvasMoveEvent(self, event):
        self.rubberBand.movePoint(event.mapPoint())
        
    def canvasReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            """ Add a new point to the rubber band """
            self.rubberBand.addPoint(event.mapPoint())
        
        elif event.button() == Qt.RightButton:
            """ Send back the geometry to the calling class """
            self.polyCompleted.emit(self.rubberBand.asGeometry())
            self.reset()
        
    def isZoomTool(self):
        return False
    
    def isTransient(self):
        return False
      
    def isEditTool(self):
        return False

