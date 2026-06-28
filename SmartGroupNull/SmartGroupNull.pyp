"""Smart Group Select for Cinema 4D 2025.2.

Marks Null objects as selectable group roots. When the global switch and the
per-tag switch are enabled, selecting any child object automatically selects
the nearest enabled marked Null. The tag also draws a viewport bounding box for
the group's descendants.
"""

import c4d
import os
import time
from c4d import documents, plugins


# Local development IDs. For public distribution, replace these with IDs from
# https://developers.maxon.net/forum/pid
PLUGIN_ID_TAG = 1069201
PLUGIN_ID_MSG = 1069202
PLUGIN_ID_CMD_MARK = 1069203
PLUGIN_ID_CMD_UNMARK = 1069204
PLUGIN_ID_CMD_TOGGLE_GLOBAL = 1069205
PLUGIN_ID_CMD_TOGGLE_SELECTED = 1069206
PLUGIN_ID_CMD_AXIS_BOTTOM = 1069207
PLUGIN_ID_CMD_AXIS_BOTTOM_GROUND = 1069208
PLUGIN_ID_CMD_OCTANE_LIGHT_MASK = 1069209

Tsmartgroupnulltag = PLUGIN_ID_TAG
SGN_TAG_ENABLE = 1000
SGN_TAG_SHOW_BOX = 1001
SGN_TAG_BOX_COLOR = 1002
SGN_TAG_PADDING = 1003

SGN_GLOBAL_ENABLED = 2000

DEFAULT_COLOR = c4d.Vector(0.0, 0.75, 1.0)
DEFAULT_PADDING = 0.0
TIMER_MS = 120
BBOX_REFRESH_SECONDS = 1.5
BOUNDARY_HELPER_NAME = "__SGN_Boundary_Box"
BOUNDARY_LAYER_NAME = "SGN Boundary Helpers"

ID_OCTANE_OBJECTTAG = 1029603
OBJECTTAG_USE_LGHT_MASK = 1326
OBJECTTAG_LGHT_MASK_ENABLE = 1327
OBJECTTAG_LIGHTID_S = 1329
OBJECTTAG_LIGHTID_E = 1330
OBJECTTAG_LIGHTID_IDS = {
    1: 1331,
    2: 1332,
    3: 1333,
    4: 1334,
    5: 1335,
    6: 1336,
    7: 1337,
    8: 1338,
    9: 1345,
    10: 1346,
    11: 1347,
    12: 1348,
    13: 1349,
    14: 1350,
    15: 1351,
    16: 1352,
    17: 1353,
    18: 1354,
    19: 1355,
    20: 1356,
    21: 1357,
    22: 1358,
    23: 1359,
    24: 1360,
    25: 1361,
    26: 1362,
    27: 1363,
    28: 1364,
    29: 1365,
    30: 1366,
    31: 1367,
    32: 1368,
}

DLG_LIGHT_MASK_SUN = 4100
DLG_LIGHT_MASK_ENV = 4101
DLG_LIGHT_MASK_ID_BASE = 4200
DLG_LIGHT_MASK_ALL = 4300
DLG_LIGHT_MASK_CLEAR = 4301

GROUP_COLORS = (
    c4d.Vector(0.00, 0.75, 1.00),  # cyan
    c4d.Vector(1.00, 0.38, 0.26),  # coral
    c4d.Vector(0.52, 0.92, 0.30),  # green
    c4d.Vector(1.00, 0.78, 0.18),  # amber
    c4d.Vector(0.62, 0.48, 1.00),  # violet
    c4d.Vector(1.00, 0.36, 0.70),  # pink
    c4d.Vector(0.18, 0.86, 0.72),  # mint
    c4d.Vector(0.38, 0.62, 1.00),  # blue
    c4d.Vector(1.00, 0.56, 0.16),  # orange
    c4d.Vector(0.76, 0.94, 0.12),  # lime
)

_selection_guard = False
_last_selection_signature = None
_bbox_cache = {}
_bbox_refresh_index = 0


def load_icon(filename):
    path = os.path.join(os.path.dirname(__file__), "icons", filename)
    bmp = c4d.bitmaps.BaseBitmap()

    result = bmp.InitWith(path)
    if isinstance(result, tuple):
        result = result[0]

    if result != c4d.IMAGERESULT_OK:
        return None
    return bmp


def get_global_enabled():
    bc = plugins.GetWorldPluginData(PLUGIN_ID_CMD_TOGGLE_GLOBAL)
    if bc is None or not bc.GetBool(SGN_GLOBAL_ENABLED, True):
        return False
    return True


def set_global_enabled(value):
    bc = plugins.GetWorldPluginData(PLUGIN_ID_CMD_TOGGLE_GLOBAL) or c4d.BaseContainer()
    bc.SetBool(SGN_GLOBAL_ENABLED, bool(value))
    plugins.SetWorldPluginData(PLUGIN_ID_CMD_TOGGLE_GLOBAL, bc, add=True)


