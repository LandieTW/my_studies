"""Module of utils functions to generate images."""

__author__ = "Yan Nascimento"
__copyright__ = "TechnipFMC"
__credits__ = ""
__license__ = ""
__version__ = "1.0"
__maintainer__ = "Yan Nascimento"
__email__ = "yan.donascimento@technipfmc.com"
__status__ = "Developed"
__last_release__ = "November, 2025"

# Public Libraries (Python)
import re
import math
import numpy as np
import OrcFxAPI as orca
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.path import Path
from matplotlib.lines import Line2D
from collections import namedtuple
from typing import Union
# Private Libraries (IAS)
from utils.utils_constants import SEAWATER_DENSITY_ORCA

# Constants
FONTSIZE = 6
DECIMAL_PLACES = 2
CM_TO_INCHES = 1 / 2.54
DOC_MAX_WIDTH_CM = 15.5
PREFIX_ATTACH = {
    "anodo": ["ANODO"],
    "peso": ["PM", "PESO", "BALLAST", "LASTRO"],
    "buoy": ["FLUT", "BOIA FINAL DE VIDA"],
    "buoy_plsv": ["SKA", "SKB", "SKN", "SKRO", "TOP", "CDA", "SKV"],
}

def get_link_position(
        line: orca.OrcaFlexLineObject, link: orca.OrcaFlexObject,
    ) -> float:
    """
    Get the arc length of the line to which the link is attached.

    Args:
        line: orcaflex line object.
        link: orcaflex link object.

    Returns:
        float: arc length value.
    """
    cum_len = line.CumulativeLength
    if line.Name in link.EndBConnection:
        z_link, rel_link = link.EndBZ, link.EndBzRelativeTo  
    else:
        z_link, rel_link = link.EndAZ, link.EndAzRelativeTo

    return cum_len[-1] - z_link if "B" in rel_link else cum_len[0] - z_link

def classify_attachment(
        attachment: str, prefix_attach: Union[list, dict],
    ) -> str:
    """
   Get attachment from the line, except stiffener types.

    Args:
        attachment: attachment name.
        prefix_attach: list of buoys, dead weight and anode prefix.

    Returns:
        str: attachment type.
    """
    prefix = attachment.split("_")[0].upper()

    if prefix in prefix_attach["buoy_plsv"] or prefix in prefix_attach["buoy"]:
        return "buoy"
    elif prefix in prefix_attach["anodo"] or prefix in prefix_attach["peso"]:
        return prefix.lower()
    elif attachment.isdigit():
        return "cont"

def get_buoys_attachment(
        model: orca.Model, 
        line: orca.OrcaFlexLineObject, 
        prefix_attach: Union[list, dict] = PREFIX_ATTACH,
    ) -> dict:
    """
   Get attachment from the line, except stiffener types.

    Args:
        model: orcaflex model object.
        line: orcaflex line object.
        prefix_attach: list of buoys, dead weight and anode prefix.

    Returns:
        Dict: attachment data - anode, buoys and dead weights.
    """
    # Merge all list of the prefix_attach
    all_itens = prefix_attach if isinstance(prefix_attach, list) else [item for sublist in prefix_attach.values() for item in sublist]
    
    # Get a tuple of the buoy values and position Z
    buoys = [
        (item, line.Attachmentz[i]) 
        for i, item in enumerate(line.AttachmentType) 
        if line.AttachmentName[i] is None and (item.split("_")[0].upper() in all_itens or item.isdigit())
    ]

    buoys_dict = {}
    line_len = line.StaticResult("Arc Length", orca.oeEndB)
    for buoy_name, buoy_pos_z in buoys:

        buoy_type = classify_attachment(buoy_name, prefix_attach)

        obj_buoy = model[buoy_name]
        buoyancy = [
            obj_buoy.Mass - obj_buoy.Volume * SEAWATER_DENSITY_ORCA 
            if obj_buoy.Volume != 0 else obj_buoy.Mass
        ]
        buoyancy = round(buoyancy[0] * 1000, 1)
        arc_length = orca.oeArcLength(line_len-buoy_pos_z)

        if buoy_pos_z not in buoys_dict.get(buoy_type, []):
            buoys_dict.setdefault(buoy_type, {})
            b_text = int(buoyancy)
            buoys_dict[buoy_type][buoy_pos_z] = {
                "buoyancy": buoyancy,
                "draw_text": f"{-1 * b_text}kg" if b_text < 0 else f"Peso {b_text}kg",
                "x": round(line.StaticResult("X", arc_length), 2),
                "z": round(line.StaticResult("Z", arc_length), 2)
            }
        else:
            # Only update the buoyancy value
            aux_dict = buoys_dict[buoy_type][buoy_pos_z]
            aux_dict["buoyancy"] = aux_dict["buoyancy"] + buoyancy
            b_text = int(aux_dict["buoyancy"])
            aux_dict["draw_text"] = f"{-1 * b_text}kg" if b_text < 0 else f"Peso {b_text}kg"

    return buoys_dict

def get_buoys_3d(model: orca.Model, period: orca.Period) -> dict:
    """
    Sum the buoyancy and group them by floating point in a dictionary. Only valid for 3D buoys.

    Args:
        model: orcaflex model object.
        period: period to get data.

    Returns:
        Dictionary with buoyancy points and their respective buoyancy
    """
    buoy_types = [obj for obj in model.objects if obj.type.value == orca.ObjectType.Buoy3D.value]

    buoy_data = {}
    rx_prefix = re.compile(r'^\D*(\d+)')

    for buoy in buoy_types:

        prefix = rx_prefix.search(buoy.Name.split("_")[0])
        if prefix is None:
            # If prefix is non-dstandard, ignore
            continue
            
        prefix = int(prefix.group(1))

        # Create the prefix key if it doesn't exist using setdefault.
        buoy_data.setdefault(
            prefix, 
            {
                "buoyancy": 0.0, 
                "x": buoy.TimeHistory("X", period=period)[0],
                "z": buoy.TimeHistory("Z", period=period)[0]
            }
        )

        buoy_data[prefix]["buoyancy"] += buoy.Volume * SEAWATER_DENSITY_ORCA - buoy.Mass
            
    return buoy_data

