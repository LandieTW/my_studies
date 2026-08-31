#!/usr/bin/env python3


# gmsh documentation (https://gmsh.info/doc/texinfo/gmsh.html) 
# gmsh distribution (https://gitlab.onelab.info/gmsh/gmsh/-/tree/gmsh_4_15_2)


# CONTENT: Translation, Rotation, others...


import gmsh
import math


gmsh.initialize()

gmsh.model.add("My model")

lc = 1e-2

# points
gmsh.model.geo.addPoint(0, 0, 0, lc, 1)
gmsh.model.geo.addPoint(.1, 0, 0, lc, 2)
gmsh.model.geo.addPoint(.1, .3, 0, lc, 3)
gmsh.model.geo.addPoint(0, .3, 0, lc, 4)

# lines
gmsh.model.geo.addLine(1, 2, 1)
gmsh.model.geo.addLine(3, 2, 2)
gmsh.model.geo.addLine(3, 4, 3)
gmsh.model.geo.addLine(4, 1, 4)

# curve loop
gmsh.model.geo.addCurveLoop([4, 1, -2, 3], 1)

# plane
gmsh.model.geo.addPlaneSurface([1], 1)

gmsh.model.geo.synchronize()

# physical group with lines 1, 2 and 4
gmsh.model.addPhysicalGroup(1, [1, 2, 4], 5)
# physical group with the plane
gmsh.model.addPhysicalGroup(2, [1], name="My surface")

# point-line out of the rectangle
gmsh.model.geo.addPoint(0, .4, 0, lc, 5)
gmsh.model.geo.addLine(4, 5, 5)


# ---------------------------------------------------------------------------
# --- NEW CONTENT - NEW CONTENT - NEW CONTENT - NEW CONTENT - NEW CONTENT ---
# ---------------------------------------------------------------------------
# --- NEW CONTENT - NEW CONTENT - NEW CONTENT - NEW CONTENT - NEW CONTENT ---
# ---------------------------------------------------------------------------

# TRANSLATE
gmsh.model.geo.translate(
    [(0, 5)],                   # list with point (dim=0; tag=5)
    -0.02, 0, 0                 # translation (dx=-0.02, dy=0, dz=0)
    )

# ROTATION
gmsh.model.geo.rotate(
    [(0, 5)],               # list with point (dim=0; tag=5)
    0, 0.3, 0,              # rotation center
    0, 0, 1,                # direction of the rotation
    -math.pi / 4            # angle of rotation
    )

# COPYING A POINT AND TRANSLATING IT
ov = gmsh.model.geo.copy([(0, 3)])
gmsh.model.geo.translate(ov, 0, 0.05, 0)

# ov[0][1] is the ov tag
gmsh.model.geo.addLine(3, ov[0][1], 7)
gmsh.model.geo.addLine(ov[0][1], 5, 8)
gmsh.model.geo.addCurveLoop([5, -8, -7, 3], 10)
gmsh.model.geo.addPlaneSurface([10], 11)

ov = gmsh.model.geo.copy([(2, 1), (2, 11)])
gmsh.model.geo.translate(ov, 0.12, 0, 0)

# how to retrieve coordinates of a point
gmsh.model.geo.synchronize()        # it is needed to synchronize first


xyz = gmsh.model.getValue(
    0, 5,                       # dim=0, tag=5
    []
)

# VOLUMES
# 1. Creating points
gmsh.model.geo.addPoint(0., 0.3, 0.12, lc, 100)
gmsh.model.geo.addPoint(0.1, 0.3, 0.12, lc, 101)
gmsh.model.geo.addPoint(0.1, 0.35, 0.12, lc, 102)
gmsh.model.geo.addPoint(xyz[0], xyz[1], 0.12, lc, 103)
# 2. Creating lines
gmsh.model.geo.addLine(4, 100, 110)
gmsh.model.geo.addLine(3, 101, 111)
gmsh.model.geo.addLine(6, 102, 112)
gmsh.model.geo.addLine(5, 103, 113)
gmsh.model.geo.addLine(103, 100, 114)
gmsh.model.geo.addLine(100, 101, 115)
gmsh.model.geo.addLine(101, 102, 116)
gmsh.model.geo.addLine(102, 103, 117)
# 3. Creating Curve Loops and its Plane Surfaces
gmsh.model.geo.addCurveLoop([115, -111, 3, 110], 118)
gmsh.model.geo.addPlaneSurface([118], 119)
gmsh.model.geo.addCurveLoop([111, 116, -112, -7], 120)
gmsh.model.geo.addPlaneSurface([120], 121)
gmsh.model.geo.addCurveLoop([112, 117, -113, -8], 122)
gmsh.model.geo.addPlaneSurface([122], 123)
gmsh.model.geo.addCurveLoop([114, -110, 5, 113], 124)
gmsh.model.geo.addPlaneSurface([124], 125)
gmsh.model.geo.addCurveLoop([115, 116, 117, 114], 126)
gmsh.model.geo.addPlaneSurface([126], 127)
# 4. Creating Surface Loop of Plane surfaces and its Volume
gmsh.model.geo.addSurfaceLoop([127, 119, 121, 123, 125, 11], 128)
gmsh.model.geo.addVolume([128], 129)

# CREATING VOLUMES WITH EXTRUSATION
ov2 = gmsh.model.geo.extrude(
    [ov[1]],                            # point ov tag
    0, 0, 0.12                          # direction of the extrusion
)

# HOW TO SET SPECIFIC MESH SIZES TO SOME POINTS
gmsh.model.geo.mesh.setSize(
    [(0, 103), (0, 105), (0, 109), (0, 102), (0, 28), (0, 24), (0, 6), (0, 5)],
    lc * 3
)

gmsh.model.geo.synchronize()
gmsh.model.addPhysicalGroup(3, [129, 130], 1, "The volume")
gmsh.model.mesh.generate(3)
gmsh.fltk.run()
gmsh.finalize()

