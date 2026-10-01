"""
LTC DVC ANALYSIS AUTOMATION

OBJECTIVE:
    This script aims to define a configuration that verticalizes the VCM under static 
    and dynamics conditions to align it with the subsea equipment hub, respecting all 
    criteria limits.

    The system is considered vertilized when presents:
    - VCM Rotation 2 between -.5° and +.5°
    - Clearance to the seabed > .5m

DATA INPUTS REQUIRED FOR AUTOMATION:
    - Operation type (1st or 2nd extremity).
    - RL's configuration suggestion.
    - Structural analysis limits from the report.
    - Bathymetric variation (for dredging cases).
    - Available vessel buoys (if different from the data below).
    - Flexible pipe section length (for jumper cases in DVC analysis).
    - Name, submerged mass and position for Anodes and Dead Weights.
"""


# ------------------------------------------------------------------------------------
# LIBRARIES --------------------------------------------------------------------------
# ------------------------------------------------------------------------------------


import os, shutil, glob, time, json
import numpy as np, pandas as pd, OrcFxAPI as orca
from utils.utils_constants import MIN_BEND_STIFFNESS_RIGID, SEAWATER_DENSITY_ORCA
from utils.excel_handler import check_file_exists, get_data_from_spreadsheet
from utils.orcaflex import license_handler, load_model
from utils.parallel import run
from typing import Union
from collections import defaultdict, Counter
from openpyxl import load_workbook
from warnings import simplefilter
from tempfile import mkdtemp
from itertools import takewhile, accumulate, repeat, product, combinations


# -------------------------------------------------------------------------------------
# MAIN INPUTS -------------------------------------------------------------------------
# -------------------------------------------------------------------------------------

# OBS.: If both are False, the script will only get analysis's data
# Run analyses from the begining
run_statics_and_dynamics = True

# Run only dynamic steps
run_only_dynamics = True

# Run test cases
# (files will be saved in this script's directory for verification)
test = False

# num of threads
num_of_workers = 10

# num of cases to be running
max_n_cases = 20

# If line section length < LDA; input section length [m]
# line_length = 0 for 2nd end DVC
line_length = 0

# links positions [m]
links_positions = (
    [14, 19],
    [20, 25],
    [25, 30],
    [30, 35],
    [35, 40],
    [40, 45]
)

# Initial suggestion of buoy configuration
rl_config = (
    [3, 6, 10],                     # Positions [m]
    [1600, 1100, 900]                # Submerged mass [kg]
    )

# Structural limits cases
# Axial force [kN], Shear force [kN], Bend moment [kN.m]
structural_limits = {
    "BMmax": [24.19, -4.12, 48.69],
    "BMmin": [-2.85, -43.37, -108.69],
    # "SFmax": [-5.35, -5.91, 3.11],
    # "SFmin": [-17.97, -21.49, -15.14],
    # "AFmax": [9.23, -8.12, -14.73],
    "AFmin": [-38.76, -28.89, -61.09]
    }

# ------------------------------------------------------------------------------------
# ANODES AND DEAD WEIGHTS ------------------------------------------------------------
# ------------------------------------------------------------------------------------


weights = [

    # ONLY ANODES
    {
        'Name': '',                 # Name = Anodo XX
        'Submerged_Mass': '',           # Nominal weight [kg]
        'Initial position': '',     # First anode's position [m]
        'Space': '',                 # Space between anodes [m]
        'Quantity': ''              # Quantity of anodes
    },

    # ONLY DEAD WEIGHTS
        {
        'Name': '',                     # Name = Peso XX
        'Submerged_Mass': '',           # Nominal weight [kg]
        'Initial position': '',         # First dead weight's position [m]
        'Space': '',                    # Space between dead weights [m]
        'Quantity': ''                  # Quantity of dead weights
    }
]


# ------------------------------------------------------------------------------------
# DREDGING CONFIGURATION -------------------------------------------------------------
# ------------------------------------------------------------------------------------


# If there's a dredging, input it below
dredging_bathymetry = {
    "A": '',                    # Hub to dredging dist. [m]
    "B": '',                    # 1st slope's horizontal dist. [m]
    "C": '',                    # Dredging's total length. [m]
    "D": '',                    # 2st slope's horizontal dist. [m]
    "E2": '',                   # 1st slope's vertical dist. [m] (Point 1 to Point 2')
    "F2": ''                    # 2st slope's vertical dist. [m] (Point 4 to Point 3')
    }


# ------------------------------------------------------------------------------------
# CONVERGENCE CONFIGURATION ----------------------------------------------------------
# ------------------------------------------------------------------------------------

'Admissible range for clearance criterion'
min_dist = .52
max_dist = .65

'Line length changing in each iteration (when paying or retrieving line)'
payout_retrieve = .2

"Admissible values for over length"
min_over_length = 1
max_over_length = 4

"Admissible line's hump height range (considering flange's height reference)"
min_height = -1     # -1m below the flange height
max_height = 2      # 2m above the flange heitght

'Admissible range of angles for VCM rotation criterion'
min_rotation = -.5
max_rotation = .5

'Static calculation counter limiter'
n_run_limit = 50
n_error_limit = 15

'steps that triggers error treatment'
trigger_treatment = (
    0, 2, 5, 10
)

'Convergence admissible error'
adm_error = 10 ** -6

'Maximum admissible error during numerical analysis to not abort operation'
max_run_error = 10 ** 5

'Maximum number of iterations (400 - orcaflex default)'
n_iterations = 2000

'Damping range adjustment for help in better static convergence'
min_damping_range = 10
max_damping_range = 50

'Convergence decimal places'
decimal = 2

'Heave tentatives'
heave = (2.5, 2.2, 2.0, 1.8)


# -----------------------------------------------------------------------------------
# BUOYANCY CONFIGURATION ------------------------------------------------------------
# -----------------------------------------------------------------------------------


buoyancy_limit = 2_000
# allows the usage of only one small buoy in each set of buoys
small_buoy = 150

'Buoyancy factors - used in buoyancy changes'
# When increasing buoyancy... 
# verify if a previous set is at least 50% to 100% major than the next one
# if not, increase that previous one, else, increase the other one
buoyancy_increase_factor = 1.5
# When reducing buoyancy... 
# verify if a previous set is at least 100% major than the nest one
# if yes, reduce that previous one, else, reduce the other one
buoyancy_reduce_factor = 2

'Buoyancy changing in each iteration [kg]'
buoyancy_variation = 50

'Change in positions of set of buoys in each iteration [m]'
buoy_position_change = .5

'Maximum number of buoys for each single position of buoys instalation'
n_buoy_pos = 1     # automation changes it to 3, if doesn't find a solution with 2


# ----------------------------------------------------------------------------------
# VESSEL'S SET OF BUOYS {'BUOYANCY': QUANTITY ...} ---------------------------------
# ----------------------------------------------------------------------------------


# CDA - 08/2025
cda_buoys = {'100': 1, '118': 6, '205': 4, '283': 4, '500': 0, '573': 3, '828': 1, 
             '973': 1, '1252': 3,}
# TOP - XX/XXXX
top_buoys = {'100': 0, '118': 6, '205': 4, '283': 4, '500': 0, '573': 3, '828': 1, 
             '973': 1, '1252': 3,}
# SKA - 09/2025
ska_buoys = {'100': 1, '101': 1, '104': 1, '155': 1, '377': 1, '381': 1, '647': 1,
             '660': 1, '741': 2, '871': 1, '1018': 1, '1240': 1, '1252': 1, '1320': 0,
             '1323': 0, '1345': 0, '1416': 0}
 
# SKB - 09/2025
skb_buoys = {'100': 1, '220': 1, '290': 1, '385': 2, '494': 1, 
             '500': 2, '708': 1, '726': 1, '760': 1, 
             '1126': 1, '1416': 1, '1425': 1, '1428': 1, '1451': 1}
# SKRO - 09/2025
skro_buoys = {'100': 5, '381': 2, '576': 3, '1213': 5,}
# SKN - 09/2025
skn_buoys = {'500': 1, '546.8': 1,'973': 1, '1000': 2, '1300': 2,}
# SKV - ...
skv_buoys = {}
# ESTRELA - ...
estrela_buoys = {}

VESSEL_BUOYS = {
    'Skandi Búzios': skb_buoys,
    'Skandi Açu': ska_buoys,
    'Skandi Vitória': skv_buoys,
    'Skandi Recife': skro_buoys,
    'Skandi Olinda': skro_buoys,
    'Coral do Atlântico': top_buoys,
    'Top Coral do Atlântico': top_buoys,
    'Skandi Niterói': skn_buoys,
    }
    
VESSEL_INITIALISM = {
        'Skandi Niterói': 'SKN',
        'Skandi Búzios': 'SKB',
        'Skandi Açu': 'SKA',
        'Skandi Vitória': 'SKV',
        'Skandi Recife': 'SKRO',
        'Skandi Olinda': 'SKRO',
        'Coral do Atlântico': 'TOP',
        'Top Coral do Atlântico': 'TOP'
        }


# -----------------------------------------------------------------------------------
# EXCEL DATA ------------------------------------------------------------------------
# -----------------------------------------------------------------------------------


'Ignoring openpyxl user_warning'
simplefilter("ignore", UserWarning)

'This script path'
THIS_PATH = os.path.dirname(__file__)

# Loading excel data
SHEET_PATH = os.path.join(THIS_PATH, glob.glob(
    os.path.join(THIS_PATH, "*Input_CVD*xlsm"))[0])
check_file_exists(SHEET_PATH)
WB = load_workbook(SHEET_PATH)

# LDA [m]
LDA = get_data_from_spreadsheet(SHEET_PATH, "Values", "C3")
BR_BM_LIMIT = get_data_from_spreadsheet(SHEET_PATH, "Values", "C28")
BR_SF_LIMIT = get_data_from_spreadsheet(SHEET_PATH, "Values", "C29")

# Flange height to the seabed [mm]
VCM_A = get_data_from_spreadsheet(SHEET_PATH, "MCV e Guindaste", "B8") / 1_000

# Vessel name, buoys and initialismo
VESSEL_NAME = get_data_from_spreadsheet(SHEET_PATH, "Results", "H25")
if not VESSEL_NAME:
    raise ValueError(f"No vessel name found in {os.path.basename(SHEET_PATH)}")
BUOYS = VESSEL_BUOYS[VESSEL_NAME]
INIT = VESSEL_INITIALISM[VESSEL_NAME]

'Analysis paths'
STATIC_FILE_PATH = os.path.join(THIS_PATH, "Estatico.dat")
AUTOMATION_PATH = os.path.join(THIS_PATH, "AutomationResults")
os.makedirs(AUTOMATION_PATH, exist_ok=True)


# ----------------------------------------------------------------------------------
# CLASSES --------------------------------------------------------------------------
# ----------------------------------------------------------------------------------


class AuxiliarVariables():
    """
    Description:
        Auxiliar variables to use in analysis
    """
    def __init__(self):
        self.dvc_type = None
        'list to save bend restrictor removing or inserting'
        self.attach = list()
        'save configurations that already were tryed'
        self.looping_buoy_results = list()
        'save links positions that already were tryed'
        self.looping_link_results = list()
        'static calculation counter'
        self.run_counter = 0
        'convergence error counter'
        self.error_counter = 0
        "VCM's rotation"
        self.rotation = None
        "Line's clearance to seabed"
        self.clearance = None
        "Flange VCM's height error"
        self.delta_flange = None
        'hump height (in 2nd end DVC)'
        self.hump_height = None
        'over length (in 2nd end DVC)'
        self.over_length = None
        'Counter of link position changing'
        self.link_position_changing = 0
        'Static handler counter'
        self.static_handler_counter = 0
        'Aprooved?'
        self.aprooved = False
    
    def check_true(self):
        if self.rotation < .5 and self.rotation > -.5 \
            and self.clearance > .52 and self.clearance < .65 \
                and self.delta_flange == 0:
            self.aprooved = True


