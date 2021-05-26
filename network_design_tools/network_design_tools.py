# -*- coding: utf-8 -*-
"""
/***************************************************************************
 NetworkDesignTools
                                 A QGIS plugin
 Network Design Tools
 Generated by Plugin Builder: http://g-sherman.github.io/Qgis-Plugin-Builder/
                              -------------------
        begin                : 2021-02-24
        git sha              : $Format:%H$
        copyright            : (C) 2021 by ESDM
        email                : paulm@esdm.co.uk
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
import os
import subprocess
from functools import partial
from qgis.PyQt.QtCore import QSettings, QTranslator, QCoreApplication, QVariant
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction, QMessageBox, QToolButton, QMenu, QFileDialog
from qgis.core import QgsProject, QgsVectorLayer, QgsField, QgsProcessingFeatureSourceDefinition, \
                      QgsVectorLayerUtils, QgsGeometry, QgsPointXY, QgsVectorFileWriter, \
                      Qgis, QgsCoordinateTransformContext, QgsFeatureRequest, NULL
from qgis.utils import unloadPlugin
import processing

# Import generic functions
from network_design_tools import common
# Initialize Qt resources from file resources.py
from .resources import *
# Import the code for the point tool
from .map_tools import SelectDCMapTool, ConnectNodesMapTool
# Import the code for the dialog
#from .property_count_dialog import PropertyCountDialog
# Import the code to connect nodes
from .connect_points import DropCableBuilder, createNodeCable
from .update_attributes import updateNodeAttributes, updatePremisesAttributes
from .sld_export import createSLD

class NetworkDesignTools:
    """QGIS Plugin Implementation."""

    def __init__(self, iface):
        """Constructor.

        :param iface: An interface instance that will be passed to this class
            which provides the hook by which you can manipulate the QGIS
            application at run time.
        :type iface: QgsInterface
        """
        # Save reference to the QGIS interface
        self.iface = iface
        # initialize plugin directory
        self.plugin_dir = os.path.dirname(__file__)
        # initialize locale
        locale = QSettings().value('locale/userLocale')[0:2]
        locale_path = os.path.join(
            self.plugin_dir,
            'i18n',
            'NetworkDesignTools_{}.qm'.format(locale))

        if os.path.exists(locale_path):
            self.translator = QTranslator()
            self.translator.load(locale_path)
            QCoreApplication.installTranslator(self.translator)

        common.initPrerequisites(self.iface)
        if len(common.prerequisites) == 0 :
            return

        # initialize  Map Tools
        self.activeTool = None
        self.linkDCTool = SelectDCMapTool(self.iface, self.iface.mapCanvas())
        self.connectNodesTool = ConnectNodesMapTool(self.iface, self.iface.mapCanvas())

        # initialize Drop Cable Builder
        self.cableBuilder = DropCableBuilder(iface)

        # Declare instance attributes
        self.actions = []
        self.menu = self.tr(u'&Network Design Tools')

        self.toolbar = self.iface.addToolBar(u'NetworkDesignTools')
        self.toolbar.setObjectName(u'Network Design Tools')
        self.routingType = None

        self.enableSLD = True
        graphvizPath = common.prerequisites['settings']['graphvizBinPath']
        if os.path.exists(graphvizPath):
            os.environ['PATH'] += os.pathsep + graphvizPath
        else:
            QMessageBox.critical(iface.mainWindow(), 'Directory not found', 'The {0} directory could not be found. The SLD tool will be disabled.'.format(graphvizPath))
            self.enableSLD = False

        # Check if plugin was started the first time in current QGIS session
        # Must be set in initGui() to survive plugin reloads
        self.first_start = None

    # noinspection PyMethodMayBeStatic
    def tr(self, message):
        """Get the translation for a string using Qt translation API.

        We implement this ourselves since we do not inherit QObject.

        :param message: String for translation.
        :type message: str, QString

        :returns: Translated version of message.
        :rtype: QString
        """
        # noinspection PyTypeChecker,PyArgumentList,PyCallByClass
        return QCoreApplication.translate('NetworkDesignTools', message)


    def add_action(
        self,
        icon_path,
        text,
        callback,
        enabled_flag=True,
        add_to_menu=True,
        add_to_toolbar=True,
        location='Default',
        status_tip=None,
        whats_this=None,
        parent=None):
        """Add a toolbar icon to the toolbar.

        :param icon_path: Path to the icon for this action. Can be a resource
            path (e.g. ':/plugins/foo/bar.png') or a normal file system path.
        :type icon_path: str

        :param text: Text that should be shown in menu items for this action.
        :type text: str

        :param callback: Function to be called when the action is triggered.
        :type callback: function

        :param enabled_flag: A flag indicating if the action should be enabled
            by default. Defaults to True.
        :type enabled_flag: bool

        :param add_to_menu: Flag indicating whether the action should also
            be added to the menu. Defaults to True.
        :type add_to_menu: bool

        :param add_to_toolbar: Flag indicating whether the action should also
            be added to the toolbar. Defaults to True.
        :type add_to_toolbar: bool

        :param status_tip: Optional text to show in a popup when mouse pointer
            hovers over the action.
        :type status_tip: str

        :param parent: Parent widget for the new action. Defaults None.
        :type parent: QWidget

        :param whats_this: Optional text to show in the status bar when the
            mouse pointer hovers over the action.

        :returns: The action that was created. Note that the action is also
            added to self.actions list.
        :rtype: QAction
        """

        icon = QIcon(icon_path)
        action = QAction(icon, text, parent)
        action.triggered.connect(callback)
        action.setEnabled(enabled_flag)

        if status_tip is not None:
            action.setStatusTip(status_tip)

        if whats_this is not None:
            action.setWhatsThis(whats_this)

        if add_to_toolbar:
            if location == 'Default':
                # Adds plugin icon to Plugins toolbar
                self.iface.addToolBarIcon(action)
            elif location == 'Custom':
                self.toolbar.addAction(action)

        if add_to_menu:
            if location == 'Default':
                self.iface.addPluginToMenu(
                    self.menu,
                    action)
            elif location == 'CableTool':
                self.cableToolButton.menu().addAction(action)

        self.actions.append(action)

        return action

    def initGui(self):
        """Create the menu entries and toolbar icons inside the QGIS GUI."""

        icon_path = ':/plugins/network_design_tools/icon.png'
        icons_folder = ':/plugins/network_design_tools/icons'

        self.add_action(
            icon_path,
            text=self.tr(u'Network Design Tools'),
            add_to_toolbar=False,
            callback=self.run,
            parent=self.iface.mainWindow())

        self.add_action(
            icon_path,
            text=self.tr(u'Close Toolkit'),
            add_to_toolbar=False,
            callback=self.closePlugin,
            parent=self.iface.mainWindow())

        self.add_action(
            os.path.join(icons_folder,'houses.png'),
            text=self.tr(u'Count properties in a polygon'),
            add_to_menu=False,
            location='Custom',
            callback=self.CountPropertiesInAPoly,
            parent=self.iface.mainWindow())

        self.add_action(
            os.path.join(icons_folder,'house.png'),
            text=self.tr(u'Create a property count layer for properties within a primary node polygon'),
            add_to_menu=False,
            location='Custom',
            callback=self.CreatePropertyCountLayer,
            parent=self.iface.mainWindow())

        self.cableToolButton = QToolButton()
        self.cableToolButton.setMenu(QMenu())
        self.cableToolButton.setPopupMode(QToolButton.MenuButtonPopup)
        self.actions.append(self.toolbar.addWidget(self.cableToolButton))

        self.aerialCableBtn = self.add_action(
            os.path.join(icons_folder,'aerial_cable_add.png'),
            text=self.tr(u'Cable builder (Aerial)'),
            add_to_toolbar=False,
            location='CableTool',
            callback=partial(self.selectNodes, 'A'),
            parent=self.iface.mainWindow())
        self.cableToolButton.setDefaultAction(self.aerialCableBtn)

        self.ugCableBtn = self.add_action(
            os.path.join(icons_folder,'cable_add.png'),
            text=self.tr(u'Cable builder (Underground)'),
            add_to_toolbar=False,
            location='CableTool',
            callback=partial(self.selectNodes, 'UG'),
            parent=self.iface.mainWindow())

        self.linkDCBtn = self.add_action(
            os.path.join(icons_folder,'node_add.png'),
            text=self.tr(u'Drop cable builder'),
            add_to_menu=False,
            location='Custom',
            callback=self.linkDC,
            parent=self.iface.mainWindow())
        self.linkDCBtn.setCheckable(True)

        self.add_action(
            os.path.join(icons_folder,'houses_update.png'),
            text=self.tr(u'Premises attribute update'),
            add_to_menu=False,
            location='Custom',
            callback=self.UpdatePremisesAttributes,
            parent=self.iface.mainWindow())

        self.add_action(
            os.path.join(icons_folder,'node_update.png'),
            text=self.tr(u'Nodes attribute update'),
            add_to_menu=False,
            location='Custom',
            callback=self.UpdateNodeAttributes,
            parent=self.iface.mainWindow())

        self.add_action(
            os.path.join(icons_folder,'table_view.png'),
            text=self.tr(u'Create a bill of quantities'),
            add_to_menu=False,
            location='Custom',
            callback=self.CreateBillofQuantities,
            parent=self.iface.mainWindow())

        self.add_action(
            os.path.join(icons_folder,'release_sheet.png'),
            text=self.tr(u'Create release sheet'),
            add_to_menu=False,
            location='Custom',
            callback=self.CreateReleaseSheet,
            parent=self.iface.mainWindow())

        sld = self.add_action(
            os.path.join(icons_folder,'sld.png'),
            text=self.tr(u'Create straight line diagram'),
            add_to_menu=False,
            location='Custom',
            callback=self.CreateSLD,
            parent=self.iface.mainWindow())
        sld.setEnabled(self.enableSLD)

        #self.linkDCPolyTool.setAction(dropCableBtn)

        # Connect the handler for the linkDCTool click event
        self.linkDCTool.dcSelected.connect(self.selectDCObject)
        self.linkDCTool.deactivated.connect(self.resetSelectDCTool)

        # Connect the handler for the connectNodesTool click event
        self.connectNodesTool.pointsClicked.connect(self.generateCable)
        self.connectNodesTool.deactivated.connect(self.resetConnectNodesTool)

        self.cableBuilder.cablesCompleted.connect(self.finishedDCObject)

        # will be set False in run()
        self.first_start = True

    def closePlugin(self):
        unloadPlugin('network_design_tools')

    def unload(self):
        """Removes the plugin menu item and icon from QGIS GUI."""
        for action in self.actions:
            self.iface.removePluginMenu(
                self.tr(u'&Network Design Tools'),
                action)
            self.iface.removeToolBarIcon(action)

        # disconnect the link DP tool handler
        self.linkDCTool.dcSelected.disconnect(self.selectDCObject)
        self.linkDCTool.deactivated.disconnect(self.resetSelectDCTool)
        del self.linkDCTool

        # disconnect the auto cable tool handler
        self.connectNodesTool.pointsClicked.disconnect(self.generateCable)
        self.connectNodesTool.deactivated.disconnect(self.resetConnectNodesTool)
        del self.connectNodesTool

        # remove the custom toolbar
        del self.toolbar

    def run(self):
        """Run method that performs all the real work"""

        if self.first_start:
            self.first_start = False


    def selectDCObject(self, nodeId, bdryId):
        '''
        Prompt user to click on pole
        Select all address points in the SN
        For each address point:
        Draw a cable from the pole to the address point
        Select the mastermap building polygon that the address point falls inside
        Delete the part of the cable that falls inside the building
        Save the cable id against the address point
        Save the address point ID against the cable
        Populate the cable fields
        '''

        if not self.cableBuilder.is_valid:
            self.cableBuilder.check_layers()

        if self.cableBuilder.is_valid:
            self.cableBuilder.create_drop_cables(nodeId, bdryId)

    def finishedDCObject(self):      
        self.linkDCBtn.setChecked(True)
        self.linkDC()

    def UpdatePremisesAttributes(self):
        """
            check that selected poly is a PN
            select all addresspoints in it (customer properties?)
            update each addresspoint with AC??? SN TN LOC?
            Set the Length field to the length of the supply drop cable
            add these fields if not exist already?
            can this be done automatically?
        """

        layers = common.prerequisites['layers']
        AddressLayerName = layers['Premises']['name']

        bdryLyr, bdryFeat = self.getSelectedBoundary()
        if bdryLyr is None:
            return
        if bdryFeat is None:
            return

        if bdryFeat['Type'] != '1':
            QMessageBox.critical(self.iface.mainWindow(), "Wrong polygon selected", \
                "You must select a Primary node polygon from the " + bdryLyr.name() + " layer.")
            return

        reply = QMessageBox.question(self.iface.mainWindow(),'Network Design Toolkit', \
            'Update {} layer with values from {}?'.format(AddressLayerName, bdryLyr.name()))
        if reply == QMessageBox.No:
            return

        updatePremisesAttributes(self.iface, bdryLyr, bdryFeat)

    def UpdateNodeAttributes(self):
        """ Update premises/address attributes for nodes """
        updateNodeAttributes(self.iface)

    def CreateBillofQuantities(self):
        bdryLyr, bdryFeat = self.getSelectedBoundary()
        if bdryLyr is None:
            return
        if bdryFeat is None:
            return

        if bdryFeat['Type'] != '1':
            QMessageBox.critical(self.iface.mainWindow(), "Wrong polygon selected", "You must select a Primary node polygon from the " + bdryLyr.name() + " layer.")
            return

        startDir = QgsProject.instance().absolutePath()
        csvFileName = QFileDialog.getSaveFileName(caption='Save Bill of Quantities As', filter='CSV (Comma delimited) (*.csv)', directory=startDir)[0]
        if csvFileName == '':
            return

        # Get the boundary, for selecting everything else
        PNLyr = QgsVectorLayer("Polygon?crs=EPSG:27700", "Temp_Boundary", "memory")
        PNLyr.dataProvider().addFeature(bdryFeat)

        # Get the LOC boundaries
        processing.run("qgis:selectbylocation", {'INPUT':bdryLyr, 'INTERSECT':PNLyr, 'METHOD':0, 'PREDICATE':[0]})
        bdryLyr.selectByExpression('\"Type\" = \'6\'', QgsVectorLayer.SelectBehavior.IntersectSelection)

        locLyr = QgsVectorLayer("Polygon?crs=EPSG:27700", "Temp_Boundary", "memory")
        locLyr.dataProvider().addFeatures(bdryLyr.selectedFeatures())

        # Run through the required checks from the json file
        boqConfig = common.prerequisites['settings']['BillofQuantities']
        headers = boqConfig['headers']
        stats = boqConfig['stats']

        results = []
        for stat in stats.values():
            if 'Layer' in stat:
                searchLayerName = stat['Layer']
            else:
                continue

            searchLyr = common.getLayerByName(self.iface, QgsProject.instance(), searchLayerName, True)
            if searchLyr is None:
                continue

            if 'Title' in stat:
                searchName = stat['Title']
            else:
                searchName = "Untitled"

            if 'GroupTitle' in stat:
                groupTitle = stat['GroupTitle']
            else:
                groupTitle = ""

            if searchName != '' or groupTitle != '':
                results.append({headers[0]: searchName, headers[1]: groupTitle})

            if 'SummaryType' in stat:
                summaryType = stat['SummaryType']
            else:
                summaryType = 'Count'

            processing.run("qgis:selectbylocation", {'INPUT':searchLyr, 'INTERSECT':PNLyr, 'METHOD':0, 'PREDICATE':[0]})
            for calc in stat['Calculations'].values():
                if 'Title' in calc:
                    calcTitle = calc['Title']
                else:
                    calcTitle = "Untitled"

                if 'SumField' in calc:
                    sumField = calc['SumField']
                else:
                    sumField = None
                
                if 'GroupBy' in calc:
                    groupBy = calc['GroupBy']
                else:
                    groupBy = ""

                if 'Criteria' not in calc: #straight count
                    searchLyr.selectAll()
                else:
                    criteria = calc['Criteria']
                    searchLyr.selectByExpression(criteria)

                if groupBy == "":
                    if summaryType == "Count":
                        total = searchLyr.selectedFeatureCount()
                    elif summaryType == "Sum":
                        if sumField is None:
                            results.append({headers[0]:calcTitle, headers[-1]:'Invalid'})
                            continue

                        total = 0
                        try:
                            for f in searchLyr.selectedFeatures():
                                if f[sumField] != NULL:
                                    total += f[sumField]
                        except Exception as e:
                            print(type(e), e)
                            results.append({headers[0]:calcTitle, headers[-1]:'Invalid'})
                            continue
                    elif summaryType == "Length":
                        total = 0
                        for f in searchLyr.selectedFeatures():
                            total += f.geometry().length()

                    # Get records that intersect locLyr which is only the LOC polygons
                    processing.run("qgis:selectbylocation", {'INPUT':searchLyr, 'INTERSECT':locLyr, 'METHOD':0, 'PREDICATE':[0]})
                    if criteria != "":
                        searchLyr.selectByExpression(criteria, QgsVectorLayer.SelectBehavior.IntersectSelection)
                    if summaryType == "Count":
                        inLoc = searchLyr.selectedFeatureCount()
                    elif summaryType == "Sum":
                        inLoc = 0
                        for f in searchLyr.selectedFeatures():
                            if f[sumField] != NULL:
                                inLoc += f[sumField]
                    elif summaryType == "Length":
                        inLoc = 0
                        for f in searchLyr.selectedFeatures():
                            inLoc += f.geometry().length()

                    buildable = total - inLoc

                    results.append({headers[0]:calcTitle, headers[-3]:buildable, headers[-2]: inLoc, headers[-1]: total})

                else: #group by the field name, write each value+count to the csv
                    groups = {}
                    ordered = QgsFeatureRequest()
                    ordered.addOrderBy(groupBy)
                    if searchLyr.selectedFeatureCount() > 0:
                        for f in searchLyr.getSelectedFeatures(ordered):
                            try:
                                group = f[groupBy]
                            except:
                                results.append({headers[0]:calcTitle, headers[-1]:'Invalid'})
                                continue

                            if group not in groups:
                                groups[group] = {'buildable':0, 'inLoc':0, 'total':0}

                            if summaryType == "Count":
                                groups[group]['total'] += 1
                            elif summaryType == "Sum":
                                if sumField is None:
                                    results.append({headers[0]:calcTitle, headers[-1]:'Invalid'})
                                    break

                                try:
                                    groups[group]['total'] += f[sumField]
                                except:
                                    results.append({headers[0]:calcTitle, headers[-1]:'Invalid'})
                                    break
                            elif summaryType == "Length":
                                groups[group]['total'] += f.geometry().length()

                            # Get records that intersect locLyr which is only the LOC polygons
                            processing.run("qgis:selectbylocation", {'INPUT':searchLyr, 'INTERSECT':locLyr, 'METHOD':0, 'PREDICATE':[0]})
                            if summaryType == "Count":
                                groups[group]['inLoc'] += 1
                            elif summaryType == "Sum":
                                groups[group]['inLoc'] += f[sumField]
                            elif summaryType == "Length":
                                groups[group]['inLoc'] += f.geometry().length()

                            groups[group]['buildable'] = groups[group]['total'] - groups[group]['inLoc']

                        for group, val in groups.items():
                            results.append({headers[0]:calcTitle, headers[1]: group, headers[-3]:val['buildable'], \
                                            headers[-2]: val['inLoc'], headers[-1]: val['total']})
                    else:
                        results.append({headers[0]:calcTitle, headers[-3]: 0, headers[-2]: 0, headers[-1]: 0})
            searchLyr.removeSelection()

        ans = common.writeToCSV(self.iface, csvFileName, headers, results)

        if ans:
            subprocess.run(['start', csvFileName], shell=True, check=True)

    def CreatePropertyCountLayer(self):
        layers = common.prerequisites['layers']
        bdryLyr, bdryFeat = self.getSelectedBoundary()
        if bdryLyr is None:
            return
        if bdryFeat is None:
            return

        #select all properties overlapping
        tempLyr = QgsVectorLayer("Polygon?crs=EPSG:27700", "Temp_Boundary", "memory")
        tempLyr.dataProvider().addFeature(bdryFeat)

        bldLayerName = layers['Premises']['name']

        cpLyr = common.getLayerByName(self.iface, QgsProject.instance(), bldLayerName, True)
        if cpLyr is None:
            return
        processing.run("qgis:selectbylocation", {'INPUT':cpLyr, 'INTERSECT':tempLyr, 'METHOD':0, 'PREDICATE':[0]})

        tempLyr2 = QgsVectorLayer("Point?crs=EPSG:27700", "Temp_Prop", "memory")
        tempLyr2.dataProvider().addAttributes( [ QgsField("x", QVariant.Double), QgsField("y", QVariant.Double) ] )
        tempLyr2.updateFields()
        for feat in cpLyr.selectedFeatures():
            pc = QgsVectorLayerUtils.createFeature(tempLyr2)
            pc.setGeometry(feat.geometry())
            #feat.asPoint().x()
            #feat.asPoint().y()
            pc.setAttribute('x', feat['X'])
            pc.setAttribute('y', feat['Y'])
            tempLyr2.dataProvider().addFeature(pc)

        tempLyr2.commitChanges()

        PCLayerName = layers['PropertyCount']['name']
        PCCountColName = layers['PropertyCount']['fields']['Count']

        QgsProject.instance().addMapLayer(tempLyr2)

        query = "Select count(*) " + PCCountColName + ",x,y from [Temp_Prop] group by {0}".format('x,y')
        vlayer = QgsVectorLayer( "?query={}".format(query), 'counts_'+bldLayerName, "virtual" )
        #append each building to a property count layer,with a count of properties in the building
        vlayer.dataProvider().addAttributes( [ QgsField(PCCountColName, QVariant.Int) ] )
        vlayer.updateFields()

        QgsProject.instance().addMapLayer(vlayer)

        pcLyr = common.getLayerByName(self.iface, QgsProject.instance(), PCLayerName, True)
        if pcLyr is None:
            return
        pcLyr.startEditing()
        try:
            # Delete all existing features
            idList = [feat.id() for feat in pcLyr.getFeatures()]
            pcLyr.deleteFeatures(idList)

            for feat in vlayer.getFeatures():
                pc = QgsVectorLayerUtils.createFeature(pcLyr)
                gPnt = QgsGeometry.fromPointXY(QgsPointXY(feat['x'],feat['y']))
                pc.setGeometry(gPnt)#(feat.geometry())
                pc.setAttribute(PCCountColName, feat[PCCountColName])
                pcLyr.addFeature(pc)
        except Exception as e:
            print(e)

        pcLyr.commitChanges()
        pcLyr.rollBack()

        featCount = vlayer.featureCount()
        QgsProject.instance().removeMapLayer(vlayer)
        QgsProject.instance().removeMapLayer(tempLyr2)

        QMessageBox.information(self.iface.mainWindow(),'Network Design Toolkit', \
                                str(featCount) +' property counts inserted.', QMessageBox.Ok)

    def CountPropertiesInAPoly(self):
        """ The user should already have a polygon selected.
            Ensure this is the case and then send the geometry to the main function. """
        bdryLyr, bdryFeat = self.getSelectedBoundary(True)
        if bdryLyr is None:
            return
        if bdryFeat is None:
            return

        tempLyr = QgsVectorLayer("Polygon?crs=EPSG:27700", "Temp_Boundary", "memory")
        tempLyr.dataProvider().addFeature(bdryFeat)

        layers = common.prerequisites['layers']

        bldLayerName = layers['Premises']['name']

        cpLyr = common.getLayerByName(self.iface, QgsProject.instance(), bldLayerName, True)
        if cpLyr is None:
            return

        processing.run("qgis:selectbylocation", {'INPUT':cpLyr, 'INTERSECT':tempLyr, 'METHOD':0, 'PREDICATE':[0]})

        QMessageBox.information(self.iface.mainWindow(),'Network Design Toolkit', \
            str(cpLyr.selectedFeatureCount()) +' properties in this area.', QMessageBox.Ok)


    def selectNodes(self, routingType):
        # Activate cable tool if required
        # Store snappingConfig to reset afterwards
        #self.snapConfig = QgsProject.instance().snappingConfig()

        self.routingType = routingType
        if self.routingType == 'UG':
            if self.cableToolButton.defaultAction().text() != self.ugCableBtn.text():
                self.cableToolButton.setDefaultAction(self.ugCableBtn)
        else:
            if self.cableToolButton.defaultAction().text() != self.aerialCableBtn.text():
                self.cableToolButton.setDefaultAction(self.aerialCableBtn)
        if not self.cableToolButton.isDown():
            self.cableToolButton.setDown(True)

        if not self.connectNodesTool.isActive():
            self.iface.mapCanvas().setMapTool(self.connectNodesTool)
        else:
            self.connectNodesTool.reset()

    def CreateReleaseSheet(self):
        bdryLyr, bdryFeat = self.getSelectedBoundary()
        if bdryLyr is None:
            return
        if bdryFeat is None:
            return

        if bdryFeat['Type'] != '1':
            QMessageBox.critical(self.iface.mainWindow(), "Wrong polygon selected", \
                "You must select a Primary node polygon from the " + bdryLyr.name() + " layer.")
            return

        cpLyrName = common.prerequisites['layers']['Premises']['name']
        cpLyr = common.getLayerByName(self.iface, QgsProject.instance(), cpLyrName, True)

        bdrySelLyr = QgsProcessingFeatureSourceDefinition(bdryLyr.source(), selectedFeaturesOnly = True)
        processing.run("qgis:selectbylocation", { 'INPUT' : cpLyr, 'INTERSECT' : bdrySelLyr, 'METHOD' : 0, 'PREDICATE' : [6] })
        bdryLyr.removeSelection()

        if cpLyr.selectedFeatureCount() == 0:
            QMessageBox.critical(self.iface.mainWindow(), "No premises selected", "No premises were found within the selected boundary")
            return

        startDir = QgsProject.instance().absolutePath()
        csvFileName = QFileDialog.getSaveFileName(caption='Save Release Sheet As', filter='CSV (Comma delimited) (*.csv)', directory=startDir)[0]
        if csvFileName == '':
            return

        fieldIndexList = common.prerequisites['settings']['releaseSheetFieldIndexList']
        indices = fieldIndexList.split(',')
        attributeList = []
        for index in indices:
            attributeList.append(int(index))

        if Qgis.QGIS_VERSION_INT > 31003:
            saveOptions = QgsVectorFileWriter.SaveVectorOptions()
            saveOptions.attributes = attributeList
            saveOptions.driverName = "CSV"
            saveOptions.fileEncoding = "utf-8"
            saveOptions.onlySelectedFeatures = True
            errorCode, errorMsg = QgsVectorFileWriter.writeAsVectorFormatV2(cpLyr, csvFileName, QgsCoordinateTransformContext(), saveOptions)
        else:
            errorCode, errorMsg = QgsVectorFileWriter.writeAsVectorFormat(cpLyr, csvFileName, "utf-8", None, "CSV", onlySelected=True, attributes=attributeList)

        if errorCode == QgsVectorFileWriter.NoError:
            subprocess.run(['start', csvFileName], shell=True, check=True)
        else:
            QMessageBox.critical(self.iface.mainWindow(),'Network Design Toolkit', 'Failed to create release sheet.\n{}: {}'.format(errorCode, errorMsg))

    def CreateSLD(self):
        bdry_lyr, bdry_feat = self.getSelectedBoundary()
        if bdry_lyr is None or bdry_feat is None:
            return

        if bdry_feat['Type'] != '1':
            QMessageBox.critical(self.iface.mainWindow(), "Wrong polygon selected", \
                "You must select a Primary node polygon from the " + bdry_lyr.name() + " layer.")
            return

        createSLD(self.iface, bdry_lyr)

# Map Tool Event Handlers

    def linkDC(self):
        if not self.linkDCTool.isActive():
            self.iface.mapCanvas().setMapTool(self.linkDCTool)

    def resetSelectDCTool(self):
        self.linkDCBtn.setChecked(False)

    def generateCable(self, startPoint, startLayerName, startFid, endPoint, endLayerName, endFid):
        createNodeCable(self.iface, self.routingType, startPoint, startLayerName, startFid, endPoint, endLayerName, endFid)

    def resetConnectNodesTool(self):
        self.routingType = None
        self.cableToolButton.setDown(False)

# Generic methods

    def getSelectedBoundary(self, currentLayer=False):
        if currentLayer:
            bdryLyr = self.iface.mapCanvas().currentLayer()
            errTitle = 'No active layer'
            errMsg = 'Please select a single polygon feature in an active layer.'
        else:
            layers = common.prerequisites['layers']
            bdryLayerName = layers['Boundaries']['name']
            bdryLyr = common.getLayerByName(self.iface, QgsProject.instance(), bdryLayerName)
            errTitle = 'No {} layer'.format(bdryLayerName)
            errMsg = "Please select a single polygon from the " + bdryLayerName + " layer."

        if bdryLyr is None:
            QMessageBox.critical(self.iface.mainWindow(), errTitle, errMsg)
            return None, None

        if bdryLyr.selectedFeatureCount() == 0:
            errTitle = "No polygon selected"
            QMessageBox.critical(self.iface.mainWindow(), errTitle, errMsg)
            return None, None
        elif bdryLyr.selectedFeatureCount() > 1:
            errTitle = "Multiple polygons selected"
            QMessageBox.critical(self.iface.mainWindow(), errTitle, errMsg)
            return None, None

        bdryFeat = bdryLyr.selectedFeatures()[0]

        return bdryLyr, bdryFeat