def get_smart_tag(op):
    if op is None:
        return None

    tag = op.GetFirstTag()
    while tag:
        if tag.CheckType(PLUGIN_ID_TAG):
            return tag
        tag = tag.GetNext()
    return None


def iter_objects(root):
    current = root
    while current:
        yield current
        child = current.GetDown()
        if child:
            yield from iter_objects(child)
        current = current.GetNext()


def iter_smart_tags(doc):
    if doc is None:
        return

    first = doc.GetFirstObject()
    if first is None:
        return

    for op in iter_objects(first):
        tag = get_smart_tag(op)
        if tag:
            yield tag


def next_group_color(doc):
    count = sum(1 for _ in iter_smart_tags(doc))
    return GROUP_COLORS[count % len(GROUP_COLORS)]


def is_tag_enabled(tag):
    return bool(tag and tag[SGN_TAG_ENABLE])


def find_enabled_group_root(op):
    current = op
    while current:
        tag = get_smart_tag(current)
        if is_tag_enabled(tag):
            return current
        current = current.GetUp()
    return None


def find_smart_group_root(op):
    current = op
    while current:
        if is_boundary_helper(current):
            current = current.GetUp()
            continue

        tag = get_smart_tag(current)
        if tag:
            return current, tag
        current = current.GetUp()
    return None, None


def object_key(op):
    if op is None:
        return None
    try:
        return str(op.GetGUID())
    except Exception:
        return str(id(op))


def clear_bbox_cache():
    _bbox_cache.clear()


def read_cached_bbox(tag):
    """Reads the root-local bbox cache without recomputing in the draw pass."""
    key = object_key(tag)
    cached = _bbox_cache.get(key)
    if not cached:
        return None
    return cached["bbox"]


def get_tag_host(tag):
    try:
        return tag.GetObject()
    except Exception:
        return None


def is_boundary_helper(op):
    if op is None:
        return False
    name = op.GetName()
    return name == BOUNDARY_HELPER_NAME or name.startswith(BOUNDARY_HELPER_NAME + "_")


def get_boundary_helper(root):
    child = root.GetDown() if root else None
    while child:
        if is_boundary_helper(child):
            return child
        child = child.GetNext()
    return None


def set_object_color(op, color):
    if op is None:
        return
    try:
        op[c4d.ID_BASEOBJECT_USECOLOR] = c4d.ID_BASEOBJECT_USECOLOR_ALWAYS
        op[c4d.ID_BASEOBJECT_COLOR] = color
    except Exception:
        pass


def set_object_hidden_from_render(op):
    if op is None:
        return
    try:
        op[c4d.ID_BASEOBJECT_VISIBILITY_RENDER] = c4d.OBJECT_OFF
    except Exception:
        pass


def set_helper_visibility(op):
    if op is None:
        return
    try:
        op[c4d.ID_BASEOBJECT_VISIBILITY_RENDER] = c4d.OBJECT_OFF
        op[c4d.ID_BASEOBJECT_VISIBILITY_EDITOR] = c4d.OBJECT_ON
    except Exception:
        pass
    try:
        op[c4d.ID_BASEOBJECT_XRAY] = True
    except Exception:
        pass


def iter_layers(layer):
    current = layer
    while current:
        yield current
        child = current.GetDown()
        if child:
            yield from iter_layers(child)
        current = current.GetNext()


def get_first_layer(layer_root):
    if layer_root is None:
        return None

    try:
        return layer_root.GetDown()
    except Exception:
        pass

    try:
        children = layer_root.GetChildren()
        return children[0] if children else None
    except Exception:
        return None


def configure_boundary_layer(doc, layer):
    if doc is None or layer is None:
        return

    data = {
        "solo": False,
        "view": True,
        "render": True,
        "manager": False,
        "locked": False,
        "generators": True,
        "expressions": True,
        "animation": True,
        "color": DEFAULT_COLOR,
        "xref": True,
    }

    try:
        layer.SetLayerData(doc, data)
    except Exception:
        pass


def get_or_create_boundary_layer(doc):
    if doc is None:
        return None

    layer_root = doc.GetLayerObjectRoot()
    if layer_root is None:
        return None

    first = get_first_layer(layer_root)
    for layer in iter_layers(first):
        if layer.GetName() == BOUNDARY_LAYER_NAME:
            return layer

    layer = documents.LayerObject()
    layer.SetName(BOUNDARY_LAYER_NAME)
    layer.InsertUnder(layer_root)
    configure_boundary_layer(doc, layer)
    return layer


def assign_boundary_layer(root, helper):
    if root is None or helper is None:
        return

    try:
        doc = root.GetDocument()
    except Exception:
        doc = documents.GetActiveDocument()

    layer = get_or_create_boundary_layer(doc)
    if layer is None:
        return

    try:
        helper.SetLayerObject(layer)
    except Exception:
        try:
            helper[c4d.ID_LAYER_LINK] = layer
        except Exception:
            pass


