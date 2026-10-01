"""Module to generate the 1st and 2nd DVC figures - Only Static"""

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

# Constants
# Control for precise movement - True to activate.
TURN_AXES_ON = False
# Define image height
FIGURE_HEIGHT_CM = 5.0

# Increase the graphic display window [m]
X_MIN_LIM = 0.0
X_MAX_LIM = 0.0
Z_MIN_LIM = 0.0
Z_MAX_LIM = 0.0

def static_1st_dvc(
        ax: object, 
        line: orca.OrcaFlexLineObject, 
        bend_restrictor: orca.OrcaFlexLineObject,
        attach_data: dict,
        line_data: tuple, 
        vcm_data: dict,
        seabed_data: tuple,
        fontsize: int, 
        use_comma: bool
    ) -> object:
    """
    Draw the dimensions of the 1st DVC.
    
    Args:
        ax: the axes object on which the plot will be drawn.
        line: orcaflex line object.
        bend_restrictor: orcaflex bend restrictor object.
        attach_data: anode, buoys, and dead weight data.
        line_data: line data tuple.
        vcm_data: vcm data object.
        seabed_data: seabed data tuple.
        fontsize: reference scale used to define text font size and line thickness.
        use_comma: unit system - True for "," and False for ".".

    Returns:
        ax: axes object on which the plot was drawn.
    """
    # Get the minimum seabed clearance of the line
    line_min_clearance = gimg.get_min_point_line(
        line, bend_restrictor,
        from_arclength=line.CumulativeLength[0], 
        to_arclength=line.CumulativeLength[-1],
    )

    # Get line XZ data
    idx_argmin = np.argmin(line_data.z)
    line_z = line_data.z[:idx_argmin]
    line_x = line_data.x[:idx_argmin]
    line_radius = line.lineTypeAt(line_data.arclength[idx_argmin]).ContactDiameter

    # Get bend restrictor data
    bend_restrictor_data = gimg.get_line_data(bend_restrictor)
    br_x_max = max(bend_restrictor_data.x)
    br_z_max = bend_restrictor_data.z[0]

    # Get the line XZ-coord - Point at the same height as the MCV flange
    z_vcm_h = min(line_z, key=lambda x: abs(x - vcm_data["flange_vcm_z"]))
    idx_vcm_h = np.nonzero(np.isclose(line_z, z_vcm_h))[0][0]
    x_vcm_h_2nd_point = line_x[idx_vcm_h]

    # Draw the distance dimension from the VCM flange to the seabed (Z-axis)
    ax = gimg.draw_vertical_dimensions(
        ax, 
        x_start=vcm_data["flange_vcm_x"], 
        x_end=vcm_data["flange_vcm_x"],
        z_start=vcm_data["flange_vcm_z"], 
        z_end=seabed_data.origin_z,
        fontsize=fontsize,
        ha="right", va="top",
        extension_line=True,
        mov_x=0,
    )

    # Draw the minimum distance dimension from the line to the seabed (Z-axis)
    ax = gimg.draw_vertical_dimensions(
        ax, 
        x_start=line_min_clearance.x_min, 
        x_end=line_min_clearance.x_min,
        z_start=line_min_clearance.z_min, 
        z_end=line_min_clearance.z_min - line_min_clearance.vertical_min,
        fontsize=fontsize,
        ha='right', va="top",
        extension_line=True,
        mov_x=0,
    )

    # Draw the vertical distance from the flange to the point of minimum seabed clearance.
    ax = gimg.draw_vertical_dimensions(
        ax, 
        x_start=line_min_clearance.x_min, 
        x_end=line_min_clearance.x_min,
        z_start=vcm_data["flange_vcm_z"], 
        z_end=line_min_clearance.z_min+line_radius,
        fontsize=fontsize, 
        ha="right", mov_x=0,
    )

    # Draw the distance dimension from the VCM flange to the bend restrictor end
    ax = gimg.draw_vertical_dimensions(
        ax, 
        x_start=x_vcm_h_2nd_point+2.5, 
        x_end=x_vcm_h_2nd_point+2.5,
        z_start=vcm_data["flange_vcm_z"], 
        z_end=br_z_max,
        fontsize=fontsize,
        ha="right", mov_x=0.0,
    )

    # line dashed
    kwargs = {"linestyle":"--", "color":"k", "lw":0.3}
    x_coord = [vcm_data["flange_vcm_x"], line_x[idx_vcm_h] + 3.0]
    ax.plot(x_coord, 2*[vcm_data["flange_vcm_z"]], **kwargs)
    ax.plot([br_x_max, line_x[idx_vcm_h] + 3.0], 2*[br_z_max], **kwargs)

    # Horizontal dimension - from the flange to the other side at the same Z
    ax = gimg.draw_horizontal_dimensions(
        ax, 
        x_start=seabed_data.origin_x, 
        x_end=x_vcm_h_2nd_point, 
        z_start=vcm_data["flange_vcm_z"], 
        z_end=vcm_data["flange_vcm_z"],
        mov_z=3.0,
        fontsize=fontsize,
        use_comma=use_comma,
    )
    
    z_comp = vcm_data["flange_vcm_z"] - br_z_max
    # Horizontal dimension - from the flange to the bend restrictor end
    ax = gimg.draw_horizontal_dimensions(
        ax, 
        x_start=seabed_data.origin_x, 
        x_end=br_x_max, 
        z_start=br_z_max, 
        z_end=br_z_max,
        mov_z=z_comp+2.0,
        fontsize=fontsize,
        use_comma=use_comma,
    )

    z_comp = vcm_data["flange_vcm_z"] - line_min_clearance.z_min
    # Horizontal dimension - from the flange to the minimum line point
    ax = gimg.draw_horizontal_dimensions(
        ax, 
        x_start=seabed_data.origin_x, 
        x_end=line_min_clearance.x_min, 
        z_start=line_min_clearance.z_min, 
        z_end=line_min_clearance.z_min,
        mov_z=z_comp+1.0,
        fontsize=fontsize,
        use_comma=use_comma,
    )

    # Draw the attachments
    ax = gimg.draw_attachments(
        ax, line, attach_data, use_comma, fontsize=fontsize, stc_descr=False,
    )

    return ax

