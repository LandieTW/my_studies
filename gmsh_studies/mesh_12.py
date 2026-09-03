#!/usr/bin/env python3


# gmsh documentation (https://gmsh.info/doc/texinfo/gmsh.html) 
# gmsh distribution (https://gitlab.onelab.info/gmsh/gmsh/-/tree/gmsh_4_15_2)


# CONTENT: Cut, Fragment and getEntities examples (OpenCASCADE geometry kernel)


import gmsh

gmsh.initialize()

gmsh.model.add("Model")

# Logging all messages for further processing with:
gmsh.logger.start()


# -----------------------------------------------------------------------------
# ---- NEW CONTENT - NEW CONTENT - NEW CONTENT - NEW CONTENT - NEW CONTENT ----
# -----------------------------------------------------------------------------
# ---- NEW CONTENT - NEW CONTENT - NEW CONTENT - NEW CONTENT - NEW CONTENT ----
# -----------------------------------------------------------------------------


# Creating two cubes:
gmsh.model.occ.addBox(0, 0, 0, 1, 1, 1, 1)
gmsh.model.occ.addBox(0, 0, 0, 0.5, 0.5, 0.5, 2)

# How to make an object minus another
gmsh.model.occ.cut(
    [(3, 1)],           # object to be cutted (dimension, tag)
    [(3, 2)],           # cutting object (dimension, tag)
    3                   # tag
    )

# Boolean operations with OpenCASCADE always create new entities. 
# By default the extra arguments `removeObject' and `removeTool' in `cut()' 
# are set to `True', which will delete the original entities.

# Generating 5 spheres
x = 0
y = 0.75
z = 0
r = 0.09
holes = []
for t in range(1, 6):
    x += 0.166
    z += 0.166
    gmsh.model.occ.addSphere(x, y, z, r, 3 + t)
    holes.append((3, 3 + t))

# To make inclusions, whose mesh should be conformal => `fragment()', 
# which intersects all volumes in a conformal manner 
# (without creating duplicate interfaces):
ov, ovv = gmsh.model.occ.fragment(
    [(3, 3)],           # cube (dimension, tag) 
    holes               # 5 spheres
    )

# ov contains all the generated entities of the same dimension as the input
# entities:
print("fragment produced volumes:")
for e in ov:
    print(e)

# ovv contains the parent-child relationships for all the input entities:
print("before/after fragment relations:")
for e in zip([(3, 3)] + holes, ovv):
    print("parent " + str(e[0]) + " -> child " + str(e[1]))

gmsh.model.occ.synchronize()


# When the boolean operation leads to simple modifications of entities, and if
# one deletes the original entities, Gmsh tries to assign the same tag to the
# new entities. (Geometry.OCCBooleanPreserveNumbering)


for i in range(1, 6):
    gmsh.model.addPhysicalGroup(3, [3 + i], i)

# The tag of the cube will change though, so we need to access it:
gmsh.model.addPhysicalGroup(3, [ov[0][1]], 10)


# To identify points or other bounding entities...
# 1. getEntities()
# 2. getBoundary()
# 3. getClosestEntities()
# 4. getEntitiesInBoundingBox()


# Define a physical group for the top-most and right-most surfaces, by finding
# amongst the surfaces making up the boundary of the model, the two closest to
# point (1, 1, 0.5):
bnd = gmsh.model.getBoundary(gmsh.model.getEntities(3))
closest = gmsh.model.occ.getClosestEntities(1, 1, 0.5, bnd, 2)[0]
gmsh.model.addPhysicalGroup(2, [closest[0][1], closest[1][1]], 100,
                            "Top & right surfaces")

# Assign a mesh size to all the points:
lcar1 = .1
lcar2 = .0005
lcar3 = .055
gmsh.model.mesh.setSize(gmsh.model.getEntities(0), lcar1)

# Override this constraint on the points of the five spheres:
gmsh.model.mesh.setSize(gmsh.model.getBoundary(holes, False, False, True),
                        lcar3)

# Set a bounding box around the point (0.5, 0.5, 0.5) and refine the mesh size
eps = 1e-3
ov = gmsh.model.getEntitiesInBoundingBox(0.5 - eps, 0.5 - eps, 0.5 - eps,
                                         0.5 + eps, 0.5 + eps, 0.5 + eps, 0)
gmsh.model.mesh.setSize(ov, lcar2)

gmsh.model.mesh.generate(3)


# Inspect the log:
log = gmsh.logger.get()
print("Logger has recorded " + str(len(log)) + " lines")
gmsh.logger.stop()

gmsh.fltk.run()

gmsh.finalize()

