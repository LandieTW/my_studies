"""Module to generate the 1st and 2nd DVC figures - Contingency"""

__author__ = ["Mauro Rodrigues", "Yan Nascimento"]
__copyright__ = "TechnipFMC"
__credits__ = ""
__license__ = ""
__version__ = "2.0"
__maintainer__ = "Yan Nascimento"
__email__ = "yan.donascimento@technipfmc.com"
__status__ = "Developed"
__last_release__ = "July, 2026"

# Public Libraries (Python)
import numpy as np
import OrcFxAPI as orca
import matplotlib.pyplot as plt
# Private Libraries (Python)
from libs import generate_images as gimg

# Constant
# Control for precise movement - True to activate.
TURN_AXES_ON = False

# Define image height
FIGURE_HEIGHT_CM = 5.0

# Increase the graphic display window [m]
X_MIN_LIM = 0.0
X_MAX_LIM = 0.0
Z_MIN_LIM = 0.0
Z_MAX_LIM = 4.0

def generate_cont(
        file_paths: dict, 
        obj_names: dict,
        dvc_type: int,
        fontsize: int = 6,
        use_comma: bool = True,
    ) -> None:
    """
    Draw the contingency figure for the 1st and 2nd DVC.
    
    Args:
        file_paths: dict of the *.sim and *.png files.
        obj_names: orcaflex object dict - DVC.
        dvc_type: dvc type, 2 for 2nd and 1 for 1st DVC.
        fontsize: reference scale used to define text font size and line thickness.
        use_comma: unit system - True for "," and False for ".".

    Returns:
        None
    """
    # Get attachment data
    model = orca.Model(file_paths["cont_sim"])

    # Get objects
    vcm = model[obj_names["vcm"]]
    line = model[obj_names["line"]]
    bend_restrictor = model[obj_names["bend_restrictor"]]
    crane = model[obj_names["crane"]]
    # Get buoys or dead weights - from dynamic file    
    attach_data = gimg.get_buoys_attachment(model, line)

    """GET DATA"""
    # Get TDP X-coord
    x_tdp = line.StaticResult("X", orca.oeTouchdown)
    z_tdp = line.StaticResult("Z", orca.oeTouchdown)

    # Get TDPs
    zipped = zip(line.RangeGraph("Seabed Clearance").X, line.RangeGraph("Seabed Clearance").Mean)
    al_sbd_clear_0 = []

    for arc_length, seabed_clear in zipped:
        if seabed_clear < 0.0:
            al_sbd_clear_0.append(arc_length)

    x_tdp_1 = line.StaticResult("X" , orca.oeArcLength(min(al_sbd_clear_0)))
    z_tdp_1 = line.StaticResult("Z" , orca.oeArcLength(min(al_sbd_clear_0)))
    x_tdp_2 = line.StaticResult("X" , orca.oeArcLength(max(al_sbd_clear_0)))
    z_tdp_2 = line.StaticResult("Z" , orca.oeArcLength(max(al_sbd_clear_0)))

    # Get line, seabed and VCM data
    line_data = gimg.get_line_data(line)
    seabed_data = gimg.get_seabed_data(model)
    vcm_data = {
        "vcm_base_point_x": vcm.StaticResult("X"),
        "vcm_base_point_z": vcm.StaticResult("Z"),
        "flange_vcm_x": line.StaticResult("X", orca.oeEndB),
        "flange_vcm_z": line.StaticResult("Z", orca.oeEndB),
    }

    """CREATE FIGURE"""
    xz_range = {
        "x_min": vcm_data["vcm_base_point_x"] - 1 + X_MIN_LIM,
        "x_max": max(line_data.x) + 0.5 + X_MAX_LIM if dvc_type == 1 else x_tdp + 1 + X_MAX_LIM,
        "z_min": seabed_data.min_z - 1.0 + Z_MIN_LIM if dvc_type == 1 else seabed_data.min_z - 0.5 + Z_MIN_LIM,
        "z_max": vcm_data["flange_vcm_z"] + 3.0 + Z_MAX_LIM if dvc_type == 1 else max(line_data.z) + Z_MAX_LIM,
    }
    figsize = gimg.get_figsize_from_data(xz_range, FIGURE_HEIGHT_CM)
    fig, ax = plt.subplots(figsize=figsize)

    """DRAW THE DVC OBJECTS"""
    # Draw the DVC itens
    ax = gimg.draw_seabed(ax, seabed_data, xz_range["x_min"], xz_range["x_max"], lw=fontsize*0.1)
    ax = gimg.draw_vcm_dvc(ax, vcm_data["vcm_base_point_x"], vcm_data["vcm_base_point_z"], linewidth=fontsize*0.05)
    ax = gimg.draw_winch(ax, crane, lw=fontsize*0.05)

    #Draw the external outline - Flexible and Bend Restrictor
    ax = gimg.draw_external_lines(ax, line, line_data, lw=fontsize*0.03)
    if bend_restrictor:
        br_data = gimg.get_line_data(bend_restrictor)
        ax = gimg.draw_external_lines(ax, bend_restrictor, br_data, facecolor="grey", lw=fontsize*0.03)

    # Draw the attachments
    ax = gimg.draw_attachments(
        ax, line, attach_data, use_comma, fontsize=fontsize, stc_descr=False, drg_cont=True,
    )
    
    if dvc_type == 2:
        ar = model[obj_names["ar"]]
        link1 = model[obj_names["link1"]]
        link2 = model[obj_names["link2"]]
        ax = gimg.draw_ar_slings(ax, ar, link1, link2, linewidth=fontsize*0.05)
        ax = gimg.indicate_tdp(ax=ax, xz_tdp=(x_tdp, z_tdp), **{"fontsize":fontsize, "ha":"center"})
    elif dvc_type == 1:
        idx_min = np.argmin(line_data.z)
        line_z = line_data.z[:idx_min]
        line_x = line_data.x[:idx_min]
        # Get the line XZ-coord - Point at 2 times the height of the MCV flange
        vcm_h = vcm_data["flange_vcm_z"]
        z_vcm_h = min(line_z, key=lambda x: abs(x - vcm_h))
        idx_vcm_h = np.nonzero(np.isclose(line_z, z_vcm_h))[0][0]

        # Horizontal dimension - from the flange to the other side at the same Z.
        ax = gimg.draw_horizontal_dimensions(
            ax, 
            x_start=seabed_data.origin_x, 
            x_end=line_x[idx_vcm_h], 
            z_start=z_vcm_h, 
            z_end=z_vcm_h,
            mov_z=5.0,
            fontsize=fontsize,
            use_comma=use_comma,
        )

        # Horizontal dimension - from the TDP1 to the TDP2.
        ax = gimg.draw_horizontal_dimensions(
            ax, 
            x_start=x_tdp_1, 
            x_end=x_tdp_2, 
            z_start=z_tdp_1, 
            z_end=z_tdp_2,
            mov_z=-1.0,
            fontsize=fontsize,
            use_comma=use_comma,
        )

    gimg.save_figure(ax, fig, xz_range, file_paths["cont_png"], turn_on_axes=TURN_AXES_ON)

    return None