def get_seabed_data(model: orca.Model) -> tuple:
    """
    Get the seabed and dredging data

    Args:
        model: OrcaFlex model.

    Returns:
        Tuple: seabed XZ-coordinates, XZ-origin and min point.
    """

    seabed_data = namedtuple("seabed", ["x", "z", "origin_x", "origin_z", "min_z"])

    seabed_origin_x = model.environment.SeabedOriginX
    seabed_origin_z = model.environment.SeabedOriginZ

    seabed_z = [seabed_origin_z]
    seabed_x = [seabed_origin_x]
    if "Profile" in model.environment.SeabedType:
        seabed_z = list(model.environment.SeabedProfileZ)
        seabed_x = [
            seabed_origin_x + d for d in model.environment.SeabedProfileDistanceFromSeabedOrigin
        ]
        # Sorted the lists according to the seabed_x
        seabed_x, seabed_z = zip(*sorted(zip(seabed_x, seabed_z)))

    return seabed_data(
        seabed_x, seabed_z, seabed_origin_x, seabed_origin_z, min(seabed_z),
    )

def get_min_point_line(
        line: orca.OrcaFlexLineObject, 
        bend_restrictor: orca.OrcaFlexLineObject,
        from_arclength: float = orca.OrcinaDefaultReal(),
        to_arclength: float = orca.OrcinaDefaultReal(),
        period: orca.PeriodNum = orca.PeriodNum.StaticState,
    ) -> tuple:
    """
    Get the line minimum point.

    orca.OrcinaDefaultReal() - dafault value for beginning and end of the line.

    Args:
        line: orcaflex line object - Line. 
        bend_restrictor: orcaflex line object - Bend Restrictor.
        from_arclength: starting point to look for the minimun point. 
        to_arclength: end point to look for the min point.
        period: period to get data,

    Returns:
        Tuple: minimum line point - XZ-coordinates, XZ-origin and min point.
    """
    obj_data = namedtuple(
        "line_min_clearance", ["x_min", "z_min", "vertical_min"],
    )

    arc_range = orca.arSpecifiedArclengths(from_arclength, to_arclength)

    # Get the Vertical Seabed Clearance from the arclengthRange
    vertical_sb_cleareance = line.RangeGraph(
        "Vertical Seabed Clearance", arclengthRange=arc_range, period=period)
    
    # Get the index of the manimum value
    idx_min = np.argmin(vertical_sb_cleareance.Mean)
    arclen = vertical_sb_cleareance.X[idx_min]

    lt_min_pos = line
    if bend_restrictor:
        end_bendres = line.Attachmentz[0] + bend_restrictor.CumulativeLength[-1]
        if arclen > line.Attachmentz[0] and arclen < end_bendres:
            lt_min_pos = bend_restrictor

    # Line Radius
    line_radius = lt_min_pos.lineTypeAt(arclen).ContactDiameter * 0.5

    return obj_data(
        line.RangeGraph("X", arclengthRange=arc_range, period=period).Mean[idx_min],
        line.RangeGraph("Z", arclengthRange=arc_range, period=period).Mean[idx_min] - line_radius,
        min(vertical_sb_cleareance.Mean),
    )

def get_max_point_line(
        line: orca.OrcaFlexLineObject, 
        from_arclength: float = orca.OrcinaDefaultReal(), 
        to_arclength: float = orca.OrcinaDefaultReal(),
        period: orca.PeriodNum = orca.PeriodNum.StaticState,
    ) -> tuple:
    """
    Get the line maximum point.

    orca.OrcinaDefaultReal() - dafault value for beginning and end of the line.

    Args:
        line: orcaflex line object - Line. 
        bend_restrictor: orcaflex line object - Bend Restrictor.
        from_arclength: starting point to look for the maximum point. 
        to_arclength: end point to look for the maximum point.
        period: period to get data,

    Returns:
        Tuple: maximum line point - XZ-coordinates, XZ-origin and maximum point.
    """
    
    obj_data = namedtuple(
        "line_max_clearance", ["x_max", "z_max", "vertical_max"],
    )

    arc_range = orca.arSpecifiedArclengths(from_arclength, to_arclength)

    # Get the Vertical Seabed Clearance from the arclengthRange
    vertical_sb_cleareance = line.RangeGraph(
        "Vertical Seabed Clearance", arclengthRange=arc_range, period=period)
    
    # Get the index of the maximum value
    idx_max = np.argmax(vertical_sb_cleareance.Mean)
    arclen = vertical_sb_cleareance.X[idx_max]
    # Line Radius
    line_radius = line.lineTypeAt(arclen).ContactDiameter * 0.5

    return obj_data(
        line.RangeGraph("X", arclengthRange=arc_range, period=period).Mean[idx_max],
        line.RangeGraph("Z", arclengthRange=arc_range, period=period).Mean[idx_max] - line_radius,
        max(vertical_sb_cleareance.Mean),
    )

def get_declination_data(
        line: orca.OrcaFlexLineObject, 
        from_arclength: float = orca.OrcinaDefaultReal(), 
        to_arclength: float = orca.OrcinaDefaultReal(),
        period: orca.PeriodNum = orca.PeriodNum.StaticState,
    ) -> np.array:
    """
    Get the seabed and dredging data.

    orca.OrcinaDefaultReal() - dafault value for beginning and end of the line.

    Args:
        line: orcaflex line object - Line. 
        from_arclength: starting point to look for the declination point. 
        to_arclength: end point to look for the declination point.
        period: period to get data.

    Returns:
        np.array: line declination
    """
    arc_range = orca.arSpecifiedArclengths(from_arclength, to_arclength)
    return line.RangeGraph(
        "Declination", arclengthRange=arc_range, period=period,
    ).Mean * np.pi / 180

