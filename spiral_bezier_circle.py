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