def apply_wire_display(op):
    if op is None:
        return

    tag = op.GetTag(c4d.Tdisplay)
    if tag is None:
        tag = c4d.BaseTag(c4d.Tdisplay)
        if tag:
            op.InsertTag(tag)

    if tag is None:
        return

    try:
        tag[c4d.DISPLAYTAG_AFFECT_DISPLAYMODE] = True
        tag[c4d.DISPLAYTAG_SDISPLAYMODE] = c4d.DISPLAYTAG_SDISPLAY_NOSHADING
        tag[c4d.DISPLAYTAG_WDISPLAYMODE] = c4d.DISPLAYTAG_WDISPLAY_WIREFRAME
    except Exception:
        pass


def make_boundary_helper(root, color):
    helper = get_boundary_helper(root)
    if helper:
        if not helper.CheckType(c4d.Ocube):
            helper.Remove()
            helper = None
        else:
            set_object_color(helper, color)
            apply_wire_display(helper)
            assign_boundary_layer(root, helper)
            return helper

    if helper:
        set_object_color(helper, color)
        return helper

    helper = c4d.BaseObject(c4d.Ocube)
    if helper is None:
        return None

    helper.SetName(BOUNDARY_HELPER_NAME)
    helper.SetMl(c4d.Matrix())
    set_object_color(helper, color)
    set_helper_visibility(helper)
    apply_wire_display(helper)

    helper.InsertUnderLast(root)
    assign_boundary_layer(root, helper)
    return helper


def remove_boundary_helper(root):
    helper = get_boundary_helper(root)
    if helper:
        helper.Remove()


def boundary_points_from_bbox(bbox, padding):
    corners = bbox_corners(bbox[0], bbox[1], padding)
    edges = (
        (0, 1), (1, 2), (2, 3), (3, 0),
        (4, 5), (5, 6), (6, 7), (7, 4),
        (0, 4), (1, 5), (2, 6), (3, 7),
    )
    points = []
    for a, b in edges:
        points.append(corners[a])
        points.append(corners[b])
    return points


def boundary_edges_from_bbox(bbox, padding):
    corners = bbox_corners(bbox[0], bbox[1], padding)
    edges = (
        (0, 1), (1, 2), (2, 3), (3, 0),
        (4, 5), (5, 6), (6, 7), (7, 4),
        (0, 4), (1, 5), (2, 6), (3, 7),
    )
    return [(corners[a], corners[b]) for a, b in edges]


def update_boundary_helper(tag, root, bbox):
    if root is None:
        return

    if not get_global_enabled() or not tag[SGN_TAG_ENABLE] or not tag[SGN_TAG_SHOW_BOX] or bbox is None:
        remove_boundary_helper(root)
        return

    helper = make_boundary_helper(root, tag[SGN_TAG_BOX_COLOR] or DEFAULT_COLOR)
    if helper is None:
        return

    set_object_color(helper, tag[SGN_TAG_BOX_COLOR] or DEFAULT_COLOR)
    set_helper_visibility(helper)
    apply_wire_display(helper)
    assign_boundary_layer(root, helper)

    min_v, max_v = bbox
    padding = max(0.0, tag[SGN_TAG_PADDING])
    min_v = min_v - c4d.Vector(padding)
    max_v = max_v + c4d.Vector(padding)
    center = (min_v + max_v) * 0.5
    size = max_v - min_v

    try:
        helper[c4d.PRIM_CUBE_LEN] = c4d.Vector(max(size.x, 0.01), max(size.y, 0.01), max(size.z, 0.01))
    except Exception:
        pass

    helper.SetRelPos(center)
    helper.SetRelRot(c4d.Vector())
    helper.SetRelScale(c4d.Vector(1.0))
    helper.Message(c4d.MSG_UPDATE)


def update_bbox_cache_for_tag(tag, root, force=False):
    key = object_key(tag)
    now = time.monotonic()
    cached = _bbox_cache.get(key)
    if cached and not force and now - cached["time"] < BBOX_REFRESH_SECONDS:
        return

    bbox = collect_descendant_bbox(root)
    if bbox is None and cached:
        cached["time"] = now
        return

    _bbox_cache[key] = {
        "time": now,
        "bbox": bbox,
    }
    update_boundary_helper(tag, root, bbox)


def update_bbox_cache(doc):
    """Refreshes at most one stale group boundary helper per timer tick."""
    global _bbox_refresh_index

    if doc is None:
        return

    groups = []
    live_keys = set()

    for tag in iter_smart_tags(doc):
        key = object_key(tag)
        live_keys.add(key)

        root = get_tag_host(tag)
        if root is None:
            continue
        if not get_global_enabled() or not tag[SGN_TAG_ENABLE] or not tag[SGN_TAG_SHOW_BOX]:
            remove_boundary_helper(root)
            continue
        groups.append((tag, root))

    for key in list(_bbox_cache.keys()):
        if key not in live_keys:
            _bbox_cache.pop(key, None)

    if not groups:
        return

    now = time.monotonic()
    count = len(groups)
    start = _bbox_refresh_index % count

    for offset in range(count):
        index = (start + offset) % count
        tag, root = groups[index]
        cached = _bbox_cache.get(object_key(tag))
        if cached is None or now - cached["time"] >= BBOX_REFRESH_SECONDS:
            update_bbox_cache_for_tag(tag, root, force=True)
            _bbox_refresh_index = (index + 1) % count
            return

    _bbox_refresh_index = (start + 1) % count