# ----------------------------------------------------------------------------------
# OBJECTS --------------------------------------------------------------------------
# ----------------------------------------------------------------------------------


cvd_obj_type = [
    orca.ObjectType.Line, 
    orca.ObjectType.Buoy6D, 
    orca.ObjectType.Buoy3D, 
    orca.ObjectType.Link, 
    orca.ObjectType.Winch,
]


# ----------------------------------------------------------------------------------
# METHOD ---------------------------------------------------------------------------
# ----------------------------------------------------------------------------------


def verify_inputs(
        model: orca.Model
    ) -> bool | str:
    """
    Description:
        Verify each input before start running analysis
    Parameters:
        model - orcaflex model
    Return
        True if inputs are correct;
        False if not, with a message of the error
    """
    
    line = model['Line']
    dvc_type = 1 if "Anchored" not in \
        [line.EndAConnection, line.EndBConnection] else 2

    # checking line_length
    if not isinstance(line_length, (int, float)) or \
        (line_length != 0 and dvc_type == 2):
        message = f'Verify line length input'
        return False, message
    
    # checking link_position
    near_link = links_positions[0]
    for pos in near_link:
        if not isinstance(pos, (int, float)):
            message = f'Verify link positions input'
            return False, message

    # checking rl_config
    rl_pos = rl_config[0]
    rl_buo = rl_config[1]
    if len(rl_pos) != len(rl_buo):
        message = f'Verify rl_config input'
        return False, message
    for i in range(len(rl_pos)):
        pos, buo = rl_pos[i], rl_buo[i]
        if not isinstance(pos, (int, float)) or not isinstance(buo, (int, float)):
            message = f'Verify rl_config input'
            return False, message
    
    # checking structural limits
    for comb in list(structural_limits.values()):
        if len(comb) != 3 or \
            not isinstance(comb[0], (int, float)) or\
                not isinstance(comb[1], (int, float)) or\
                    not isinstance(comb[2], (int, float)):
            message = f'Verify structural limits input'
            return False, message
    
    # checking weights
    for w in weights:
        if w['Name']:
            if not isinstance(w['Name'], str) or \
                not isinstance(w['Submerged_Mass'], (int, float)) or \
                    not isinstance(w['Initial position'], (int, float)) or \
                        not isinstance(w['Space'], (int, float)) or \
                            not isinstance(w['Quantity'], (int, float)):
                message = f'Verify the weights input'
                return False, message

    # checking dredging bathymetry
    for dist in list(dredging_bathymetry.values()):
        if dist:
            if not isinstance(dist, (int, float)):
                message = f'Verify the dredging input'
                return False, message

    # checking vessel_name
    if isinstance(VESSEL_NAME, str):
        if VESSEL_NAME not in list(VESSEL_BUOYS.keys()):
            message = f'Verify the vessel name input'
            return False, message
    
    checking_buoys(model)

    return True, ''


def jumper_condition(
        line: orca.OrcaFlexLineObject,
        a_r: orca.OrcaFlexObject,
        line_length: Union[int, float]
    ) -> None:
    """
    Description
        Adjust A/R length when modeling a 1st end DVC jumper case
    Parameters:
        line - OrcaFlex Line
        a_r - OrcaFlex A/R 
        line_length - Line's length (< Water depth)
    Return
        None
    """
    a_r.StageValue[0] = line.CumulativeLength[-1] - line_length
    line.Length[0] -= line.CumulativeLength[-1] - line_length - line.Length[-1]
    if line.NumberOfSections == 9:  # PU Vert's rigid zone and Flange adapter
        line.Length[0] += line.Length[-2] + line.Length[-3]
    elif line.NumberOfSections == 8:    # PU Vert's rigid zone or Flange adapter
        line.Length[0] += line.Length[-2]
    line.EndAZ = - a_r.StageValue[0]


def adjusting_bathymetry(
        bathymetry: dict,
        env: orca.oeEnvironment
    ) -> None:
    """
    Description:
        Adjusting bathymetry when we have a dredge
    Parameters:
        bathymetry - dict with dredge measures
        env - Orcaflex Environment
    Return None
    """
    env.SeabedProfileNumberOfPoints = 5
    env.SeabedProfileDistanceFromSeabedOrigin[1] = bathymetry["A"]
    env.SeabedProfileDistanceFromSeabedOrigin[2] = bathymetry["A"] + \
        bathymetry["B"]
    env.SeabedProfileDistanceFromSeabedOrigin[3] = bathymetry["A"] + \
        bathymetry["C"] - bathymetry["D"]
    env.SeabedProfileDistanceFromSeabedOrigin[4] = bathymetry["A"] + \
        bathymetry["C"]
    env.SeabedProfileZ[2] -= bathymetry["E2"]
    env.SeabedProfileZ[3] -= bathymetry["F2"]


def insert_weigths(
        aux_var: AuxiliarVariables,
        path: str,
        case: str,
        model: orca.Model,
        vcm: orca.OrcaFlexObject,
        line: orca.OrcaFlexLineObject,
        bend_restrictor: orca.OrcaFlexObject,
        link1: orca.OrcaFlexObject,
        link2: orca.OrcaFlexObject,
        general: orca.OrcaFlexObject,
        env: orca.oeEnvironment,
    ) -> None:
    """
    Description:
        Insert anodes and/or dead weights in line
    Parameters:
        aux_var - class that saves analysis data individually in the multiprocessing
        path - temp path of the analysis directory
        case - wich case is running
        model - orcaflex model
        vcm - VCM in model
        line - line in model
        bend_restrictor - vert in the model
        link1 - link in the model
        link2 - link in the model
        general - general in model
        env - environment in model
    Return:
        None
    """
    anodes = weights[0]
    dead_weights = weights[1]

    def insert(
            weight: dict
            ):
        ''
        # creating weight (anode or dead weight), if necessary
        clumps = [obj.Name for obj in model.objects if obj.type == \
                  orca.ObjectType.ClumpType.value]
        if weight['Name'] not in clumps:
            subm_weight = model.CreateObject(orca.ObjectType.ClumpType)
            subm_weight.Name = weight['Name']
            subm_weight.Mass = weight['Submerged_Mass'] / 1_000
            subm_weight.Volume = 0
            subm_weight.Height = 1

        i = 0
        while i < weight['Quantity']:
            position = round(i*weight['Space']+weight['Initial position'], decimal)
            print(f"\n{case}\
                  Inserting {weight['Submerged_Mass']}kg in {position}m from VCM")
            line.NumberOfAttachments += 1
            line.AttachmentType[-1] = weight['Name']
            line.Attachmentz[-1] = position

            static_run_calculation(aux_var, path, case, model, vcm, line, 
                                   bend_restrictor, link1, link2, general, env, False)
            i += 1

    if anodes['Name']:
        insert(anodes)
    if dead_weights['Name']:
        insert(dead_weights)


def checking_buoys(
        model: orca.Model
    ) -> None:
    """
    Description:
    Parameters:
    """
    # checking buoys
    buoys = list(BUOYS.keys())
    qtt = list(BUOYS.values())
    buoys_we_have = [buoys[i] for i in range(len(qtt)) if qtt[i] > 0]
    attach = [f'{INIT}_{b}' for b in buoys_we_have]
    buoys_in_model = [b.Name for b in model.objects if b.type == orca.ObjectType.ClumpType]
    for att in attach:
        if att not in buoys_in_model:
            new_buoy = model.CreateObject(orca.ObjectType.ClumpType)
            new_buoy.Name = att
            new_buoy.Volume = 2
            new_buoy.Height = 1
            displaced_mass = 2 * SEAWATER_DENSITY_ORCA
            buoyancy = float(att.split("_")[1])/1_000
            new_buoy.Mass = displaced_mass - buoyancy


def near_far_position(
        positions: list
    ) -> list | list:
    """
    Description:
        Generate range positions for buoy's set
    Parameters:
        positions - positions suggestion (based on the RL Configuration)
    Return
        Buoy's position near to the VCM
        Buoy's position for of the VCM
    """
    if len(positions) == 1:
        near_vcm_positions = [3]
        far_vcm_positions = [15]
    elif len(positions) == 2:
        near_vcm_positions = [3, 6]
        far_vcm_positions = [9, 15]
    elif len(positions) == 3:
        near_vcm_positions = [3, 6, 9]
        far_vcm_positions = [6, 9, 15]
    
    return near_vcm_positions, far_vcm_positions


def generate_buoyconfig(
        rl_config: dict,
    ) -> dict:
    """
    Description:
        Generate different cases starting from rl_config
    Parameters:
        rl_config - initial user suggestion of buoys configuration
    Return:
        Different configurations to be tested
    """
    pos = rl_config[0]
    buoy = rl_config[1]
    moment = [p * b for p, b in zip(pos, buoy)]

    near_vcm_positions, far_vcm_positions = near_far_position(pos)

    position_ranges = [
        [round(p, 1)
         for p in list(takewhile(lambda x: x <= far,
                                  accumulate(repeat(buoy_position_change), initial=near)))
         if near <= p <= far]
        for near, far in zip(near_vcm_positions, far_vcm_positions)
    ]

    positions = []
    for combo in product(*position_ranges):
        if all(combo[i+1] - combo[i] >= 3 for i in range(len(combo)-1)):
            positions.append(list(combo))

    # sort with euclidyan distance from the rl_config
    def distance_to_original(p):
        return sum((p[i] - pos[i])**2 for i in range(len(p)))

    positions.sort(key=distance_to_original)
    positions = positions[:max_n_cases]  # limits to 25 config tentatives

    buoyancy = []
    for position in positions:
        buoys = []
        for i in range(len(moment)):
            bm = moment[i]
            reductor = position[i] / pos[i]
            buoys.append(round((bm / position[i]) * reductor, 0))
        buoyancy.append(buoys)

    analysis_cases = [[positions[i], buoyancy[i]] for i in range(len(positions))]
    return analysis_cases


