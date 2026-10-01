"""Module to generate the dredging figure."""

__author__ = "Yan Nascimento"
__copyright__ = "TechnipFMC"
__credits__ = ""
__license__ = ""
__version__ = "1.0"
__maintainer__ = "Yan Nascimento"
__email__ = "yan.donascimento@technipfmc.com"
__status__ = "Under Developement"
__last_release__ = "May, 2026"

# Public Libraries 
import OrcFxAPI as orca
# Private libaries (IAS)
from utils import excel_handler
from libs import generate_images as gimg
# Constants
RANGE_SEABED_PROFILE = "data_seabed_profile"
TBL_LABEL_SEABED_X = "Dist. Hor."
TBL_LABEL_SEABED_Z = "Profundidade"
CM_TO_INCHES = 1 / 2.54
FIGURE_SIZE_CM  = (15*CM_TO_INCHES, 5.2*CM_TO_INCHES)
# Control for precise movement - True to activate.
TURN_AXES_ON = False

def generate_dredging(
        model: orca.Model, 
        file_paths: dict, 
        obj_names: dict,
        fontsize: int = 6,
    ) -> None:
    """
    Draw the dredging and seabed profile.
    
    Args:
        model: orcaflex model object.
        file_paths: dict of the *.sim and *.png files.
        obj_names: orcaflex object dict - DVC.
        fontsize: reference scale used to define text font size and line thickness.

    Returns:
        None
    """

    # Get files to generate the figure
    df_files = excel_handler.load_data_range_to_df(        
            xlsx_file=file_paths["xlsx_file"], 
            range_name=RANGE_SEABED_PROFILE, 
            is_table=True,
        )

    # Get objects from OrcaFlex model
    vcm = model[obj_names["vcm"]]
    line = model[obj_names["line"]]
    
    # Get OrcaFlex data
    hub_to_flange = line.StaticResult("X", orca.oeEndB) - vcm.StaticResult("X")
    
    orca_seabed_data = gimg.get_seabed_data(model)
    offset = hub_to_flange - orca_seabed_data.origin_x
    orca_seabed_x = [x + offset for x in orca_seabed_data.x]

    # Get seabed data from the spreadsheet
    xlsx_seabed_x = df_files[TBL_LABEL_SEABED_X].to_list()
    xlsx_seabed_x = [x + hub_to_flange for x in xlsx_seabed_x]
    xlsx_seabed_z = (-df_files[TBL_LABEL_SEABED_Z]).tolist()

    """CREATE FIGURE"""
    xz_range = {
        "x_min": 0,
        "x_max": max(orca_seabed_x)+5,
        "z_min": min(orca_seabed_data.z)-0.25,
        "z_max": max(orca_seabed_data.z)+0.25,
    }

    fig, ax = gimg.create_plot(
        x_label="Distância horizontal em relação ao centro do HUB (m)", 
        z_label="Profundidade (m)", 
        title="Perfil do solo - com e sem dragagem", 
        fontsize=fontsize,
        figsize=FIGURE_SIZE_CM,
    ) 

    """PLOT CURVES"""
    kwargs = {"marker":"o", "markersize":fontsize*0.5, "lw": fontsize*0.125}

    # Plot the dredging profile
    ax.plot(
        orca_seabed_x, orca_seabed_data.z, 
        color="red", linestyle="dashed", label="Com dragagem", **kwargs
    )

    # Variable to prevent coordinate overlap
    # Plot the coordinates
    for x_i, z_i, z_i2 in zip(orca_seabed_x, orca_seabed_data.z, (orca_seabed_data.z + (orca_seabed_data.z[-1],))[1:]):
        vert_pos="top"
        horz_pos="left"
        if z_i >= z_i2:
            vert_pos = "bottom"
        # Changes the plot side of the second coordinate
        if x_i == orca_seabed_x[1]:
            vert_pos = "top"
            horz_pos = "right"
        ax.annotate(
            f"({x_i:.1f}, {z_i:.1f})    ",
            (x_i, z_i),
            xytext=(fontsize*0.4, fontsize*0.4),
            textcoords="offset points",
            va=vert_pos,
            ha=horz_pos,
            fontsize=fontsize,
        )

    # Plot the original seabed profile - extend curve without mutating original lists
    x_ext = [0, *xlsx_seabed_x, xz_range["x_max"]]
    z_ext = [xlsx_seabed_z[0], *xlsx_seabed_z, xlsx_seabed_z[-1]]
    ax.plot(
        x_ext, z_ext, color="blue", label="Sem dragagem", **kwargs
    )

    ax.legend(
        fontsize=fontsize*0.8, loc="upper right", frameon=True, fancybox=True,
    )

    gimg.save_figure(
        ax, fig, xz_range, file_paths["dredging_png"], 
        set_spine=True, turn_on_axes=True,
    )

    return None