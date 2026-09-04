#!/usr/bin/env python3


# gmsh documentation (https://gmsh.info/doc/texinfo/gmsh.html) 
# gmsh distribution (https://gitlab.onelab.info/gmsh/gmsh/-/tree/gmsh_4_15_2)


# CONTENT: Building volumes/shapes with extrusion along curve loops


import gmsh
import math


gmsh.initialize()

gmsh.model.add("Model")

# Volumes can be constructed from (closed) curve loops 
# (addThruSections)
gmsh.model.occ.addCircle(0, 0, 0, 0.5, 1)
gmsh.model.occ.addCurveLoop([1], 1)
gmsh.model.occ.addCircle(0.1, 0.05, 1, 0.1, 2)
gmsh.model.occ.addCurveLoop([2], 2)
gmsh.model.occ.addCircle(-0.1, -0.1, 2, 0.3, 3)
gmsh.model.occ.addCurveLoop([3], 3)
gmsh.model.occ.addThruSections([1, 2, 3], 1)
gmsh.model.occ.synchronize()

# Forcing the creation of ruled surfaces:
gmsh.model.occ.addCircle(2 + 0, 0, 0, 0.5, 11)
gmsh.model.occ.addCurveLoop([11], 11)
gmsh.model.occ.addCircle(2 + 0.1, 0.05, 1, 0.1, 12)
gmsh.model.occ.addCurveLoop([12], 12)
gmsh.model.occ.addCircle(2 - 0.1, -0.1, 2, 0.3, 13)
gmsh.model.occ.addCurveLoop([13], 13)
gmsh.model.occ.addThruSections([11, 12, 13], 11, True, True)
gmsh.model.occ.synchronize()

# Copying the first volume, and fillet all its edges:
out = gmsh.model.occ.copy([(3, 1)])
gmsh.model.occ.translate(out, 4, 0, 0)
gmsh.model.occ.synchronize()
e = gmsh.model.getBoundary(gmsh.model.getBoundary(out), False)
gmsh.model.occ.fillet([out[0][1]], [abs(i[1]) for i in e], [0.1])
gmsh.model.occ.synchronize()


# OpenCASCADE allows general extrusions along a smooth path.
nturns = 1.
npts = 20
r = 1.
h = 1. * nturns
p = []
for i in range(0, npts):
    theta = i * 2 * math.pi * nturns / npts
    gmsh.model.occ.addPoint(r * math.cos(theta), r * math.sin(theta),
                            i * h / npts, 1, 1000 + i)
    p.append(1000 + i)
gmsh.model.occ.addSpline(p, 1000)       # adding a spline
gmsh.model.occ.addWire([1000], 1000)        # wire is a curve loop, but open
gmsh.model.occ.addDisk(1, 0, 0, 0.2, 0.2, 1000)     # shape to be extruded along the spline
gmsh.model.occ.rotate([(2, 1000)], 0, 0, 0, 1, 0, 0, math.pi / 2)

# Disk is extruded along the spline to create a pipe
gmsh.model.occ.addPipe([(2, 1000)], 1000, 'DiscreteTrihedron')  # or 'Frenet'


# Deleting source surface and increasing the number of sub-edges for a better display
gmsh.model.occ.remove([(2, 1000)])
gmsh.option.setNumber("Geometry.NumSubEdges", 1000)

gmsh.model.occ.synchronize()

# Activating calculation of mesh element sizes based on curvature
# (20 elements per 2*Pi radians)
gmsh.option.setNumber("Mesh.MeshSizeFromCurvature", 20)

# Constraint to the min and max element sizes to stay within reasonable values
gmsh.option.setNumber("Mesh.MeshSizeMin", 0.001)
gmsh.option.setNumber("Mesh.MeshSizeMax", 0.3)

gmsh.model.mesh.generate(3)

gmsh.fltk.run()

gmsh.finalize()