def select_buoy_combination(
        config: list,
    ) -> dict:
    """
    Description:
        Creates a combination of buoys and select the closer of config suggestion
    Parameters:
        config: list with reference for position and buoyancy
        buoy_set: Dict with vessel's buoys
    Return:
        Selection of buoy's combinations that better fits config suggestion
    """

    def buoy_combination(
            buoys: list,
        ) -> dict:
        """
        Description:
            Combines buoys, following next rules:
            1 - Each combination must have less than 2000 kg of submerged mass
            2 - Each combination must combine, at maximum, {N_BUOY_POS} buoys
            3 - Each combination must respect vessel's availability for each buoy
            4 - If a combination is done with N_BUOY_POS == 3, than, at least, 
            one of this buoys is a small buoy (<150kg of submerged mass)
        Parameters:
            buoys: List with elements from buoy_set
        Return:
            A dict with this format {'b1+b2': b1+b2, ...}
        """
        comb = list(combinations(buoys, 1)) + \
            list(combinations(buoys, 2))
        if n_buoy_pos == 3:
            comb += list(combinations(buoys, 3))
    
        final_comb = defaultdict(float)     # avoid reppeated combinations

        for combination in comb:

            if len(combination) == 1:
                val = combination[0]
                key = str(val)
                final_comb[key] = val

            elif len(combination) == 2:
                if (val := combination[0] + combination[1]) <= buoyancy_limit:
                    key = str(combination[0]) + "+" + str(combination[1])
                    final_comb[key] = val

            elif len(combination) == 3:
                if combination[0] <= small_buoy or combination[1] <= small_buoy \
                        or combination[2] <= small_buoy:      # < 2000kg
                    if (val := combination[0] + combination[1] + combination[2]) <= \
                        buoyancy_limit:     # one of three is a small buoy
                        key = str(combination[0]) + "+" \
                            + str(combination[1]) + "+" + str(combination[2])
                        final_comb[key] = val
        # all combinations
        return dict(sorted(final_comb.items(), key=lambda item: item[1], reverse=True))

    b = [int(key) for key, count in BUOYS.items() for _ in range(count)]

    selection = {}

    for ref in config[1]:

        if ref == buoyancy_limit:       # treating a possible error
            ref = .9 * ref

        buoy_comb = buoy_combination(b)     # combining buoys
        
        buoys = list(buoy_comb.keys())
        buoyancy = list(buoy_comb.values())

        # making selection
        buoyancy.append(ref)
        buoyancy.sort(reverse=True)
        i = buoyancy.index(ref)
        
        if i == 0:      # reference is bigger than our combinations options
            index = i + 1       # index 0 = ref / index 1 = selection
            key = buoys[index]

        # reference is smaller than our combinations options
        elif i == len(buoyancy) - 1:
            index = i - 1       # index -1 = ref / index -2 = selection
            key = buoys[index]
            
        else:   # reference is between our combinations options
            buoyancy_options = [buoyancy[i - 1], buoyancy[i + 1]]       # two options
            # look which option is closer to the reference
            if abs(ref - buoyancy_options[0]) < abs(ref - buoyancy_options[1]):
                index = i - 1
                key = buoys[index]
            else:
                index = i + 1
                key = buoys[i]
        
        if key in selection.keys():
            key += " "  # for cases when the keys are reppeated
            selection[key] = buoyancy[index]
        else:
            selection[key] = buoyancy[index]   # selection
        
        buoys = key.split("+")
        for buoy in buoys:              # excluding chosen buoys, for next selection
            b.remove(int(buoy))
    
    return selection        # {'b1+b2': b1+b2, ...}


def StaticProgHandler(
        _,
        progress
    ) -> bool:
    """
    Description:
        Method to handle statics calculations
    Parameters:
        _: OrcaFlex model
        progress: convergence error, for each iteration
    Return:
        True for stop CalculateStatics (did not converged)
        False for keep running (already converged)
    """
    try:
        static_error = progress.split()
        
        index = 0
        if progress.startswith('\nFull statics for Line (no torsion)'):
            index = 10
        elif progress.startswith('\nFull statics for Line'):
            index = 8
        elif progress.startswith('\nWhole system statics'):
            index = 7
        elif progress.startswith('\nConverged with error'):
            index = 4
        if index != 0:
            error = static_error[index].replace(',', '.')
            final_error = round(float(error), decimal)
            
            if final_error < adm_error:
                if index == 4:
                    print(f"\nWhole system statics converged \n\
                          with error: {final_error}")
                    return False

            if final_error > max_run_error:
                print(f"\nConvergence failed.")
                return True
        
    except Exception as e:
        print(f"\n{e}")
        return False


def insert_remove_vert(
        aux_var: AuxiliarVariables,
        line: orca.OrcaFlexLineObject,
        remove_or_insert: bool
    ) -> None:
    """
    Description:
        Remove or insert vert of the line
    Parameters:
        aux_var - class that saves analysis data individually in the multiprocessing
        line - OrcaFlex line
        remove_or_insert - True = insert / False = remove
    Return:
        None
    """
    if remove_or_insert:
        line.NumberOfAttachments += 1
        if line.NumberOfAttachments > 1:
            i = 1
            n = line.NumberOfAttachments
            while i < n:
                line.AttachmentType[n-i] = line.AttachmentType[n-i-1]
                line.Attachmentz[n-i] = line.Attachmentz[n-i-1]
                line.AttachmentzRelativeTo[n-i] = line.AttachmentzRelativeTo[n-i-1]
                if line.AttachmentName[n-i-1]:
                    line.AttachmentName[n-i] = line.AttachmentName[n-i-1]
                i += 1
        line.AttachmentType[0] = aux_var.attach[0]
        line.Attachmentz[0] = aux_var.attach[1]
        line.AttachmentzRelativeTo[0] = aux_var.attach[2]
        line.AttachmentName[0] = aux_var.attach[3]
        aux_var.attach.clear()
    else:
        i = 0
        while i < line.NumberOfAttachments:
            if aux_var.attach:
                line.AttachmentType[i-1] = line.AttachmentType[i]
                line.Attachmentz[i-1] = line.Attachmentz[i]
                line.AttachmentzRelativeTo[i-1] = line.AttachmentzRelativeTo[i]
                if line.AttachmentName[i]:
                    line.AttachmentName[i-1] = line.AttachmentName[i]
            elif line.AttachmentName[i].startswith("Stiffener") \
            and line.AttachmentName[i]:
                aux_var.attach.append(line.AttachmentType[i])
                aux_var.attach.append(line.Attachmentz[i])
                aux_var.attach.append(line.AttachmentzRelativeTo[i])
                aux_var.attach.append(line.AttachmentName[i])
            i += 1
        line.NumberOfAttachments -= 1


def error_treatment(
        aux_var: AuxiliarVariables,
        case:str,
        general: orca.OrcaFlexObject,
        line: orca.OrcaFlexLineObject,
        vcm: orca.OrcaFlexObject,
        env: orca.OrcaFlexObject,
    ) -> None:
    """
    Description:
        Tentatives to get convergence in static calculation, after it fails 
    Parameters:
        aux_var - class that saves analysis data individually in the multiprocessing
        case - wich case is running
        general - OrcaFlex general
        line - OrcaFlex Line
        vcm - OrcaFlex VCM
        env - Orcaflex environment
    Return:
        None
    """
    if aux_var.error_counter >= n_error_limit:
        print(f"\nConvergence problem could not be solved.")
        aux_var.run_counter = n_run_limit + 1
    else:
        vcm.DegreesOfFreedomInStatics = "All"
        env.SeabedNormalStiffness = 100

        if aux_var.error_counter < n_error_limit:
            print(f"\n{case} - ERROR N°{aux_var.error_counter}")
            print('-'*50)
            if aux_var.error_counter not in trigger_treatment:
                print(f"\
                      Displacing VCM\n")
            # tries to pull VCM away and "force" axial traction to the system 
            # (the idea is to avoid compression forces, wich mess with the convergence)
            vcm.InitialX -= 5

        if aux_var.error_counter == trigger_treatment[0]:
            print(f"\
                  Displacing VCM\n\
                  Increasing damping range\n\
                  Removing line x soil interation\n\
                  Changing static policy to Catenary")
            general.StaticsMinDamping = min_damping_range   # reducing damping range
            general.StaticsMaxDamping = max_damping_range   # increasing damping range
            line.StaticsStep1 = "Catenary"      # catenary static policy
            if aux_var.dvc_type == 1:
                env.SeabedNormalStiffness = 0
        
        if aux_var.error_counter == trigger_treatment[1]:
            print(f"\
                  Displacing VCM\n\
                  Increasing maximum iteration limits")
            general.StaticsMaxIterations = n_iterations   # increasing iterations

        if aux_var.error_counter == trigger_treatment[2]:
            print(f"\
                  Displacing VCM\n\
                  Removing VCM's degrees of freedom in statics")
            vcm.InitialX = 0
            vcm.DegreesOfFreedomInStatics = "None"
            if 'Vert' in line.AttachmentType:
                print(f"\
                  Removing the Bend Restrictor for better convergence")
                insert_remove_vert(aux_var, line, False)
        
        if aux_var.error_counter == trigger_treatment[3]:
            print(f"\
                  Displacing VCM\n\
                  Trying with no step2 static policy")
            vcm.InitialX = 0
            general.LineStaticsStep2Policy = "None"

        aux_var.error_counter += 1


@license_handler
def static_run_calculation(
        aux_var: AuxiliarVariables,
        path: str,
        case: str,
        model: orca.Model,
        vcm: orca.OrcaFlex6DBuoyObject,
        line: orca.OrcaFlexLineObject,
        bend_restrictor: orca.OrcaFlexObject,
        link1: Union[orca.OrcaFlexObject, None],
        link2: Union[orca.OrcaFlexObject, None],
        general: orca.OrcaFlexObject,
        env: orca.oeEnvironment,
        final: bool
    ) -> None:
    """
    Description:
        Runs static simulation
    Parameters:
        aux_var - class that saves analysis data individually in the multiprocessing
        path - Path to save run cases
        case - wich case is running
        model - OrcaFlex model
        vcm - OrcaFlex VCM
        line - OrcaFlex line
        bend_restrictor - vert in the model
        link1 - link1 in model
        link2 - link2 in model
        general - OrcaFlex general
        env - OrcaFlex Environment
        final - trigger to verify flange and vert loads
    Return:
        None
    """
    try:
        if aux_var.run_counter > n_run_limit:
            return

        print(f"\n{case} - Trying static calculation convergence")
        # default to static progresshandler
        model.staticsProgressHandler = StaticProgHandler
        model.CalculateStatics()
        
        aux_var.rotation = round(vcm.StaticResult(varNames="Rotation 2"), decimal)
        aux_var.clearance = verify_clearance(aux_var, line, link1)
        aux_var.delta_flange = verify_flange_height(line)
        if aux_var.dvc_type == 2:
            aux_var.hump_height = verify_hump_height(line, link1, link2)
            aux_var.over_length = verify_over_length(line)
        
        # necessary verification to avoid crazy convergences...
        line_nc = verify_normalised_curvature(line)
        if line_nc >= 1 and aux_var.clearance > 0 and abs(aux_var.rotation) < .5:
            print(f"{case} - Convergence error")
            line.StaticsStep1 = "Catenary"
            model.staticsProgressHandler = StaticProgHandler
            model.CalculateStatics()

            aux_var.rotation = round(vcm.StaticResult("Rotation 2"), decimal)
            aux_var.clearance = verify_clearance(aux_var, line, link1)
            aux_var.delta_flange = verify_flange_height(line)
            if aux_var.dvc_type == 2:
                aux_var.hump_height = verify_hump_height(line, link1, link2)
                aux_var.over_length = verify_over_length(line)

        if final:
            # exclude verticalization with no admissible loands in VCM's flange or 
            # bend restrictor
            aux_var.run_counter -= 1
            flange_loads = verify_flange_loads(line)
            vert_loads = verify_normalised_curvature(model['Stiffener1'])
                        
            if not flange_loads or not vert_loads:
                aux_var.aprooved = False

        aux_var.run_counter += 1
        save_simulation = os.path.join(
            path, f"{os.path.basename(path)}_{str(aux_var.run_counter)}_Static.sim")
        model.SaveSimulation(save_simulation)

        model.UseCalculatedPositions(SetLinesToUserSpecifiedStartingShape=True)

        print("\n")
        print('-'*50)
        print(f"{case} - {aux_var.run_counter}th static simulation run")
        print('-'*50)
        print(f"VCM's rotation: {aux_var.rotation}°")
        print(f"Line's clearance to seabed: {aux_var.clearance}[m]")
        print(f"Flange's height error: {aux_var.delta_flange}[m]")
        if aux_var.dvc_type == 2:
            print(f"Hump's height: {aux_var.hump_height}[m]")
            print(f"Over length: {aux_var.over_length}[m]")
            print(f"Link's positions: {link1.EndBZ} : {link2.EndBZ}")
        print('-'*50)

        aux_var.error_counter = 0 if 'Vert' in line.AttachmentType else aux_var.error_counter
        env.SeabedNormalStiffness = 100
        general.StaticsMinDamping = 15
        general.StaticsMaxDamping = 30
        general.LineStaticsStep2Policy = 'Parent lines excluded'
        if 'Vert' not in line.AttachmentType:
            insert_remove_vert(aux_var, line, True)

    except Exception as e:
        print(e)
        error_treatment(aux_var, case, general, line, vcm, env)
        static_run_calculation(aux_var, path, case, model, vcm, line, bend_restrictor,
                               link1, link2, general, env, final)

