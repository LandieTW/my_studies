#!/usr/bin/env python3.12

"""
DVC AUTO CONFIG TOOL
SECTION: XLSX DATA

GOALS:
    Extract data from Excel file used to model DVC analysis cases
"""


__author__ = ["Daniel T. Wanderley"]
__copyright__ = "TechnipFMC"
__credits__ = ""
__license__ = ""
__version__ = "1.0.0"
__maintainer__ = ["Daniel T. Wanderley"]
__email__ = ["daniel.wanderley@technipfmc.com"]
__status__ = "Developed"
__last_release__ = "august, 2026"


# ---
# --------
# ------------------
# --------------------------------------
# -----------------------------------------------------------------------------
# --------------------------------------
# ------------------
# --------
# ---


# Public libraries
import os
from glob import glob
from warnings import simplefilter

# IAS Private libraries
from utils.excel_handler import load_data_range_to_df

# Tool constants
from src.constants import RANGED_NAMES


# ---
# --------
# ------------------
# --------------------------------------
# -----------------------------------------------------------------------------
# --------------------------------------
# ------------------
# --------
# ---


# ignoring openpyxl user warnings
simplefilter("ignore", UserWarning)


src_path = os.path.dirname(__file__)
this_path = os.path.basename(src_path)
base_path = os.path.dirname(this_path)

xlsx_path = glob(os.path.join(base_path, "*Input_CVD*xlsm"))[0]

line = load_data_range_to_df(
    xlsx_file=xlsx_path,
    range_name=RANGED_NAMES["line"],
)
structure = load_data_range_to_df(
    xlsx_file=xlsx_path,
    range_name=RANGED_NAMES["structure"],
)
bend_restrictor = load_data_range_to_df(
    xlsx_file=xlsx_path,
    range_name=RANGED_NAMES["bend_restrictor"],
)
end_fitting = load_data_range_to_df(
    xlsx_file=xlsx_path,
    range_name=RANGED_NAMES["end_fitting"],
)
flange_adapter = load_data_range_to_df(
    xlsx_file=xlsx_path,
    range_name=RANGED_NAMES["flange_adapter"],
)
bend_restrictor_rigid_zone = load_data_range_to_df(
    xlsx_file=xlsx_path,
    range_name=RANGED_NAMES["bend_restrictor_rigid_zone"],
)

vcm_drawing = load_data_range_to_df(
    xlsx_file=xlsx_path,
    range_name=RANGED_NAMES["vcm_drawing"]
)
vcm_orcaflex = load_data_range_to_df(
    xlsx_file=xlsx_path,
    range_name=RANGED_NAMES["vcm_drawing"]
)
bathymetry = load_data_range_to_df(
    xlsx_file=xlsx_path,
    range_name="data_seabed_profile",
    is_table=True
)

water_depth = line.iloc[0, 1]

br_bm_limit = bend_restrictor.iloc[11, 1]
br_sf_limit = bend_restrictor.iloc[12, 1]

vcm_a = vcm_drawing.iloc[5, 1] / 1_000  # in meters

