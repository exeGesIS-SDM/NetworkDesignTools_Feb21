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
                    "The selected boundary does not intersect any buildings in the {} layer. Features will not be clipped to buildings.".format(self.topoAreaParams['name']))
        except Exception as e:
            print(type(e), e)
            self.failedInitialisation = True
            QMessageBox.critical(self.iface.mainWindow(), "MasterMap Selection Failed", \
                    "Failed to select buildings within the selected boundary. Features will not be clipped to buildings.")

    def removeSelection(self):
        try:
            self.initialised = True
            if self.topoAreaLyr is None:
                return

            self.topoAreaLyr.removeSelection()
        except Exception as e:
            print(type(e), e)

    def clipGeometryByBuilding(self, point, node_point, orig_geom):
        if not self.initialised:
            self.selectBuildingsWithinBoundary()

        if self.failedInitialisation:
            return orig_geom

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

                # Split geometry
                try:
                    # Create a copy as splitGeometry modifies the input geometry
                    new_geom = QgsGeometry(orig_geom)
                    result, split_geom, _ = new_geom.splitGeometry(points, False)
                    if result == QgsGeometry.OperationResult.Success:
                        new_geom = split_geom[-1]
                    else:
                        new_geom = orig_geom
                except Exception as e:
                    print(type(e), e)
                    new_geom = orig_geom

                # Replace point with nearest building point
                try:
                    nearest_point = geom.nearestPoint(node_point).asPoint()
                    # Create a copy as moveVertex modifies the input geometry
                    point_geom = QgsGeometry(orig_geom)
                    result = point_geom.moveVertex(QgsPoint(nearest_point), 0)
                except Exception as e:
                    print(type(e), e)
                    point_geom = orig_geom
            else:
                if b.geometry().intersects(orig_geom):
                    intersect_count += 1

        if within_building:
            if intersect_count > 0:
                return point_geom
            return new_geom

        # Return original geometry if does not intersect
        return orig_geom