@license_handler
def dyn_run(model):
    model.RunSimulation()

def dynamic_run_calculation(
        path: str
    ) -> None:
    """
    Description:
        Runs dynamic simulation
    Parameters:
        path - Path of a succesfull verticalized case
    Return:
        None
    """
    case = os.path.basename(path).upper()

    model, _ = load_model(file=path, return_model_name=True)

    line = model['Line']
    general = model['General']

    cvd_objs = [obj for obj in model.objects if obj.type in cvd_obj_type]
    obj_names = [obj.name for obj in cvd_objs]
    vcm_name = next((item for item in [line.EndBConnection, line.EndAConnection] \
                     if item in obj_names), None)
    if vcm_name:
        vcm = model[vcm_name]
        vcm.Connection = "Fixed"
    
    winches = [obj for obj in cvd_objs if obj.type == orca.ObjectType.Winch.value]
    winch = next((item for item in winches if item.Connection[0] or \
                  item.Connection[1] in vcm_name), None)
    a_r = next((item for item in winches if winch.Name not in item.Name), None)
    
    for o in range(len(heave)):
        h = heave[o]
        print(f"\nRunning {case} dynamic simulation for a heave up of {h}m")
        a_r.StageValue[2] = -h
        dyn_run(model)

        check_loads, _, as_tqf = dyn_loads(line, general)

        if "Static" in os.path.basename(path):
            file_name = os.path.basename(path).replace("Static", "Dynamic")
            file_name = file_name.replace(f".sim", f"_{str(h)}m.sim")
        else:
            file_name = os.path.basename(path).split("Dynamic_")[0]
            file_name += f"Dynamic_{str(h)}m.sim"

        save_simulation = os.path.join(
            os.path.dirname(path),
            file_name
        )

        if check_loads and not as_tqf:
            model.SaveSimulation(save_simulation)
            break
        else:
            if as_tqf:
                destiny_dir = os.path.join(os.path.dirname(save_simulation),
                                           "TQF")
                os.makedirs(destiny_dir, exist_ok=True)
            else:
                destiny_dir = os.path.join(os.path.dirname(save_simulation),
                                           "failed")
                
            destiny_path = os.path.join(destiny_dir, 
                                        os.path.basename(save_simulation))
            model.SaveSimulation(destiny_path)


def verify_normalised_curvature(
        element: orca.OrcaFlexLineObject,
    ) -> float:
    """
    Description:
        Verify element's normalised curvature value
    Parameters:
        element: OrcaFlex object (Line or bend restrictor)
        magnitude: 'Mean' for static calculation
    Returns:
        Element's normalised curvature value
    """

    def verify_br_loads(
            vert: orca.OrcaFlexLineObject,
        ) -> bool:
        """
        Description:
            Verify if vert's loads are admissible (Just if limits were given)
        Parameter:
            vert: Bend restrictor
        Return:
            True if loads < limits, False if loads > limtis.
        """
        structural_limits = [
            BR_SF_LIMIT,      # Shear force limit
            BR_BM_LIMIT       # Bend moment limit
        ]

        check = []

        for i in range(len(structural_limits)):

            if i == 0 and structural_limits[i]:      # shear force limit case
                shear = vert.RangeGraph("Shear Force").Mean
                shear = round(max(abs(min(shear)), max(shear)), decimal)
                check.append(shear < structural_limits[i])
                print(f"Vert - Shear force: {shear}")
            
            if i == 1 and structural_limits[i]:      # bend moment limit case
                moment = vert.RangeGraph("Bend moment").Mean
                moment = round(max(abs(min(moment)), max(moment)), decimal)
                check.append(moment < structural_limits[i])
                print(f"Vert - Bend moment: {moment}")
        
        if all(check):
            print("\nVert's loads aprooved!")
            return True
        else:
            print("\nVert's loads reprooved!")
            return False

    n_curve = element.RangeGraph('Normalised curvature').Mean

    if element.name == "Line":
        return round(max(n_curve), decimal)
    
    if round(max(n_curve), decimal) >= 1:
        print(f"\nVert's locked")
        return verify_br_loads(element)
    else:
        print(f"\nVert isn't locked")
        return True


def verify_clearance(
        aux_var: Union[AuxiliarVariables, int],
        element: orca.OrcaFlexObject,
        link1: Union[orca.OrcaFlexObject, None]
    ) -> float:
    """
    Description:
        Verify element's clearance value, in metters
    Parameters:
        element: OrcaFlex object (Line, and others)
        aux_var: class that saves analysis data individually in the multiprocessing
        link1: 1st link in the line's hump
    Returns
        Element's clearance value
    """
    if isinstance(aux_var, int):
        if dvc_type == 1:
            clearance = element.RangeGraph('Seabed clearance').Mean
        else:
            clearance = element.RangeGraph(
                varName='Seabed clearance',
                arclengthRange=orca.arSpecifiedArclengths(
                    element.NodeArclengths[-1]-link1.EndBZ,
                    element.NodeArclengths[-1]-5)           # change
                ).Mean
    else:
        if aux_var.dvc_type == 1:
            clearance = element.RangeGraph('Seabed clearance').Mean
        else:
            clearance = element.RangeGraph(
                varName='Seabed clearance',
                arclengthRange=orca.arSpecifiedArclengths(
                    element.NodeArclengths[-1]-link1.EndBZ,
                    element.NodeArclengths[-1]-5)           # change
                ).Mean
    return round(min(clearance), decimal)


def verify_flange_height(
        element: orca.OrcaFlexObject,
    ) -> float:
    """
    Description:
        Verify flange's height error, in metters.
    Parameters:
        element: OrcaFlex object (Line, and others)
        water_depth: water depth, in metters
        vcm_height: flange to soil height, in mm
    Returns:
        Flange's height error
    """
    correct_depth = - LDA + VCM_A
    depth_verified = element.StaticResult('Z', orca.oeEndB)
    return round(correct_depth - depth_verified, decimal)


def verify_flange_loads(
        line: orca.OrcaFlexLineObject,
        ) -> bool:
    """
    Description:
        Verify if flange's loads are admissible
    Parameters:
        line: Flexible pipe
        limits: Structural limits for flange
        case: Load case analysis - (2)
    Returns
        True if loads < limits, False if loads > limits.
    """
    loads = np.array([
        abs(round(line.StaticResult("End Ez force", orca.oeEndB), decimal)),
        -abs(round(line.StaticResult("End Ex force", orca.oeEndB), decimal)),
        -abs(round(line.StaticResult("End Ey moment", orca.oeEndB), decimal))
    ])
    case = []
    for limit in list(structural_limits.values()):
        result, _ = checking_loads(loads, np.round(limit, decimal))
        case.append(result)
    
    return any(case)


def verify_over_length(
        line: orca.OrcaFlexLineObject,
    ) -> float:
    '''
    Description:
        Verify the over length criterion
        comprimento suspenso - (coord X flange - coord X TDP)
    Parameters:
        line - line in model
    Return:
        Over length
    '''
    touch_down_point = line.StaticResult("X", objectExtra=orca.oeTouchdown)
    
    layed_length = line.StaticResult("Arc length", objectExtra=orca.oeTouchdown)
    total_length = line.CumulativeLength[-1]
    hump_length = round(total_length - layed_length, decimal)
    
    flange_pos = line.StaticResult(varNames="X", objectExtra=orca.oeEndB)

    tdp_to_flange = touch_down_point - flange_pos
    
    return round(hump_length - tdp_to_flange, decimal)


def verify_hump_height(
        line: orca.OrcaFlexLineObject,
        ling1: orca.OrcaFlexObject,
        ling2: orca.OrcaFlexObject,
    ) -> float:
    '''
    Description:
        Verify 'hump' height to manage A/R paying/retrieving action
    Parameters:
        line - line in the model
        ling1 - link1 in model
        ling2 - link2 in model
    Return
        High line point
    '''
    z_position = line.RangeGraph(
        varName='Z',
        arclengthRange=orca.arSpecifiedArclengths(
            FromArclength=line.NodeArclengths[-1]-ling2.EndBZ,  
            ToArclength=line.NodeArclengths[-1]-ling1.EndBZ)
        ).Mean
    
    return round(max(z_position) + LDA, decimal)


def payout_retrieve_function(
        case: str,
        aux_var: AuxiliarVariables,
        line: orca.OrcaFlexLineObject,
        a_r: orca.OrcaFlexObject,
        delta: float,
    ) -> None:
    """
    Description:
        Controls the way how line is payed or retrieved
    Parameters:
        case - wich case is running
        aux_var - class that saves analysis data individually in the multiprocessing
        line: Flexible pipe
        a_r: A/R cable
        delta: payout or retrieve quantity of line or A/R
    Return
        None
    """
    # case when line's length > LDA
    if not line_length and aux_var.dvc_type == 1:

        if delta > 0:
            print(f"\n{case} - Paying out {delta}m of line,\n\
                  from {round(line.CumulativeLength[-1], decimal)}m \n\
                    to {round(line.CumulativeLength[-1] + delta, decimal)}m")
        else:
            print(f"\n{case} - Retrieving out {-delta}m of line,\n\
                  from {round(line.CumulativeLength[-1], decimal)}m \n\
                    to {round(line.CumulativeLength[-1] + delta, decimal)}m")
        
        new_length = line.Length[0] + delta     # for discretization correction
        new_segment = new_length / 100

        line.Length[0] = round(new_length, decimal)     # new line's length
        # new line's discretization
        line.TargetSegmentLength[0] = round(new_segment, decimal)       
    
    else:       # case when line's length < LDA

        new_length = a_r.StageValue[0]  + delta

        if delta > 0:
            print(f"\n{case} - Paying out {delta}m of A/R cable,\n\
                  from {round(a_r.StageValue[0], decimal)}m \n\
                    to {round(new_length, decimal)}m")
        else:
            print(f"\n{case} - Retrieving out {-delta}m of A/R cable,\n\
                  from {round(a_r.StageValue[0], decimal)}m \n\
                    to {round(new_length, decimal)}m")

        a_r.StageValue[0] = round(new_length, decimal)      # new A/R length


def make_pointer(
        aux_var: AuxiliarVariables,
        n: int,
        positions: list,
        near_pos: list,
        far_pos: list
    ) -> int:
    """
    Description:
        Creates a pointer for buoy_set's position, when it's being prioritized to 
        change some position in a set of buoys
        If we need to add (+) buoyancy...
            See how many buoys we have in the position that gonna be changed
                Then, choose to change buoyancy in nearest to VCM position,
                moving it away from VCM
                (without infringe minimum distance between positions)
        If we need to reduce (-) buoyancy...
            See how many buoys we have in the position that gonna be changed
                Then, choose to change buoyancy in far from VCM position,
                moving it near to the VCM
                (without infringe minimum distance between positions)
    Parameters:
        aux_var - class that saves analysis data individually in the multiprocessing
        n - Number of positions with buoys
        positions - actual positions in line, where we have buoys
        near_pos - Positions closer to VCM
        far_pos - Positions far from VCM
    Return:
        Selected index-position for change buoyancy
    """
    if aux_var.rotation > 0 or\
        (aux_var.dvc_type == 2 and\
        ((aux_var.hump_height > VCM_A + max_height) or\
            (aux_var.dvc_type == 2 and aux_var.over_length > max_over_length))):
        
        pointer = 0
        if n == 2:      # there are 2 positions with buoys
            # verify if limits position were matched already
            if positions[pointer] <= near_pos[pointer]:
                pointer = 1     # if yes, choose the most distant from VCM
        if n == 3:      # there are 3 positions with buoys
            if positions[pointer] <= near_pos[pointer]:
                pointer = 1
                if positions[pointer] <= near_pos[pointer]:
                    pointer = 2
    
    elif aux_var.rotation < 0 or\
        (aux_var.dvc_type == 2 and\
        (aux_var.hump_height < VCM_A + min_height) or\
            aux_var.over_length < min_over_length):
        
        pointer = n - 1
        if n == 2:      # there are 2 positions with buoys
            # verify if limits position were matched already
            if positions[pointer] >= far_pos[pointer]:
                pointer = 0     # if yes, choose the closer of VCM
        elif n == 3:        # there are 3 positions with buoys
            if positions[pointer] >= far_pos[pointer]:
                pointer = 1
                if positions[pointer] >= far_pos[pointer]:
                    pointer = 0

    return pointer


