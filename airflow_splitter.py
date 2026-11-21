"""
Airflow splitter ("core" + 4 elbow tubes) for Blender.

Run from Blender's Scripting workspace (Text Editor > Open > Run Script).
Tested against the Blender 3.x / 4.x Python API (uses the EXACT boolean solver).

All dimensions below are in centimetres. UNIT converts cm -> Blender units
(0.01 = Blender's default metre scale, so 4 cm shows up as 0.04 m).
Set UNIT = 1.0 if you would rather have 1 Blender unit = 1 cm.

Axes
  X : core length (the tubes leave through the +X and -X walls)
  Y : core width  (the ridge of the internal slopes runs along Y)
  Z : up. The core's bottom sits at z = 0 and its top is open.
"""

import math

import bmesh
import bpy
from mathutils import Vector

# --------------------------------------------------------------------------
# CONFIG (cm)
# --------------------------------------------------------------------------
CORE_LENGTH = 4.0      # X (outer)
CORE_WIDTH = 4.0       # Y (outer)
CORE_HEIGHT = 4.0      # Z (outer)

TUBE_DIAMETER = 1.0    # outer diameter
TUBE_LENGTH = 15.0     # straight run, measured from the core wall along the tube axis
TUBE_DROP = 1.0        # straight-down section after the 90 degree bend
TUBE_ANGLES = (30, 150, 210, 330)   # degrees from +X, measured in the XY plane
TUBE_Y_OFFSET = None   # where each tube meets the wall (|y|); None -> CORE_WIDTH / 4

WALL = 0.1             # wall thickness of core and tubes

RIDGE_HEIGHT = 2.5     # height of the high point of the internal slopes (z, from bottom)
CURVE_POWER = 2.0      # 1 = straight slope, >1 = curved: flat where it meets the tubes, steeper at the ridge

UNIT = 0.01            # cm -> Blender units
SEGMENTS = 48          # tube / sphere smoothness
RAMP_STEPS = 24        # samples per slope

OBJECT_NAME = "AirSplitter"


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------
def U(v):
    """cm vector/tuple -> Blender-unit Vector."""
    return Vector(v) * UNIT


def ensure_object_mode():
    if bpy.context.object and bpy.context.object.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")


def add_box(size, center, name):
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=U(center))
    obj = bpy.context.active_object
    obj.name = name
    obj.scale = U(size)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    return obj


def add_cylinder(p0, p1, radius, name):
    p0, p1 = U(p0), U(p1)
    d = p1 - p0
    if abs(d.x) + abs(d.y) < 1e-12:
        rot = (0.0, 0.0, 0.0)  # vertical; a cylinder is symmetric so direction doesn't matter
    else:
        rot = d.to_track_quat("Z", "Y").to_euler()
    bpy.ops.mesh.primitive_cylinder_add(
        vertices=SEGMENTS,
        radius=radius * UNIT,
        depth=d.length,
        location=(p0 + p1) / 2,
        rotation=rot,
    )
    obj = bpy.context.active_object
    obj.name = name
    return obj


def add_sphere(center, radius, name):
    bpy.ops.mesh.primitive_uv_sphere_add(
        segments=SEGMENTS,
        ring_count=SEGMENTS // 2,
        radius=radius * UNIT,
        location=U(center),
    )
    obj = bpy.context.active_object
    obj.name = name
    return obj


def boolean(target, cutter, operation):
    """Apply a boolean (UNION / DIFFERENCE) to target, then delete cutter."""
    mod = target.modifiers.new("bool", "BOOLEAN")
    mod.operation = operation
    mod.object = cutter
    mod.solver = "EXACT"
    bpy.ops.object.select_all(action="DESELECT")
    target.select_set(True)
    bpy.context.view_layer.objects.active = target
    bpy.ops.object.modifier_apply(modifier=mod.name)
    bpy.data.objects.remove(cutter, do_unlink=True)


