# c4d_svg_parse.py

import hou, re
import xml.etree.ElementTree as ET

node = hou.pwd()
geo = node.geometry()

svg_file_path = "C:/Users/PC05/Desktop/bordermap/eq_bordered/result/wgs84_main_f-c4d.svg"

geo.addAttrib(hou.attribType.Prim, "pathid", "")
geo.addAttrib(hou.attribType.Prim, "Cd", hou.Vector3(1, 1, 1))

def _assign_tags(poly, alldata):
    # alldata = [0]=g_name, [1]=p_name, [2]=p_color, [3]=p_data

    g_name = alldata['g_name']
    p_color = alldata['p_color']
    p_data = alldata['p_data']

    tags = p_data.split('|')
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
        
    is_special_layer = False #any(token in alldata['g_name'].lower() for token in unclosing_tokens_list)
    
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
        
    for layer in layers: # проход по всем <g>

        # все <path> внутри группы
        paths = layer.findall('.//svg:path', namespaces)
        group_id = layer.get('id', '') # <g id=""> 
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