def change_buoy_position(
        aux_var: AuxiliarVariables,
        line: orca.OrcaFlexLineObject,
        link1: orca.OrcaFlexObject,
        new_positions: list,
        i: int,
        n: int,
        actual_positions: list,
    ) -> None:
    """
    Description:
        Changes position of buoys in pointer position
    Parameters:
        aux_var - class that saves analysis data individually in the multiprocessing
        line - line in model
        link1 - link1 in the model
        new_positions - the new positions for buoy's set
        i - index of the new position where buoy gonna be placed
        n - number of buoys in model
        actual_positions - actual buoy's set's position in model
    """
    p = 1
    temp = []       # auxiliary list for print position changing

    for z in range(0, n):
        # keep any buoy set, at least, 5m far away from links (in 2nd end DVC)
        if (aux_var.dvc_type == 2 \
            and actual_positions[z] + buoy_position_change < link1.EndBZ - 5)\
                or aux_var.dvc_type == 1:
            # Condition that satisfies at least 3m of distance between buoys
            if actual_positions[z] + buoy_position_change == new_positions[i] \
                or actual_positions[z] - buoy_position_change == new_positions[i]:
                # Avoid reppeated positions (because there's more than 1 buoy in the 
                # same postion)
                if new_positions[i] not in temp:

                    temp.append(new_positions[i])
                    print(f"\nChanging buoys positioned at {line.Attachmentz[p]}m\n\
                        Positioning them at {new_positions[i]}m")
                    
                line.Attachmentz[p] = new_positions[i]
            p += 1


def changing_buoyancy(
        aux_var: AuxiliarVariables,
        position: list,
        reference: list,
        ) -> list:
    
    """
    Description:
        Controlls how buoyancy reference changes
        1st - Check if we need to add / reduce buoyancy
        2st - See how many buoys, in a position, we have to add / reduce buoyancy
        3st - Consideer add / reduce 50kg in submerged mass in the 'pointed' position
        Obs.:   Try to make it in a way that respect the 1st and 2st buoyancy factors
                Each buoyancy factor consideer the reason buoyancy in the pointer 
                position and its next or previous
                When we want to add buoyancy: buoyancy_increase_factor - Reason 
                between one buoy and its next
                When we want to reduce buoyancy: buoyancy_reduce_factor - Reason 
                between one buoy and its previous
    Parameters:
        aux_var - class that saves analysis data individually in the multiprocessing
        position - Positions where we have buoys installed
        reference - RL_configuration suggestion
    """
    total_buoyancy = reference[1]
    
    # we gonna add buoyancy, focusing in positions farther from the VCM
    if aux_var.rotation > 0:        
        if len(total_buoyancy) == 1:        # we have 1 buoy's position
            # if we add buoyancy, we still having less tha 2Tf
            if (total := total_buoyancy[0] + buoyancy_variation) < buoyancy_limit:
                print(f"\nIncreasing buoyancy reference: \n\
                      {total_buoyancy[0]}kg, in +{buoyancy_variation}kg")
                total_buoyancy[0] = total
            else:
                return 'fail'       # we reached buoyancy limit
        
        elif len(total_buoyancy) == 2:      # we have 2 buoy's position
            if total_buoyancy[0] >= buoyancy_increase_factor * total_buoyancy[1]:
                # if we add buoyancy, we still having less tha 2Tf
                if (total := total_buoyancy[1] + buoyancy_variation) < buoyancy_limit:
                    print(f"\nIncreasing 2st buoyancy reference: \n\
                          {total_buoyancy[1]}kg, in +{buoyancy_variation}kg")
                    total_buoyancy[1] = total
                else:
                    return 'fail'       # we reached buoyancy limit
            else:
                # if we add buoyancy, we still having less tha 2Tf
                if (total := total_buoyancy[0] + buoyancy_variation) < buoyancy_limit:
                    print(f"\nIncreasing 1st buoyancy reference: \n\
                          {total_buoyancy[0]}kg, in +{buoyancy_variation}kg")
                    total_buoyancy[0] = total
                else:
                    return 'fail'       # we reached buoyancy limit
        
        elif len(total_buoyancy) == 3:      # we have 3 buoy's positon
            # Buoyancy in 1st position is, at least, 50% higher than buoyancy in 2st 
            # position
            if total_buoyancy[0] >= buoyancy_increase_factor * total_buoyancy[1]:
                # Buoyancy in 2st position is, at least, 50% higher than buoyancy 
                # in 3st #position
                if total_buoyancy[1] >= buoyancy_increase_factor * total_buoyancy[2]:
                    # if we add buoyancy, we still having less tha 2Tf
                    if (total := total_buoyancy[2] + buoyancy_variation) < \
                    buoyancy_limit:
                        print(f"\nIncreasing 3st buoyancy reference: \n\
                              {total_buoyancy[2]}kg, in +{buoyancy_variation}kg")
                        total_buoyancy[2] = total
                    else:
                        return 'fail'       # we reached buoyancy limit
                else:
                    # if we add buoyancy, we still having less tha 2Tf
                    if (total := total_buoyancy[1] + buoyancy_variation) < \
                    buoyancy_limit:
                        print(f"\nIncreasing 2st buoyancy reference: \n\
                              {total_buoyancy[1]}kg, in +{buoyancy_variation}kg")
                        total_buoyancy[1] = total
                    else:
                        return 'fail'       # we reached buoyancy limit
            else:
                # if we add buoyancy, we still having less tha 2Tf
                if (total := total_buoyancy[0] + buoyancy_variation) < \
                buoyancy_limit:
                    print(f"\nIncreasing 1st buoyancy reference: \n\
                          {total_buoyancy[0]}kg, in +{buoyancy_variation}kg")
                    total_buoyancy[0] = total
                else:
                    return 'fail'       # we reached buoyancy limit
    
    # we gonna reduce buoyancy, focusing in positions closer to VCM
    elif aux_var.rotation < 0:

        if len(total_buoyancy) == 1:        # we have 1 buoy's position
            if (total := total_buoyancy[0] - buoyancy_variation) > 0:  # can't be 0
                print(f"\nReducing buoyancy reference: \n\
                      {total_buoyancy[0]}kg, in {-buoyancy_variation}kg")
                total_buoyancy[0] = total
            else:
                return 'fail'       # we reached 0
        
        elif len(total_buoyancy) == 2:      # we have 2 buoy's position
            # Buoyancy in 1st position is, at least, 100% higher than buoyancy in 2st 
            # position
            if total_buoyancy[0] >= buoyancy_reduce_factor * total_buoyancy[1]:
                if (total := total_buoyancy[0] - buoyancy_variation) > 0:
                    # can't be 0
                    print(f"\nReducing 1st buoyancy reference: \n\
                          {total_buoyancy[0]}kg, in {-buoyancy_variation}kg")
                    total_buoyancy[0] = total
                else:
                    return 'fail'       # we reached 0
            else:
                if (total := total_buoyancy[1] - buoyancy_variation) > 0:
                    # can't be 0
                    print(f"\nReducing 2st buoyancy reference: \n\
                          {total_buoyancy[1]}kg, in {-buoyancy_variation}kg")
                    total_buoyancy[1] = total
                else:
                    return 'fail'       # we reached 0
        
        elif len(total_buoyancy) == 3:      # we have 3 buoy's position
            # Buoyancy in 2st position is, at least, 100% higher than buoyancy in 
            # 3st position
            if total_buoyancy[1] >= buoyancy_reduce_factor * total_buoyancy[2]:
                # Buoyancy in 1st position is, at least, 100% higher than buoyancy in 
                # 2st position
                if total_buoyancy[0] >= buoyancy_reduce_factor * total_buoyancy[1]:
                    if (total := total_buoyancy[0] - buoyancy_variation) > 0: 
                        # can't be 0
                        print(f"\nReducing 1st buoyancy reference: \n\
                              {total_buoyancy[0]}kg, in {-buoyancy_variation}kg")
                        total_buoyancy[0] = total
                    else:
                        return 'fail'       # we reached 0
                else:
                    if (total := total_buoyancy[1] - buoyancy_variation) > 0: 
                        # can't be 0
                        print(f"\nReducing 2st buoyancy reference: \n\
                              {total_buoyancy[1]}kg, in {-buoyancy_variation}kg")
                        total_buoyancy[1] = total
                    else:
                        return 'fail'       # we reached 0
            else:
                if (total := total_buoyancy[2] - buoyancy_variation) > 0:    
                    # can't be 0
                    print(f"\nReducing 3st buoyancy reference: \n\
                          {total_buoyancy[2]}kg, in {-buoyancy_variation}kg")
                    total_buoyancy[2] = total
                else:
                    return 'fail'       # we reached 0
    
    return [position, total_buoyancy]


def changing_buoys(
        aux_var: AuxiliarVariables,
        selection: dict,
        new_rl_config: list,
        line: orca.OrcaFlexLineObject,
    ) -> dict:
    """
    Description:
        Resume the work of changing buoys in model
    Parameters:
        aux_var - class that saves analysis data individually in the multiprocessing
        selection: Old reference for changing buoys
        new_rl_config: New reference for configuration
        line: Flexible pipe
    Return
        New selection (reference) based on new_rl_config
    """
    # gonna verify if the buoyancy reference's changing was enough 
    # (if made selection changes)
    old_selection = selection

    # make a new selection
    selection = select_buoy_combination(new_rl_config)

    if old_selection == selection:  # selection didn't change
        aux_var.run_counter -= 1      # do not count this iteration    
    else: 
        print(f"\nChanging selection of buoys")
        print(f"\nOld selection: {list(old_selection.keys())} = \n\
              Total buoyancy: {list(old_selection.values())}")
        print(f"\nNew selection: {list(selection.keys())} = \n\
              Total buoyancy: {list(selection.values())}")

        treated_buoys = buoys_treatment(new_rl_config, selection)
        num_buoys = number_of_buoys(treated_buoys)
        # changing buoys in the model
        putting_buoys_in_model(line, num_buoys, treated_buoys)

    return selection


def buoys_treatment(
        rl_config: list, 
        selected_buoys: dict,
        ) -> dict:
    """
    Description:
        Get the Dict result (selection) from 'buoyancy' and transforms it in 
        Orcaflex attachments
    Parameters:
        rl_config: configuration suggested 
        selected_buoys: selected buoys, in format: {'b1+b2': b1+b2, ...}
    Return:
        Orcaflex attachments equivalents to selection
    """
    # strip() is necessary for cases when keys are reppeated in dict
    keys = [[f"{INIT}_{subkey.strip()}"       
             for subkey in key.split("+")]      #  1st position         2st position
             for key in selected_buoys.keys()]  #  [[SKA_100, SKA_500], [SKA_300]]

    return {
        rl_config[0][i]: keys[i]
        for i in range(len(keys))       # merges rl_config and selection
    }