def get_selection_signature(active_objects):
    return tuple(object_key(op) for op in active_objects)


def collect_descendant_bbox(root):
    """Returns root-local min/max vectors for renderable descendants."""
    if root is None:
        return None

    points = []
    root_inv = ~root.GetMg()

    def add_object_bbox(op):
        if op is None:
            return
        if is_boundary_helper(op):
            return

        has_box = False

        # Nulls usually have no useful radius; still traverse their children.
        if not op.CheckType(c4d.Onull):
            mp = op.GetMp()
            rad = op.GetRad()
            if rad.x != 0.0 or rad.y != 0.0 or rad.z != 0.0:
                has_box = True
                mg = op.GetMg()
                for sx in (-1.0, 1.0):
                    for sy in (-1.0, 1.0):
                        for sz in (-1.0, 1.0):
                            world_point = mg * (mp + c4d.Vector(rad.x * sx, rad.y * sy, rad.z * sz))
                            points.append(root_inv * world_point)

        # Generated/deformed caches are expensive to traverse. Only use them
        # when the object itself exposes no usable bounding box.
        cache = None if has_box else (op.GetDeformCache() or op.GetCache())
        if cache:
            add_object_bbox(cache)

        child = op.GetDown()
        while child:
            add_object_bbox(child)
            child = child.GetNext()

    child = root.GetDown()
    while child:
        add_object_bbox(child)
        child = child.GetNext()

    if not points:
        return None

    min_v = c4d.Vector(points[0])
    max_v = c4d.Vector(points[0])
    for point in points[1:]:
        min_v.x = min(min_v.x, point.x)
        min_v.y = min(min_v.y, point.y)
        min_v.z = min(min_v.z, point.z)
        max_v.x = max(max_v.x, point.x)
        max_v.y = max(max_v.y, point.y)
        max_v.z = max(max_v.z, point.z)

    return min_v, max_v


def collect_descendant_world_bbox(root):
    """Returns world-space min/max vectors for renderable descendants."""
    if root is None:
        return None

    points = []

    def add_object_bbox(op):
        if op is None:
            return
        if is_boundary_helper(op):
            return

        has_box = False

        if not op.CheckType(c4d.Onull):
            mp = op.GetMp()
            rad = op.GetRad()
            if rad.x != 0.0 or rad.y != 0.0 or rad.z != 0.0:
                has_box = True
                mg = op.GetMg()
                for sx in (-1.0, 1.0):
                    for sy in (-1.0, 1.0):
                        for sz in (-1.0, 1.0):
                            points.append(mg * (mp + c4d.Vector(rad.x * sx, rad.y * sy, rad.z * sz)))

        cache = None if has_box else (op.GetDeformCache() or op.GetCache())
        if cache:
            add_object_bbox(cache)

        child = op.GetDown()
        while child:
            add_object_bbox(child)
            child = child.GetNext()

    child = root.GetDown()
    while child:
        add_object_bbox(child)
        child = child.GetNext()

    if not points:
        return None

    min_v = c4d.Vector(points[0])
    max_v = c4d.Vector(points[0])
    for point in points[1:]:
        min_v.x = min(min_v.x, point.x)
        min_v.y = min(min_v.y, point.y)
        min_v.z = min(min_v.z, point.z)
        max_v.x = max(max_v.x, point.x)
        max_v.y = max(max_v.y, point.y)
        max_v.z = max(max_v.z, point.z)

    return min_v, max_v


def bbox_corners(min_v, max_v, padding, matrix=None):
    p = max(0.0, padding)
    min_v = min_v - c4d.Vector(p)
    max_v = max_v + c4d.Vector(p)
    corners = [
        c4d.Vector(min_v.x, min_v.y, min_v.z),
        c4d.Vector(max_v.x, min_v.y, min_v.z),
        c4d.Vector(max_v.x, max_v.y, min_v.z),
        c4d.Vector(min_v.x, max_v.y, min_v.z),
        c4d.Vector(min_v.x, min_v.y, max_v.z),
        c4d.Vector(max_v.x, min_v.y, max_v.z),
        c4d.Vector(max_v.x, max_v.y, max_v.z),
        c4d.Vector(min_v.x, max_v.y, max_v.z),
    ]

    if matrix is not None:
        corners = [matrix * point for point in corners]

    return corners


