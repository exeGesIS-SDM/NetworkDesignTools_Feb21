from qgis.core import QgsProject, QgsProcessingFeatureSourceDefinition, QgsGeometry, QgsPointXY
from qgis.PyQt.QtWidgets import QMessageBox
import processing
from network_design_tools import common

class MastermapProcessing:
    def __init__(self, iface, topoAreaName, bdryLyr, bdryId):
        self.iface = iface
        self.topoAreaParams = common.prerequisites['layers'][topoAreaName]
        self.topoAreaLyr = common.getLayerByName(iface, QgsProject.instance(), self.topoAreaParams['name'])
        self.bdryLyr = bdryLyr
        self.bdryId = bdryId
        self.initialised = False
        self.failedInitialisation = False

    def selectBuildingsWithinBoundary(self):
        try:
            self.initialised = True
            if self.topoAreaLyr is None:
                self.failedInitialisation = True
                return

            processing.run("qgis:selectbyattribute", \
                {'INPUT':self.topoAreaLyr, 'FIELD':self.topoAreaParams['fields']['descriptiveGroup'], 'METHOD':0, 'OPERATOR':0, 'VALUE':'Building'})

            self.bdryLyr.selectByExpression('$id={}'.format(self.bdryId))
            bdrySelLyr = QgsProcessingFeatureSourceDefinition(self.bdryLyr.source(), selectedFeaturesOnly = True)
            processing.run("qgis:selectbylocation", {'INPUT':self.topoAreaLyr, 'INTERSECT':bdrySelLyr, 'METHOD':2, 'PREDICATE':[0]})
            self.bdryLyr.removeSelection()

            if self.topoAreaLyr.selectedFeatureCount() == 0 :
                self.failedInitialisation = False
                QMessageBox.critical(self.iface.mainWindow(), "No MasterMap Buildings", \
                    "The selected boundary does not intersect any buildings in the {} layer. Cables will not be clipped to buildings.".format(self.topoAreaParams['name']))
        except Exception as e:
            print(type(e), e)
            self.failedInitialisation = True
            QMessageBox.critical(self.iface.mainWindow(), "MasterMap Selection Failed", \
                    "Failed to select buildings within the selected boundary. Cables will not be clipped to buildings.")

    def clipCableByBuilding(self, point, cable):
        if not self.initialised:
            self.selectBuildingsWithinBoundary()

        if self.failedInitialisation:
            return cable

        for b in self.topoAreaLyr.getSelectedFeatures():
            if b.geometry().contains(point):
                geom = b.geometry()
                if geom.isMultipart():
                    geom = geom.asGeometryCollection()[0]

                # Convert building to PolylineXY
                points = []
                for v in geom.vertices():
                    points.append(QgsPointXY(v))

                # Split cable
                try:
                    result, split_cable, _ = cable.splitGeometry(points, False)
                    if result == QgsGeometry.OperationResult.Success:
                        cable = split_cable[-1]
                except Exception as e:
                    print(type(e), e)

                return cable

        # Return original cable if does not intersect
        return cable
