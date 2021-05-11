import os
from qgis.PyQt.QtWidgets import QMessageBox, QFileDialog
from qgis.core import QgsProject, QgsProcessingFeatureSourceDefinition, QgsFeatureRequest, NULL
import processing
from network_design_tools import common
try:
    from graphviz import Graph
except ModuleNotFoundError:
    QMessageBox.critical("Graphviz missing", "graphviz python package must be installed using pip.")

def createSLD(iface, bdry_lyr):
    layers = common.prerequisites['layers']
    nodes_lyr = common.getLayerByName(iface, QgsProject.instance(), layers['Node']['name'])
    if nodes_lyr is None:
        return

    cable_lyr = common.getLayerByName(iface, QgsProject.instance(), layers['Cable']['name'])
    if cable_lyr is None:
        return

    start_dir = QgsProject.instance().absolutePath()
    file_name = QFileDialog.getSaveFileName(caption='Save SLD As', filter='SVG (Scalable Vector Graphics) (*.svg)', directory=start_dir)[0]
    if len(file_name) == 0:
        return
    dir_name = os.path.dirname(file_name)
    if not os.path.exists(dir_name):
        os.makedirs(dir_name)

    bdry_sel_lyr = QgsProcessingFeatureSourceDefinition(bdry_lyr.source(), selectedFeaturesOnly = True)
    processing.run("qgis:selectbylocation", { 'INPUT' : nodes_lyr, 'INTERSECT' : bdry_sel_lyr, 'METHOD' : 0, 'PREDICATE' : [6] })

    try:
        g = Graph('SLD', filename=os.path.splitext(os.path.basename(file_name))[0], directory=dir_name, format='svg')
    except:
        return

    node_flds = layers['Node']['fields']
    request = QgsFeatureRequest()

    # Add primary node
    g.attr('node', shape='square', size='20')
    request.setFilterExpression('\"{}\" = 1'.format(node_flds['use']))
    for node in nodes_lyr.getSelectedFeatures(request):
        g.node(node[node_flds['id']], label='UGPN')

    # Add secondary nodes
    g.attr('node', shape='square', size='12')
    request.setFilterExpression('\"{}\" = 2'.format(node_flds['use']))
    for node in nodes_lyr.getFeatures(request):
        g.node(node[node_flds['id']], label='UGSN')

    g.attr('node', shape='circle', size='12')
    request.setFilterExpression('\"{}\" = 3'.format(node_flds['use']))
    for node in nodes_lyr.getFeatures(request):
        g.node(node[node_flds['id']], label='PMSN')

    g.attr('node', shape='triangle', size='12')
    request.setFilterExpression('\"{}\" = 6'.format(node_flds['use']))
    for node in nodes_lyr.getFeatures(request):
        g.node(node[node_flds['id']], label='MSN')

    # Add tertiary nodes
    g.attr('node', shape='square', size='8')
    request.setFilterExpression('\"{}\" = 5'.format(node_flds['use']))
    for node in nodes_lyr.getFeatures(request):
        g.node(node[node_flds['id']], label='UGCE')

    g.attr('node', shape='circle', size='8')
    request.setFilterExpression('\"{}\" = 4'.format(node_flds['use']))
    for node in nodes_lyr.getFeatures(request):
        g.node(node[node_flds['id']], label='PMCE')

    g.attr('node', shape='triangle', size='8')
    request.setFilterExpression('\"{}\" = 7'.format(node_flds['use']))
    for node in nodes_lyr.getFeatures(request):
        g.node(node[node_flds['id']], label='MCE')

    #TODO: Add joints to nodes

    processing.run("qgis:selectbylocation", { 'INPUT' : cable_lyr, 'INTERSECT' : bdry_sel_lyr, 'METHOD' : 0, 'PREDICATE' : [0] })

    cable_flds = layers['Cable']['fields']
    type_index = cable_lyr.dataProvider().fieldNameIndex(cable_flds['type'])
    type_map = cable_lyr.editorWidgetSetup(type_index).config()['map']

    request.setFilterExpression('\"{}\" = 1 AND \"{}\" > 1'.format(cable_flds['feed'], cable_flds['use']))
    for cable in cable_lyr.getSelectedFeatures():
        type_label = get_type_label(type_map, cable[cable_flds['type']])
        label = '{} Cable\\n{}'.format(type_label, cable[cable_flds['label']])
        name = cable[cable_flds['name']]
        if name != NULL:
            nodes = name.split('/')
            if len(nodes) == 2:
                g.edge(nodes[0], nodes[1], label= label)

    g.attr('edge', style='dashed')
    request.setFilterExpression('\"{}\" = 2 AND \"{}\" > 1'.format(cable_flds['feed'], cable_flds['use']))
    for cable in cable_lyr.getSelectedFeatures():
        type_label = get_type_label(type_map, cable[cable_flds['type']])
        label = '{} ULW Cable\\n{}'.format(type_label, cable[cable_flds['label']])
        name = cable[cable_flds['name']]
        if name != NULL:
            nodes = name.split('/')
            if len(nodes) == 2:
                g.edge(nodes[0], nodes[1], label= label)

    g.view()

def get_type_label(type_map, type_val):
    if type_val != NULL:
        for kvp in type_map:
            if type_val in kvp:
                return kvp[type_val]

        return '({})'.format(type_val)

    return 'Unknown'
