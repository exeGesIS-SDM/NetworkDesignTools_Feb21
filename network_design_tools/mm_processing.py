from qgis.core import QgsProject, QgsProcessingFeatureSourceDefinition, QgsGeometry, QgsPointXY, QgsPoint
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

    def removeSelection(self):
        try:
            self.initialised = True
            if self.topoAreaLyr is None:
                return

            self.topoAreaLyr.removeSelection()
        except Exception as e:
            print(type(e), e)

    def clipCableByBuilding(self, point, nodePoint, orig_cable):
        if not self.initialised:
            self.selectBuildingsWithinBoundary()

        if self.failedInitialisation:
            return orig_cable

        within_building = False
        intersect_count = 0

        for b in self.topoAreaLyr.getSelectedFeatures():
            if b.geometry().contains(point):
                within_building = True
                geom = b.geometry()
                if geom.isMultipart():
                    geom = geom.asGeometryCollection()[0]

                # Convert building to PolylineXY
                points = []
                for v in geom.vertices():
                    points.append(QgsPointXY(v))

                # Split cable
                try:
                    # Create a copy as splitGeometry modifies the input geometry
                    new_cable = QgsGeometry(orig_cable)
                    result, split_cable, _ = new_cable.splitGeometry(points, False)
                    if result == QgsGeometry.OperationResult.Success:
                        new_cable = split_cable[-1]
                    else:
                        new_cable = orig_cable
                except Exception as e:
                    print(type(e), e)
                    new_cable = orig_cable

                # Replace point with nearest building point
                try:
                    nearest_point = geom.nearestPoint(nodePoint).asPoint()
                    # Create a copy as moveVertex modifies the input geometry
                    point_cable = QgsGeometry(orig_cable)
                    result = point_cable.moveVertex(QgsPoint(nearest_point), 0)
                except Exception as e:
                    print(type(e), e)
                    point_cable = orig_cable
            else:
                if b.geometry().intersects(orig_cable):
                    intersect_count += 1

        if within_building:
            if intersect_count > 0:
                return point_cable
            return new_cable

        # Return original cable if does not intersect
        return orig_cable