def number_of_buoys(
        buoys_attachment: dict
        ) -> int:
    """
    Description:
        Get the number of attachments in the Dict result (treated_buoys) from 
        'buoyancy_treatment'
    Parameters:
        buoys_attachment: buoys that goes to model
    Return:
        Number of attachments
    """
    return len([buoy[i] 
                for buoy in buoys_attachment.values()
                for i in range(len(buoy))])


def putting_buoys_in_model(
        element: orca.OrcaFlexObject,
        n_buoys: int,
        attachments: dict,
        ):
    """
    Description:
        Insert the attachments from the Dict result (treated_buoys) from 
        'buoyancy_treatment' in the model.
    Parameters:
        element: line in model
        n_buoys: number of attachments that will be putted in line
        attachments: attachment to insert in model
    """
    # removing buoys installed
    idx = 0
    while idx < element.NumberOfAttachments:
        if INIT in element.AttachmentType[idx]:
            element.AttachmentType[idx]=element.AttachmentType[-1]
            element.Attachmentz[idx]=element.Attachmentz[-1]
            element.AttachmentzRelativeTo[idx]=element.AttachmentzRelativeTo[-1]
            if element.AttachmentName[-1]:
                element.AttachmentName[idx]=element.AttachmentName[-1]
            element.NumberOfAttachments -= 1
            idx-=1
        idx+=1

    # anodes count
    anodes_count = weights[0]['Quantity']\
        if (weights[0]['Name'] in element.AttachmentType \
            and weights[0]['Name']) else 0
    # dead weights count
    dead_weights_count = weights[1]['Quantity'] \
        if (weights[1]['Name'] in element.AttachmentType \
            and weights[1]['Name']) else 0
    # vert count
    vert_count = 1 if 'Vert' in element.AttachmentType else 0
    
    n_ini_att = anodes_count + dead_weights_count + vert_count

    element.NumberOfAttachments = int(n_buoys + n_ini_att)
    # (position1, position2)
    att_buoy_key = tuple(attachments.keys())
    # ([buoys in position1], [buoys in position2])
    att_buoy_val = tuple(attachments.values())

    k = n_ini_att
    while k < element.NumberOfAttachments:
        for i in range(len(att_buoy_val)):
            for j in range(len(att_buoy_val[i])):
                element.AttachmentType[k] = att_buoy_val[i][j]
                # insert attachments
                element.Attachmentz[k] = att_buoy_key[i]
                # insert attachment's position
                element.AttachmentzRelativeTo[k] = "End B"
                k += 1


def call_changing_buoys(
        aux_var: AuxiliarVariables,
        line: orca.OrcaFlexLineObject,
        positions: list,
        buoy_model: list,
        rl_config: dict,
        selection: dict,
        near_pos: list, 
        far_pos: list
    ) -> dict | list | None:
    """
    Description:
        Controls how buoy's set changes...
        Obs.: Remember each tentative (configuration) is saved in LOOPING_RESULTS
        1st - Check if actual buoy_set is equal last tentative 
        (buoy_model == LOOPING_RESULTS[-1])
            If yes... That means it's equal some last tentative, what occurs as a 
            consequence of the possible reppeated combination of buoys
            2st - So, just try changing buoyancy reference 
            (new_rl_config = changing_buoyancy(positions, rl_config))
                If it works... we have new_buoys
                If not (buoyancy > 2Tf), them...
            If not (buoyancy > 2Tf), them...
                3st - Check what to do consideering the two next options:
                    3.1 - Try configurations with 3 buoys in each position
                    (default: N_BUOYS = 2)
                    3.2 - Try configurations with 3 positions for buoys 
                    (default: N_BUOYS = 2)
    Parameters:
        aux_var - class that saves analysis data individually in the multiprocessing
        line: Flexible pipe
        positions: Positions where buoys are in the model
        buoy_set: Actual set of buoys in model
        buoy_model: Actual configuration in model
        rl_config: Actual (old) reference for buoy's configuration
        selection: Actual (old) selection of buoys
        near_pos - Buoy's position near to the vcm
        far_pos - Buoy's position for from the vcm
    Return:
        New selection of buoys and its limits of range position
    """
    global n_buoy_pos

    if buoy_model == aux_var.looping_buoy_results[-1]:       # 1st

        new_rl_config = changing_buoyancy(aux_var, positions, rl_config)     # 2st

        if type(new_rl_config) == list:     # changing_buoyancy worked

            selection = changing_buoys(aux_var, selection, new_rl_config, line)
        
        if type(new_rl_config) == str:      # changin_buoyancy didn't worked

            if len(selection) < 3:

                if n_buoy_pos < 3:
                    
                    n_buoy_pos += 1        # try config. with 3 buoys / position

                    selection = changing_buoys(aux_var, selection, rl_config, line)
                
                elif n_buoy_pos == 3:
                    
                    n_buoy_pos -= 1        # try config. with 2 buoys / position
                    if aux_var.rotation > 0:
                        # adding one position of buoys
                        new_pos = rl_config[0][-1] + 3
                        near_pos.append(new_pos)
                        far_pos.append(new_pos+3)
                        rl_config[0].append(new_pos)
                        rl_config[1].append(100)
                    elif len(selection) == 1:
                        aux_var.run_counter = n_run_limit + 1   # no buoys
                        # failed to find a solution
                        return None, near_pos, far_pos
                    else:
                        # reducing one position of buoys
                        del near_pos[-1]
                        del far_pos[-1]
                        rl_config[0].remove(rl_config[0][-1])
                        rl_config[1].remove(rl_config[1][-1])

                    selection = changing_buoys(aux_var, selection, rl_config, line)
            
            if len(selection) == 3:

                if n_buoy_pos < 3:

                    n_buoy_pos += 1        # try config. with 3 buoys / position

                    selection = changing_buoys(aux_var, selection, rl_config, line)
                
                elif n_buoy_pos == 3:

                    aux_var.run_counter = n_run_limit + 1     
                    # failed to find a solution
                    return None, near_pos, far_pos
    
    # 3st (changing_buoyancy failed)
    elif buoy_model != aux_var.looping_buoy_results[-1]:

        if len(selection) < 3:

            if n_buoy_pos < 3:
                
                n_buoy_pos += 1        # try config. with 3 buoys / position

                selection = changing_buoys(aux_var, selection, rl_config, line)
            
            elif n_buoy_pos == 3:
                    
                n_buoy_pos -= 1        # try config. with 2 buoys / position
                if aux_var.rotation > 0:
                    # adding one position of buoys
                    new_pos = rl_config[0][-1] + 3
                    near_pos.append(new_pos)
                    far_pos.append(new_pos+3)
                    rl_config[0].append(new_pos)
                    rl_config[1].append(100)
                elif len(selection) == 1:
                    aux_var.run_counter = n_run_limit + 1   # no buoys
                    # failed to find a solution
                    return None, near_pos, far_pos
                else:
                    # reducing one position of buoys
                    del near_pos[-1]
                    del far_pos[-1]
                    rl_config[0].remove(rl_config[0][-1])
                    rl_config[1].remove(rl_config[1][-1])

                selection = changing_buoys(aux_var, selection, rl_config, line)
        
        if len(selection) == 3:

            if n_buoy_pos < 3:

                n_buoy_pos += 1        # try config. with 3 buoys / position

                selection = changing_buoys(aux_var, selection, rl_config, line,)
            
            elif n_buoy_pos == 3:

                aux_var.run_counter = n_run_limit + 1     # failed to find a solution
                return None, near_pos, far_pos
    
    return selection, near_pos, far_pos


def dyn_loads(
        line: orca.OrcaFlexLineObject, 
        general: orca.OrcaFlexObject
    ) -> dict | bool:
    """
    Description:
        Validates dynamic combinations of loads
        for heave up time and Touch down time
    Parameters:
        line - line in the model
        general - general in model
    Return:
        True if combination of loads passed, False if not
        Combination of loads
    """
    
    period = orca.SpecifiedPeriod(FromTime=general.StageStartTime[0], ToTime=70)

    varname = "End Ey Moment", "End Ez force", "End Ex force"

    stats = line.LinkedStatistics(varNames=varname, period=period, objectExtra=orca.oeEndB)

    bm_sf, bm_af = stats.Query("End Ey moment", "End Ex force"), stats.Query("End Ey moment", "End Ez force")
    sf_af, sf_bm = stats.Query("End Ex force", "End Ez force"), stats.Query("End Ex force", "End Ey moment")
    af_sf, af_bm = stats.Query("End Ez force", "End Ex force"), stats.Query("End Ez force", "End Ey moment")

    combinations = {
        "BMmax": [round(bm_af.LinkedValueAtMax, decimal), 
                    -round(bm_sf.LinkedValueAtMax, decimal), 
                    -round(bm_af.ValueAtMax, decimal)],
        "BMmin": [round(bm_af.LinkedValueAtMin, decimal), 
                    -round(bm_sf.LinkedValueAtMin, decimal), 
                    -round(bm_af.ValueAtMin, decimal)],
        "SFmax": [round(sf_af.LinkedValueAtMax, decimal), 
                    -round(sf_af.ValueAtMax, decimal), 
                    -round(sf_bm.LinkedValueAtMax, decimal)],
        "SFmin": [round(sf_af.LinkedValueAtMin, decimal), 
                    -round(sf_af.ValueAtMin, decimal), 
                   -round(sf_bm.LinkedValueAtMin, decimal)],
        "AFmax": [round(af_sf.ValueAtMax, decimal), 
                    -round(af_sf.LinkedValueAtMax, decimal), 
                    -round(af_bm.LinkedValueAtMax, decimal)],
        "AFmin": [round(af_sf.ValueAtMin, decimal), 
                    -round(af_sf.LinkedValueAtMin, decimal), 
                    -round(af_bm.LinkedValueAtMin, decimal)]
    }

    check = defaultdict()
    as_tqf_list = []
    for key in combinations.keys():
        case = []
        for limit in list(structural_limits.values()):
            result, as_tqf = checking_loads(np.array(combinations[key]),
                                            np.round(limit, decimal))
            case.append(result)
            as_tqf_list.append(as_tqf)

        check[key] = any(case)
    
    check_loads = all(list(check.values()))
    as_tqf = any(as_tqf_list)

    return check_loads, combinations, as_tqf


def checking_loads(
        loads: np.array,
        limits: np.array
    ) -> bool:
    '''
    Description:

    Parameters:
        loads - Load case combination
        limits - Limit case combination
    Return:
        True | True -> Need to call a TQF
        True | False -> Loads aprooved
        False | False -> Loads reprooved
    '''
    check = []
    as_tqf = False
    for g in range(len(loads)):
        if loads[g] > 0 and limits[g] > 0:
            result = loads[g] < limits[g]
        elif (loads[g] < 0 and limits[g] > 0) or\
            (loads[g] > 0 and limits[g] < 0):
            if abs(loads[g]) < abs(limits[g]):
                as_tqf = True
                result = True
            else:
                result = False
        elif loads[g] < 0 and limits[g] < 0:
            result = loads[g] > limits[g]
        
        check.append(result)
        if not result:
            break

    return all(check), as_tqf