def get_line_data(
        line: orca.OrcaFlexLineObject, 
        from_arclength: float = orca.OrcinaDefaultReal(), 
        to_arclength: float = orca.OrcinaDefaultReal(),
        period: orca.PeriodNum = orca.PeriodNum.StaticState,
    ) -> tuple:
    """
    Get the line maximum point.

    orca.OrcinaDefaultReal() - dafault value for beginning and end of the line.

    Args:
        line: orcaflex line object - Line. 
        bend_restrictor: orcaflex line object - Bend Restrictor.
        from_arclength: starting point to look for the maximum point. 
        to_arclength: end point to look for the maximum point.
        period: period to get data,

    Returns:
        Tuple: line data - XZ-coordinates, declination and arclength.
    """
    obj_data = namedtuple(
        "line", [
            "x", "z", "y", "cos_declination", "sin_declination", "arclength"],
    )

    arc_range = orca.arSpecifiedArclengths(from_arclength, to_arclength)
    line_declination = get_declination_data(
        line, from_arclength=from_arclength, to_arclength=to_arclength,
    )

    return obj_data(
        line.RangeGraph("X", arclengthRange=arc_range, period=period).Mean, 
        line.RangeGraph("Z", arclengthRange=arc_range, period=period).Mean, 
        line.RangeGraph("Y", arclengthRange=arc_range, period=period).Mean, 
        np.cos(line_declination), 
        np.sin(line_declination), 
        line.RangeGraph("X", arclengthRange=arc_range, period=period).X,
    )

def format_number(
        num_to_str: float, 
        use_comma: bool = True, 
        decimal_places: int = DECIMAL_PLACES,
        unit: str = "m"
    ) -> str:
    """
    Convert dot for comma - unit system.

    Args:
        num_to_str: number to convert.
        use_comma: unit system - True for "," and False for ".".
        decimal_places: number of decimal places.
        unit: dimension unit - if not applicable, use "".

    Returns:
        str: converted number.
    """
    if use_comma:
        return f"{num_to_str:.{decimal_places}f}{unit}".replace(".", ",")
    return f"{num_to_str:.{decimal_places}f}{unit}"

def draw_attachments(
        ax: object, 
        line: orca.OrcaFlexLineObject, 
        attach_data: dict, 
        use_comma: bool, 
        **kwargs,
    ) -> object:
    """
    Draw all attachments - depending on the kwargs.

    Args:
        ax: the axes object on which the plot will be drawn.
        line: orcaflex line object - Line.
        attach_data: anode, buoys, and dead weight data.
        use_comma: unit system - True for "," and False for ".".
        **kwargs: Optional keyword arguments.
            - fontsize: text font size.
            - decimal_places: number of decimal places. 
            - cont_descr: if true, draw the cont description.
            - sts_descr: if true, draw the static description.
            - drg_anode: if true, draw the anode on the line.
            - drg_dw: if true, draw the dead weigths on the line.
            - drg_ballast: if true, draw the ballast on the line.
            - drg_buoy: if true, draw the buoys on the line.
            - drg_cont: if true, draw the buoys cont on the line.

    Returns:
        ax: axes object on which the plot was drawn.
    """
    fontsize = kwargs.get("fontsize", FONTSIZE)
    decimal_places = kwargs.get("decimal_places", DECIMAL_PLACES)

    cont_descr  = (kwargs.get("cont_descr", True), "cont_descr")
    stc_descr = (kwargs.get("stc_descr", True), "stc_descr")

    drg_anode = kwargs.get("drg_anode", True)
    drg_dw = kwargs.get("drg_peso", True)
    drg_ballast = kwargs.get("drg_ballast", True)
    drg_buoy = kwargs.get("drg_buoy", True)
    drg_cont = kwargs.get("drg_cont", False)

    # Draw the attachments
    if "buoy" in attach_data and drg_buoy:
        for item, att_dict in attach_data["buoy"].items():
            z_pos = format_number(item, use_comma, decimal_places)
            ax = draw_buoys_dvc(ax, att_dict, z_pos, stc_descr, **{"fontsize": fontsize})
    if "cont" in attach_data and drg_cont:
        for item, att_dict in attach_data["cont"].items():
            z_pos = format_number(item, use_comma, decimal_places)
            ax = draw_buoys_dvc(ax, att_dict, z_pos, cont_descr, **{"fontsize": fontsize})
    if "anodo" in attach_data and drg_anode:
        ax = draw_anode(ax, line, attach_data["anodo"])
    if "peso" in attach_data and drg_dw:
        for item, att_dict in attach_data["peso"].items():
            ax = draw_dead_weigths(ax, att_dict)
    if "ballast" in attach_data and drg_ballast:
        for item, att_dict in attach_data["ballast"].items():
            ax = draw_dead_weigths(ax, att_dict)
    return ax

def draw_dead_weigths(
        ax: object, 
        attach_data: dict, 
        fontsize: int = FONTSIZE,
        **kwargs,
    ) -> object:
    """
    Draw dead weigths.

    Args:
        ax: the axes object on which the plot will be drawn.
        attach_data: anode, buoys, and dead weight data.
        fontsize: reference scale used to define text font size and line thickness.
        **kwargs: Optional keyword arguments passed to ax.add_patch(patches.Circle) function.

    Returns:
        ax: axes object on which the plot was drawn.
    """
    # Set default values if not provided
    up_kwargs = {
        "edgecolor": kwargs.get("edgecolor", "black"),
        "facecolor": kwargs.get("facecolor", "black"),
        **kwargs
    }
    
    x = float(attach_data["x"])
    z = float(attach_data["z"])

    ax.plot((x,x), (z, z - 0.5), color="black", linewidth=fontsize*0.075)
    circle = patches.Circle((x, z - 0.5), radius=fontsize*0.02)

    circle.set(**up_kwargs)
    ax.add_patch(circle)

    return ax

