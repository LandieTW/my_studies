#!/usr/bin/env python3


# gmsh documentation (https://gmsh.info/doc/texinfo/gmsh.html) 
# gmsh distribution (https://gitlab.onelab.info/gmsh/gmsh/-/tree/gmsh_4_15_2)


# CONTENT: How to manipulate mesh shapes


import gmsh


gmsh.initialize()

gmsh.model.add("Model")

p1 = gmsh.model.geo.addPoint(-1.25, -.5, 0)
p2 = gmsh.model.geo.addPoint(1.25, -.5, 0)
p3 = gmsh.model.geo.addPoint(1.25, 1.25, 0)
p4 = gmsh.model.geo.addPoint(-1.25, 1.25, 0)

l1 = gmsh.model.geo.addLine(p1, p2)
l2 = gmsh.model.geo.addLine(p2, p3)
l3 = gmsh.model.geo.addLine(p3, p4)
l4 = gmsh.model.geo.addLine(p4, p1)

cl = gmsh.model.geo.addCurveLoop([l1, l2, l3, l4])
pl = gmsh.model.geo.addPlaneSurface([cl])

gmsh.model.geo.synchronize()

# -----------------------------------------------------------------------------
# ---- NEW CONTENT - NEW CONTENT - NEW CONTENT - NEW CONTENT - NEW CONTENT ----
# -----------------------------------------------------------------------------
# ---- NEW CONTENT - NEW CONTENT - NEW CONTENT - NEW CONTENT - NEW CONTENT ----
# -----------------------------------------------------------------------------

field = gmsh.model.mesh.field
field.add("MathEval", 1)
field.setString(1, "F", "0.01*(1.0+30.*(y-x*x)*(y-x*x) + (1-x)*(1-x))")
field.setAsBackgroundMesh(1)

# TO GENERATE QUADRANGLES INSTEAD OF TRIANGLES
gmsh.model.mesh.setRecombine(2, pl)

# COULD USE ALSO
# Mesh.RecombineAll
gmsh.option.setNumber("Mesh.RecombineAll", 1)

'''
The default recombination algorithm is called "Blossom"
It uses a minimum cost perfect matching algorithm to generate fully 
quadrilateral meshes from triangulations.
'''

'''
For even better 2D (planar) quadrilateral meshes, you can try the experimental
Frontal-Delaunay for quads meshing algorithm, which is a triagulation algorithm
that creates right triangles almost everywhere.
'''
gmsh.option.setNumber("Mesh.Algorithm", 8)

'''
To generate full-quad meshes, you can either subdivide the resulting hybrid
mesh or use the full-quad recombination algorithm, wich will automatically
perform a coarser mesh followed by recombination, smoothing and subdivision.
'''
gmsh.option.setNumber("Mesh.RecombinationAlgorithm", 2)     # or 3

# subsivision
gmsh.option.setNumber("Mesh.SubdivisionAlgorithm", 1)

gmsh.model.mesh.refine()

gmsh.model.mesh.generate(2)

gmsh.fltk.run()

gmsh.finalize()

