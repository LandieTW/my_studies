#!/usr/bin/env python3


# gmsh documentation (https://gmsh.info/doc/texinfo/gmsh.html) 
# gmsh distribution (https://gitlab.onelab.info/gmsh/gmsh/-/tree/gmsh_4_15_2)


import gmsh
import math


gmsh.initialize()


def createGeometryAndMesh():

    gmsh.clear()
    gmsh.model.add("Model")

    lc = 1e-2
    gmsh.model.geo.addPoint(0, 0, 0, lc, 1)
    gmsh.model.geo.addPoint(.1, 0, 0, lc, 2)
    gmsh.model.geo.addPoint(.1, .3, 0, lc, 3)
    gmsh.model.geo.addPoint(0, .3, 0, lc, 4)
    gmsh.model.geo.addLine(1, 2, 1)
    gmsh.model.geo.addLine(3, 2, 2)
    gmsh.model.geo.addLine(3, 4, 3)
    gmsh.model.geo.addLine(4, 1, 4)
    gmsh.model.geo.addCurveLoop([4, 1, -2, 3], 1)
    gmsh.model.geo.addPlaneSurface([1], 1)
    gmsh.model.geo.synchronize()
    gmsh.model.addPhysicalGroup(1, [1, 2, 4], 5)
    gmsh.model.addPhysicalGroup(2, [1], name="My surface")


    # -------------------------------------------------------------------------
    # -- NEW CONTENT - NEW CONTENT - NEW CONTENT - NEW CONTENT - NEW CONTENT --
    # -------------------------------------------------------------------------
    # -- NEW CONTENT - NEW CONTENT - NEW CONTENT - NEW CONTENT - NEW CONTENT --
    # -------------------------------------------------------------------------


    # MESH AND GEOMETRY EXTRUSION
    h = 0.1
    ov = gmsh.model.geo.extrude(
        [(2, 1)],                               # plane surface
        0, 0, h,                                # direction of extrusion
        [8, 2],                                 # number of elements by layer
        [0.5, 1]                                # height of layers
    )

    # EXTRUSION WITH ROTATION
    ov = gmsh.model.geo.revolve(
        [(2, 28)],                      # points tags
        -0.1, 0, 0.1,                   # axis point
        0, 1, 0,                        # revolve direction
        -math.pi / 2,                   # revolve angle
        [7]
    )

    # Using the built-in geometry kernel, only rotations with angles < Pi are
    # supported. To do a full turn, you will thus need to apply at least 3
    # rotations. The OpenCASCADE geometry kernel does not have this limitation.

    # TRANSLATION AND ROTATION AT SAME TIME = TWIST
    angle = gmsh.onelab.getNumber('Parameters/Twisting angle')[0]
    ov = gmsh.model.geo.twist(
        [(2, 50)],                          # points tags
        0, 0.15, 0.25,                      # axis point
        -2 * h, 0, 0,                       # extrusion direction
        1, 0, 0,                            # revolve direction
        angle * math.pi / 180.,             # twisting rotation angle
        [10],                               # number of elements by layer
        [],                                 # layers heights
        True                                # mesh recombination after twisting
    )

    # All the extrusion functions return a vector of extruded entities: the
    # "top" of the extruded surface (in `ov[0]'), the newly created volume (in
    # `ov[1]') and the tags of the lateral surfaces (in `ov[2]', `ov[3]', ...).

    gmsh.model.geo.synchronize()

    gmsh.model.addPhysicalGroup(3, [1, 2, ov[1][1]], 101)
    
    gmsh.model.mesh.generate(3)

# MAKING POINT TAGS VISIBLE AND CHANGING SOME COLORS
gmsh.option.setNumber("Geometry.PointNumbers", 1)
gmsh.option.setColor("Geometry.Color.Points", 255, 165, 0)
gmsh.option.setColor("General.Color.Text", 255, 255, 255)
gmsh.option.setColor("Mesh.Color.Points", 255, 0, 0)

r, g, b, a = gmsh.option.getColor("Geometry.Points")
gmsh.option.setColor("Geometry.Surfaces", r, g, b, a)

# We create a ONELAB parameter to define the angle of the twist. ONELAB
# parameters can be modified interactively in the GUI, and can be exchanged with
# other codes connected to the same ONELAB database. The database can be
# accessed through the Gmsh Python API using JSON-formatted strings (see
# https://gitlab.onelab.info/doc/models/wikis/ONELAB-JSON-interface for more
# information):
gmsh.onelab.set("""[
  {
    "type":"number",
    "name":"Parameters/Twisting angle",
    "values":[90],
    "min":0,
    "max":120,
    "step":1
  }
]""")

createGeometryAndMesh()

def checkForEvent():
    '''
    Makes graphics change according to user iteraction
    '''
    action = gmsh.onelab.getString("ONELAB/Action")
    if len(action) and action[0] == "check":
        gmsh.onelab.setString("ONELAB/Action", [""])
        createGeometryAndMesh()
        gmsh.graphics.draw()
    return True

gmsh.fltk.initialize()
while gmsh.fltk.isAvailable() and checkForEvent():
    gmsh.fltk.wait()


gmsh.finalize()