def draw_anode(
        ax: object, 
        line: orca.OrcaFlexLineObject, 
        anode_dict: dict,
        fontsize: int = FONTSIZE,
    ) -> object:
    """
    Draw anode.

    Args:
        ax: the axes object on which the plot will be drawn.
        line: orcaflex line object - Line.
        anode_dict: anode, buoys, and dead weight data.
        fontsize: reference scale used to define text font size and line thickness.

    Returns:
        ax: axes object on which the plot was drawn.
    """
    line_data = get_line_data(line)

    x_text, z_text = [],[]
    for anode_data in anode_dict.items():
        # Find closest index to attachment arclength
        key = next(iter(anode_data))
        target_arclength = line_data.arclength[-1] - key
        idx = np.argmin(np.abs(line_data.arclength - target_arclength))

        # Center point
        x, z = line_data.x[idx], line_data.z[idx]
        x_text.append(x)
        z_text.append(z)

        # Neighboring points (direction)
        x_prev, z_prev = line_data.x[idx - 1], line_data.z[idx - 1]
        x_next, z_next = line_data.x[idx + 1], line_data.z[idx + 1]

        # Line angle
        theta = math.atan2(z_prev - z_next, x_prev - x_next)

        # Rectangle dimensions
        dim = line.lineTypeAt(target_arclength).ContactDiameter * 0.5
        w = abs(dim)
        h = abs(dim) * 0.55

        # Rectangle centered at origin
        corners = np.array([
            [-w, -h], [w, -h], [w, h], [-w, h],
        ])

        # Rotation matrix
        sin_theta = math.sin(theta)
        cos_theta = math.cos(theta)
        R = np.array([[cos_theta, -sin_theta], [sin_theta,  cos_theta]])

        # Rotate and translate
        rectangle = corners @ R.T
        rectangle += np.array([x, z])

        # Plot base rectangle
        ax.fill(
            rectangle[:, 0],
            rectangle[:, 1],
            color="0.75",
            edgecolor="black",
            linewidth=fontsize*0.015,
        )

        # Plot offset rectangles
        for sign in (-1, 1):
            shifted = rectangle + sign * h * 2.5 * np.array([-sin_theta, cos_theta])
            ax.fill(
                shifted[:, 0],
                shifted[:, 1],
                color="0.75",
                edgecolor="black",
                linewidth=fontsize*0.015,
            )

    return ax

def draw_buoys_dvc(
        ax: object, att_data: dict, line_pos: float, descr: tuple, **kwargs,
    ) -> object:
    """
    Draw buoys.

    Args:
        ax: the axes object on which the plot will be drawn.
        attach_data: anode, buoys, and dead weight data.
        line_pos: buoys position on the line - for the description.
        descr: Tuple where:
            descr[0] -> bool: whether to draw the description
            descr[1] -> str: name of the descriptor key (e.g., "cont_descr")
        **kwargs: Optional keyword arguments passed to ax.annotate function.

    Returns:
        ax: axes object on which the plot was drawn.
    """
    # Set default values if not provided
    up_kwargs = {
        "arrowprops": kwargs.get("arrowprops", {"arrowstyle":"-", "connectionstyle": "arc3", "lw":0.3}),
        "textcoords": kwargs.get("textcoords", "data"),
        "fontsize": kwargs.get("fontsize", FONTSIZE),
        **kwargs
    }

    # Draws a vertical line
    ax.plot([att_data["x"]]*2, [att_data["z"], att_data["z"]+1], "k-", lw=0.3)

    prefix = "Até " if "cont" in descr[1] else ""

    if descr[0]:
        draw_text = att_data["draw_text"]
        ax.annotate(
            f"{prefix}{draw_text} de\nempuxo\na {line_pos}\ndo flange",
            xy=(att_data["x"], att_data["z"] + 1.2), 
            xytext=(att_data["x"], att_data["z"] + 3.0),  
            **up_kwargs,
        )

    # Adds a yellow rectangle above the line
    ax.add_patch(
        patches.Rectangle(
            (att_data["x"]-0.25, att_data["z"]+1.0), 
            width=0.5, height=0.5, facecolor="y",
            )
        )
    return ax

def draw_buoy_3d(
        ax: object, 
        x_coord: float, 
        z_coord: float, 
        buoyancy: int, 
        fontsize: int, 
        linewidth: int,
        decimal_places: int = DECIMAL_PLACES,
    ) -> object:
    """
    Draws the buoys in the correct positions and plots the buoyancy indication of each buoy. Only valid for 3D buoys.

    Args:
        ax: The axes object on which the plot will be drawn.
        x_coord: X coordinates of the buoy position.
        z_coord: Y coordinates of the buoy position.
        buoyancy: Total buoyancy of each buoy.
        linewidth: width of the plotted line in points.
        decimal_places: number of decimal places. 

    Returns:
        Adds all buoys from the model to the drawing.
    """
    ax.plot(2*[x_coord], [z_coord+1, z_coord-1], lw=linewidth, color="blue")
    text_value = format_number(buoyancy, use_comma=True, decimal_places=decimal_places, unit="")
    ax.text(x_coord, z_coord+2, f"Empuxo de {text_value}Te", ha="center", fontsize=fontsize)
    return ax

def draw_sea_layer(ax: object, x_min: float, x_max: float, **kwargs) -> object:
    """
    Draw the sea layer.

    Args:
        ax: axes object where the plot will be drawn.
        x_min: minimum X-coord.
        x_max: maximum X-coord.
        **kwargs: Optional keyword arguments passed to ax.plot function.

    Returns:
        ax: axes object on which the plot was drawn.
    """
    # Set default values if not provided
    fontsize = kwargs.get("fontsize", FONTSIZE)    
    up_kwargs = {
        "color": kwargs.get("color", "cyan"), 
        "lw": kwargs.get("lw", fontsize*0.7),
        **kwargs
    }
    
    ax.plot((x_min, x_max), (0,0), **up_kwargs)

    return ax

def draw_seabed(
        ax: object, seabed_data: tuple, x_min: float, x_max: float, **kwargs,
    ) -> object:
    """
    Draw the seabed profile.

    Args:
        ax: the axes object on which the plot will be drawn.
        seabed_data: seabed data tuple.
        x_min: minimum X-coord.
        x_max: maximum X-coord.
        **kwargs: Optional keyword arguments passed to ax.plot function.

    Returns:
        ax: axes object on which the plot was drawn.
    """
    # Set default values if not provided
    fontsize = kwargs.get("fontsize", FONTSIZE)
    up_kwargs = {
        "color": kwargs.get("color", "brown"), 
        "lw": kwargs.get("lw", fontsize*0.08),
        **kwargs
    }

    ax.plot(seabed_data.x, seabed_data.z, **up_kwargs)
    ax.plot([x_min, seabed_data.origin_x], [seabed_data.origin_z]*2, **up_kwargs)
    ax.plot([seabed_data.x[-1], x_max], [seabed_data.z[-1]]*2, **up_kwargs)

    return ax

