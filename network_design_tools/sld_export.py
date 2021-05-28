import os
from textwrap import wrap
from qgis.PyQt.QtWidgets import QMessageBox, QFileDialog
from qgis.core import QgsProject, QgsProcessingFeatureSourceDefinition, QgsFeatureRequest, \
                      QgsVectorLayer, NULL, QgsProcessingException
import processing
try:
    from graphviz import Graph
except ModuleNotFoundError:
    pass
from network_design_tools import common

def createSLD(iface, bdry_lyr):
    layers = common.prerequisites['layers']
    nodes_lyr = common.getLayerByName(iface, QgsProject.instance(), layers['Node']['name'])
    if nodes_lyr is None:
        return

    joints_lyr = common.getLayerByName(iface, QgsProject.instance(), layers['Joint']['name'])
    if joints_lyr is None:
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
    try:
        processing.run("qgis:selectbylocation", { 'INPUT' : nodes_lyr, 'INTERSECT' : bdry_sel_lyr, 'METHOD' : 0, 'PREDICATE' : [6] })
    except QgsProcessingException as e:
        QMessageBox.critical(iface.mainWindow(),'Selection Failure', \
                            'Failed to select Nodes. Please check geometries in Boundaries layer are valid.\nQGIS error: {}'.format(e), QMessageBox.Ok)
        return

    file_no_ext = os.path.splitext(os.path.basename(file_name))[0]
    try:
        g = Graph('SLD', filename=file_no_ext, directory=dir_name, format='svg')
    except:
        QMessageBox.critical(iface.mainWindow(), "Graphviz not installed", "graphviz python package must be installed using pip.")
        return

    node_flds = layers['Node']['fields']
    request = QgsFeatureRequest()

    # Set to draw from left to right
    g.attr(rankdir='LR', splines='ortho', ranksep='3', pad='0.25')
    g.attr('edge', fontsize='12', fontname='arial')
    g.attr('node', fontsize='12', fontname='arial')

    # Add primary node
    processing.run("qgis:selectbylocation", { 'INPUT' : nodes_lyr, 'INTERSECT' : bdry_sel_lyr, 'METHOD' : 0, 'PREDICATE' : [0] })
    nodes_lyr.selectByExpression('\"{}\" = 1'.format(node_flds['use']), QgsVectorLayer.IntersectSelection)
    for node in nodes_lyr.getSelectedFeatures():
        node_id = node[node_flds['id']]
        node_label = []
        node_label.append('<<b><table border="0" cellpadding="0" cellspacing="0">')
        node_label.append('<tr><td align="left">{}</td></tr>'.format(node_id))
        node_label.append('<tr><td align="left">{}P</td></tr>'.format(node[node_flds['premises']]))
        node_label.append('<tr><td align="left">{}</td></tr>'.format('</td></tr><tr><td align="left">'.join(wrap(node[node_flds['address']], width=25))))
        node_label.append('</table></b>>')
        with g.subgraph(name='cluster_{}'.format(node_id)) as c:
            c.attr(style='invis')
            c.node(node_id, label='UGPN', shape='square', width='1.5', height='1.5', fixedsize='shape')
            c.node('{}_L_html'.format(node_id), label=''.join(node_label), shape='plain')

    # Add joints
    joint_flds = layers['Joint']['fields']

    processing.run("qgis:selectbylocation", { 'INPUT' : joints_lyr, 'INTERSECT' : bdry_sel_lyr, 'METHOD' : 0, 'PREDICATE' : [0] })
    for joint in joints_lyr.getSelectedFeatures():
        joint_id = joint[joint_flds['id']]
        joint_label = []
        joint_label.append('<<b><table border="0" cellpadding="0" cellspacing="0">')
        joint_label.append('<tr><td align="left">{}</td></tr>'.format(joint_id))
        joint_label.append('<tr><td align="left">{}</td></tr>'.format(joint[joint_flds['size']]))
        joint_label.append('<tr><td align="left">{}</td></tr>'.format('</td></tr><tr><td align="left">'.join(wrap(joint[joint_flds['address']], width=25))))
        joint_label.append('</table></b>>')
        with g.subgraph(name='cluster_{}'.format(joint[joint_flds['id']])) as c:
            c.attr(style='invis')
            with c.subgraph(name='cluster_{}_S'.format(joint[joint_flds['id']])) as s:
                s.attr(style='dashed', margin='25')
                s.node(joint_id, label='', shape='circle', style='filled', color='black', width='0.3', height='0.3', fixedsize='shape')
            c.node('{}_L_html'.format(joint_id), label=''.join(joint_label), shape='plain')

    # Add secondary nodes
    processing.run("qgis:selectbylocation", { 'INPUT' : nodes_lyr, 'INTERSECT' : bdry_sel_lyr, 'METHOD' : 0, 'PREDICATE' : [0] })
    nodes_lyr.selectByExpression('\"{}\" IN (2, 5, 6, 7)'.format(node_flds['use']), QgsVectorLayer.IntersectSelection)
    for node in nodes_lyr.getSelectedFeatures():
        node_id = node[node_flds['id']]
        node_label = []
        node_label.append('<<b><table border="0" cellpadding="0" cellspacing="0">')
        node_label.append('<tr><td align="left"><font color="red">{}F</font></td></tr>'.format(node[node_flds['splitters_1_8']]))
        node_label.append('<tr><td align="left">{}</td></tr>'.format(node_id))
        node_label.append('<tr><td align="left">{}x1:8 ({}P)</td></tr>'.format(node[node_flds['splitters_1_8']], node[node_flds['premises']]))
        node_label.append('<tr><td align="left">{}</td></tr>'.format('</td></tr><tr><td align="left">'.join(wrap(node[node_flds['address']], width=25))))
        node_label.append('</table></b>>')
        with g.subgraph(name='cluster_{}'.format(node_id)) as c:
            c.attr(style='invis', nodesep='0.02')
            if node[node_flds['use']] == 2:
                c.node(node_id, label='UGSN', shape='square', width='1', height='1', fixedsize='shape')
            elif node[node_flds['use']] == 5:
                c.node(node_id, label='UGCE', shape='square', width='1', height='1', fixedsize='shape')
            elif node[node_flds['use']] == 6:
                c.node(node_id, label='MSN', shape='square', width='1', height='1', fixedsize='shape')
            else:
                c.node(node_id, label='MCE', shape='square', width='1', height='1', fixedsize='shape')
            c.node('{}_L_html'.format(node_id), label=''.join(node_label), shape='plain')

    processing.run("qgis:selectbylocation", { 'INPUT' : nodes_lyr, 'INTERSECT' : bdry_sel_lyr, 'METHOD' : 0, 'PREDICATE' : [0] })
    nodes_lyr.selectByExpression('\"{}\" in (3, 4)'.format(node_flds['use']), QgsVectorLayer.IntersectSelection)
    for node in nodes_lyr.getSelectedFeatures():
        node_id = node[node_flds['id']]
        node_label = []
        node_label.append('<<b><table border="0" cellpadding="0" cellspacing="0">')
        node_label.append('<tr><td align="left"><font color="red">{}F</font></td></tr>'.format(node[node_flds['splitters_1_8']]))
        node_label.append('<tr><td align="left">{}</td></tr>'.format(node_id))
        node_label.append('<tr><td align="left">{}x1:8 ({}P)</td></tr>'.format(node[node_flds['splitters_1_8']], node[node_flds['premises']]))
        node_label.append('<tr><td align="left">{}</td></tr>'.format('</td></tr><tr><td align="left">'.join(wrap(node[node_flds['address']], width=25))))
        node_label.append('</table></b>>')
        with g.subgraph(name='cluster_{}'.format(node_id)) as c:
            c.attr(style='invis', nodesep='0.02')
            if node[node_flds['use']] == 3:
                c.node(node_id, label='PMSN', shape='circle', width='1', height='1', fixedsize='shape')
            else:
                c.node(node_id, label='PMCE', shape='circle', width='1', height='1', fixedsize='shape')
            c.node('{}_L_html'.format(node_id), label=''.join(node_label), shape='plain')

    nodes_lyr.removeSelection()

    cable_flds = layers['Cable']['fields']
    type_index = cable_lyr.dataProvider().fieldNameIndex(cable_flds['type'])
    type_map = cable_lyr.editorWidgetSetup(type_index).config()['map']

    processing.run("qgis:selectbylocation", { 'INPUT' : cable_lyr, 'INTERSECT' : bdry_sel_lyr, 'METHOD' : 0, 'PREDICATE' : [0] })
    cable_lyr.selectByExpression('"{}" = 1 AND \"{}\" > 1'.format(cable_flds['feed'], cable_flds['use']), QgsVectorLayer.IntersectSelection)
    for cable in cable_lyr.getSelectedFeatures():
        type_label = get_value_text(type_map, cable[cable_flds['type']])
        label = '{} Cable\n{}'.format(type_label, cable[cable_flds['label']])
        nodes = get_node_ids(cable[cable_flds['name']])
        if len(nodes) == 2:
            g.edge(nodes[0], nodes[1], xlabel=label)

    g.attr('edge', style='dashed')
    processing.run("qgis:selectbylocation", { 'INPUT' : cable_lyr, 'INTERSECT' : bdry_sel_lyr, 'METHOD' : 0, 'PREDICATE' : [0] })
    cable_lyr.selectByExpression('"{}" = 2 AND \"{}\" > 1'.format(cable_flds['feed'], cable_flds['use']), QgsVectorLayer.IntersectSelection)
    for cable in cable_lyr.getSelectedFeatures(request):
        type_label = get_value_text(type_map, cable[cable_flds['type']])
        label = '{} ULW Cable\n{}'.format(type_label, cable[cable_flds['label']])
        nodes = get_node_ids(cable[cable_flds['name']])
        if len(nodes) == 2:
            g.edge(nodes[0], nodes[1], xlabel=label)

    cable_lyr.removeSelection()
    #try:
    g.view(cleanup=True)
    #except Exception as e:
    #    print(type(e), e)
    #    QMessageBox.critical(iface.mainWindow(), "Graphviz missing", "Graphviz executables must be installed and the settings > " + \
    #                                             "graphvizBinPath set to the correct path in the prerequisites.")

def get_node_ids(name):
    node_ids = []
    if name == NULL:
        return node_ids

    node_names = name.split('/')

    if len(node_names) != 2:
        return node_ids

    node_ids.append(node_names[0])

    # Cable names are shortened to remove duplicate text, get name prefix for end node
    start_split = node_names[0].split('-')
    start_split.pop()

    end_split = node_names[1].split('-')

    prefix = []
    for word in start_split:
        if word not in end_split:
            prefix.append(word)

    if len(prefix) > 0:
        node_ids.append('{}-{}'.format('-'.join(prefix),node_names[1]))
    else:
        node_ids.append(node_names[1])

    return node_ids

def get_value_text(type_map, type_val):
    if type_val != NULL:
        for kvp in type_map:
            for key, value in kvp.items():
                if value == str(type_val):
                    return key

        return '({})'.format(type_val)

    return 'Unknown'