def draw_bbox(bd, corners, color):
    edges = (
        (0, 1), (1, 2), (2, 3), (3, 0),
        (4, 5), (5, 6), (6, 7), (7, 4),
        (0, 4), (1, 5), (2, 6), (3, 7),
    )

    bd.SetMatrix_Matrix(None, c4d.Matrix())
    bd.SetPen(color)
    try:
        bd.SetDepth(True)
    except Exception:
        pass
    for a, b in edges:
        bd.DrawLine(corners[a], corners[b], c4d.NOCLIP_D)


def add_smart_tag(op, color=None):
    tag = get_smart_tag(op)
    if tag:
        return tag

    tag = c4d.BaseTag(PLUGIN_ID_TAG)
    if tag is None:
        return None

    tag[SGN_TAG_ENABLE] = True
    tag[SGN_TAG_SHOW_BOX] = True
    tag[SGN_TAG_BOX_COLOR] = color or DEFAULT_COLOR
    tag[SGN_TAG_PADDING] = DEFAULT_PADDING
    op.InsertTag(tag)
    return tag


def selected_objects(doc):
    return doc.GetActiveObjects(c4d.GETACTIVEOBJECTFLAGS_NONE)


def get_octane_object_tag(op):
    if op is None:
        return None

    tag = op.GetFirstTag()
    while tag:
        if tag.CheckType(ID_OCTANE_OBJECTTAG):
            return tag
        tag = tag.GetNext()
    return None


def get_or_add_octane_object_tag(doc, op):
    tag = get_octane_object_tag(op)
    if tag:
        return tag, False

    tag = c4d.BaseTag(ID_OCTANE_OBJECTTAG)
    if tag is None:
        return None, False

    op.InsertTag(tag)
    if doc:
        doc.AddUndo(c4d.UNDOTYPE_NEWOBJ, tag)
    return tag, True


def apply_octane_light_mask(doc, objects, selected_ids, include_sun=False, include_env=False):
    if not objects:
        return 0

    selected_ids = set(selected_ids)
    changed = 0

    doc.StartUndo()
    try:
        for op in objects:
            if op is None or is_boundary_helper(op):
                continue

            doc.AddUndo(c4d.UNDOTYPE_CHANGE, op)
            tag, _created = get_or_add_octane_object_tag(doc, op)
            if tag is None:
                continue

            doc.AddUndo(c4d.UNDOTYPE_CHANGE, tag)
            tag[OBJECTTAG_USE_LGHT_MASK] = OBJECTTAG_LGHT_MASK_ENABLE
            tag[OBJECTTAG_LIGHTID_S] = bool(include_sun)
            tag[OBJECTTAG_LIGHTID_E] = bool(include_env)

            for light_id, param_id in OBJECTTAG_LIGHTID_IDS.items():
                tag[param_id] = light_id in selected_ids

            tag.Message(c4d.MSG_UPDATE)
            changed += 1
    finally:
        doc.EndUndo()

    c4d.EventAdd()
    return changed


def selected_smart_roots(doc):
    roots = []
    seen = set()
    for op in selected_objects(doc):
        root, tag = find_smart_group_root(op)
        if root is None or tag is None:
            continue
        key = object_key(root)
        if key in seen:
            continue
        seen.add(key)
        roots.append((root, tag))
    return roots


def direct_children(op, include_helpers=False):
    children = []
    child = op.GetDown() if op else None
    while child:
        if include_helpers or not is_boundary_helper(child):
            children.append(child)
        child = child.GetNext()
    return children


def move_axis_to_bottom_center(doc, root, tag):
    bbox = collect_descendant_world_bbox(root)
    if bbox is None:
        return None

    min_v, max_v = bbox
    axis_world = c4d.Vector(
        (min_v.x + max_v.x) * 0.5,
        min_v.y,
        (min_v.z + max_v.z) * 0.5,
    )

    old_mg = root.GetMg()
    delta = axis_world - old_mg.off
    if abs(delta.x) < 0.0001 and abs(delta.y) < 0.0001 and abs(delta.z) < 0.0001:
        update_bbox_cache_for_tag(tag, root, force=True)
        return old_mg

    new_mg = c4d.Matrix()
    new_mg.off = axis_world
    new_mg.v1 = old_mg.v1
    new_mg.v2 = old_mg.v2
    new_mg.v3 = old_mg.v3

    children = direct_children(root, include_helpers=True)
    new_root_inv = ~new_mg
    child_local_matrices = [(child, new_root_inv * child.GetMg()) for child in children]

    doc.AddUndo(c4d.UNDOTYPE_CHANGE, root)
    root.SetMg(new_mg)

    for child, child_ml in child_local_matrices:
        doc.AddUndo(c4d.UNDOTYPE_CHANGE, child)
        child.SetMl(child_ml)

    update_bbox_cache_for_tag(tag, root, force=True)
    return new_mg


def get_ordered_selection(doc):
    active = selected_objects(doc)
    if not active:
        return active

    first = doc.GetActiveObject()
    if first is None or first not in active:
        return active

    return [first] + [op for op in active if op is not first]