def static_1st_dvc_zoom(
        ax: object, 
        line: orca.OrcaFlexLineObject, 
        attach_data: dict,
        line_data: tuple, 
        vcm_data: dict,
        fontsize: int, 
        use_comma: bool
    ) -> object:
    """
    Draw the dimensions of the 1st DVC.
    
    Args:
        ax: the axes object on which the plot will be drawn.
        line: orcaflex line object.
        attach_data: anode, buoys, and dead weight data.
        line_data: line data tuple.
        vcm_data: vcm data object.
        fontsize: reference scale used to define text font size and line thickness.
        use_comma: unit system - True for "," and False for ".".

    Returns:
        ax: axes object on which the plot was drawn.
    """
    # Draw the catenary dimensions - Arc length
    idx_argmin = np.argmin(line_data.z)
    line_z = line_data.z[:idx_argmin]

    # Get the line XZ-coord - Point at the same height as the MCV flange
    z_vcm_h = min(line_z, key=lambda x: abs(x - vcm_data["flange_vcm_z"]))
    idx_vcm_h = np.nonzero(np.isclose(line_z, z_vcm_h))[0][0]

    # From flange to the minimum line point
    ax = gimg.draw_arclength_dimensions(
        ax,
        line_data=line_data,
        start_point=idx_vcm_h, end_point=idx_argmin, 
        mov_x=0, mov_z=-0.2,
        fontsize=fontsize,
        use_comma=use_comma,
    ) 

    # From the minimum point to the other side at the same Z
    ax = gimg.draw_arclength_dimensions(
        ax,
        line_data=line_data,
        start_point=idx_argmin, end_point=len(line_data.z)-1, 
        mov_x=0, mov_z=-0.1, 
        fontsize=fontsize,
        use_comma=use_comma,
    ) 

    # Draw the attachments
    ax = gimg.draw_attachments(ax, line, attach_data, use_comma, fontsize=fontsize)

    return ax

