#!/usr/bin/env python3


# gmsh documentation (https://gmsh.info/doc/texinfo/gmsh.html) 
# gmsh distribution (https://gitlab.onelab.info/gmsh/gmsh/-/tree/gmsh_4_15_2)


import gmsh


gmsh.initialize()
gmsh.model.add("Model")

# target mesh_size close to the point
ms = 1e-1

p1 = gmsh.model.geo.addPoint(
    -5, -5, 0,                      # points coordinates
    ms                              # mesh size around the point
    )
p2 = gmsh.model.geo.addPoint(-5, 5, 0, ms)
p3 = gmsh.model.geo.addPoint(5, 5, 0, ms)
p4 = gmsh.model.geo.addPoint(5, -5, 0, ms)

l1 = gmsh.model.geo.addLine(
    p1, p2                          # start and end points
    )
l2 = gmsh.model.geo.addLine(p2, p3)
l3 = gmsh.model.geo.addLine(p3, p4)
l4 = gmsh.model.geo.addLine(p4, p1)

gmsh.model.geo.addCurveLoop(
    [1, 2, 3, 4],                   # surface boundary composed by lines
    1                               # surface boundary tag
    )
gmsh.model.geo.addPlaneSurface(
    [1]                             # Surface plan inside boundary
    )

# Calling Built-in CAD kernel

gmsh.model.addPhysicalGroup(
    1,                              # 1-D
    [1, 2, 3, 4]                    # lines tags
)
gmsh.model.addPhysicalGroup(
    2,                              # 2-D
    [1]                             # plane surface tag
)

gmsh.model.geo.synchronize()
gmsh.model.mesh.generate(2)
gmsh.fltk.run()
gmsh.finalize()