class SmartGroupTag(plugins.TagData):
    def Init(self, node, isCloneInit=False):
        node[SGN_TAG_ENABLE] = True
        node[SGN_TAG_SHOW_BOX] = True
        node[SGN_TAG_BOX_COLOR] = DEFAULT_COLOR
        node[SGN_TAG_PADDING] = DEFAULT_PADDING
        return True

    def Draw(self, tag, op, bd, bh):
        return c4d.DRAWRESULT_OK


class SmartGroupWatcher(plugins.MessageData):
    def CoreMessage(self, mid, bc):
        if mid != c4d.MSG_TIMER:
            return True
        doc = documents.GetActiveDocument()
        update_bbox_cache(doc)
        process_selection(doc)
        return True

    def GetTimer(self):
        return TIMER_MS


def process_selection(doc=None):
    global _selection_guard, _last_selection_signature

    if _selection_guard or not get_global_enabled():
        return

    doc = doc or documents.GetActiveDocument()
    if doc is None:
        return

    # Keep component editing undisturbed, but allow both object and model modes.
    try:
        if doc.IsEditMode():
            return
    except Exception:
        pass

    active = get_ordered_selection(doc)
    signature = get_selection_signature(active)
    if signature == _last_selection_signature:
        return

    replacement = []
    seen = set()
    changed = False

    for op in active:
        root = find_enabled_group_root(op)
        target = root or op
        key = object_key(target)
        if key not in seen:
            seen.add(key)
            replacement.append(target)
        if target is not op:
            changed = True

    _last_selection_signature = signature
    if not changed or not replacement:
        return

    _selection_guard = True
    try:
        doc.SetActiveObject(None, c4d.SELECTION_NEW)
        doc.SetActiveObject(replacement[0], c4d.SELECTION_NEW)
        for op in replacement[1:]:
            doc.SetActiveObject(op, c4d.SELECTION_ADD)
        _last_selection_signature = get_selection_signature(replacement)
        c4d.CallCommand(12147)  # Redraw View
        c4d.EventAdd(c4d.EVENT_FORCEREDRAW)
    finally:
        _selection_guard = False


class MarkSelectedNullsCommand(plugins.CommandData):
    def Execute(self, doc):
        objects = [op for op in selected_objects(doc) if op.CheckType(c4d.Onull)]
        if not objects:
            c4d.gui.MessageDialog("Please select one or more Null objects.")
            return True

        doc.StartUndo()
        try:
            for op in objects:
                doc.AddUndo(c4d.UNDOTYPE_CHANGE, op)
                tag = add_smart_tag(op, next_group_color(doc))
                if tag:
                    doc.AddUndo(c4d.UNDOTYPE_NEWOBJ, tag)
                    update_bbox_cache_for_tag(tag, op, force=True)
        finally:
            doc.EndUndo()

        c4d.EventAdd()
        return True


class UnmarkSelectedCommand(plugins.CommandData):
    def Execute(self, doc):
        tags = []
        for op in selected_objects(doc):
            tag = get_smart_tag(op)
            if tag:
                tags.append(tag)

        if not tags:
            c4d.gui.MessageDialog("Selected objects do not have Smart Group Select tags.")
            return True

        doc.StartUndo()
        try:
            for tag in tags:
                doc.AddUndo(c4d.UNDOTYPE_DELETEOBJ, tag)
                root = get_tag_host(tag)
                if root:
                    helper = get_boundary_helper(root)
                    if helper:
                        doc.AddUndo(c4d.UNDOTYPE_DELETEOBJ, helper)
                    remove_boundary_helper(root)
                _bbox_cache.pop(object_key(tag), None)
                tag.Remove()
        finally:
            doc.EndUndo()

        c4d.EventAdd()
        return True


class ToggleGlobalCommand(plugins.CommandData):
    def Execute(self, doc):
        set_global_enabled(not get_global_enabled())
        update_bbox_cache(doc)
        c4d.EventAdd()
        return True

    def GetState(self, doc):
        return c4d.CMD_ENABLED | (c4d.CMD_VALUE if get_global_enabled() else 0)


class ToggleSelectedGroupsCommand(plugins.CommandData):
    def Execute(self, doc):
        tags = []
        for op in selected_objects(doc):
            tag = get_smart_tag(op)
            if tag:
                tags.append(tag)

        if not tags:
            c4d.gui.MessageDialog("Select one or more Smart Groups.")
            return True

        # If any selected group is off, turn all selected groups on. Otherwise turn them off.
        new_value = any(not tag[SGN_TAG_ENABLE] for tag in tags)

        doc.StartUndo()
        try:
            for tag in tags:
                doc.AddUndo(c4d.UNDOTYPE_CHANGE, tag)
                tag[SGN_TAG_ENABLE] = new_value
                root = get_tag_host(tag)
                if root and new_value:
                    update_bbox_cache_for_tag(tag, root, force=True)
                elif root:
                    helper = get_boundary_helper(root)
                    if helper:
                        doc.AddUndo(c4d.UNDOTYPE_DELETEOBJ, helper)
                    remove_boundary_helper(root)
        finally:
            doc.EndUndo()

        c4d.EventAdd()
        return True