def static_2nd_dvc(
        ax: object,
        model: orca.Model, 
        line: orca.OrcaFlexLineObject, 
        attach_data: dict,
        obj_names: dict,
        vcm_data: dict,
        seabed_data: tuple,
        fontsize: int, 
        use_comma: bool
    ) -> object:
    """
    Draw the dimensions of the 2nd DVC.
    
    Args:
       draw_buoys_dvc ax: the axes object on which the plot will be drawn.
        model: orcaflex model object.
        line: orcaflex line object.
        attach_data: anode, buoys, and dead weight data.
        obj_names: orcaflex object dict - DVC.
        vcm_data: vcm data dict.
        seabed_data: seabed data tuple.
        fontsize: reference scale used to define text font size and line thickness.
        use_comma: unit system - True for "," and False for ".".

    Returns:
        ax: axes object on which the plot was drawn.
    """

    # Get the link positions - arc length
    ar = model[obj_names["ar"]]
    link1 = model[obj_names["link1"]]
    link2 = model[obj_names["link2"]]

    # Get link coordinates
    x_link1_enda = link1.StaticResult("End A X")
    z_link1_enda = link1.StaticResult("End A Z")
    x_link1_endb = link1.StaticResult("End B X")
    z_link1_endb = link1.StaticResult("End B Z") 

    # Get line connection point (arc length) to the links
    link1_arclength = gimg.get_link_position(line, link1)
    link2_arclength = gimg.get_link_position(line, link2)

    # Get tdp data
    x_tdp = line.StaticResult("X", orca.oeTouchdown)
    z_tdp = line.StaticResult("Z", orca.oeTouchdown)

    # Get the minimum seabed clearance of the line
    line_min_clearance = gimg.get_min_point_line(
        line, bend_restrictor=None,
        from_arclength=link1_arclength, to_arclength=line.CumulativeLength[-1],
    )
    # Get the maximum seabed clearance of the line
    line_max_clearance = gimg.get_max_point_line(
        line, from_arclength=link1_arclength, to_arclength=link2_arclength,
    )

    z_comp = line_max_clearance.z_max - line_min_clearance.z_min
    # From flange (X-axis) to the sag (X-axis)
    ax = gimg.draw_horizontal_dimensions(
        ax, 
        x_start=vcm_data["flange_vcm_x"], 
        x_end=line_min_clearance.x_min,
        z_start=line_min_clearance.z_min,
        z_end=line_min_clearance.z_min,
        fontsize=fontsize,
        mov_z=z_comp,
    )

    z_comp = line_max_clearance.z_max - z_link1_endb
    # From flange (X-axis) to the first sling
    ax = gimg.draw_horizontal_dimensions(
        ax, 
        x_start=vcm_data["flange_vcm_x"], 
        x_end=x_link1_endb,
        z_start=z_link1_endb, 
        z_end=z_link1_endb,
        fontsize=fontsize,
        mov_z=z_comp + 1.0,
    )

    # From flange (X-axis) to the hog (X-axis)
    ax = gimg.draw_horizontal_dimensions(
        ax, 
        x_start=vcm_data["flange_vcm_x"], 
        x_end=line_max_clearance.x_max,
        z_start=line_max_clearance.z_max, 
        z_end=line_max_clearance.z_max,
        fontsize=fontsize,
        mov_z=2.0,
    )

    z_comp = line_max_clearance.z_max - z_link1_enda
    # From flange (X-axis) to the AR/winch
    ax = gimg.draw_horizontal_dimensions(
        ax, 
        x_start=vcm_data["flange_vcm_x"], 
        x_end=x_link1_enda,
        z_start=z_link1_enda, 
        z_end=z_link1_enda,
        fontsize=fontsize,
        mov_z=z_comp + 3.0,
    )

    z_comp = line_max_clearance.z_max - seabed_data.origin_z
    # From flange (X-axis) to the TDP
    ax = gimg.draw_horizontal_dimensions(
        ax, 
        x_start=vcm_data["flange_vcm_x"], 
        x_end=x_tdp,
        z_start=seabed_data.origin_z, 
        z_end=seabed_data.origin_z,
        fontsize=fontsize,
        mov_z=z_comp + 4.0,
    )

    # Draw the distance dimension from the VCM flange to the seabed (Z-axis)
    ax = gimg.draw_vertical_dimensions(
        ax, 
        x_start=vcm_data["flange_vcm_x"],
        x_end=vcm_data["flange_vcm_x"],
        z_start=vcm_data["flange_vcm_z"],
        z_end=seabed_data.origin_z,
        fontsize=fontsize,
        ha="right", va="top",
        extension_line=True,
        mov_x=0,
    )

    # From the line to the seabed (Z-axis)
    ax = gimg.draw_vertical_dimensions(
        ax, 
        x_start=line_min_clearance.x_min, 
        x_end=line_min_clearance.x_min,
        z_start=line_min_clearance.z_min, 
        z_end=line_min_clearance.z_min - line_min_clearance.vertical_min,
        fontsize=fontsize,
        ha="right", va="top",
        extension_line=True,
        mov_x=0,
    )

    # From the line to the seabed in the hump area (Z-axis)
    ax = gimg.draw_vertical_dimensions(
        ax, 
        x_start=line_max_clearance.x_max, 
        x_end=line_max_clearance.x_max,
        z_start=line_max_clearance.z_max, 
        z_end=line_max_clearance.z_max-line_max_clearance.vertical_max,
        fontsize=fontsize,
        ha="right", va="top",
        extension_line=True,
        mov_x=0,
    )

    # Draw slings, attachments and the TDP are
    ax = gimg.draw_ar_slings(ax, ar, link1, link2, linewidth=fontsize*0.05)
    ax = gimg.indicate_tdp(ax=ax, xz_tdp=(x_tdp, z_tdp), **{"fontsize":fontsize, "ha":"center"})
    ax = gimg.draw_attachments(
        ax, line, attach_data, use_comma, fontsize=fontsize, stc_descr=False,
    )
    return ax

