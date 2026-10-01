#!/usr/bin/env python3.12

"""
DVC AUTO CONFIG TOOL
SECTION: INPUTS

GOALS:
    Handle inputs for DVC auto configuration tool.    
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


# Automation will start trying this buoy configuration.
rl_config = (
    [3, 6, 10],         # Positions [m]
    [1600, 1100, 900]          # Submerged mass [kg]
)

# Number of starting cases to be tested for DVC auto configuration tool
n_cases = 5

# RL limit load combinations to validate analysis results
structural_limits_combinations = {
    # "Combination": [AF [kN], SF [kN], BM [kN.m]]
    "AF_max": [],
    "AF_min": [],
    "SF_max": [],
    "SF_min": [],
    "BM_max": [],
    "BM_min": [],
}

# Maximum number of buoy sets
# NOTE: Automation ever starts with the minimum number of buoy sets and, if 
#       criterion are not achieved, increase it gradually
max_n_buoy_sets = 4

# Flexible jumper length
# NOTE: Applicable only for 1st End DVC Analyses
#       (If flexible length < Water depth, otherwise, set it equal to 0)
flexible_length = 0

# Automation will find a configuration considering these links positions.
# NOTE: Applicable only for 2nd End DVC analyses
links_positions = (
    (14, 19),
    (20, 25),
    (25, 30),
    (30, 35),
    (35, 40),
    (40, 45)
)

# Automation will set automatically any weight configuration
weights = [
    # ONLY ANODES
    {
        'Name': '',                     # Name = Anode XX
        'Submerged_Mass': '',           # Nominal weight [kg]
        'Initial position': '',         # First anode's position [m]
        'Space': '',                    # Space between anodes [m]
        'Quantity': ''                  # Number of anodes
    },
    # ONLY DEAD WEIGHTS
    {
        'Name': '',                     # Name = Dead Weight XX
        'Submerged_Mass': '',           # Nominal weight [kg]
        'Initial position': '',         # First dead weight's position [m]
        'Space': '',                    # Space between dead weights [m]
        'Quantity': ''                  # Number of dead weights
    }
]

# Dredging bathymetry data
dredging_bathymetry = {
    "A": '',            # Hub to dredging dist. [m]
    "B": '',            # 1st slope's horizontal dist. [m]
    "C": '',            # Dredging's total length. [m]
    "D": '',            # 2st slope's horizontal dist. [m]
    "E2": '',           # 1st slope's vertical dist. [m] (Point 1 to Point 2')
    "F2": ''            # 2st slope's vertical dist. [m] (Point 4 to Point 3')
}

# Vessel initialism
# NOTE: Same initialism used in model clump types (see options below)
# SKA - Skandi Açu;     SKB - Skandi Búzios;    SKRO - Skandi Recife/Olinda;
# SKN - Skandi Niterói; SKV - Skandi Vitória;   CDA - Coral do Atlântico
vessel_initialism = "SKRO"

# Vessel buoys
# NOTE: Keys refers to buoyancy and Values to numbers of allowables vessel 
#       buoys with that buoyancy
vessel_buoys = {
    "100": 10,
    "200": 10,
    "500": 10,
    "1_000": 10,
    "2_000": 10
}

