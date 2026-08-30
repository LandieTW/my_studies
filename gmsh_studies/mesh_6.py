

import gmsh

gmsh.initialize()

gmsh.model.add("Model")

lc=1e-2

factory = gmsh.model.geo

factory.addPoint(0, 0, 0, lc, 1)
factory.addPoint(.1, 0, 0, lc, 2)
factory.addPoint(.1, .3, 0, lc, 3)
factory.addPoint(0, .3, 0, lc, 4)
factory.addLine(1, 2, 1)
factory.addLine(3, 2, 2)
factory.addLine(3, 4, 3)
factory.addLine(4, 1, 4)
factory.addCurveLoop([4, 1, -2, 3], 1)
factory.addPlaneSurface([1], 1)

# DELETE THE SURFACE AND THE LEFT LINE
factory.remove([(2, 1), (1, 4)])

p1 = factory.addPoint(-0.05, 0.05, 0, lc)
p2 = factory.addPoint(-0.05, 0.1, 0, lc)
l1 = factory.addLine(1, p1)
l2 = factory.addLine(p1, p2)
l3 = factory.addLine(p2, 4)

factory.addCurveLoop([2, -1, l1, l2, l3, -3], 2)
factory.addPlaneSurface([-2], 1)

# forces 20 uniformly placed nodes on curve 2
factory.mesh.setTransfiniteCurve(2, 20)
# 20 points total on combination of curves l1, l2, l3
factory.mesh.setTransfiniteCurve(l1, 6)
factory.mesh.setTransfiniteCurve(l2, 6)
factory.mesh.setTransfiniteCurve(l3, 10)

# put 30 nodes following a goemetric progression on curve 1 and on curve 3
factory.mesh.setTransfiniteCurve(1, 30, "Progression", -1.2)
factory.mesh.setTransfiniteCurve(3, 30, "Progression", 1.2)

'''
setTransfiniteSurface
meshing constraint uses a transfinite interpolation algorithm in the parametric
plane of the surface to connect the nodes on the boudary using a structured
grid. If the surface has more than 4 corner points, the corners of the
transfinite interpolation have be specified.
'''
factory.mesh.setTransfiniteSurface(1, "Left", [1, 2, 3, 4])

# To create quadrangles instead of triangles
factory.mesh.setRecombine(2, 1)

factory.addPoint(0.2, 0.2, 0, 1.0, 7)
factory.addPoint(0.2, 0.1, 0, 1.0, 8)
factory.addPoint(0.25, 0.2, 0, 1.0, 9)
factory.addPoint(0.3, 0.1, 0, 1.0, 10)
factory.addLine(8, 10, 10)
factory.addLine(10, 9, 11)
factory.addLine(9, 7, 12)
factory.addLine(7, 8, 13)
factory.addCurveLoop([13, 10, 11, 12], 14)
factory.addPlaneSurface([14], 15)
for i in range(10, 14):
    factory.mesh.setTransfiniteCurve(i, 10)
factory.mesh.setTransfiniteSurface(15)

'''
The way triangles are generated can be controlled by specifying "Left",
"Right" or "Alternate" in `setTransfiniteSurface()'. Try e.g.

gmsh.model.geo.mesh.setTransfiniteSurface(15, "Alternate")
'''

factory.synchronize()
gmsh.option.setNumber("Mesh.Smoothing", 100)
gmsh.model.mesh.generate(2)

gmsh.fltk.run()
gmsh.finalize()

