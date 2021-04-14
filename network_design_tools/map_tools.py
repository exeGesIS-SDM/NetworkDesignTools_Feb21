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
import common


class SelectDCpolyTool(QgsMapToolEmitPoint):
        
    dpSelected = pyqtSignal('QgsFeatureId', list)
    
    def __init__(self, iface, canvas):
        QgsMapToolEmitPoint.__init__(self, canvas)

        """ The user should already have a pole object selected. Ensure 
        this is the case and then send the geometry to the main 
        function. """

        self.iface = iface
        self.canvas = canvas
        print ('ere')
        layers = common.prerequisites['layers']
        poleLyrname = layers['Poles']['name']
        poleLyr = common.getLayerByName(self.iface, QgsProject.instance(), poleLyrname, True)
        if poleLyr == None: return
        
        selectedLyr = self.iface.mapCanvas().currentLayer()

        if selectedLyr == None:
            errMsg = "You must select a Pole from the " + poleLyrname + " layer."
            errTitle = 'Wrong layer selected: ' + selectedLyr.name()
            QMessageBox.critical(self.iface.mainWindow(), errTitle, errMsg)
            self.iface.setActiveLayer(poleLyr)
            return

        if selectedLyr.name() != poleLyrname:
            errMsg = "You must select a Pole from the " + poleLyrname + " layer."
            errTitle = 'Wrong layer selected: ' + selectedLyr.name()
            QMessageBox.critical(self.iface.mainWindow(), errTitle, errMsg)
            self.iface.setActiveLayer(poleLyr)
            return

        if selectedLyr.selectedFeatureCount() > 1:
            errMsg = "You must select a single Pole from the " + poleLyrname + " layer."
            errTitle = "Multiple polygons selected"
            QMessageBox.critical(self.iface.mainWindow(), errTitle, errMsg)
            self.iface.setActiveLayer(poleLyr)
            return

        self.setCursor(Qt.CrossCursor)
        self.iface = iface
        self.canvas = canvas
        # self.snapper = QgsMapCanvasSnappingUtils(self.canvas)
        self.bdryLayerName = common.prerequisites['layers']['Boundaries']['name']
        self.bdryLayer = None
        self.dpLayerName = common.prerequisites['layers']['DistributionPoints']['name']
        self.dpLayer = None
        self.dpFields = common.prerequisites['layers']['DistributionPoints']['fields']
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
                self.dpLayer = common.getLayerByName(self.iface, QgsProject.instance(), self.dpLayerName)
                if self.dpLayer != None:
                    self.crs = self.dpLayer.crs().authid()
                else:
                    self.deactivate()

            point = event.mapPoint()
            request = QgsFeatureRequest(QgsRectangle(point.x()-1,point.y()-1, point.x()+1, point.y()+1))
            # Get name of DP features by concatenating Cabinet-FibreIndex.Branch.PFDPId
            dpNames = []
            for dp in self.dpLayer.getFeatures(request):
                dpNames.append('{}-{}.{}.{}'.format(dp[self.dpFields['Cabinet']], dp[self.dpFields['FibreIndex']], dp[self.dpFields['Branch']], dp[self.dpFields['PFDPId']]))

            if len(dpNames) > 0:                
                self.dpSelected.emit(self.bdryId, dpNames)
            else:
                self.iface.messageBar().pushInfo('No Distribution Point', 'No Distribution Point at that location')
            self.reset()
        else:
            if self.bdryLayer == None:
                self.bdryLayer = common.getLayerByName(self.iface, QgsProject.instance(), self.bdryLayerName)
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