def changing_link_position(
        aux_var: AuxiliarVariables,
        path: str,
        case: str,
        model: orca.Model,
        vcm: orca.OrcaFlexObject,
        line: orca.OrcaFlexLineObject,
        bend_restrictor: orca.OrcaFlexObject,
        link1: orca.OrcaFlexObject,
        link2: orca.OrcaFlexObject,
        general: orca.OrcaFlexObject,
        env: orca.oeEnvironment,
        final: bool
    ) -> None:
    """
    Description:
        Changing links positions
    Parameters:
        aux_var - class that saves analysis data individually in the multiprocessing
        link1 - link1 in model
        link2 - link2 in model 
    """

    actual_state = [
        link1.EndBZ,
        link2.EndBZ
        ]

    link_idx = links_positions.index(actual_state)

    if aux_var.over_length < min_over_length:
        check_idx = -1
        select_idx = link_idx+1

    elif aux_var.over_length > max_over_length:
        check_idx = 0
        select_idx = link_idx-1

    if actual_state == links_positions[check_idx]:
        aux_var.run_counter = n_run_limit + 1
    else:

        print(f"Changing links positions\n\
                from [{str(int(actual_state[0]))},{str(int(actual_state[1]))}]\n\
                to [{str(links_positions[select_idx][0])},{str(links_positions[select_idx][1])}]")

        while link1.EndBZ != links_positions[select_idx][0]:
            if select_idx > link_idx:
                link1.EndBZ += 1
                link2.EndBZ += 1
            elif select_idx < link_idx:
                link1.EndBZ -= 1
                link2.EndBZ -= 1
    
            static_run_calculation(aux_var, path, case, model, vcm, line,
                               bend_restrictor, link1, link2, general, env, final)


@license_handler
def looping(
        aux_var: AuxiliarVariables,
        path: str,
        case: str,
        near_pos: list,
        far_pos: list,
        model: orca.Model,
        vcm: orca.OrcaFlex6DBuoyObject,
        line: orca.OrcaFlexLineObject,
        bend_restrictor: orca.OrcaFlexObject,
        link1: orca.OrcaFlexObject,
        link2: orca.OrcaFlexObject,
        general: orca.OrcaFlexObject,
        env: orca.oeEnvironment,
        a_r: orca.OrcaFlexObject,
        winch: orca.OrcaFlexObject,
        buoy_config: list,
        selection: dict,
        final: bool
        ):
    """
    Description:
        Loop function that iterates the model, making changes to find verticalization
        solutions. The changes are described below:
        1 - Changing in line's or A/R's length, based on line clearance criteria
        2 - Changing links positions, based on line clearance criteria
        3 - Changing the position of buoy's sets, based on VCM's iclination criteria
        4 - Changing the buoy's sets, based on VCM's inclination criteria
        5 - Changing winch length, based on Flange VCM's height 
    Parameters:
        aux_var - class that saves analysis data individually in the multiprocessing
        path - temp path for the analysis
        case - wich case is running
        near_pos - Buoy's position near to the vcm
        far_pos - Buoy's position far from the vcm
        model - Orcaflex model
        vcm - VCM in the model
        line - line in model
        bend_restrictor - vert in model
        link1 - link1 in model
        link2 - link2 in model
        general - general in model
        env - environment in model
        a_r - A&R in model
        winch - winch in model
        buoy_config - buoy configuration
        selection - 
        final -  
    """
    if aux_var.run_counter >= n_run_limit:
        print(f"\n{case} - Failed")
        return
    
    static_run_calculation(aux_var, path, case, model, vcm, line, bend_restrictor,
                           link1, link2, general, env, final)
    
    env.SeabedOriginX = vcm.InitialX

    # Criteria - Clearance between line and soil controlled between [.52; .65]m
    if aux_var.clearance < min_dist or aux_var.clearance > max_dist:
        # line's touching seabed or too close
        if aux_var.clearance < min_dist/2:
            delta = -payout_retrieve
        # clearance almost 50cm
        elif aux_var.clearance < min_dist:
            delta = -payout_retrieve/5
        # line's a little bit far from soil
        elif aux_var.clearance > max_dist:
            if aux_var.dvc_type == 2 and aux_var.over_length < min_over_length:
                changing_link_position(aux_var, path, case, model, vcm, line, 
                                       bend_restrictor, link1, link2, general,
                                       env, final)
                delta = -payout_retrieve
            elif aux_var.dvc_type == 2:
                delta = payout_retrieve
            else:
                delta = aux_var.clearance

        payout_retrieve_function(case, aux_var, line, a_r, delta)
        
        aux_var.run_counter -= 1       # Doesn't count this iterations
    
    # Criteria - VCM rotation controlled between [-.5; .5]°
    elif aux_var.rotation > max_rotation or aux_var.rotation < min_rotation:
    
        number = line.NumberOfAttachments

        position = []

        idx = 0 if 'Vert' not in line.AttachmentType else 1
        for k in range(idx, number):
            if INIT in line.AttachmentType[k]:
                position.append(line.Attachmentz[k])

        buoys = list(selection.values())
        # get actual buoys and buoy's position in the model
        buoy_model = [position, buoys]
        
        n_positions = len(buoy_model[0])

        # save tentatives already used
        if buoy_model not in aux_var.looping_buoy_results:
            aux_var.looping_buoy_results.append(buoy_model)

        # buoy's position without reppeated values
        unique_positions = list(Counter(position).keys())

        pointer = make_pointer(aux_var, len(unique_positions), unique_positions, \
                               near_pos, far_pos)     # defines index for changing

        if aux_var.rotation > max_rotation:     # VCM inclined in line's direction

            # condition for change buoys position
            if unique_positions[pointer] > far_pos[pointer]:

                # new_positions are far from VCM
                new_positions = [buoy_position - buoy_position_change 
                                 for buoy_position in unique_positions]
                
                change_buoy_position(aux_var, line, link1, new_positions, \
                                     pointer, n_positions, position)
                aux_var.run_counter -= 1       # Doesn't count this iterations
            
            else:       # Condition for change the buoy's set

                selection, near_pos, far_pos = call_changing_buoys(
                    aux_var, line, unique_positions, buoy_model, 
                    buoy_config, selection, near_pos, far_pos)
                if selection == None:
                    return

        # VCM inclined away of line's direction
        elif (aux_var.rotation < min_rotation) or\
            (aux_var.dvc_type == 2 and \
            (aux_var.hump_height < VCM_A + min_height or\
                aux_var.over_length < min_over_length)):

            # condition for change buoys position
            if unique_positions[pointer] < near_pos[pointer]:

                # new_positions are near from VCM
                new_positions = [buoy_position + buoy_position_change 
                                 for buoy_position in unique_positions]

                change_buoy_position(aux_var, line, link1, new_positions, \
                                     pointer, n_positions, position)
                aux_var.run_counter -= 1      # Doesn't count this iterations
            
            else:       # Condition for change the buoy's set
                
                selection, near_pos, far_pos = call_changing_buoys(
                    aux_var, line, unique_positions, buoy_model, 
                    buoy_config, selection, near_pos, far_pos)
                if selection == None:
                    return
    
    elif (aux_var.dvc_type == 2 and (aux_var.over_length < min_over_length or\
                                     aux_var.over_length > max_over_length)):
        changing_link_position(aux_var, path, case, model, vcm, line, 
                               bend_restrictor, link1, link2, general, env,
                               final)
    
    # Criteria - Perfect adjustment of flange's height
    elif aux_var.delta_flange != round(0, decimal):

        # This case, sometimes, demands retry some buoy_config tentatives
        if aux_var.delta_flange > .1:
            aux_var.looping_buoy_results.clear()

        old_length = round(winch.StageValue[0], decimal)
        new_length = round(winch.StageValue[0] + aux_var.delta_flange, decimal)
        if aux_var.delta_flange > 0:
            print(f"\n\
                  {case} - Paying out {aux_var.delta_flange}m from the winch,\
                  \nfrom {old_length} to {new_length}.")
        else:
            print(f"\n\
                  {case} - Retrieving {aux_var.delta_flange}m from the winch,\
                  \nfrom {old_length} to {new_length}.")
        
        # adjust flange's height
        winch.StageValue[0] = \
            round(winch.StageValue[0] - aux_var.delta_flange, decimal)

        # convergence is kinda difficult in this part
        general.StaticsMaxDamping = max_damping_range
        general.StaticsMinDamping = min_damping_range
        general.StaticsMaxIterations = n_iterations
    
    else:
        aux_var.check_true()
        static_run_calculation(aux_var, path, case, model, vcm, line, bend_restrictor,
                               link1, link2, general, env, True)
        
        return
    
    looping(aux_var, path, case, near_pos, far_pos, model, vcm, line, bend_restrictor,
            link1, link2, general, env, a_r, winch, buoy_config, selection, final)


@license_handler
def run_automation(
        path: str
    ) -> None:
    """
    Description:
        Function that calls the automation process for each single case of 
        buoy config suggestion.
    Parameters:
        path - temp path of the analysis case
    Return:
        None
    """

    start_time = time.time()

    aux_var = AuxiliarVariables()

    # creating status
    case = os.path.basename(path).upper()

    # orcaflex file path
    orca_path = os.path.join(path, "Estatico.dat")
    # json with buoy configuration
    json_path = glob.glob(os.path.join(path, "*.json"))[0]
    with open(json_path, 'r', encoding='utf-8') as f:
        buoy_config = json.load(f)

    # model, filename
    model, _ = load_model(file=orca_path, return_model_name=True)

    problem, message = verify_inputs(model)
    if not problem:
        raise ValueError(f"ERROR: {message}")
    
    print(f"{case} - Starting...")

    # DVC Objects
    cvd_objs = [obj for obj in model.objects if obj.type in cvd_obj_type]
    obj_names = [obj.name for obj in cvd_objs]
    
    # Line object
    line = model['Line']
    
    # DVC type - 1 for 1st end DVC and 2 for 2nd end DVC
    aux_var.dvc_type = 1 if "Anchored" not in [line.EndAConnection, line.EndBConnection] \
    else 2
    
    # Bend restrictor object
    stiffener_name = next((item for item in line.AttachmentName if item in obj_names), 
                          None)
    if stiffener_name:
        bend_restrictor = model[stiffener_name]

    # VCM object
    vcm_name = next((item for item in [line.EndBConnection, line.EndAConnection] \
                     if item in obj_names), None)
    if vcm_name:
        vcm = model[vcm_name]

    # winches and A/R object
    winches = [obj for obj in cvd_objs if obj.type == orca.ObjectType.Winch.value]
    winch = next((item for item in winches if item.Connection[0] or \
                  item.Connection[1] in vcm_name), None)
    winch.Stiffness = 227*(MIN_BEND_STIFFNESS_RIGID)
    a_r = next((item for item in winches if winch.Name not in item.Name), None)
    
    # general and environment
    general = model['General']
    general.StaticsMaxIterations = 400
    env = model['Environment']
    
    # 3dbuoy
    buoy_3d = [obj for obj in cvd_objs if obj.type == orca.ObjectType.Buoy3D.value]
    link1 = link2 = None
    if buoy_3d:
        joint_name = next((item for item in buoy_3d if a_r.Connection[0] or \
                           a_r.Connection[1] in a_r.Name))

        # links
        links = [obj for obj in cvd_objs if obj.type == orca.ObjectType.Link.value]
        line_links = [item for item in links if \
                      (item.EndAConnection or item.EndBConnection) in joint_name.Name]
        
        if line_links and aux_var.dvc_type == 2:
            link1, link2 = sorted(line_links, key=lambda x: max(x.EndAz, x.EndBz))

    static_run_calculation(aux_var, path, case, model, vcm, line, bend_restrictor,
                           link1, link2, general, env, False)
    
    if aux_var.run_counter > n_run_limit:
        return

    # initial model adjustment
    if aux_var.dvc_type == 1 and line_length:
        print(f"\n{case} - Adjusting line and A/R length")
        jumper_condition(line, a_r, line_length)
        static_run_calculation(aux_var, path, case, model, vcm, line, bend_restrictor,
                               link1, link2, general, env, False)

    if isinstance(dredging_bathymetry['A'], (float, int)):
        print(f"\n{case} - Adjusting bathymetry to the dredging geometry")
        adjusting_bathymetry(dredging_bathymetry, env)
        static_run_calculation(aux_var, path, case, model, vcm, line, bend_restrictor,
                               link1, link2, general, env, False)

    # putting buoys in line
    k = 1
    n_increment = int(max(buoy_config[1])/250)
    while k <= n_increment:
        # each increment creates a partial buoyancy of rl_config
        buoy_config_partial = [
            buoy_config[0],
            [round(k * x / n_increment, 0) for x in buoy_config[1]]
        ]

        # choosing best buoy's combination
        selection = select_buoy_combination(buoy_config_partial)
        # treating it to fit with orcaflex attachments
        treated_selection = buoys_treatment(buoy_config_partial, selection)
        n_buoys = number_of_buoys(treated_selection)
        # inserting buoys in model
        putting_buoys_in_model(line, n_buoys, treated_selection)

        print(f"\n\
              {case} - Inserting {list(selection.values())}kg of buoyancy \n\
              in these posiitons: {buoy_config[0]}m from VCM")
        static_run_calculation(aux_var, path, case, model, vcm, line, bend_restrictor,
                               link1, link2, general, env, False)
        k += 1

    # inserting anodes / dead weights, if necessary
    insert_weigths(aux_var, path, case, model, vcm, line, bend_restrictor, link1, 
                   link2, general, env)
    
    # generating range for buoy's set position
    near_pos, far_pos = near_far_position(buoy_config[0])

    print(f"\n{case} - STARTING LOOPING ITERATION")
    looping(aux_var, path, case, near_pos, far_pos, model, vcm, line, bend_restrictor,
            link1, link2, general, env, a_r, winch, buoy_config, selection, False)

    if aux_var.aprooved:
        print(f"\n{case} - Succesful")
        destiny_path = os.path.join(AUTOMATION_PATH, f"{case}_Static.sim")
    else:
        print(f"\n{case} - Failed")
        failed_path = os.path.join(AUTOMATION_PATH, "failed")
        os.makedirs(failed_path, exist_ok=True)
        destiny_path = os.path.join(failed_path, f"{case}_Static.sim")

    simulation = max((glob.glob(os.path.join(path, "*.sim"))), 
                        key=os.path.getmtime)  # last simulation (verticalization)
    shutil.copy(simulation, destiny_path)
    
    end_time = round((time.time() - start_time)/60, decimal)
    print(f"\nAnalysis time: {end_time}min")

    if aux_var.aprooved:
        dynamic_run_calculation(destiny_path)