def draw_winch(ax: object, obj: orca.OrcaFlexObject, **kwargs) -> object:
    """
    Draw the winch object.

    Args:
        ax: the axes object on which the plot will be drawn.
        obj: orcaflex winch object.
        **kwargs: Optional keyword arguments passed to ax.plot function.

    Returns:
        ax: axes object on which the plot was drawn.
    """
    # Set default values if not provided
    fontsize = kwargs.get("fontsize", FONTSIZE)
    up_kwargs = {
        "color": kwargs.get("color", "k"), 
        "lw": kwargs.get("lw", fontsize*0.08),
        **kwargs
    }

    ax.plot(
        [obj.StaticResult("X", orca.oeWinch(2)), obj.StaticResult("X", orca.oeWinch(1))],
        [obj.StaticResult("Z", orca.oeWinch(2)), obj.StaticResult("Z", orca.oeWinch(1))], 
        **up_kwargs,
    )
    return ax

def draw_vcm_dvc(
        ax: object, 
        vcm_base_point_x: float, 
        vcm_base_point_z: float, 
        vcm_base_angle: float = 0.0, 
        **kwargs,
    ) -> object:

    """
    Draw the VCM model for DVC.

    Args:
        ax: the axes object on which the plot will be drawn.
        vcm_base_point_x: X-coord of the VCM.
        vcm_base_point_z: Z-coord of the VCM.
        vcm_base_angle: Rotation angle around the Y-axis (in degrees).
        **kwargs: Optional keyword arguments passed to ax.add_patch function.

    Returns:
        ax: axes object on which the plot was drawn.
    """
    # Set default values if not provided
    fontsize = kwargs.get("fontsize", FONTSIZE)
    up_kwargs = {
        "facecolor": kwargs.get("facecolor", "r"),
        "edgecolor": kwargs.get("edgecolor", "k"),
        "linewidth": kwargs.get("linewidth", fontsize*0.08),
        **kwargs
    }

    # Base vertices
    vcm_verts = np.array([
        (vcm_base_point_x, vcm_base_point_z),
        (vcm_base_point_x - .5, vcm_base_point_z),
        (vcm_base_point_x - .25, vcm_base_point_z + 1.2),
        (vcm_base_point_x + .25, vcm_base_point_z + 1.2),
        (vcm_base_point_x + .5,  vcm_base_point_z),
        (0.0, 0.0)
    ], float)

    if vcm_base_angle != 0:
        angle = np.radians(vcm_base_angle)

        # Rotation matrix
        R = np.array([
            [np.cos(angle), -np.sin(angle)], [np.sin(angle),  np.cos(angle)]
        ])

        # Rotate all vertices except the CLOSEPOLY placeholder
        origin = np.array([vcm_base_point_x, vcm_base_point_z])
        vcm_verts[:-1] = (vcm_verts[:-1] - origin) @ R.T + origin

    # Path + Patch
    path = Path(
        vcm_verts, 
        [Path.MOVETO]+[Path.LINETO]*(len(vcm_verts)-2)+[Path.CLOSEPOLY]
    )

    ax.add_patch(patches.PathPatch(path, **up_kwargs))

    return ax

def draw_ar_slings(
        ax: object, 
        ar_obj: orca.OrcaFlexObject, 
        link1_obj: orca.OrcaFlexObject, 
        link2_obj: orca.OrcaFlexObject,
        **kwargs,
    ) -> object:
    """
    Draw the slings and the A&R winch wire.

    Args:
        ax: the axes object on which the plot will be drawn.
        ar_obj: orcaflex winch object - A&R.
        link1_obj: orcaflex object - link1.
        link2_obj: orcaflex object - link2.
        **kwargs: Optional keyword arguments passed to ax.plot function.

    Returns:
        ax: axes object on which the plot was drawn.
    """
    # Set default values if not provided
    fontsize = kwargs.get("fontsize", FONTSIZE)
    up_kwargs = {
        "color": kwargs.get("color", "k"), 
        "linewidth": kwargs.get("linewidth", fontsize*0.08),
        **kwargs,
    }

    ar_line_x = ar_obj.StaticResult("X", orca.oeWinch(2))
    ar_line_z = ar_obj.StaticResult("Z", orca.oeWinch(2))
    ar_join = ar_obj.StaticResult("Z", orca.oeWinch(1))

    ax.plot(
        [link1_obj.StaticResult("End B X"), ar_line_x, link2_obj.StaticResult("End B X")], 
        [link1_obj.StaticResult("End B Z"), ar_line_z, link2_obj.StaticResult("End B Z")], 
        **up_kwargs
    )
    ax.plot([ar_line_x]*2 , [ar_line_z, ar_join], **up_kwargs)

    return ax

def draw_external_lines(
        ax: object, line: orca.OrcaFlexLineObject, line_data: tuple, **kwargs,
    ) -> object:
    """
    Draw the external outline - for line objects.

    Args:
        ax: the axes object on which the plot will be drawn.
        line: orcaflex line object.
        line_data: line data tuple.
        **kwargs: Optional keyword arguments passed to ax.annotate function.

    Returns:
        ax: axes object on which the plot was drawn.
    """
    # Set default values if not provided
    fontsize = kwargs.get("fontsize", FONTSIZE)
    up_kwargs = {
        "facecolor": kwargs.get("facecolor", "y"), 
        "edgecolor": kwargs.get("edgecolor", "k"),
        "lw": kwargs.get("lw", fontsize*0.03),
        **kwargs,
    }

    upper_face = []
    lower_face = []

    cum_len = line.CumulativeLength
    cum_seg = [0] + list(line.CumulativeNumberOfSegments)

    for i in range(len(line.LineType)):

        dim = line.lineTypeAt(cum_len[i]).ContactDiameter * 0.5

        idx_end = cum_seg[i + 1] + 1
        obj_x = line_data.x[cum_seg[i]:idx_end]
        obj_z = line_data.z[cum_seg[i]:idx_end]
        cos_dec = line_data.cos_declination[cum_seg[i]:idx_end]
        sin_dec = line_data.sin_declination[cum_seg[i]:idx_end]

        upper_face.extend(map(tuple, zip(obj_x + dim * cos_dec, obj_z + dim * sin_dec)))
        lower_face.extend(map(tuple, zip(obj_x - dim * cos_dec, obj_z - dim * sin_dec)))

    upper_face.extend(reversed(lower_face))
    obj_list = np.array(upper_face, float)
    path = Path(obj_list, [Path.MOVETO] + [Path.LINETO] * (len(obj_list) - 1))
    ax.add_patch(patches.PathPatch(path, **up_kwargs))

    return ax

def resize_array(line_data: list, len_list: int) -> list:

    if len(line_data) > len_list:
        return line_data[:-1]
    return np.append(line_data, line_data[-1])

