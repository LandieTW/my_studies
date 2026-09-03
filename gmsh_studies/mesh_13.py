#!/usr/bin/env python3


# gmsh documentation (https://gmsh.info/doc/texinfo/gmsh.html) 
# gmsh distribution (https://gitlab.onelab.info/gmsh/gmsh/-/tree/gmsh_4_15_2)


# CONTENT: Periodicity


import gmsh

gmsh.initialize()

gmsh.model.add("Model")


# Generating a unit cube with a non-uniform mesh size constraint 
gmsh.model.occ.addBox(0, 0, 0, 1, 1, 1, 1)
gmsh.model.occ.synchronize()
gmsh.model.mesh.setSize(gmsh.model.getEntities(0), 0.1)
gmsh.model.mesh.setSize([(0, 1)], 0.02)


# PERIODICITY:
# Impose that the mesh on surface 2 mathces the mesh from surface 1
# by copying surface 1 mesh to surface 2, with a 4x4 affine transformation 
# matrix that translates
translation = [1, 0, 0, 1, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1]
gmsh.model.mesh.setPeriodic(2, [2], [1], translation)

# Multiple periodicities can be imposed in the same way:
gmsh.model.mesh.setPeriodic(2, [6], [5],
                            [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 1, 0, 0, 0, 1])
gmsh.model.mesh.setPeriodic(2, [4], [3],
                            [1, 0, 0, 0, 0, 1, 0, 1, 0, 0, 1, 0, 0, 0, 0, 1])

# Generating a more complicated geometry.
gmsh.model.occ.addBox(2, 0, 0, 1, 1, 1, 10)
x = 2 - 0.3
y = 0
z = 0
gmsh.model.occ.addSphere(x, y, z, 0.35, 11)
gmsh.model.occ.addSphere(x + 1, y, z, 0.35, 12)
gmsh.model.occ.addSphere(x, y + 1, z, 0.35, 13)
gmsh.model.occ.addSphere(x, y, z + 1, 0.35, 14)
gmsh.model.occ.addSphere(x + 1, y + 1, z, 0.35, 15)
gmsh.model.occ.addSphere(x, y + 1, z + 1, 0.35, 16)
gmsh.model.occ.addSphere(x + 1, y, z + 1, 0.35, 17)
gmsh.model.occ.addSphere(x + 1, y + 1, z + 1, 0.35, 18)

# Fragment all the volumes, which will leave parts of spheres outside the cube
out, _ = gmsh.model.occ.fragment([(3, 10)], [(3, i) for i in range(11, 19)])
gmsh.model.occ.synchronize()

# Ask OpenCASCADE to compute more accurate bounding boxes of entities using
# the STL mesh
gmsh.option.setNumber("Geometry.OCCBoundsUseStl", 1)

# Retrieving all the volumes in the bounding box of the original cube,
# and delete all the parts outside it:
eps = 1e-3
vin = gmsh.model.getEntitiesInBoundingBox(2 - eps, -eps, -eps, 2 + 1 + eps,
                                          1 + eps, 1 + eps, 3)
for v in vin:
    out.remove(v)
gmsh.model.removeEntities(out, True)  # Delete outside parts recursively

# Set a non-uniform mesh size constraint 
# (To check results visually):
p = gmsh.model.getBoundary(vin, False, False, True)  # Get all points
gmsh.model.mesh.setSize(p, 0.1)
p = gmsh.model.getEntitiesInBoundingBox(2 - eps, -eps, -eps, 2 + eps, eps, eps,
                                        0)
gmsh.model.mesh.setSize(p, 0.001)

# Identify corresponding surfaces on the left and right sides of the
# geometry automatically. Starting from all surfaces on the left:
sxmin = gmsh.model.getEntitiesInBoundingBox(2 - eps, -eps, -eps, 
                                            2 + eps, 1 + eps, 1 + eps,
                                            2)
for i in sxmin:
    # Getting the bounding box of each left surface
    xmin, ymin, zmin, xmax, ymax, zmax = gmsh.model.getBoundingBox(i[0], i[1])
    # Translate bounding box to the right and look for surfaces inside it
    sxmax = gmsh.model.getEntitiesInBoundingBox(xmin - eps + 1, ymin - eps,
                                                zmin - eps, xmax + eps + 1,
                                                ymax + eps, zmax + eps, 
                                                2)
    # For all the matches, compare the corresponding bounding boxes...
    for j in sxmax:
        xmin2, ymin2, zmin2, xmax2, ymax2, zmax2 = gmsh.model.getBoundingBox(
            j[0], j[1])
        xmin2 -= 1
        xmax2 -= 1
        # ...and if they match, periodicity constraint is applied
        if (abs(xmin2 - xmin) < eps and abs(xmax2 - xmax) < eps and
            abs(ymin2 - ymin) < eps and abs(ymax2 - ymax) < eps and
            abs(zmin2 - zmin) < eps and abs(zmax2 - zmax) < eps):
            gmsh.model.mesh.setPeriodic(2, [j[1]], [i[1]], translation)

gmsh.model.mesh.generate(3)
gmsh.fltk.run()
gmsh.finalize()

