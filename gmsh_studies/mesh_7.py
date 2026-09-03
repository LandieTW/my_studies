#!/usr/bin/env python3


# gmsh documentation (https://gmsh.info/doc/texinfo/gmsh.html) 
# gmsh distribution (https://gitlab.onelab.info/gmsh/gmsh/-/tree/gmsh_4_15_2)


# CONTENT: Differents ways how to manipulate mesh sizes


import gmsh


gmsh.initialize()

gmsh.model.add("Model")

# Simple rectangular geometry:
lc = .15
gmsh.model.geo.addPoint(0.0, 0.0, 0, lc, 1)
gmsh.model.geo.addPoint(1, 0.0, 0, lc, 2)
gmsh.model.geo.addPoint(1, 1, 0, lc, 3)
gmsh.model.geo.addPoint(0, 1, 0, lc, 4)
gmsh.model.geo.addPoint(0.2, .5, 0, lc, 5)

gmsh.model.geo.addLine(1, 2, 1)
gmsh.model.geo.addLine(2, 3, 2)
gmsh.model.geo.addLine(3, 4, 3)
gmsh.model.geo.addLine(4, 1, 4)

gmsh.model.geo.addCurveLoop([1, 2, 3, 4], 5)
gmsh.model.geo.addPlaneSurface([5], 6)

gmsh.model.geo.synchronize()


# -----------------------------------------------------------------------------
# ---- NEW CONTENT - NEW CONTENT - NEW CONTENT - NEW CONTENT - NEW CONTENT ----
# -----------------------------------------------------------------------------
# ---- NEW CONTENT - NEW CONTENT - NEW CONTENT - NEW CONTENT - NEW CONTENT ----
# -----------------------------------------------------------------------------


# Obtainning mesh elements with a certain size near curve 2 and point 5

# DISTANCE
gmsh.model.mesh.field.add(
    "Distance",                 # add distance field
    1                           # distance field tag
    )
gmsh.model.mesh.field.setNumbers(1,                 # reference field tag
                                 "PointsList",      # set numerical list of values
                                 [5]                # reference point 5 tag
                                 )
gmsh.model.mesh.field.setNumbers(1, "CurvesList", [2])      # samething, but for curve 2
gmsh.model.mesh.field.setNumber(
    1, 
    "Sampling",         # sampling number of points on curve 2 to compute distance
    100                 # number of equidistant points on curve 2
    )

# THRESHOLD
# Samething as Distance Field, but with a simple change in element size 
# relative to the computed distances
gmsh.model.mesh.field.add(
    "Threshold",                # add threshold field
    2                           # threshold field tag
    )
# Diferent ways how to set the threshold field values
gmsh.model.mesh.field.setNumber(2, "InField", 1)
gmsh.model.mesh.field.setNumber(2, "SizeMin", lc / 30)
gmsh.model.mesh.field.setNumber(2, "SizeMax", lc)
gmsh.model.mesh.field.setNumber(2, "DistMin", 0.15)
gmsh.model.mesh.field.setNumber(2, "DistMax", 0.5)

# modulating mesh size using mathematical function of spatial coord.
gmsh.model.mesh.field.add("MathEval", 3)
gmsh.model.mesh.field.setString(
    3,
    "F",
    "cos(4*3.14*x) * sin(4*3.14*y) / 10 + 0.101"
    )

# MathEval combined with values  from other fields.
gmsh.model.mesh.field.add("Distance", 4)
gmsh.model.mesh.field.setNumbers(4, "PointsList", [1])
gmsh.model.mesh.field.add("MathEval", 5)
gmsh.model.mesh.field.setString(5, "F", "F4^3 + " + str(lc / 100))

# Imposing a step change in elements size
gmsh.model.mesh.field.add("Box", 6)
gmsh.model.mesh.field.setNumber(6, "VIn", lc / 15)
gmsh.model.mesh.field.setNumber(6, "VOut", lc)
gmsh.model.mesh.field.setNumber(6, "XMin", 0.3)
gmsh.model.mesh.field.setNumber(6, "XMax", 0.6)
gmsh.model.mesh.field.setNumber(6, "YMin", 0.3)
gmsh.model.mesh.field.setNumber(6, "YMax", 0.6)
gmsh.model.mesh.field.setNumber(6, "Thickness", 0.3)

# other field
gmsh.model.mesh.field.add("Min", 7)
gmsh.model.mesh.field.setNumbers(7, "FieldsList", [2, 3, 5, 6])
gmsh.model.mesh.field.setAsBackgroundMesh(7)


def meshSizeCallback(dim, tag, x, y, z, lc):
    """Callback function to compute mesh size at a given point (x, y, z)."""
    return min(lc, 0.02 * x + 0.01)


gmsh.model.mesh.setSizeCallback(meshSizeCallback)


# gmsh locally computes mesh elements size finding the minimum of:
# 1. size of model bouding box;
# 2. mesh specified at geometric points, if "Mesh.MeshSizeFromPoints" is set;
# 3. mesh size based on curvature, if "Mesh.MeshSizeFromCurvature" is positive;
# 4. background mesh size field;
# 5. any per-entity mesh size constraint.

# mesh size can be modified in the interval ["Mesh.MeshSizeMin", "Mesh.MeshSizeMax"]
# it can be multiplied by "Mesh.MeshSizeFactor" to globally scale the mesh size.
# also, mesh size can be interpolated inside surfaces and/or volumes depending 
# on the value of "Mesh.MeshSizeExtendFromBoundary"


# PREVENT OVER-REFINEMENT DUE TO SMALL MESH SIZES ON BOUNDARY
gmsh.option.setNumber("Mesh.MeshSizeExtendFromBoundary", 0)
gmsh.option.setNumber("Mesh.MeshSizeFromPoints", 0)
gmsh.option.setNumber("Mesh.MeshSizeFromCurvature", 0)

# "Frontal-Delaunay" 2D meshing algorithm (Mesh.Algorithm = 6) usually leads 
# to the highest quality meshes
# "Delaunay" algorithm (Mesh.Algorithm = 5) handle complex mesh size fields 
# better - in particular size fields with large element size gradients
gmsh.option.setNumber("Mesh.Algorithm", 5)

gmsh.model.mesh.generate(2)

gmsh.fltk.run()
gmsh.finalize()

