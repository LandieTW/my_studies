

import gmsh


gmsh.initialize()

gmsh.model.add("Model")

# Let's create a simple rectangular geometry:
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

# if we want to obtain mesh elements with size lc/30 near curve 2 and point 5
# and size lc elsewhere. We do it with "Distance" AND "Threshold".

# DISTANCE
# We define a Distance field 'Field[1] on points 5 and on curve 2.
# This field returns the distance to point 5 and to (100 equidistant points on) 
# curve 2
gmsh.model.mesh.field.add("Distance", 1)
gmsh.model.mesh.field.setNumbers(1, "PointsList", [5])
gmsh.model.mesh.field.setNumbers(1, "CurvesList", [2])
gmsh.model.mesh.field.setNumber(1, "Sampling", 100)

# THRESHOLD
# We define a 'Threshold' field, which uses the return value of the 'Distance'
# field 1 in order to define a simple change in element size depending on the
# computed distances
gmsh.model.mesh.field.add("Threshold", 2)
gmsh.model.mesh.field.setNumber(2, "InField", 1)
gmsh.model.mesh.field.setNumber(2, "SizeMin", lc / 30)
gmsh.model.mesh.field.setNumber(2, "SizeMax", lc)
gmsh.model.mesh.field.setNumber(2, "DistMin", 0.15)
gmsh.model.mesh.field.setNumber(2, "DistMax", 0.5)

# modulating mesh size using mathematical function of spatial coord.
gmsh.model.mesh.field.add("MathEval", 3)
gmsh.model.mesh.field.setString(
    3, "F", "cos(4*3.14*x) * sin(4*3.14*y) / 10 + 0.101")

# Also, it's possible to combine MathEval with values coming from other fields.
gmsh.model.mesh.field.add("Distance", 4)
gmsh.model.mesh.field.setNumbers(4, "PointsList", [1])
gmsh.model.mesh.field.add("MathEval", 5)
gmsh.model.mesh.field.setString(5, "F", "F4^3 + " + str(lc / 100))

# Also, it's possible to impose a step change in elements size
gmsh.model.mesh.field.add("Box", 6)
gmsh.model.mesh.field.setNumber(6, "VIn", lc / 15)
gmsh.model.mesh.field.setNumber(6, "VOut", lc)
gmsh.model.mesh.field.setNumber(6, "XMin", 0.3)
gmsh.model.mesh.field.setNumber(6, "XMax", 0.6)
gmsh.model.mesh.field.setNumber(6, "YMin", 0.3)
gmsh.model.mesh.field.setNumber(6, "YMax", 0.6)
gmsh.model.mesh.field.setNumber(6, "Thickness", 0.3)

# there are a lot of fileds
gmsh.model.mesh.field.add("Min", 7)
gmsh.model.mesh.field.setNumbers(7, "FieldsList", [2, 3, 5, 6])
gmsh.model.mesh.field.setAsBackgroundMesh(7)

# Creating a global mesh size callback, called each time mesh size is queried
def meshSizeCallback(dim, tag, x, y, z, lc):
    return min(lc, 0.02 * x + 0.01)

gmsh.model.mesh.setSizeCallback(meshSizeCallback)

# HOW gmsh LOCALLY COMPUTES MESH ELEMENTS SIZE
'''
Locally computes the minimum of 
1. size of the model bounding box;
2. if "Mesh.MeshSizeFromPoints" is set, mesh specified at geometric points;
3. if "Mesh.MeshSizeFromCurvature" is positive, mesh size based on curvature
4. Background mesh size field;
5. Any Per-Entity mesh size constraint.

This value can be further modified in the interval 
["Mesh.MeshSizeMin", "Mesh.MeshSizeMax"]
and multiplied by "Mesh.MeshSizeFactor".
Boundary mesh sizes are interpolated inside surfaces and/or volumes depending
on the value of "Mesh.MeshSizeExtendFromBoundary"
'''

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

