import bpy, math

segments = 128          # smoothness
r_start, r_end = 2.0, 3.0

curve = bpy.data.curves.new("SpiralCircle", type='CURVE')
curve.dimensions = '3D'
spline = curve.splines.new('POLY')
spline.points.add(segments)   # already has 1 point

for i in range(segments + 1):
    t = i / segments                      # 0 -> 1
    theta = t * 2 * math.pi
    r = r_start + (r_end - r_start) * t   # 2 -> 3
    spline.points[i].co = (r * math.cos(theta), r * math.sin(theta), 0, 1)

obj = bpy.data.objects.new("SpiralCircle", curve)
bpy.context.collection.objects.link(obj)

# optional: give it thickness
curve.bevel_depth = 0.02


import bpy, bmesh, math
from mathutils import Vector

# ---------------- parameters ----------------
segments   = 128        # smoothness
r_start, r_end = 2.0, 3.0
CAP_HEIGHT_CM = 2.0     # vertical height of the cap, in centimeters (default 2 cm)
# --------------------------------------------

# Convert cm to Blender units, respecting the scene's unit scale
# (default: 1 BU = 1 m, so 2 cm = 0.02 BU)
unit_scale = bpy.context.scene.unit_settings.scale_length
cap_height = (CAP_HEIGHT_CM / 100.0) / unit_scale

# ---- 1. build the spiral as a curve ----
curve = bpy.data.curves.new("SpiralCircle", type='CURVE')
curve.dimensions = '3D'
spline = curve.splines.new('POLY')
spline.points.add(segments)   # already has 1 point

for i in range(segments + 1):
    t = i / segments
    theta = t * 2 * math.pi
    r = r_start + (r_end - r_start) * t
    spline.points[i].co = (r * math.cos(theta), r * math.sin(theta), 0, 1)

spline.use_cyclic_u = True    # closes end -> start with a straight edge

curve_obj = bpy.data.objects.new("SpiralCurve", curve)
bpy.context.collection.objects.link(curve_obj)

# ---- 2. convert the curve to a mesh ----
depsgraph = bpy.context.evaluated_depsgraph_get()
mesh = bpy.data.meshes.new_from_object(curve_obj.evaluated_get(depsgraph))
mesh.name = "SpiralMesh"

# ---- 3. add the cap: fill the loop, then extrude up by cap_height ----
bm = bmesh.new()
bm.from_mesh(mesh)

bmesh.ops.edgeloop_fill(bm, edges=bm.edges[:])           # face from the closed loop
ext = bmesh.ops.extrude_face_region(bm, geom=bm.faces[:])
new_verts = [e for e in ext["geom"] if isinstance(e, bmesh.types.BMVert)]
bmesh.ops.translate(bm, verts=new_verts, vec=Vector((0, 0, cap_height)))
bmesh.ops.recalc_face_n