#!/usr/bin/env python3.12

"""
DVC AUTO CONFIG TOOL
SECTION: CONSTANTS

GOALS:
    Handle constants for DVC auto configuration tool.    
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


import OrcFxAPI as orca
from multiprocessing import cpu_count


# ---
# --------
# ------------------
# --------------------------------------
# -----------------------------------------------------------------------------
# --------------------------------------
# ------------------
# --------
# ---


# Number of CPUs to be used in parallel processing
N_WORKERS = cpu_count() - 5

# Maximum number of tentatives
N_RUN_LIMIT = 50

# Maximum number of sequential tentatives
# (while trying to solve convergence errors)
N_RUN_ERROR_LIMIT = 15

# Usual number of iterations
N_ITERATION = 400
# Maximum number of iterations
N_ITERATION_LIMIT = 4_000

# Damping coefficient range reference
DAMPING = (1, 10)

# Numerical admissible error value -> Allows convergence
ADM_ERROR = 1e-5

# Numerical non-admissible error value -> Aborts calculation
NOT_ADM_ERROR = 1e6

# Absolute tolerance adopted (number of decimal places)
ATOL = 2

# Limit of Sumberged Mass considered for a single buoy set
SUBM_MASS_LIMIT = 2_000      # [kg]

# Maximum number of buoys for each buoy set
N_BUOY_P_SET_LIMIT = 3


# ---
# --------
# ------------------
# --------------------------------------
# -----------------------------------------------------------------------------
# --------------------------------------
# ------------------
# --------
# ---


# Flexible length [m] variation in each iteration
payout_retrieve = .2

# Flexible to seabed clearance limits [m]
clearance = (.5, .65)

# Over length limits [m]
over_length = (1, 4)

# Camelback height [m] limits (relative to flenge connection height)
camelback_rel_height = (-1, 2)

# VCM rotation limits [°]
vcm_rotation = (-.5, .5)

# Heave Up height tentatives [m]
heave = (2.5, 2.2, 2.0, 1.8)

# Maximum submerged mass [kg] allowed in a single position
buoyancy_limit = 2_000

# Buoys with less than this submerged mass [kg] will be considered small
small_buoy = 150

# Submerged mass of new buoys 
new_buoy = 50

# When increasing buoyancy...
# is verifyed if a previous set is at least 1.5 times more than the next
# if not, increase that previous set, otherwise, increase the next set
buoyancy_increase_factor = 1.5

# When reducing buoyancy...
# is verifyed if a previous set is at least 2 times more than the next
# if yes, reduce that previous set, otherwise, reduce the next set
buoyancy_reduce_factor = 2

# Submerged mass [kg] variation in each iteration
buoyancy_variation = 50

# Buoy set distance from VCM [m] variation in each iteration
buoy_position_variation = .5


# ---
# --------
# ------------------
# --------------------------------------
# -----------------------------------------------------------------------------
# --------------------------------------
# ------------------
# --------
# ---


# ERROR TREATMENT STEPS

# VCM DISPLACEMENT
# Initially, consider VCM in its initial position
# Then places (or displaces) VCM -5m, then -10m, and finally -15m
vcm_displacement = (0, -5, -10)
# Initially, consider usual damping range, then consider multiples of that
damping_multiple = (1, 5, 10)
# Soil interaction
seabed_stiffness = (100, 0)
# vcm degrees of freedom
vcm_dof = ("All", "X,Y,Z", "None")


# ---
# --------
# ------------------
# --------------------------------------
# -----------------------------------------------------------------------------
# --------------------------------------
# ------------------
# --------
# ---


# NOTE: Ranged names from Excel file used to model DVC analyses
RANGED_NAMES = {
    "line": "Values!B4:C9",
    "structure": "Values!B10:C23",
    "bend_restrictor": "Values!B24:C44",
    "end_fitting": "Values!B45:C57",
    "flange_adapter": "Values!B58:C70",
    "bend_restrictor_rigid_zone": "Values!B71:C83",
    "vcm_drawing": "MCV e Guindaste!A3:B14",
    "vcm_orcaflex": "MCV e Guindaste!B18:C29"
    }


# ---
# --------
# ------------------
# --------------------------------------
# -----------------------------------------------------------------------------
# --------------------------------------
# ------------------
# --------
# ---


dvc_obj_type = [
    orca.ObjectType.Line, 
    orca.ObjectType.Buoy6D, 
    orca.ObjectType.Buoy3D, 
    orca.ObjectType.Link, 
    orca.ObjectType.Winch
]


# ---
# --------
# ------------------
# --------------------------------------
# -----------------------------------------------------------------------------
# --------------------------------------
# ------------------
# --------
# ---


STATIC_FILE_NAME = "Estatico.dat"