class AxisToBottomCenterCommand(plugins.CommandData):
    def Execute(self, doc):
        roots = selected_smart_roots(doc)

        if not roots:
            c4d.gui.MessageDialog("Select one or more Smart Groups.")
            return True

        doc.StartUndo()
        changed = False
        try:
            for root, tag in roots:
                changed = move_axis_to_bottom_center(doc, root, tag) is not None or changed
        finally:
            doc.EndUndo()

        if not changed:
            c4d.gui.MessageDialog("No valid child bounds were found for the selected Smart Groups.")
        c4d.EventAdd(c4d.EVENT_FORCEREDRAW)
        return True


class AxisToBottomAndGroundCommand(plugins.CommandData):
    def Execute(self, doc):
        roots = selected_smart_roots(doc)

        if not roots:
            c4d.gui.MessageDialog("Select one or more Smart Groups.")
            return True

        doc.StartUndo()
        changed = False
        try:
            for root, tag in roots:
                final_mg = move_axis_to_bottom_center(doc, root, tag)
                if final_mg is None:
                    continue
                changed = True

                if abs(final_mg.off.y) < 0.0001:
                    continue

                grounded_mg = c4d.Matrix()
                grounded_mg.off = c4d.Vector(final_mg.off.x, 0.0, final_mg.off.z)
                grounded_mg.v1 = final_mg.v1
                grounded_mg.v2 = final_mg.v2
                grounded_mg.v3 = final_mg.v3

                doc.AddUndo(c4d.UNDOTYPE_CHANGE, root)
                root.SetMg(grounded_mg)
                update_bbox_cache_for_tag(tag, root, force=True)
        finally:
            doc.EndUndo()

        if not changed:
            c4d.gui.MessageDialog("No valid child bounds were found for the selected Smart Groups.")
        c4d.EventAdd(c4d.EVENT_FORCEREDRAW)
        return True


class OctaneLightMaskDialog(c4d.gui.GeDialog):
    def __init__(self):
        super().__init__()
        self.accepted = False
        self.include_sun = False
        self.include_env = False
        self.selected_ids = []

    def CreateLayout(self):
        self.SetTitle("Light Mask")

        self.GroupBegin(5000, c4d.BFH_SCALEFIT | c4d.BFV_TOP, 1, 0, "Octane Light IDs", c4d.BORDER_GROUP_IN)
        self.GroupBorderSpace(10, 8, 10, 8)
        self.AddStaticText(5001, c4d.BFH_SCALEFIT, name="Selected objects receive only checked light IDs.")
        self.AddSeparatorH(c4d.BFH_SCALEFIT)

        self.GroupBegin(5002, c4d.BFH_LEFT | c4d.BFV_TOP, 2, 0)
        self.AddCheckbox(DLG_LIGHT_MASK_SUN, c4d.BFH_LEFT, 0, 0, "Sun")
        self.AddCheckbox(DLG_LIGHT_MASK_ENV, c4d.BFH_LEFT, 0, 0, "Env")
        self.GroupEnd()

        self.AddSeparatorH(c4d.BFH_SCALEFIT)

        self.GroupBegin(5003, c4d.BFH_SCALEFIT | c4d.BFV_TOP, 8, 0)
        for light_id in range(1, 33):
            self.AddCheckbox(DLG_LIGHT_MASK_ID_BASE + light_id, c4d.BFH_LEFT, 0, 0, str(light_id))
        self.GroupEnd()

        self.AddSeparatorH(c4d.BFH_SCALEFIT)

        self.GroupBegin(5004, c4d.BFH_LEFT | c4d.BFV_TOP, 2, 0)
        self.AddButton(DLG_LIGHT_MASK_ALL, c4d.BFH_LEFT, 80, 18, "All")
        self.AddButton(DLG_LIGHT_MASK_CLEAR, c4d.BFH_LEFT, 80, 18, "Clear")
        self.GroupEnd()

        self.GroupEnd()
        self.AddSeparatorH(c4d.BFH_SCALEFIT)
        self.AddDlgGroup(c4d.DLG_OK | c4d.DLG_CANCEL)
        return True

    def InitValues(self):
        self.SetBool(DLG_LIGHT_MASK_ID_BASE + 1, True)
        return True

    def Command(self, cid, msg):
        if cid == c4d.DLG_OK:
            self.include_sun = bool(self.GetBool(DLG_LIGHT_MASK_SUN))
            self.include_env = bool(self.GetBool(DLG_LIGHT_MASK_ENV))
            self.selected_ids = [
                light_id
                for light_id in range(1, 33)
                if self.GetBool(DLG_LIGHT_MASK_ID_BASE + light_id)
            ]
            self.accepted = True
            self.Close()
            return True

        if cid == c4d.DLG_CANCEL:
            self.Close()
            return True

        if cid == DLG_LIGHT_MASK_ALL:
            self.SetBool(DLG_LIGHT_MASK_SUN, True)
            self.SetBool(DLG_LIGHT_MASK_ENV, True)
            for light_id in range(1, 33):
                self.SetBool(DLG_LIGHT_MASK_ID_BASE + light_id, True)
            return True

        if cid == DLG_LIGHT_MASK_CLEAR:
            self.SetBool(DLG_LIGHT_MASK_SUN, False)
            self.SetBool(DLG_LIGHT_MASK_ENV, False)
            for light_id in range(1, 33):
                self.SetBool(DLG_LIGHT_MASK_ID_BASE + light_id, False)
            return True

        return True