def static_2nd_dvc_zoom(
        ax: object, 
        model: orca.Model,
        attach_data: dict,
        obj_names: dict, 
        fontsize: int, 
        use_comma: bool,
    ) -> tuple:
    """
    Draw the dimensions of the 2nd DVC - detailed.
    
    Args:
        ax: the axes object on which the plot will be drawn.
        model: orcaflex model object.
        attach_data: anode, buoys, and dead weight data.
        obj_names: orcaflex object dict - DVC.
        fontsize: reference scale used to define text font size and line thickness.
        use_comma: unit system - True for "," and False for ".".

    Returns:
        Tuple:
            ax: axes object on which the plot was drawn.
            XZ-coord - position of the firt sling
    """

    ar = model[obj_names["ar"]]
    line = model[obj_names["line"]]
    link1 = model[obj_names["link1"]]
    link2 = model[obj_names["link2"]]

    # Get line connection point (arc length) to the links
    link1_arclength = gimg.get_link_position(line, link1)
    line_data = gimg.get_line_data(line, from_arclength=link1_arclength)
    
    # Get the minimum point
    idx_argmin = np.argmin(line_data.z)

    # Draw slings
    ax = gimg.draw_ar_slings(ax, ar, link1, link2)
    
    # From flange to the minimum line point
    ax = gimg.draw_arclength_dimensions(
        ax,
        line_data=line_data,
        start_point=idx_argmin, end_point=len(line_data.z)-1, 
        mov_x=0, mov_z=-0.1,
        fontsize=fontsize,
        use_comma=use_comma,
    ) 

    # From the minimum point to the first sling
    ax = gimg.draw_arclength_dimensions(
        ax,
        line_data=line_data,
        start_point=0, end_point=idx_argmin, 
        mov_x=0, mov_z=-0.1, 
        fontsize=fontsize,
        use_comma=use_comma,
    ) 

    # Draw the attachments
    ax = gimg.draw_attachments(ax, line, attach_data, use_comma, fontsize=fontsize)

    return ax, max(line_data.x), max(line_data.z)