def draw_arclength_dimensions(
        ax: object,
        line_data: tuple,
        start_point: int, end_point: int, 
        mov_x: float, mov_z: float,
        use_comma: bool = True,
        decimal_places: int = DECIMAL_PLACES,
        **kwargs,
    ) -> object:
    """
    Draw the arc length dimensions.

    Args:
        ax: the axes object on which the plot will be drawn.
        line_data: line data tuple.
        start_point: starting point of the arclength dimension.
        end_point: end point of the arclength dimension.
        mov_x: move text along X-axis.
        mov_z: move text along Z-axis.
        use_comma: unit system - True for "," and False for ".".
        decimal_places: number of decimal places.
        **kwargs: Optional keyword arguments passed to ax.text function.

    Returns:
        ax: axes object on which the plot was drawn.
    """
    # Set default values if not provided
    fontsize = kwargs.get("fontsize", FONTSIZE)
    up_kwargs = {
        "fontsize": fontsize, 
        "va": kwargs.get("va", "top"),
        "ha": kwargs.get("ha", "center"),
        "rotation": kwargs.get("rotation", "horizontal"),
        **kwargs
    }

    cota_x = []
    cota_z = []

    # The lengths of the Declination and XYZ-coord arrays are different.
    same_len = True if len(line_data.cos_declination) == len(line_data.x) else False
    line_cos = line_data.cos_declination if same_len else resize_array(line_data.cos_declination, len(line_data.x))
    line_sin = line_data.sin_declination if same_len else resize_array(line_data.sin_declination, len(line_data.x))
    for idx in range(start_point, end_point + 1):
        cota_x.append(line_data.x[idx] - line_cos[idx])
        cota_z.append(line_data.z[idx] - line_sin[idx])

    # Dimension lines - ArcLength
    ax.plot(cota_x, cota_z, "k-", lw=fontsize*0.08)

    # Dimension lines - left arrow
    arrow_args = {
        "arrowstyle": "->", 
        "connectionstyle": "arc3", 
        "shrinkA": 0, "shrinkB": 0, 
        "mutation_scale": 7, 
        "lw": fontsize*0.08,
    }

    ax.annotate(
        "",
        xy=(cota_x[-1], cota_z[-1]), 
        xytext=(cota_x[-2], cota_z[-2]), 
        textcoords="data",
        fontsize=fontsize,
        arrowprops=arrow_args, 
    )
    # Dimension lines - rigth arrow
    ax.annotate(
        "",
        xy=(cota_x[0], cota_z[0]),
        xytext=(cota_x[1], cota_z[1]),
        textcoords="data",
        fontsize=fontsize,
        arrowprops=arrow_args,
    )

    idx_pos = int((end_point + start_point)*0.5)
    arclength = line_data.arclength
    # Dimension text
    ax.text( 
        x=line_data.x[idx_pos] - line_cos[idx_pos] + mov_x,
        y=line_data.z[idx_pos] - line_sin[idx_pos] + mov_z,
        s=format_number(arclength[end_point] - arclength[start_point], use_comma, decimal_places),
        **up_kwargs,
    )

    return ax

def draw_horizontal_dimensions(
        ax: object, 
        x_start: float, x_end: float, 
        z_start: float, z_end: float, 
        mov_z: float = -1.25,
        use_comma: bool = True,
        decimal_places: int = DECIMAL_PLACES,
        **kwargs,
    ) -> object:
    """
    Draw the horizontal dimensions.

    Args:
        ax: the axes object on which the plot will be drawn.
        x_start: starting X-coord of the arclength dimension.
        x_end: end X-coord of the arclength dimension.
        z_start: starting Z-coord of the arclength dimension.
        z_end: end Z-coord of the arclength dimension.
        mov_z: move text along Z-axis.
        use_comma: unit system - True for "," and False for ".".
        decimal_places: number of decimal places.
        **kwargs: Optional keyword arguments passed to ax.text function.

    Returns:
        ax: axes object on which the plot was drawn.
    """
    # Set default values if not provided
    up_kwargs = {
        "fontsize": kwargs.get("fontsize", FONTSIZE),
        "va": kwargs.get("va", "bottom"),
        "ha": kwargs.get("ha", "center"),
        "rotation": kwargs.get("rotation", "horizontal"),
        **kwargs,
    }
    fontsize = up_kwargs["fontsize"]

    arrows_arg = {
        "arrowstyle": "<->", 
        "connectionstyle": "arc3", 
        "shrinkA": 0, "shrinkB": 0, 
        "mutation_scale": fontsize*1.2, 
        "lw": fontsize*0.07,
    }

    # Dimension lines
    ax.annotate(
        "",
        xy=(x_start, z_end+mov_z), 
        xytext=(x_end, z_end+mov_z), 
        textcoords="data",
        fontsize=fontsize,
        arrowprops=arrows_arg,
    )

    gap = mov_z*0.05 if "top" in up_kwargs["va"] else mov_z*0.1
    # Extension lines
    ax.plot([x_start]*2, [z_start+gap, z_end+mov_z+gap], "k-", lw=fontsize*0.05)
    ax.plot([x_end]*2, [z_start+gap, z_end+mov_z+gap], "k-", lw=fontsize*0.05)

    # Dimension text
    text_value = format_number(abs(x_end-x_start), use_comma, decimal_places)
    ax.text(x=(x_start+x_end)*0.5, y=z_end+mov_z, s=text_value, **up_kwargs) 

    return ax

