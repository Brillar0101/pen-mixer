import bpy, bmesh, math
from mathutils import Vector
OUT = "/Users/barakaeli/Desktop/pen-mixer/production/output/case_proto"
SP = "/private/tmp/claude-501/-Users-barakaeli/3e694807-c74d-41d0-b641-bfa3e9bb23c6/scratchpad"
L, W, H = 58.0, 25.0, 15.0
T = 1.8; H_BOT, H_TOP = 11.0, 4.0
LIP_T, LIP_H, CLR = 1.0, 2.0, 0.2
BUMP, GROOVE = 0.35, 0.45
SLAB_W, SLAB_L, SLAB_T = 25.0, 58.0, 4.0
RAIL, LIP_IN, LIP_TT, CLR_W, CLR_H, DETENT, OV = 1.6, 1.5, 1.0, 0.3, 0.3, 0.3, 0.2
R_OUT = 3.0; R_IN = R_OUT - T          # 3.0 outside, 1.2 inside: uniform wall around the corner
R_BOTTOM, R_RAILTOP = 3.0, 0.5
OX, OY = L/2 + T, W/2 + T
Z_RIM = T + H_BOT; Z_ROOF = Z_RIM + H_TOP; Z_TOP = Z_ROOF + T
z_plate = Z_TOP; z_ch = z_plate + SLAB_T + CLR_H; z_rail_top = z_ch + LIP_TT

bpy.ops.wm.read_factory_settings(use_empty=True); sc = bpy.context.scene

def rprism(name, x0, x1, y0, y1, z0, z1, r, segs=10):
    """Extruded rounded rectangle."""
    r = max(0.0, min(r, (x1-x0)/2 - 0.01, (y1-y0)/2 - 0.01))
    pts = []
    for cx, cy, a0 in ((x1-r, y1-r, 0), (x0+r, y1-r, 90), (x0+r, y0+r, 180), (x1-r, y0+r, 270)):
        for i in range(segs+1):
            a = math.radians(a0 + 90*i/segs); pts.append((cx + r*math.cos(a), cy + r*math.sin(a)))
    bm = bmesh.new()
    vs = [bm.verts.new((x, y, z0)) for x, y in pts]
    f = bm.faces.new(vs); bmesh.ops.recalc_face_normals(bm, faces=[f])
    res = bmesh.ops.extrude_face_region(bm, geom=[f])
    bmesh.ops.translate(bm, verts=[e for e in res["geom"] if isinstance(e, bmesh.types.BMVert)], vec=(0, 0, z1-z0))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    o = bpy.data.objects.new(name, me); bpy.context.collection.objects.link(o); return o
def box(name, x0, x1, y0, y1, z0, z1):
    bpy.ops.mesh.primitive_cube_add(size=1); o = bpy.context.active_object; o.name = name
    o.scale = ((x1-x0), (y1-y0), (z1-z0)); o.location = ((x0+x1)/2, (y0+y1)/2, (z0+z1)/2)
    bpy.ops.object.transform_apply(scale=True, location=True); return o
def boolean(t, c, op):
    m = t.modifiers.new("b", "BOOLEAN"); m.operation = op; m.object = c; m.solver = "EXACT"
    with bpy.context.temp_override(object=t, active_object=t, selected_objects=[t]):
        bpy.ops.object.modifier_apply(modifier=m.name)
    bpy.data.objects.remove(c, do_unlink=True)
def round_edges(o, pick, width, segs=4):
    """Weight-bevel the edges selected by pick(v0, v1)."""
    bm = bmesh.new(); bm.from_mesh(o.data)
    layer = bm.edges.layers.float.get("bevel_weight_edge") or bm.edges.layers.float.new("bevel_weight_edge")
    n = 0
    for e in bm.edges:
        w = 1.0 if pick(e.verts[0].co, e.verts[1].co) else 0.0
        e[layer] = w; n += w > 0
    bm.to_mesh(o.data); bm.free()
    m = o.modifiers.new("r", "BEVEL"); m.width = width; m.segments = segs; m.limit_method = "WEIGHT"; m.harden_normals = False
    with bpy.context.temp_override(object=o, active_object=o, selected_objects=[o]):
        bpy.ops.object.modifier_apply(modifier=m.name)
    return n
def export(o, path):
    bpy.ops.object.select_all(action="DESELECT"); o.select_set(True); bpy.context.view_layer.objects.active = o
    bpy.ops.wm.stl_export(filepath=path, export_selected_objects=True, global_scale=1.0, ascii_format=False)
    pts = [o.matrix_world @ Vector(c) for c in o.bound_box]
    mn = [min(p[i] for p in pts) for i in range(3)]; mx = [max(p[i] for p in pts) for i in range(3)]
    print(f"EXPORT {path.split('/')[-1]}: {mx[0]-mn[0]:.2f} x {mx[1]-mn[1]:.2f} x {mx[2]-mn[2]:.2f} mm (z {mn[2]:.2f}..{mx[2]:.2f}), faces={len(o.data.polygons)}")

# ---- bottom tray ----------------------------------------------------------
bot = rprism("case_proto_bottom", -OX, OX, -OY, OY, 0, Z_RIM, R_OUT)
n = round_edges(bot, lambda a, b: a.z < 0.01 and b.z < 0.01, R_BOTTOM)          # rounded bottom edge
boolean(bot, rprism("cavity", -L/2, L/2, -W/2, W/2, T, Z_RIM+1, R_IN), "DIFFERENCE")
for sx in (-1, 1):
    for sy in (-1, 1):
        boolean(bot, box("groove", sx*L/4-2.3, sx*L/4+2.3, sy*W/2 - (GROOVE if sy<0 else -OV), sy*W/2 + (OV if sy<0 else GROOVE), Z_RIM-2.2, Z_RIM-1.0), "DIFFERENCE")