def generate_static(
        model: orca.Model, 
        file_paths: dict, 
        obj_names: dict,
        dvc_type: int,
        detailed: bool = False, 
        fontsize: int = 6,
        use_comma: bool = True,
    ) -> None:
    """
    Draw the 1st and 2nd DVC figures.
    
    Args:
        model: orcaflex model object.
        file_paths: dict of the *.sim and *.png files.
        obj_names: orcaflex object dict - DVC.
        dvc_type: dvc type, 2 for 2nd and 1 for 1st DVC.
        detailed: detailed figure, only for 2nd DVC.
        fontsize: reference scale used to define text font size and line thickness.
        use_comma: unit system - True for "," and False for ".".

    Returns:
        None
    """
    line_name = obj_names["line"]

    # Get attachment data from the Dynamics file
    model_dyn = orca.Model(file_paths["dynamic_sim"])
    line_obj_dyn = model_dyn[line_name]
    # Get buoys or dead weights - from dynamic file    
    attach_data = gimg.get_buoys_attachment(model_dyn, line_obj_dyn)

    # From here - Only layaway file
    vcm = model[obj_names["vcm"]]
    line = model[obj_names["line"]]
    bend_restrictor = model[obj_names["bend_restrictor"]]
    crane = model[obj_names["crane"]]

    """GET DATA"""
    # Get TDP X-coord
    x_tdp = 0 if dvc_type == 1 else line.StaticResult("X", orca.oeTouchdown)

    # Get MCV data
    vcm_data = {
        "vcm_base_point_x": vcm.StaticResult("X"),
        "vcm_base_point_z": vcm.StaticResult("Z"),
        "flange_vcm_x": line.StaticResult("X", orca.oeEndB),
        "flange_vcm_z": line.StaticResult("Z", orca.oeEndB),
    }
    line_data = gimg.get_line_data(line)
    seabed_data = gimg.get_seabed_data(model)

    """CREATE FIGURE"""
    xz_range = {
        "x_min": vcm_data["vcm_base_point_x"] - 1.0 + X_MIN_LIM,
        "x_max": max(line_data.x) + 1.0 + X_MAX_LIM if dvc_type == 1 else x_tdp + 1.0,
        "z_min": seabed_data.min_z - 1.5 + Z_MIN_LIM,
        "z_max": line_data.z[-1] + 3.5 + Z_MAX_LIM if dvc_type == 1 else max(line_data.z) + 7.0 + Z_MAX_LIM,
    }
    figsize = gimg.get_figsize_from_data(xz_range, FIGURE_HEIGHT_CM)
    fig, ax = plt.subplots(figsize=figsize)

    """DRAW THE DVC OBJECTS"""
    # Draw the DVC itens
    ax = gimg.draw_seabed(ax, seabed_data, xz_range["x_min"], xz_range["x_max"],  lw=fontsize*0.1)
    ax = gimg.draw_vcm_dvc(ax, vcm_data["vcm_base_point_x"], vcm_data["vcm_base_point_z"], linewidth=fontsize*0.05)
    ax = gimg.draw_winch(ax, crane, lw=fontsize*0.05)

    #Draw the external outline - Flexible and Bend Restrictor
    ax = gimg.draw_external_lines(ax, line, line_data, lw=fontsize*0.03)
    if bend_restrictor:
        br_data = gimg.get_line_data(bend_restrictor)
        ax = gimg.draw_external_lines(ax, bend_restrictor, br_data, facecolor="grey", lw=fontsize*0.03)

    """DRAW THE DVC DIMENSIONS"""
    filename_png = file_paths["static_zoom_png"] if detailed else file_paths["static_png"] 
    if dvc_type == 1 and not detailed:
        ax = static_1st_dvc(
            ax, 
            line, bend_restrictor, attach_data, 
            line_data, vcm_data, seabed_data,
            fontsize, use_comma,
        )
    elif dvc_type == 2 and not detailed:
        ax = static_2nd_dvc(
            ax, 
            model, line, attach_data,
            obj_names, vcm_data, seabed_data,
            fontsize, use_comma,
        )
    elif dvc_type == 1 and detailed:
        ax = static_1st_dvc_zoom(
            ax, line, attach_data, line_data, vcm_data, fontsize, use_comma,
        )
        xz_range["z_min"] = xz_range["z_min"] + 1.0
        xz_range["z_max"] = xz_range["z_max"] + 0.5
        fig.set_size_inches(gimg.get_figsize_from_data(xz_range, FIGURE_HEIGHT_CM))
    elif dvc_type == 2 and detailed:
        ax, xlim, zlim = static_2nd_dvc_zoom(
            ax, 
            model, attach_data, obj_names,
            fontsize=fontsize*0.8, use_comma=use_comma,
        )
        xz_range["x_max"] = xlim + 1.5
        xz_range["z_min"] = xz_range["z_min"] + 1.0
        xz_range["z_max"] = zlim + 4.0
        fig.set_size_inches(gimg.get_figsize_from_data(xz_range, FIGURE_HEIGHT_CM))

    gimg.save_figure(ax, fig, xz_range, filename_png, turn_on_axes=TURN_AXES_ON)
    return None
