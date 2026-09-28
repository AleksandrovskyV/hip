import hou, re
import xml.etree.ElementTree as ET

node = hou.pwd()
geo = node.geometry()


# expample    = "C:/Users/PC05/Desktop/earth_project/files/admin0.svg"
svg_file_path = "C:/Users/you/Desktop/earth_project/files/you.svg"

clean_attr = False
is_mapshaper = True
unclosing_tokens_list = ["graticules", "bounding", "time", "seas", "eez"]


# for custom parsing svg from "mapshaper.org", readme:
# https://github.com/AleksandrovskyV/notes/mapshaper.md

# [mapshaper attr] "uattr" > [svg tag] "<data-info>" 
# type | wikidataid | uname | uid | adm1_code | iso_3166_2

# uid - custom country idx
# adm1_code and iso_3166_2 - optional on admin1


geo.addAttrib(hou.attribType.Prim, "Cd", hou.Vector3(1, 1, 1))
if is_mapshaper:
    geo.addAttrib(hou.attribType.Prim, "shapefile", "")

    geo.addAttrib(hou.attribType.Prim, "type", "")
    geo.addAttrib(hou.attribType.Prim, "wikidata", "")
    geo.addAttrib(hou.attribType.Prim, "uname", "")
    geo.addAttrib(hou.attribType.Prim, "uid", -1)
    geo.addAttrib(hou.attribType.Prim, "adm1_code", "")
    geo.addAttrib(hou.attribType.Prim, "iso_code", "")
else:
    geo.addAttrib(hou.attribType.Prim, "pathid", "")



def _assign_tags(poly, alldata):
    # alldata = [0]=g_name, [1]=p_name, [2]=p_color, [3]=p_data

    g_name = alldata['g_name']
    p_color = alldata['p_color']
    p_data = alldata['p_data']

    tags = p_data.split('|')

    if len(tags) > 0 and is_mapshaper:
        type_str = str(tags[0])
        
        poly.setAttribValue("shapefile", g_name)

        # ne_10m_admin_1_states_provinces
        if type_str == "admin":
            poly.setAttribValue("type", type_str)
            poly.setAttribValue("wikidata", str(tags[1]))
            poly.setAttribValue("uname", str(tags[2]).replace('_', ' '))
            poly.setAttribValue("uid", int(tags[3]))
            poly.setAttribValue("adm1_code", str(tags[4])) 
            poly.setAttribValue("iso_code", str(tags[5]))  

        # special layers
        # ne_110m_graticules_30
        elif type_str in ["lines", "water", "guide"]:
            poly.setAttribValue("type", type_str)
            poly.setAttribValue("uid", int(tags[1]))
        else:
            poly.setAttribValue("type", p_data)
            poly.setAttribValue("uid", -999)
    else:
        poly.setAttribValue("pathid", alldata['p_name'])

    # Color convert HEX>RGB
    if p_color and p_color.startswith('#'):
        hex_str = p_color.lstrip('#')
        if len(hex_str) == 6:
            r = int(hex_str[0:2], 16) / 255.0
            g = int(hex_str[2:4], 16) / 255.0
            b = int(hex_str[4:6], 16) / 255.0
            poly.setAttribValue("Cd", hou.Vector3(r, g, b))


def flush_current_path(pts, closed, geometry, alldata): #
    """create poly and append attr"""
    if len(pts) < 2:
        return
        
    poly = geometry.createPolygon()
    for pt in pts:
        poly.addVertex(pt)
        
    is_special_layer = any(token in alldata['g_name'].lower() for token in unclosing_tokens_list)
    
    if is_special_layer:
        poly.setIsClosed(False)
    else:
        poly.setIsClosed(closed if len(pts) >= 3 else False)
        
    _assign_tags(poly, alldata)


try:
    tree = ET.parse(svg_file_path)
    root = tree.getroot()
    namespaces = {'svg': 'http://www.w3.org/2000/svg'}

    # 1. выбор всех <g> в файле
    groups = root.findall('.//svg:g', namespaces)
    if not groups:
        groups = root.findall('.//g')
        
    layers = groups if groups else [root]
        
    for layer in layers: # проход по всем <g> ~ layers

        # все <path> внутри группы
        paths = layer.findall('.//svg:path', namespaces)
        group_id = layer.get('id', '') # <g id=""> == layer name in mapshaper
        if not paths:
            paths = layer.findall('.//path')

        for path in paths:
            d_string = path.get('d', '')
            fill_color = path.get('fill', None)
            stroke_color = path.get('stroke', None)
            
            alldata = {
                'g_name': group_id,
                'p_name': path.get('id', group_id),
                'p_color': fill_color or stroke_color or '#ffffff',
                'p_data': path.get('data-uattr', group_id)
            }
            
            if not d_string:
                continue

            commands = re.findall(r'([MmLlHhVvCcSsQtTtAaZz])([^MmLlHhVvCcSsQtTtAaZz]*)', d_string)
            current_pts = []
            cur_x, cur_y = 0.0, 0.0
            is_closed = False 
            
            for cmd, num_str in commands:
                coords = [float(x) for x in re.findall(r'[-+]?\d*\.\d+|\d+', num_str)]
                
                if cmd in ['M', 'm']:
                    if current_pts:
                        flush_current_path(current_pts, is_closed, geo, alldata)
                        current_pts = []
                        is_closed = False 
                        
                    if len(coords) >= 2:
                        if cmd == 'M':
                            cur_x, cur_y = coords[0], -coords[1]
                        else:
                            cur_x += coords[0]
                            cur_y -= coords[1]
                            
                        pt = geo.createPoint()
                        pt.setPosition(hou.Vector3(cur_x, cur_y, 0.0))
                        current_pts.append(pt)
                        
                        for j in range(2, len(coords), 2):
                            if cmd == 'M':
                                cur_x, cur_y = coords[j], -coords[j+1]
                            else:
                                cur_x += coords[j]
                                cur_y -= coords[j+1]
                            pt = geo.createPoint()
                            pt.setPosition(hou.Vector3(cur_x, cur_y, 0.0))
                            current_pts.append(pt)
                            
                elif cmd in ['L', 'l']:
                    for j in range(0, len(coords), 2):
                        if cmd == 'L':
                            cur_x, cur_y = coords[j], -coords[j+1]
                        else:
                            cur_x += coords[j]
                            cur_y -= coords[j+1]
                        pt = geo.createPoint()
                        pt.setPosition(hou.Vector3(cur_x, cur_y, 0.0))
                        current_pts.append(pt)
                        
                elif cmd in ['Z', 'z']:
                    is_closed = True
                    if current_pts:
                        flush_current_path(current_pts, is_closed, geo, alldata)
                        current_pts = []
                    is_closed = False 

            if current_pts:
                flush_current_path(current_pts, is_closed, geo, alldata)

except Exception as e:
    raise hou.Error("Error parsing SVG geometry: " + str(e))



if clean_attr: # remove pts and prims attr
    attribs_to_delete = []
    for attr in geo.primAttribs():
        if attr.dataType() == hou.attribData.String:
            all_values = set(geo.primStringAttribValues(attr.name()))
            if all_values == set([""]) or not all_values:
                attribs_to_delete.append(attr)

    for attr in attribs_to_delete:
        attr.destroy()

    attribs_to_delete = []
    for attr in geo.pointAttribs():
        if attr.dataType() == hou.attribData.String:
            all_values = set(geo.pointStringAttribValues(attr.name()))
            if all_values == set([""]) or not all_values:
                attribs_to_delete.append(attr)

    for attr in attribs_to_delete:
        attr.destroy()