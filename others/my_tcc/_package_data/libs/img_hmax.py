"""Module to generate the 2nd DVC figures - Hmax"""

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
import OrcFxAPI as orca
import matplotlib.pyplot as plt
# Private Libraries (Python)
from libs import generate_images as gimg

# Constants
# Control for precise movement - True to activate.
TURN_AXES_ON = False

# Define image height
FIGURE_HEIGHT_CM = 4.0

# Increase the graphic display window [m]
X_MIN_LIM = 0.0
X_MAX_LIM = 0.0
Z_MIN_LIM = 0.0
Z_MAX_LIM = 0.0

HMAX_TEXT = "Esta configuração NÃO deve ser utilizada após acoplamento no HUB."

def generate_static_hmax(
        ax: object, 
        line: orca.OrcaFlexLineObject, 
        bend_restrictor: orca.OrcaFlex6DBuoyObject, 
        vcm: orca.OrcaFlex6DBuoyObject,
    ) -> object:
    """
    Draw the static figure for the Hmax analysis - 2nd DVC.
    
    Args:
        ax: the axes object on which the plot will be drawn.
        line: orcaflex line object - Line.
        bend_restrictor: orcaflex line object - Bend Restrictor.
        vcm: orcaflex 6D buoy object - VCM.

    Returns:
        ax: axes object on which the plot was drawn.
    """
    # Get data
    line_data = gimg.get_line_data(line)
    vcm_base_x = vcm.StaticResult("X")
    vcm_base_z = vcm.StaticResult("Z")
    vcm_base_angle = vcm.StaticResult("Declination")
    #Draw the external outline - Flexible and Bend Restrictor
    ax = gimg.draw_external_lines(ax, line, line_data, facecolor="gainsboro", lw=0)
    if bend_restrictor:
        br_data = gimg.get_line_data(bend_restrictor)
        ax = gimg.draw_external_lines(ax, bend_restrictor, br_data, facecolor="gainsboro", lw=0)

    gimg.draw_vcm_dvc(ax, vcm_base_x, vcm_base_z, vcm_base_angle=vcm_base_angle, facecolor="gainsboro", lw=0)

    return ax