def make_cavity():
    """
    Hollow interior of the core as a prism: curved floor (two slopes meeting in a
    ridge along Y), straight walls, and extended above the top so the top is open.
    """
    hi = CORE_LENGTH / 2 - WALL     # inner half-length (X)
    hw = CORE_WIDTH / 2 - WALL      # inner half-width  (Y)
    z_low = WALL                    # floor height at the tube walls (= tube bore bottom)
    z_top = CORE_HEIGHT + 1.0       # poke through the open top

    n_steps = RAMP_STEPS * 2
    profile = []
    for i in range(n_steps + 1):
        x = -hi + 2 * hi * i / n_steps
        s = 1.0 - abs(x) / hi       # 0 at the walls, 1 at the ridge
        z = z_low + (RIDGE_HEIGHT - z_low) * (s ** CURVE_POWER)
        profile.append((x, z))
    profile += [(hi, z_top), (-hi, z_top)]

    n = len(profile)
    verts = []
    for y in (-hw, hw):
        for x, z in profile:
            verts.append(U((x, y, z)))
    faces = [list(range(n)), list(range(2 * n - 1, n - 1, -1))]
    for i in range(n):
        j = (i + 1) % n
        faces.append((i, j, n + j, n + i))

    mesh = bpy.data.meshes.new("cavity_mesh")
    mesh.from_pydata([tuple(v) for v in verts], [], faces)
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bmesh.ops.triangulate(bm, faces=bm.faces)
    bm.to_mesh(mesh)
    bm.free()

    obj = bpy.data.objects.new("cavity", mesh)
    bpy.context.collection.objects.link(obj)
    return obj


def tube_path(angle_deg):
    """Return (start, wall_point, bend, end) for one tube, in cm."""
    r = TUBE_DIAMETER / 2
    a = math.radians(angle_deg)
    d = Vector((math.cos(a), math.sin(a), 0.0))
    side = 1.0 if d.x > 0 else -1.0
    y_off = CORE_WIDTH / 4 if TUBE_Y_OFFSET is None else TUBE_Y_OFFSET
    y0 = y_off if d.y > 0 else -y_off
    wall_pt = Vector((side * CORE_LENGTH / 2, y0, r))   # tube bottom is at z = 0
    bend = wall_pt + d * TUBE_LENGTH
    end = bend + Vector((0.0, 0.0, -TUBE_DROP))
    return d, wall_pt, bend, end


# --------------------------------------------------------------------------
# build
# --------------------------------------------------------------------------
def build():
    # sanity checks
    r_out = TUBE_DIAMETER / 2
    r_in = r_out - WALL
    assert r_in > 0, "WALL is too thick for TUBE_DIAMETER"
    assert WALL < RIDGE_HEIGHT < CORE_HEIGHT, "RIDGE_HEIGHT must be between WALL and CORE_HEIGHT"
    assert CORE_LENGTH > 4 * WALL and CORE_WIDTH > 4 * WALL, "core too small for WALL"
    y_off = CORE_WIDTH / 4 if TUBE_Y_OFFSET is None else TUBE_Y_OFFSET
    assert y_off + r_out <= CORE_WIDTH / 2, "tubes don't fit on the core wall; reduce TUBE_Y_OFFSET"

    ensure_object_mode()
    old = bpy.data.objects.get(OBJECT_NAME)
    if old:
        bpy.data.objects.remove(old, do_unlink=True)

    # 1. outer solid: core box + tube shells (cylinders with a sphere at each elbow)
    core = add_box(
        (CORE_LENGTH, CORE_WIDTH, CORE_HEIGHT),
        (0, 0, CORE_HEIGHT / 2),
        OBJECT_NAME,
    )

    paths = [tube_path(a) for a in TUBE_ANGLES]

    for i, (d, wall_pt, bend, end) in enumerate(paths):
        start = wall_pt - d * (2 * WALL)   # start slightly inside the core wall
        boolean(core, add_cylinder(start, bend, r_out, f"out_run_{i}"), "UNION")
        boolean(core, add_sphere(bend, r_out, f"out_elbow_{i}"), "UNION")
        boolean(core, add_cylinder(bend, end, r_out, f"out_drop_{i}"), "UNION")

    # 2. carve the core's interior (open top, curved ridge floor)
    boolean(core, make_cavity(), "DIFFERENCE")

    # 3. carve the tube bores (run + elbow + drop), through the open end
    for i, (d, wall_pt, bend, end) in enumerate(paths):
        start = wall_pt - d * (3 * WALL)   # reach into the cavity so the bore connects
        end_open = end + Vector((0.0, 0.0, -0.2))
        boolean(core, add_cylinder(start, bend, r_in, f"in_run_{i}"), "DIFFERENCE")
        boolean(core, add_sphere(bend, r_in, f"in_elbow_{i}"), "DIFFERENCE")
        boolean(core, add_cylinder(bend, end_open, r_in, f"in_drop_{i}"), "DIFFERENCE")

    # 4. tidy up
    bpy.ops.object.select_all(action="DESELECT")
    core.select_set(True)
    bpy.context.view_layer.objects.active = core
    bpy.ops.object.shade_smooth()
    return core


if __name__ == "__main__":
    build()