def draw_vertical_dimensions(        
        ax: object, 
        x_start: float, x_end: float, 
        z_start: float, z_end: float, 
        mov_x: float = 1.5,
        use_comma: bool = True,
        extension_line: bool = False,
        decimal_places: int = DECIMAL_PLACES,
        **kwargs,
    ) -> object:
    """
    Draw the vertical dimensions.

    Args:
        ax: the axes object on which the plot will be drawn.
        x_start: starting X-coord of the arclength dimension.
        x_end: end X-coord of the arclength dimension.
        z_start: starting Z-coord of the arclength dimension.
        z_end: end Z-coord of the arclength dimension.
        mov_x: move text along X-axis.
        use_comma: unit system - True for "," and False for ".".
        extension_line: extend the dimension line for better visibility.
        decimal_places: number of decimal places.
        **kwargs: Optional keyword arguments passed to ax.text function.

    Returns:
        ax: axes object on which the plot was drawn.
    """
    # Set default values if not provided
    up_kwargs = {
        "fontsize": kwargs.get("fontsize", FONTSIZE),
        "va": kwargs.get("va", "center"),
        "ha": kwargs.get("ha", "left"),
        "rotation": kwargs.get("rotation", "vertical"),
        **kwargs,
    }
    fontsize = up_kwargs["fontsize"]

    arrows_arg = {
        "arrowstyle": "<->", 
        "connectionstyle": "arc3", 
        "shrinkA": 0, "shrinkB": 0, 
        "mutation_scale": fontsize*1.2, 
        "lw": fontsize*0.07,
    }

    # Dimension lines
    ax.annotate(
        "",
        xy=(x_end+mov_x, z_start), 
        xytext=(x_end+mov_x, z_end), 
        textcoords="data",
        fontsize=fontsize,
        arrowprops=arrows_arg, 
    )

    # Extension lines
    dimension_pos = (z_start + z_end) * 0.5
    if extension_line:
        ax.plot(
            [x_end + mov_x, x_end + mov_x],[z_end - (fontsize * 0.3), z_start],
            lw=fontsize*0.03, color="black"
        )
        dimension_pos = z_end - 0.1

    gap = mov_x*0.1 if "left" in up_kwargs["ha"] else -(mov_x*0.1)
    ax.plot([x_start+gap, x_end+mov_x+gap], [z_start]*2, "k-", lw=fontsize*0.05)
    ax.plot([x_start+gap, x_end+mov_x+gap], [z_end]*2, "k-", lw=fontsize*0.05)

    # Dimension text
    text_value = format_number(abs(z_end-z_start), use_comma, decimal_places)
    ax.text(x=x_end+mov_x, y=dimension_pos, s=text_value, **up_kwargs,) 

    return ax

def draw_angular_dimension(
        ax: object,
        line: orca.OrcaFlexLineObject, 
        x_start: float, z_start: float,
        x_point_1: float, z_point_1: float,
        mov_x: float = 20,
        use_comma: bool = True,
        decimal_places: int = DECIMAL_PLACES,
        **kwargs
) -> object:
    """
    Draw an angular dimension arc and label on a matplotlib axis.

    This function computes the angular span based on the line declination,
    generates a circular arc between the reference points, and draws both the
    arc and its corresponding numeric dimension value.

    Args:
        ax: the axes object on which the plot will be drawn.
        line: orcaflex line object - Line. 
        x_start: X-coordinate of the arc center.
        z_start: Z-coordinate of the arc center.
        x_point_1: X-coordinate of the reference point defining the radius.
        z_point_1: Z-coordinate of the reference point defining the radius.
        mov_x: Horizontal offset applied to the dimension text.
        use_comma: unit system - True for "," and False for ".".
        decimal_places: number of decimal places.
        **kwargs: Optional keyword arguments passed to ax.text function.

    Returns:
        ax: axes object on which the plot was drawn.
    """
    # Set default values if not provided
    fontsize = kwargs.get("fontsize", FONTSIZE)
    line_kwargs = {
        "lw": kwargs.get("lw", fontsize*0.08),
        "color": kwargs.get("color", "k")
    }
    text_kwargs = {
        "fontsize": fontsize,
        "color": kwargs.get("color", "k"),
        "ha": kwargs.get("ha", "left")
    }

    angle = 180 - line.StaticResult("Declination", orca.oeEndA)
    radius = np.sqrt((x_point_1 - x_start)**2 + (z_point_1 - z_start)**2)

    # Calculate the initial angle
    theta0 = np.degrees(np.arctan2(z_point_1 - z_start, x_point_1 - x_start))

    # Generate points along the arc
    theta = np.radians(np.linspace(theta0, theta0 + angle, 200))
    x = x_start + radius * np.cos(theta)
    z = z_start + radius * np.sin(theta)

    # Draw the dimension arc
    ax.plot(x, z, **line_kwargs)

    # Draw the dimension value
    text_value = format_number(
        180 - line.StaticResult("Declination", orca.oeEndA),
        use_comma, decimal_places, unit="°",
    )
    ax.text(x[-1] + mov_x, z[-1], f"{text_value}", **text_kwargs)

    return ax

def indicate_tdp(
        ax: object, xz_tdp: tuple, text: str = "TDP", **kwargs,
    ) -> object:
    """
    Indicate the TDP point in the figure.

    Args:
        ax: the axes object on which the plot will be drawn.
        xz_tdp: XZ-coord of the TDP dimension.
        **kwargs: Optional keyword arguments passed to ax.annotate function.

    Returns:
        ax: axes object on which the plot was drawn.
    """
    # Set default values if not provided
    up_kwargs = {"fontsize": FONTSIZE, **kwargs}
    fontsize = up_kwargs["fontsize"]
    radius = kwargs.get("radius", fontsize*0.08)
    up_kwargs.pop("radius", None)
    
    # Insert a circle around the TDP area
    ax.text(xz_tdp[0], xz_tdp[1]+1.5*radius, text, **up_kwargs)
    ax.add_patch(
        patches.Circle(
            xy=xz_tdp, radius=radius, zorder=10, lw=fontsize*0.04, fill=False,
        )
    )
    return ax

def create_plot(
        x_label: str, z_label: str, 
        title: str, 
        fontsize: int,
        figsize: tuple,
    ) -> tuple:
    """
    Create a figure and axes with predefined formatting for engineering plots.
    
    Args:
        x_label: label for the x-axis.
        z_label: label for the z-axis.
        title: plot title.
        fontsize: reference scale used to define text font size and line thickness.
        figsize: figure size (width, height). 

    Return:
        tuple: (fig, ax), where:
            - fig (matplotlib.figure.Figure): Created figure.
            - ax (matplotlib.axes.Axes): Configured axes.
    """
    # Create figure
    fig, ax = plt.subplots(figsize=figsize)

    # Aspect ratio
    ax.set_aspect(fontsize*0.7)

    # Tick formatting
    ax.tick_params(axis="both", labelsize=fontsize*0.7)

    # Grid configuration
    ax.minorticks_on()
    ax.grid(which="major", linewidth=fontsize*0.1)
    ax.grid(which="minor", linewidth=fontsize*0.05)

    # Axis labels
    ax.set_xlabel(x_label,fontsize=fontsize)
    ax.set_ylabel(z_label, fontsize=fontsize)
    ax.set_title(title, fontsize=fontsize)

    return fig, ax

