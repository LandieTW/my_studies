#!/usr/bin/env python3.12

"""
DVC AUTO CONFIG TOOL
SECTION: MAIN

GOALS:
    Manage execution flow for DVC auto configuration tool.

CRITERION:
    VCM verticalized (0° ± 0.5°)
    Flexible clearance to seabed between 0.5 m and 0.65 m
    Flange connection in correct height position
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
import json
import sys
from io import StringIO
import OrcFxAPI as orca
from tempfile import gettempdir

# IAS Private libraries
from utils.parallel import run

# Tool inputs
from inputs import (rl_config, n_cases)
# Tool constants
from src.constants import (STATIC_FILE_NAME, N_WORKERS, N_ITERATION, DAMPING)
# Tool functions
from src.config_prop import (generate_config, automation_starter_flow)


# ---
# --------
# ------------------
# --------------------------------------
# -----------------------------------------------------------------------------
# --------------------------------------
# ------------------
# --------
# ---


class DualOutput:
    """
    Description:
        Saves prints in a buffer to allow exportation
    """
    def __init__(self, original_stdout, buffer):
        self.original_stdout = original_stdout
        self.buffer = buffer

    def write(self, message):
        self.original_stdout.write(message)
        self.buffer.write(message)

    def flush(self):
        self.original_stdout.flush()


# ---
# --------
# ------------------
# --------------------------------------
# -----------------------------------------------------------------------------
# --------------------------------------
# ------------------
# --------
# ---


original_stdout = sys.stdout
buffer = StringIO()
sys.stdout = DualOutput(original_stdout, buffer)

# Check inputs before starting automation flow process
# problem, problem_message = verify_inputs()
# if problem:
#     raise ValueError(f"ERROR: {problem_message}")

print("\n")
print(f"Generating {n_cases} different configurations...")

base_path = os.path.dirname(os.path.dirname(__file__))
static_file_path = os.path.join(base_path, STATIC_FILE_NAME)
static_model = orca.Model(static_file_path)
static_model.NewVariationModel(static_file_path)

# setting initial general configurations
general = static_model["General"]
general.StaticsMaxIterations = N_ITERATION
general.StaticsMinDamping = DAMPING[0]
general.StaticsMaxDamping = DAMPING[1]

temporary_directory = os.path.join(gettempdir(), "LTC_DVC_Configuration")
work_path = os.path.realpath(temporary_directory)

configs_to_test = generate_config(rl_config, n_cases)

cases = list()
for i in range(len(configs_to_test)):
    case_path = os.path.join(work_path, f"Case_{str(i + 1)}")
    os.makedirs(case_path, exist_ok=True)
    case_static_file_path = os.path.join(
        case_path, STATIC_FILE_NAME.replace(".dat", ".yml"))
    static_model.SaveData(case_static_file_path)

    config_path = os.path.join(case_path, f"Case_{str(i + 1)}.json")
    with open(config_path, 'w', encoding='utf-8') as f:
        json.dump(configs_to_test[i], f, ensure_ascii=False, indent=4)

    cases.append(case_path)

print("\n")
print("Starting automation flow process...")

run(
    function=automation_starter_flow,
    args=cases,
    n_workers=N_WORKERS,
    thread=True
)

print("STOP")

sys.stdout = original_stdout
captured_text = buffer.getvalue()
output_path = os.path.join(base_path, "output.txt")
with open(output_path, 'w', encoding='utf-8') as file:
    file.write(captured_text)

