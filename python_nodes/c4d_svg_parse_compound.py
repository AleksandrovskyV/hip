# c4d_svg_parse_compound.py
# so long but work with compound pathes

import hou, re
import xml.etree.ElementTree as ET

node = hou.pwd()
geo = node.geometry()

svg_file_path = "C:/Users/....../wgs84_main_f-c4d.svg"

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


def flush_current_path(pts, closed, geometry, alldata, prim_group=None):
    """create poly and append attr"""
    if len(pts) < 2:
        return None

    poly = geometry.createPolygon()
    for pt in pts:
        poly.addVertex(pt)

    is_special_layer = False # any(token in alldata['g_name'].lower() for token in unclosing_tokens_list)

    if is_special_layer:
        poly.setIsClosed(False)
    else:
        poly.setIsClosed(closed if len(pts) >= 3 else False)

    _assign_tags(poly, alldata)

    if prim_group is not None:
        prim_group.add(poly)

    return poly


def apply_holes(geometry, prim_group):
    """make holes from enclosed polygons"""
    if prim_group is None:
        return

    if prim_group.primCount() < 2:
        return

    try:
        hole_verb = hou.sopNodeTypeCategory().nodeVerb("hole")
        hole_verb.setParms({
            "group": prim_group.name()
        })

        hole_verb.execute(geometry, [geometry])

    except Exception as e:
        raise hou.Error("Error creating SVG holes: " + str(e))


try:
    tree = ET.parse(svg_file_path)
    root = tree.getroot()
    namespaces = {'svg': 'http://www.w3.org/2000/svg'}

    # 1. выбор всех <g> в файле
    groups = root.findall('.//svg:g', namespaces)
    if not groups:
        groups = root.findall('.//g')

    layers = groups if groups else [root]
    compound_group_id = 0

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

            # SVG fill-rule
            fill_rule = path.get('fill-rule', 'nonzero').lower()
            has_fill = fill_color is None or fill_color.lower() != 'none'

            commands = re.findall(
                r'([MmLlHhVvCcSsQtTtAaZz])([^MmLlHhVvCcSsQtTtAaZz]*)',
                d_string
            )

            current_pts = []
            cur_x, cur_y = 0.0, 0.0
            is_closed = False

            path_prims = []
            compound_group = None

            if fill_rule == 'evenodd':
                compound_group_name = "svg_compound_%d" % compound_group_id
                compound_group_id += 1
                compound_group = geo.createPrimGroup(compound_group_name)

            for cmd, num_str in commands:

                coords = [
                    float(x)
                    for x in re.findall(
                        r'[-+]?\d*\.\d+|\d+',
                        num_str
                    )
                ]

                if cmd in ['M', 'm']:
                    if current_pts:
                        closed_for_fill = is_closed or has_fill

                        poly = flush_current_path(
                            current_pts,
                            closed_for_fill,
                            geo,
                            alldata,
                            compound_group
                        )

                        if poly is not None:
                            path_prims.append(poly)

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

                        poly = flush_current_path(
                            current_pts,
                            True,
                            geo,
                            alldata,
                            compound_group
                        )

                        if poly is not None:
                            path_prims.append(poly)

                        current_pts = []

                    is_closed = False

            if current_pts:

                closed_for_fill = is_closed or has_fill

                poly = flush_current_path(
                    current_pts,
                    closed_for_fill,
                    geo,
                    alldata,
                    compound_group
                )

                if poly is not None:
                    path_prims.append(poly)

            if (
                fill_rule == 'evenodd'
                and len(path_prims) > 1
                and compound_group is not None
            ):
                apply_holes(geo, compound_group)

            if compound_group is not None:
                compound_group.destroy()


except Exception as e:
    raise hou.Error("Error parsing SVG geometry: " + str(e))