class OctaneLightMaskCommand(plugins.CommandData):
    def Execute(self, doc):
        objects = selected_objects(doc)
        if not objects:
            c4d.gui.MessageDialog("Select one or more objects.")
            return True

        dlg = OctaneLightMaskDialog()
        dialog_type = getattr(c4d, "DLG_TYPE_MODAL_RESIZEABLE", c4d.DLG_TYPE_MODAL)
        dlg.Open(dialog_type, defaultw=360, defaulth=380)
        if not dlg.accepted:
            return True

        if not dlg.include_sun and not dlg.include_env and not dlg.selected_ids:
            c4d.gui.MessageDialog("Select at least one light ID.")
            return True

        changed = apply_octane_light_mask(
            doc,
            objects,
            dlg.selected_ids,
            include_sun=dlg.include_sun,
            include_env=dlg.include_env,
        )

        if changed == 0:
            c4d.gui.MessageDialog("No objects were updated. Is Octane installed?")
        return True


def main():
    if plugins.GetWorldPluginData(PLUGIN_ID_CMD_TOGGLE_GLOBAL) is None:
        set_global_enabled(True)

    plugins.RegisterTagPlugin(
        id=PLUGIN_ID_TAG,
        str="Smart Group Select",
        info=c4d.TAG_EXPRESSION | c4d.TAG_VISIBLE,
        g=SmartGroupTag,
        description="Tsmartgroupnulltag",
        icon=load_icon("smart-group-tag.png"),
    )

    plugins.RegisterMessagePlugin(
        id=PLUGIN_ID_MSG,
        str="Smart Group Select Watcher",
        info=0,
        dat=SmartGroupWatcher(),
    )

    plugins.RegisterCommandPlugin(
        id=PLUGIN_ID_CMD_MARK,
        str="Mark Group",
        info=0,
        icon=load_icon("mark-selected-nulls.png"),
        help="Add Smart Group Select tags to selected Null objects.",
        dat=MarkSelectedNullsCommand(),
    )
    plugins.RegisterCommandPlugin(
        id=PLUGIN_ID_CMD_TOGGLE_GLOBAL,
        str="Master Toggle",
        info=0,
        icon=load_icon("global-enable.png"),
        help="Enable or disable all Smart Group Select behavior.",
        dat=ToggleGlobalCommand(),
    )
    plugins.RegisterCommandPlugin(
        id=PLUGIN_ID_CMD_TOGGLE_SELECTED,
        str="Toggle Group",
        info=0,
        icon=load_icon("toggle-selected-groups.png"),
        help="Toggle selected Smart Groups.",
        dat=ToggleSelectedGroupsCommand(),
    )
    plugins.RegisterCommandPlugin(
        id=PLUGIN_ID_CMD_UNMARK,
        str="Unmark",
        info=0,
        icon=load_icon("remove-from-selected.png"),
        help="Remove Smart Group Select tags from selected objects.",
        dat=UnmarkSelectedCommand(),
    )
    plugins.RegisterCommandPlugin(
        id=PLUGIN_ID_CMD_AXIS_BOTTOM,
        str="Axis Bottom",
        info=0,
        icon=load_icon("axis-bottom-center.png"),
        help="Move selected Smart Group axes to the world bottom center without moving children.",
        dat=AxisToBottomCenterCommand(),
    )
    plugins.RegisterCommandPlugin(
        id=PLUGIN_ID_CMD_AXIS_BOTTOM_GROUND,
        str="Axis Ground",
        info=0,
        icon=load_icon("axis-bottom-ground.png"),
        help="Move selected Smart Group axes to the bottom center, then place them on world Y zero.",
        dat=AxisToBottomAndGroundCommand(),
    )
    plugins.RegisterCommandPlugin(
        id=PLUGIN_ID_CMD_OCTANE_LIGHT_MASK,
        str="Light Mask",
        info=0,
        icon=load_icon("octane-light-mask.png"),
        help="Set Octane light pass mask on selected objects.",
        dat=OctaneLightMaskCommand(),
    )


if __name__ == "__main__":
    main()