def generate_hmax(
        model_dyn: orca.Model,
        file_paths: dict, 
        obj_names: dict,
        fontsize: int = 6,
        use_comma: bool = True,
    ) -> None:
    """
    Draw the Hmax figure for the 2nd DVC.
    
    Args:
        model_stc: orcaflex model object - dynamic file.
        file_paths: dict of the *.sim and *.png files.
        obj_names: orcaflex object dict - DVC.
        fontsize: reference scale used to define text font size and line thickness.
        use_comma: unit system - True for "," and False for ".".

    Returns:
        None
    """

    # Static file
    line_stc = model_dyn[obj_names["line"]]
    vcm_stc = model_dyn[obj_names["vcm"]]
    bend_restrictor_stc = model_dyn[obj_names["bend_restrictor"]]
    vcm_base_point_x_stc = vcm_stc.StaticResult("X")

    # Hmax file
    model_hmax = orca.Model(file_paths["hmax_sim"])
    # Get objects
    line = model_hmax[obj_names["line"]]
    vcm = model_hmax[obj_names["vcm"]]
    bend_restrictor = model_hmax[obj_names["bend_restrictor"]]
    ar = model_hmax[obj_names["ar"]]
    crane = model_hmax[obj_names["crane"]]
    link1 = model_hmax[obj_names["link1"]]
    link2 = model_hmax[obj_names["link2"]]
    # Get buoys or dead weights - from dynamic file    
    attach_data = gimg.get_buoys_attachment(model_hmax, line)

    """GET DATA"""
    # Get TDP X-coord
    x_tdp = line.StaticResult("X", orca.oeTouchdown)
    z_tdp = line.StaticResult("Z", orca.oeTouchdown)

    # Get line, seabed and VCM data
    line_data = gimg.get_line_data(line)
    n_nodes = line.CumulativeLength[-1]
    seabed_data = gimg.get_seabed_data(model_hmax)
    vcm_data = {
        "vcm_base_point_x": vcm.StaticResult("X"),
        "vcm_base_point_z": vcm.StaticResult("Z"),
        "flange_vcm_x": line.StaticResult("X", orca.oeEndB),
        "flange_vcm_z": line.StaticResult("Z", orca.oeEndB),
        "vcm_base_angle": vcm.StaticResult("Declination")
    }

    # Get line connection point (arc length) to the links
    link1_arclength = gimg.get_link_position(line, link1)
    link2_arclength = gimg.get_link_position(line, link2)

    # Get the minimum seabed clearance of the line
    line_min_clearance = gimg.get_min_point_line(
        line, bend_restrictor=None,
        from_arclength=link1_arclength, to_arclength=n_nodes,
    )
    # Get the maximum seabed clearance of the line
    line_max_clearance = gimg.get_max_point_line(
        line, from_arclength=link1_arclength, to_arclength=link2_arclength,
    )

    """CREATE FIGURE"""
    xz_range = {
        "x_min": vcm_base_point_x_stc - 1.0 + X_MIN_LIM,
        "x_max": x_tdp + 1.0 + X_MAX_LIM,
        "z_min": seabed_data.min_z - 2.0 + Z_MIN_LIM,
        "z_max": link1.StaticResult("End A Z") + 0.5 + Z_MAX_LIM,
    }

    figsize = gimg.get_figsize_from_data(xz_range, FIGURE_HEIGHT_CM)
    fig, ax = plt.subplots(figsize=figsize)

    """DRAW THE DVC OBJECTS"""
    # Static file
    ax = generate_static_hmax(ax, line_stc, bend_restrictor_stc, vcm_stc)

    # From here, only hmax file
    # Draw the DVC itens
    ax = gimg.draw_seabed(ax, seabed_data, xz_range["x_min"], xz_range["x_max"], lw=fontsize*0.1)
    ax = gimg.draw_vcm_dvc(ax, vcm_data["vcm_base_point_x"], vcm_data["vcm_base_point_z"],vcm_data["vcm_base_angle"], linewidth=fontsize*0.05)
    ax = gimg.draw_winch(ax, crane, lw=fontsize*0.05)
    ax = gimg.draw_ar_slings(ax, ar, link1, link2, linewidth=fontsize*0.05)
    ax = gimg.indicate_tdp(ax=ax, xz_tdp=(x_tdp, z_tdp), **{"fontsize":fontsize, "ha":"center"})

    #Draw the external outline - Flexible and Bend Restrictor
    ax = gimg.draw_external_lines(ax, line, line_data, lw=fontsize*0.03)
    if bend_restrictor:
        br_data = gimg.get_line_data(bend_restrictor)
        ax = gimg.draw_external_lines(ax, bend_restrictor, br_data, facecolor="grey", lw=fontsize*0.03)

    """DRAW THE DVC DIMENSIONS"""
    # Draw the distance dimension from the VCM flange to the seabed (Z-axis)
    hmax_endb_sb_clearance = line.StaticResult("Vertical seabed clearance", orca.oeEndB)
    line_radius = line.lineTypeAt(n_nodes).ContactDiameter * 0.5

    fs_ratio = 0.9

    ax = gimg.draw_vertical_dimensions(
        ax, 
        x_start=vcm_data["flange_vcm_x"],
        x_end=vcm_data["flange_vcm_x"],
        z_start=vcm_data["flange_vcm_z"],
        z_end=vcm_data["flange_vcm_z"]-(hmax_endb_sb_clearance+line_radius),
        fontsize=fontsize*fs_ratio,
        rotation="horizontal",
        mov_x=0,
    )

    # From the line to the seabed (Z-axis)
    ax = gimg.draw_vertical_dimensions(
        ax, 
        x_start=line_min_clearance.x_min, 
        x_end=line_min_clearance.x_min,
        z_start=line_min_clearance.z_min, 
        z_end=line_min_clearance.z_min - line_min_clearance.vertical_min,
        fontsize=fontsize*fs_ratio,
        rotation="horizontal",
        mov_x=0,
    )

    # From the line to the seabed in the hump area (Z-axis)
    ax = gimg.draw_vertical_dimensions(
        ax, 
        x_start=line_max_clearance.x_max, 
        x_end=line_max_clearance.x_max,
        z_start=line_max_clearance.z_max, 
        z_end=line_max_clearance.z_max-line_max_clearance.vertical_max,
        fontsize=fontsize*fs_ratio,
        rotation="horizontal",
        mov_x=0,
    )

    # From the TDP to the flange (X-axis)
    ax = gimg.draw_horizontal_dimensions(
        ax, 
        x_start=vcm_data["flange_vcm_x"], 
        x_end=x_tdp,
        z_start=seabed_data.min_z, 
        z_end=link1.StaticResult("End A Z"),
        fontsize=fontsize*fs_ratio,
        mov_z=0,
    )

    ref_z = -fontsize*0.25
    # From the flange (static) to the flange (hmax)
    ax = gimg.draw_horizontal_dimensions(
        ax, 
        x_start=line_stc.StaticResult("X", orca.oeEndB), 
        x_end=vcm_data["flange_vcm_x"],
        z_start=line_stc.StaticResult("Z", orca.oeEndB), 
        z_end=seabed_data.min_z,
        fontsize=fontsize*fs_ratio,
        mov_z=ref_z,
    )

    # Draw the attachments
    ax = gimg.draw_attachments(
        ax, line, attach_data, use_comma, fontsize=fontsize*fs_ratio, stc_descr=False,
    )

    ax.text(
        line_max_clearance.x_max,  
        seabed_data.min_z-0.7+ref_z, 
        s=HMAX_TEXT, 
        fontweight="bold",
        ha="center",
        fontsize=fontsize*fs_ratio,
    )

    gimg.save_figure(ax, fig, xz_range, file_paths["hmax_png"], turn_on_axes=TURN_AXES_ON)
    return None