def get_figsize_from_data(xz_range: dict, height_cm: int) -> tuple:
    """
    Compute figure size preserving data aspect ratio with fixed height
    and limited maximum width.

    Args:
        xz: dict of xz-axis values.
        height_cm: figure height for Word documents..

    Returns:
        tuple[float, float]: figure size in inches as (width, height),
        suitable for use with matplotlib 'figsize'.
    """

    # axes aspect ratio (y/x scaling)
    x_range = abs(xz_range["x_max"] - xz_range["x_min"]) 
    z_range = abs(xz_range["z_max"] - xz_range["z_min"])

    # Keep figure scale
    aspect_ratio = x_range / z_range
    width_cm = min(round(height_cm * aspect_ratio, 1), DOC_MAX_WIDTH_CM)

    # Adjust height due to width limit
    if np.isclose(width_cm, DOC_MAX_WIDTH_CM, atol=1e-3):
        height_cm = round(DOC_MAX_WIDTH_CM / aspect_ratio, 1) - 0.1

    # Convert values from cm to inches
    return width_cm * CM_TO_INCHES, height_cm * CM_TO_INCHES

def save_figure(
        ax: object, 
        fig: object, 
        xz_range: dict, 
        figure_name: str,
        set_spine: bool = False,
        turn_on_axes: bool = False,
    ) -> None:
    """
    Save figures.

    Args:
        ax: the axes object on which the plot will be drawn.
        fig: figure object to be saved.
        xz_range: dict with keys that defining the limits for the XZ axes.
        figure_name: filename to save the figure.
        set_spine: enable or disable Axes spines (plot borders).
        turn_on_axes: if True, displays axes; otherwise hides them.

    Returns:
        None
    """
    plt.xlim(xz_range["x_min"], xz_range["x_max"])
    plt.ylim(xz_range["z_min"], xz_range["z_max"])

    for axis in [ax.get_xaxis(), ax.get_yaxis()]:
        axis.set_visible(turn_on_axes)

    for spine in ax.spines.values():
        spine.set_visible(set_spine)
    
    fig.tight_layout()
    fig.savefig(figure_name, dpi=600)
    plt.close(fig)

    return None
       
def add_legend_from_dict(
        ax: object,
        legend_dict: dict,
        linewidth: int = 6,
        linestyle: str = "-",
        title:  str = "Legenda",
        loc: str = "best",
        fontsize: int = FONTSIZE,
    ):
    """
    Cria entradas de legenda tipo 'barra' a partir de um dicionário (label, color[, overrides]).

    Cada valor em `legend_dict` pode ser:
      - (label, color)
      - (label, color, overrides_dict)  # ex.: {"linestyle": "None", "marker": "o"}

    Args:
        ax: Axes onde a legenda será desenhada.
        legend_dict: Mapeamento de chave -> (label, color[, overrides_dict]).
        linewidth: Largura padrão das linhas (se não for sobrescrito por item).
        linestyle: Estilo padrão de linha.
        title: Título da legenda.
        loc: Posição da legenda.
        fontsize: reference scale used to define text font size and line thickness.

    Returns:
        Matplotlib Legend object.
    """
    handles = []
    labels  = []

    for key, value in legend_dict.items():
        if not isinstance(value, (list, tuple)) or len(value) < 2:
            raise ValueError(f"Valor inválido para '{key}': esperado (nome, cor[, overrides])")

        name = value[0]
        color = value[1]
        overrides = value[2] if len(value) >= 3 and isinstance(value[2], dict) else {}

        base_kwargs = {
            "color":color,
            "linestyle":linestyle,
            "lw":linewidth,
            "solid_capstyle":"butt",
            "label":name,
        }

        base_kwargs.update(overrides)

        h = Line2D([0], [0], **base_kwargs)
        handles.append(h)
        labels.append(name)

    leg = ax.legend(
        handles=handles,
        labels=labels,
        title=title,
        loc=loc,
        frameon=True,
        fancybox=True,
        fontsize=fontsize,
        handlelength=2.2,
        handletextpad=0.8,
        borderpad=0.6,
    )
    plt.setp(leg.get_title(), fontsize=fontsize, weight="bold")

    return leg

def search_nearest_tdp(
        arc_length: np.array, clearence: np.array, index: int, direction: str,
    ) -> float:
    """
    Find the nearest TDP (touch-down point) arclength given seabed clearance.

    The TDP is defined where seabed clearance transitions from ≤0 to >0.
    The search walks left or right from an initial index until a positive
    clearance is found, then returns the neighbor arclength element.

    Args:
        arc_length: arclength samples along the line (m), aligned with 'clearence'.
        clearence: seabed clearance samples (m), same shape as 'arc_length'.
        index: starting index for the directional search.
        direction: "left" or "right" search direction

    Returns:
        Arclength value at closest index to the transition.

    Raise
        IndexError: If the index exceeds the array length, no TDP can be found.
    """

    inc = -1 if "left" in direction.lower() else 1

    if len(arc_length) < index or len(clearence) < 80:
        raise IndexError("Could not find a TDP")
    
    while True:
        try:
            if clearence[index] > 0 and clearence[index+30*inc] > 0:
               return arc_length[index-inc]
            else:
                index += inc
        except IndexError:
                raise IndexError("Could not find a TDP")
        
def draw_terminations(
        ax: object, line: orca.OrcaFlexLineObject, markersize: int = 2,
    ) -> bool:
    """
    ??????????????????????????????????????????????????????????????????????????

    Args:
        ax: the axes object on which the plot will be drawn.
        line: orcaflex line object - Line.
        marksize: ?????????????????????????????????????

    Returns:
        ax: axes object on which the plot was drawn.
    """

    for item, length in zip(line.TargetSegmentLength, line.CumulativeLength):
        if np.isclose(item, orca.OrcinaDefaultReal()):
            x = line.StaticResult("X" , orca.oeArcLength(length))
            z = line.StaticResult("Z" , orca.oeArcLength(length))
            ax.plot(x, z, "ro", markersize=markersize)
    
    return ax