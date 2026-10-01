"""Module to generate the 2nd DVC figures - Puxada"""

__author__ = ["Mauro Rodrigues", "Yan Nascimento"]
__copyright__ = "TechnipFMC"
__credits__ = ""
__license__ = ""
__version__ = "2.0"
__maintainer__ = "Yan Nascimento"
__email__ = "yan.donascimento@technipfmc.com"
__status__ = "Developed"
__status__ = "Developed"
__last_release__ = "July, 2026"

# Public Libraries (Python)
import OrcFxAPI as orca
import matplotlib.pyplot as plt
# Private Libraries (Python)
from libs import generate_images as gimg
# Constants
FIGURE_HEIGHT_CM = 5.0
# Control for precise movement - True to activate.
TURN_AXES_ON = False

# Increase the graphic display window [m]
X_MIN_LIM = 0.0
X_MAX_LIM = 0.0
Z_MIN_LIM = 0.0
Z_MAX_LIM = 0.0

def generate_puxada(
        file_paths: dict, 
        obj_names: dict,
        fontsize: int = 6,
        use_comma: bool = True,
    ) -> None:
    """
    Draw the 'Puxada' figure for the 2nd DVC.
    
    Args:
        file_paths: dict of the *.sim and *.png files.
        obj_names: orcaflex object dict - DVC.
        fontsize: reference scale used to define text font size and line thickness.
        use_comma: unit system - True for "," and False for ".".

    Returns:
        None
    """

    # Puxada file
    model = orca.Model(file_paths["puxada_sim"])
    # Get objects
    line = model[obj_names["line"]]
    vcm = model[obj_names["vcm"]]
    bend_restrictor = model[obj_names["bend_restrictor"]]
    ar = model[obj_names["ar"]]
    crane = model[obj_names["crane"]]
    link1 = model[obj_names["link1"]]
    link2 = model[obj_names["link2"]]
    # Get buoys or dead weights - from dynamic file    
    attach_data = gimg.get_buoys_attachment(model, line)

    """GET DATA"""
    # Get TDP X-coord
    x_tdp = line.StaticResult("X", orca.oeTouchdown)
    z_tdp = line.StaticResult("Z", orca.oeTouchdown)

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
        "x_min": vcm_data["vcm_base_point_x"] - 1.0 + X_MIN_LIM,
        "x_max": x_tdp + 1.0 + X_MAX_LIM,
        "z_min": seabed_data.min_z - 0.5 + Z_MIN_LIM,
        "z_max": max(line_data.z) + 4.5 + Z_MAX_LIM,
    }
    figsize = gimg.get_figsize_from_data(xz_range, FIGURE_HEIGHT_CM)
    fig, ax = plt.subplots(figsize=figsize)

    """DRAW THE DVC OBJECTS"""
    # Draw the DVC itens
    ax = gimg.draw_seabed(ax, seabed_data, xz_range["x_min"], xz_range["x_max"], lw=fontsize*0.1)
    ax = gimg.draw_vcm_dvc(ax, vcm_data["vcm_base_point_x"], vcm_data["vcm_base_point_z"], linewidth=fontsize*0.05)
    ax = gimg.draw_winch(ax, crane, lw=fontsize*0.05)
    ax = gimg.draw_ar_slings(ax, ar, link1, link2, linewidth=fontsize*0.05)
    ax = gimg.indicate_tdp(ax=ax, xz_tdp=(x_tdp, z_tdp), **{"fontsize":fontsize, "ha":"center"})

    #Draw the external outline - Flexible and Bend Restrictor
    ax = gimg.draw_external_lines(ax, line, line_data)
    if bend_restrictor:
        br_data = gimg.get_line_data(bend_restrictor)
        ax = gimg.draw_external_lines(ax, bend_restrictor, br_data, facecolor="grey")

    # Draw the attachments
    ax = gimg.draw_attachments(
        ax, line, attach_data, use_comma, fontsize=fontsize*0.8, stc_descr=False,
    )

    gimg.save_figure(ax, fig, xz_range, file_paths["puxada_png"], turn_on_axes=TURN_AXES_ON)
    return None
