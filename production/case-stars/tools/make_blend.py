"""Build case_both.blend: tray, lid with rails, and the wooden slab, assembled. Run: blender -b -P tools/make_blend.py"""
import bpy, math, os
from mathutils import Vector
D = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAILS_TOP = 26.3                      # H + slab_thk + slab_clear_h + lip_thk from enclosure.scad
SLAB = (58.0, 27.0, 5.0)
bpy.ops.wm.read_factory_settings(use_empty=True); sc = bpy.context.scene
def mat(name, rgba):
    m = bpy.data.materials.new(name); m.diffuse_color = rgba; return m
bpy.ops.wm.stl_import(filepath=os.path.join(D, "bottom.stl"), global_scale=1.0)
tray = bpy.context.active_object; tray.name = "tray (bottom)"; tray.data.materials.append(mat("slate", (0.44, 0.50, 0.56, 1)))
bpy.ops.wm.stl_import(filepath=os.path.join(D, "top.stl"), global_scale=1.0)
lid = bpy.context.active_object; lid.name = "lid with slab rails"; lid.data.materials.append(mat("orange", (1.0, 0.55, 0.12, 1)))
lid.rotation_euler = (math.pi, 0, 0); lid.location = (0, 0, RAILS_TOP)   # undo the print flip
bpy.ops.mesh.primitive_cube_add(size=1); slab = bpy.context.active_object; slab.name = "wooden slab"
slab.scale = SLAB; slab.location = (32.95 - 1.6 - SLAB[0] / 2 - 20, 0, 19 + SLAB[2] / 2 + 0.05)
slab.data.materials.append(mat("wood", (0.55, 0.35, 0.18, 1)))
sc.unit_settings.system = "METRIC"; sc.unit_settings.scale_length = 0.001; sc.unit_settings.length_unit = "MILLIMETERS"
for scr in bpy.data.screens:
    for area in scr.areas:
        if area.type == "VIEW_3D":
            sp = area.spaces[0]; sp.clip_start, sp.clip_end = 0.1, 10000
            sp.shading.type = "SOLID"; sp.shading.color_type = "MATERIAL"; sp.shading.show_cavity = True
            sp.region_3d.view_location = (0, 0, 10); sp.region_3d.view_distance = 150
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(D, "case_both.blend")); print("SAVED")
out = os.environ.get("RENDER_DIR")
if out:
    cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam")); sc.collection.objects.link(cam); sc.camera = cam
    sc.render.engine = "BLENDER_WORKBENCH"; sc.display.shading.light = "STUDIO"; sc.display.shading.color_type = "MATERIAL"; sc.display.shading.show_cavity = True
    sc.render.resolution_x, sc.render.resolution_y = 1400, 900
    for name, off in (("slab_assembled", Vector((-90, -115, 80))), ("slab_end", Vector((-120, 0, 12)))):
        c = Vector((0, 0, 12)); cam.location = c + off; cam.rotation_euler = (c - cam.location).to_track_quat("-Z", "Y").to_euler()
        sc.render.filepath = os.path.join(out, name + ".png"); bpy.ops.render.render(write_still=True)
    print("RENDERED")