boolean(bot, box("usb", -OX-1, -L/2+1, -5.5, 5.5, T+2.0, T+9.0), "DIFFERENCE")
export(bot, f"{OUT}/case_proto_bottom.stl"); print(f"  bottom edge rounded on {n} edges")

# ---- lid ------------------------------------------------------------------
lid = rprism("case_proto_top", -OX, OX, -OY, OY, Z_RIM, Z_TOP, R_OUT)
boolean(lid, rprism("lid_cavity", -L/2, L/2, -W/2, W/2, Z_RIM-1, Z_ROOF, R_IN), "DIFFERENCE")
lx, ly = L/2 - CLR, W/2 - CLR
lip = rprism("lip", -lx, lx, -ly, ly, Z_RIM-LIP_H, Z_RIM+OV, R_IN-CLR)
boolean(lip, rprism("lip_in", -lx+LIP_T, lx-LIP_T, -ly+LIP_T, ly-LIP_T, Z_RIM-LIP_H-1, Z_RIM+1, max(0.2, R_IN-CLR-LIP_T)), "DIFFERENCE")
boolean(lid, lip, "UNION")
for sx in (-1, 1):
    for sy in (-1, 1):
        boolean(lid, box("bump", sx*L/4-2.0, sx*L/4+2.0, sy*ly - (OV if sy>0 else BUMP), sy*ly + (BUMP if sy>0 else OV), Z_RIM-2.1, Z_RIM-1.1), "UNION")
# slab rails as a frame, trimmed to the rounded outline, tops rounded
hx = SLAB_W/2 + CLR_W/2
frame = None
for s in (-1, 1):
    y_rail = sorted((s*hx, s*OY)); y_lip = sorted((s*(hx-LIP_IN), s*hx)); y_det = sorted((s*(hx-LIP_IN), s*(hx+OV)))
    for b in (box("rail", -OX, OX, y_rail[0], y_rail[1], z_plate-OV, z_rail_top),
              box("lip2", -OX, OX, y_lip[0], y_lip[1], z_ch, z_rail_top),
              box("detent", -OX+3.5, -OX+4.5, y_det[0], y_det[1], z_ch-DETENT, z_ch+OV)):
        if frame is None: frame = b; frame.name = "rail_frame"
        else: boolean(frame, b, "UNION")
boolean(frame, box("stop", OX-RAIL, OX, -OY, OY, z_plate-OV, z_rail_top), "UNION")
boolean(frame, rprism("trim", -OX, OX, -OY, OY, z_plate-1, z_rail_top+1, R_OUT), "INTERSECT")
n2 = round_edges(frame, lambda a, b: a.z > z_rail_top-0.01 and b.z > z_rail_top-0.01, R_RAILTOP, 3)
boolean(lid, frame, "UNION")
export(lid, f"{OUT}/case_proto_top.stl"); print(f"  rail tops rounded on {n2} edges")
print(f"interior {L} x {W} x {H} (corners r{R_IN}); outer {2*OX:.1f} x {2*OY:.1f} x {Z_TOP:.1f} (+{z_rail_top-Z_TOP:.1f} rails), corners r{R_OUT}")

# ---- renders ----------------------------------------------------------------
pla = bpy.data.materials.new("pla"); pla.diffuse_color = (0.85, 0.92, 0.96, 1)
wood = bpy.data.materials.new("wood"); wood.diffuse_color = (0.55, 0.35, 0.18, 1)
for o in (bot, lid): o.data.materials.append(pla)
slab = box("slab", OX-RAIL-SLAB_L-16, OX-RAIL-16, -12.5, 12.5, z_plate+0.05, z_plate+SLAB_T); slab.data.materials.append(wood)
cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam")); sc.collection.objects.link(cam); sc.camera = cam; cam.data.lens = 50
sc.render.engine = "BLENDER_WORKBENCH"; sc.display.shading.light = "STUDIO"; sc.display.shading.color_type = "MATERIAL"; sc.display.shading.show_cavity = True
sc.render.resolution_x, sc.render.resolution_y = 1400, 900
def shoot(name, c, off):
    cam.location = c + off; cam.rotation_euler = (c - cam.location).to_track_quat("-Z", "Y").to_euler()
    sc.render.filepath = f"{SP}/{name}.png"; bpy.ops.render.render(write_still=True); print("RENDER", name)
shoot("proto_round_assembled", Vector((0, 0, 10)), Vector((-95, -120, 75)))
bot.name, lid.name, slab.name = "case bottom", "case lid with rails", "wooden slab"
slab.location.x += 16   # seated against the stop
bpy.ops.object.transform_apply(location=True)
sc.unit_settings.system = "METRIC"; sc.unit_settings.length_unit = "MILLIMETERS"
bpy.ops.wm.save_as_mainfile(filepath="/Users/barakaeli/Desktop/pen-mixer/production/blender/case_proto.blend")
print("SAVED case_proto.blend")
slab.location.x -= 16; bpy.ops.object.transform_apply(location=True)
lid.location.z += 22; slab.location.z += 22
shoot("proto_round_exploded", Vector((0, 0, 20)), Vector((-95, -125, 70)))