# ----------------------------------------------------------------------------------
# CODING ---------------------------------------------------------------------------
# ----------------------------------------------------------------------------------


# generating different buoy's set configurations
buoy_config = generate_buoyconfig(rl_config)


if test:
    os.makedirs(os.path.join(THIS_PATH, 'test'), exist_ok=True)
    ini_path = os.path.join(THIS_PATH, 'test')
else:
    temp_dir = mkdtemp()
    ini_path = os.path.realpath(temp_dir)

for i in range(len(buoy_config)):
    if test:
        case_path = os.path.join(ini_path, f"Case_{str(i)}")
    else:
        case_path = os.path.join(ini_path, f"Case_{str(i)}")
    os.makedirs(case_path, exist_ok=True)   # Case i dir
    analysis_path = os.path.join(case_path, os.path.basename(STATIC_FILE_PATH))
    shutil.copy(STATIC_FILE_PATH, analysis_path)        # copying static.dat
    config_path = os.path.join(case_path, f"Case_{str(i)}.json")
    with open(config_path, 'w', encoding='utf-8') as f: # saving buoy config json
        json.dump(buoy_config[i], f, ensure_ascii=False, indent=4)


# various analysis case's path
cases = [os.path.join(ini_path, d)
         for d in os.listdir(ini_path)
         if os.path.isdir(os.path.join(ini_path, d))]


if run_statics_and_dynamics:
    # for tests
    # run_automation(cases[0])
    
    run(
        function=run_automation,
        args=cases,
        n_workers=num_of_workers,
        thread=True
    )
    '''
    '''
    # shutil.rmtree(temp_dir)

if not run_statics_and_dynamics and run_only_dynamics:
    dyn_cases = glob.glob(os.path.join(AUTOMATION_PATH, "*Static.sim"))
    # for tests
    # dynamic_run_calculation(dyn_cases[6])
    
    run(
        function=dynamic_run_calculation,
        args=dyn_cases,
        n_workers=num_of_workers,
        thread=True
    )
    '''
    '''

# ------------------------------------------------------------------------------------
# POST PROCESSING --------------------------------------------------------------------
# ------------------------------------------------------------------------------------

static_files = glob.glob(os.path.join(AUTOMATION_PATH, "*.sim"))
final_files = static_files

failed_dir = os.path.join(AUTOMATION_PATH, "failed")
if os.path.isdir(failed_dir):
    static_files_failed = glob.glob(os.path.join(failed_dir, "*.sim"))
    final_files += static_files_failed

tqs_dir = os.path.join(AUTOMATION_PATH, "TQF")
if os.path.isdir(tqs_dir):
    tqs_files = glob.glob(os.path.join(tqs_dir, "*.sim"))
    final_files += tqs_files

static_results_list = []
dynamic_results_list = []

for file in final_files:

    model, _ = load_model(file=file, return_model_name=True)
    line = model['Line']
    dvc_type = 1 if "Anchored" not in [line.EndAConnection, 
                                       line.EndBConnection] else 2
    general = model['General']
    cvd_objs = [obj for obj in model.objects if obj.type in cvd_obj_type]
    obj_names = [obj.name for obj in cvd_objs]

    vcm_name = next((item for item in [line.EndBConnection, line.EndAConnection] \
                     if item in obj_names), None)
    vcm = model[vcm_name] if vcm_name else None

    stiffener_name = next((item for item in line.AttachmentName \
                           if item in obj_names), None)
    bend_restrictor = model[stiffener_name] if stiffener_name else None

    # winches and A/R object
    winches = [obj for obj in cvd_objs if obj.type == orca.ObjectType.Winch.value]
    winch = next((item for item in winches if item.Connection[0] or \
                  item.Connection[1] in vcm_name), None)

    a_r = next((item for item in winches if winch.Name not in item.Name), None)

    # 3dbuoy
    buoy_3d = [obj for obj in cvd_objs if obj.type == orca.ObjectType.Buoy3D.value]
    link1 = link2 = None
    if buoy_3d:
        joint_name = next((item for item in buoy_3d if a_r.Connection[0] or \
                           a_r.Connection[1] in a_r.Name))

        # links
        links = [obj for obj in cvd_objs if obj.type == orca.ObjectType.Link.value]
        line_links = [item for item in links if \
                      (item.EndAConnection or item.EndBConnection) in joint_name.Name]
        
        if line_links and dvc_type == 2:
            link1, link2 = sorted(line_links, key=lambda x: max(x.EndAz, x.EndBz))

    if bend_restrictor:

        n_curve = model['Stiffener1'].RangeGraph('Normalised curvature').Max\
            if "Dynamic" in os.path.basename(file) else\
                model['Stiffener1'].RangeGraph('Normalised curvature').Mean

        if round(max(n_curve), decimal) < 1:
            bend_status = "Unlocked"
            shear = moment = 0
        else:
            bend_status = "Locked"
            if "Dynamic" in os.path.basename(file):
                shear_force = bend_restrictor.RangeGraph("Shear Force")
                shear_min, shear_max = min(shear_force.Min), max(shear_force.Max)
                bend_moment = bend_restrictor.RangeGraph("Bend moment")
                moment_min, moment_max = min(bend_moment.Min), max(bend_moment.Max)
            else:
                shear = bend_restrictor.RangeGraph("Shear Force").Mean
                shear_min, shear_max = min(shear), max(shear)
                moment = bend_restrictor.RangeGraph("Bend moment").Mean
                moment_min, moment_max = min(moment), max(moment)
        
            shear = round(max(abs(shear_min), abs(shear_max)), decimal)
            moment = round(max(abs(moment_min), abs(moment_max)), decimal)
    else:
        bend_status = shear = moment = "Nan"

    if "Dynamic" in os.path.basename(file):
        
        loads_checked, load_combinations, as_tqf = dyn_loads(line, general)

        br_check = True
        if bend_status == 'Locked':
            if BR_SF_LIMIT:
                sf_check = BR_SF_LIMIT > shear
                br_check = all([br_check, sf_check])
            if BR_BM_LIMIT:
                bm_check = BR_BM_LIMIT > moment
                br_check = all([br_check, bm_check])

        aprooved = all([br_check, loads_checked])
        
        dynamic_results_list.append({
            "File": os.path.basename(file).split(".sim")[0],
            "Loads (BMmax)": ", ".join(
                [str(load_combinations["BMmax"][b])
                 for b in range(len(load_combinations["BMmax"]))]),
            "Loads (BMmin)": ", ".join(
                [str(load_combinations["BMmin"][b])
                 for b in range(len(load_combinations["BMmin"]))]),
            "Loads (SFmax)": ", ".join(
                [str(load_combinations["SFmax"][b])
                 for b in range(len(load_combinations["SFmax"]))]),
            "Loads (SFmin)": ", ".join(
                [str(load_combinations["SFmin"][b])
                 for b in range(len(load_combinations["SFmin"]))]),
            "Loads (AFmax)": ", ".join(
                [str(load_combinations["AFmax"][b])
                 for b in range(len(load_combinations["AFmax"]))]),
            "Loads (AFmin)": ", ".join(
                [str(load_combinations["AFmin"][b])
                 for b in range(len(load_combinations["AFmin"]))]),
            "Bend Restrictor": bend_status,
            "Shear force (Vert)": shear,
            "Bend moment (Vert)": moment,
            "Aprooved": aprooved,
            "TQF": as_tqf
        })

        results_df = pd.DataFrame(dynamic_results_list)
        dyn_results = os.path.join(AUTOMATION_PATH, "Results_dynamics.json")
        results_df.to_json(dyn_results, orient='records', lines=True)

    else:
        static_results_list.append({
            "File": os.path.basename(file).split(".sim")[0],
            "Buoy set": ", ".join([line.AttachmentType[i] 
                                for i in range(line.NumberOfAttachments) \
                                if line.AttachmentType[i].startswith(INIT)]),
            "Buoy set's position": ", ".join(
                [str(line.Attachmentz[f]) for f in range(line.NumberOfAttachments) \
                 if line.AttachmentType[f].startswith(INIT)]),
            "VCM's Rotation XZ": round(vcm.StaticResult("Rotation 2"), decimal) \
                if vcm else "Nan",
            "Line's clearance to seabed": verify_clearance(dvc_type, line, None) \
                if dvc_type == 1 else verify_clearance(dvc_type, line, link1),
            "Axial force (VCM)": float(abs(round(line.StaticResult(
                varNames="End Ez force", objectExtra=orca.oeEndB), decimal))),
            "Shear force (VCM)": float(abs(round(line.StaticResult(
                varNames="End Ex force", objectExtra=orca.oeEndB), decimal))),
            "Bend moment (VCM)": float(abs(round(line.StaticResult(
                varNames="End Ey moment", objectExtra=orca.oeEndB), decimal))),
            "Bend Restrictor": bend_status,
            "Shear force (Vert)": shear,
            "Bend moment (Vert)": moment,
            "Aprooved": failed_dir not in file
        })

        results_df = pd.DataFrame(static_results_list)
        static_path = os.path.join(AUTOMATION_PATH, "Results_statics.json")
        results_df.to_json(static_path, orient='records', lines=True)

print("\nFinished.")
