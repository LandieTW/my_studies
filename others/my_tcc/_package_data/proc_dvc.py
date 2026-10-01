"""Module to generate the DVC cases 4 and 5."""

__author__ = "Yan Nascimento"
__copyright__ = "TechnipFMC"
__credits__ = ""
__license__ = ""
__version__ = "3.0"
__maintainer__ = "Yan Nascimento"
__email__ = [
    "yan.donascimento@technipfmc.com",
]
__status__ = "Developed"
__last_release__ = "May, 2026"

"""Reference Document: ET-3000.00-1500-941-PMU-006 - Rev C"""

"""
V2.0: Original 
V3.0:
- Centralized constants in the code header for best practices.
- New feature - line density and pressure fields are populated for cases 4 and 5.
"""

# Public(Python) Libraries
import os
import sys
import glob
import time
import locale
import OrcFxAPI as orca
from pathlib import Path
from collections import defaultdict
# Private(IAS) Libraries
from utils import orcaflex
from utils import excel_handler

# Constants - Model objects
AR_NAME = "A/R"
LINE_NAME = "Line"
WINCH_NAME = "Guindaste"
PLSV_NAME = "PLSV"
SLING1_NAME = "Cabrestante 1"
SLING2_NAME = "Cabrestante 2"
BUOYS_3D = "Junção"
STIFFNESS_CURVE_LAYING = "Stiffness_Lançamento"
STIFFNESS_CURVE_TEST = "Stiffness_Teste"
STIFFNESS_CURVE_OPERATION = "Stiffness_Operação"
OBJ_REMOVE_2ND_DVD = (SLING1_NAME, SLING2_NAME, AR_NAME, BUOYS_3D)
ABBREV_ANCILLARIES = ("ZR", "EF", "FA", "BR")
PREFIX_ATTACH = ("SKA", "SKB", "SKN", "SKRO", "SKV", "TOP", "CDA", "PESO")
DFT_LINE_PRESSURE = 0.0
# Constants from ET - General
ET_BUOY_LINK_LENGTH = 3.0
ET_BUOY_LINK_STIFFNESS = 1000.0
# Constants from ET - Case 4 and 5
ET_CASE_4_5_LINE_FULL_STATICS_TOLERANCE = 10
ET_CASES_4_5_LINE_STATICS_STEP2 = "None"
ET_CASES_4_5_WHOLE_SYSTEM_STATICS_ENABLE = "No"
ET_CASES_4_5_STIFFNESS_CURVE_HYSTERETIC = "No"
# Contants from ET - These constants can be adjusted
ET_CASES_4_5_STAGE_COUNT = 2
ET_STAGE_DURATION = 50.0
ET_LINE_LAID_LENGTH = 50.0
ET_STABILIZATION_TIME = 30.0
ET_LAYING_SPEED = 0.1
# Constants - Others
AR_RECOVERED_LENGTH = 10
CASES_4_5_MAX_ITERATIONS = 1000 # Improve convergence

# Only for debug or to run manually - Do not change!
DEBUG_ENABLE = False
DEBUG_SPREADSHEET_DIR = r""
DEBUG_DVC_TYPE = 2
DEBUG_FUNCTION_NAME = "layaway"

######## ATTENTION - IT IS NOT NECESSARY TO CHANGE ANYTHING FROM HERE #########

"""General Functions"""

def error_msg(msg: str) -> None:
    """Show error message"""
    print(f"ERRO: {msg}")
    time.sleep(5)
    exit()

def update_attachment_list(
        line: orca.OrcaFlexLineObject, attach_list: list,
    ) -> orca.OrcaFlexLineObject:
    """
    Update the line attachment ignoring dead weights and buoys.

    Args:
        line: orcaflex line object.
        attach_list: attachment list - not buoys and not dead weights.

    Returns:
        the orcaflex line object is returned.
    """
    line.NumberOfAttachments = len(attach_list)

    for i, attach in enumerate(attach_list):
        line.AttachmentType[i] = attach["name"]
        line.Attachmentz[i] = attach["z"]
        line.AttachmentzRelativeTo[i] = attach["relative"]

        if attach["att_name"] is not None:
            line.AttachmentName[i] = attach["att_name"]

    return line

def get_attach_coordinates(line: orca.OrcaFlexLineObject, attach_z: float) -> tuple:
    """
    Gets the attachments X and Z coordinates (global) - in the static state.
    
    Args:
        line: orcaflex line object.
        attach_z: Z coordinate (local)

    Returns:
        Tuple: X and Z coordinates
    """

    period = orca.PeriodNum.StaticState
    line_z_arc_length = line.TimeHistory("Arc length", period=period, objectExtra=orca.oeEndB)

    obj_extra = orca.oeArcLength(line_z_arc_length - attach_z)
    coord_x = line.TimeHistory("X", period=period, objectExtra=obj_extra)
    coord_z = line.TimeHistory("Z", period=period, objectExtra=obj_extra)

    return coord_x, coord_z

def get_attach_drag(obj_attach: orca.ObjectType.ClumpType) -> dict:
    """
    Get the drag coefficient from the clump types.

    Args:
        obj_attach: it is the clump type object.

    Returns:
        dict of the attachment drag data.
    """
    return {
        "drag_area_x": obj_attach.DragAreaX,
        "drag_area_y": obj_attach.DragAreaY,
        "drag_area_z": obj_attach.DragAreaZ,
        "cd_x": obj_attach.CdX,
        "cd_y": obj_attach.CdY,
        "cd_z": obj_attach.CdZ,
        "ca_x": obj_attach.CaX,
        "ca_y": obj_attach.CaY,
        "ca_z": obj_attach.CaZ,
    }

def split_buoys_and_non_buoys(model: orca.Model, line: orca.OrcaFlexLineObject) -> dict:
    """
    Get a dict of two lists of attachments, the first list with 
    non-dead weights or buoys and other list with remaining attchments.

    Args:
        model: it is the python representation of the model file.
        line: orcaflex line object.

    Returns:
        dict of two lists:
            "non_buoys_dw" is a list of attachment that are non-dead weights or buoys.
            "buoys_dw" is a list of attachment that are dead weights or buoys.
    """
    non_buoys_dw_list = []
    buoys_dw_list = []
    
    for i, atach_type in enumerate(line.AttachmentType):

        obj_attach = model[atach_type]

        attach = {
            "att_name": line.AttachmentName[i],
            "name": line.AttachmentType[i],
            "z": line.Attachmentz[i],
            "relative": line.AttachmentzRelativeTo[i],
            "coordinates": get_attach_coordinates(line, line.Attachmentz[i]),
            "drag_data": get_attach_drag(obj_attach) if "ClumpType" in obj_attach.type.name else None,
            "volume": obj_attach.Volume if "ClumpType" in obj_attach.type.name else None,
        }

        if atach_type.split("_")[0].upper() not in PREFIX_ATTACH:
            non_buoys_dw_list.append(attach)
        else: 
            buoys_dw_list.append(attach)

    return {"non_buoys_dw": non_buoys_dw_list, "buoys_dw": buoys_dw_list}

def get_winch_ar_length(model: orca.Model) -> tuple:
    """
    Get total AR length in the end of the whole simulation
    Args:
        model: it is the python representation of the model file.

    Returns:
        tuple: orcaflex winch object and AR length
    """
    winch_ar = model[AR_NAME]
    ar_length = winch_ar.TimeHistory("Length", period=orca.PeriodNum.WholeSimulation)[-1]
    
    return winch_ar, ar_length

def manager_workspace(spreadsheet_dir: str) -> tuple:
    """
    Manager the folders and files of the workspace.
    - Create the cases 4 and 5 folder. 
    - Get the complete file paths.

    Args:
        spreadsheet_dir: it is the DVC spreadsheet directory.

    Returns:
        Two dictionaries.
        - First: full paths of the files.
        - Second: stiffness curve name and simulation file paths. 
    """
    # Get the root path
    root_path = os.path.dirname(spreadsheet_dir)

    df_files = excel_handler.load_data_range_to_df(        
            xlsx_file=spreadsheet_dir, 
            range_name="data_tab_files_path", 
            is_table=True,
        )

    df_files = df_files.set_index(df_files.columns[0])
    paths = df_files["filename"].to_dict()

    # Create folder of the cases 4 and 5
    Path(os.path.join(root_path, paths["dir_cases_4_5"])).mkdir(parents=True, exist_ok=True)

    # Get the Case3 model FILE - with attachments
    basefile =  f"{paths["file_dynamic"]}.sim"
    model_file = glob.glob(os.path.join(root_path, basefile))

    if not model_file:
        error_msg("The 'Dinamico.sim' file was not found!")

    file_paths = {} 
    file_paths["file_dynamic"] = model_file[0]
    filename = paths["file_contingency"]
    cont_file = f"{filename}1.dat"
    file_paths["file_contingency"] = os.path.join(root_path, cont_file)
    filename = paths["file_case3_layaway"]
    case3_file = f"{filename}.dat"
    file_paths["file_case3_layaway"] = os.path.join(root_path, case3_file)

    data_et_cases = {}
    data_et_cases["lan"] = { 
        "basename": os.path.join(root_path, paths["file_case4_laying"]),
        "curve_name": STIFFNESS_CURVE_LAYING,
        "pressure": DFT_LINE_PRESSURE,
        "density": None,
    }
    data_et_cases["hid"] = { 
        "basename": os.path.join(root_path, paths["file_case4_test"]),
        "curve_name": STIFFNESS_CURVE_TEST,
        "pressure": None,
        "density": None,
    }
    data_et_cases["ope"] = { 
        "basename": os.path.join(root_path, paths["file_case5_operation"]),
        "curve_name": STIFFNESS_CURVE_OPERATION,
        "pressure": None,
        "density": None,
    }

    return file_paths, data_et_cases

"""Cases 4 and 5 Functions"""

def get_buoys3d(model: orca.Model) -> list:
    """
    Get the buoys/dead weight list.

    Args:
        model: it is the python representation of the model file.

    Returns:
        list of links.
    """
    obj_type = orca.ObjectType.Buoy3D.value
    obj_list = orcaflex.search_objects(model, pattern="B*", obj_type=obj_type)
    obj_list.extend(orcaflex.search_objects(model, pattern="P*", obj_type=obj_type))

    return obj_list

def get_links(model: orca.Model) -> list:
    """
    Get the link list of buoys.

    Args:
        model: it is the python representation of the model file.

    Returns:
        list of links.
    """
    obj_type = orca.ObjectType.Link.value
    return orcaflex.search_objects(model, pattern="L*", obj_type=obj_type)

def remove_buoys_dead_weights(model: orca.Model) -> orca.Model:
    """
    Remove the buoys and dead weights - Links and Buoys3D.

    Args:
        model: it is the python representation of the model file.

    Returns:
        orca.Model - it is the model updated after the function is called.
    """
    obj_list = get_buoys3d(model)
    obj_list.extend(get_links(model))

    for item in obj_list:
        model.DestroyObject(model[item.Name])
    
    return model

def create_filename(filename: str, has_buoys: bool) -> str:
    """
    Get the orcaflex filename.

    Args:
        filename: it is the filename without the extension and the suffix.
        has_buoys: bool to indicate whether it has buoys or not.

    Returns:
        the orcaflex line object is returned.
    """
    if has_buoys:
        return f"{filename}_comflut.dat"
    else:
        return f"{filename}_semflut.dat"

def create_new_case(
        model: orca.Model,
        line: orca.ObjectType.Line,
        flex_linetype: orca.ObjectType.LineType, 
        data_et_cases: dict, 
        has_buoys: bool = True,
    ) -> orca.Model:
    """
    This function updates the stiffness curve and replace the line EIx value.

    Args:
        model: it is the python representation of the model file.
        line: orcaflex line object.
        flex_linetype: it is the flexible linetype.
        data_et_cases: dict of stiffness curve, pressure and density for cases 4 and 5.
        has_buoys: if the simulation has buoys or not.

    Returns:
        orca.Model - it is the model updated after the function is called.
    """
    base_filename = create_filename(data_et_cases["basename"], has_buoys)

    stiffness_curve = data_et_cases["curve_name"]
    flex_linetype.EIx = stiffness_curve
    model[stiffness_curve].Hysteretic = ET_CASES_4_5_STIFFNESS_CURVE_HYSTERETIC

    line.ContentsPressure = data_et_cases["pressure"]

    line_contents_density = line.ContentsDensity   
    if data_et_cases["density"]:    
        line.ContentsDensity = data_et_cases["density"]
        
    model.SaveData(base_filename)
    line.ContentsDensity = line_contents_density

    return model

def update_coordinates_buoys3d(model: orca.Model, coord_buoys3d: dict) -> orca.Model:
    """
    Update the 3D buoys coordinates.

    Args:
        model: it is the python representation of the model file.
        coord_buoys3d: a dict of the 3D buoys coordinates

    Returns:
        orca.Model - it is the model updated after the function is called.
    """
    buoys3d_list = get_buoys3d(model)
    # Get the prefix of the first item
    prefix = buoys3d_list[0].Name[0]

    for key in coord_buoys3d.keys():
        # Replace link name to the buoys3d name
        obj = model[key.replace("L", prefix)]
        obj.InitialX = coord_buoys3d[key]["X"]
        obj.InitialY = coord_buoys3d[key]["Y"]
        obj.InitialZ = coord_buoys3d[key]["Z"]

    return model

def remove_release_links(model: orca.Model) -> orca.Model:
    """
    Remove the release of links - change for the default value.

    Args:
        model: it is the python representation of the model file.

    Returns:
        orca.Model - it is the model updated after the function is called.
    """
    links = get_links(model)

    for item in links:
        # Default value of ReleaseStage
        model[item.Name].ReleaseStage = orca.OrcinaDefaultWord

    return model

def get_structure(model: orca.Model, line: orca.ObjectType.Line) -> orca.Model:
    """
    Get the section connected to the VCM

    Args:
        model: it is the python representation of the model file.
        line: orcaflex line object.

    Returns:
        orca.Model - it is the model updated after the function is called.
    """

    for item in tuple(reversed(line.LineType)):
        if item.split("_")[0] not in ABBREV_ANCILLARIES:
            print(f"Estrutura: {item}")
            return model[item]
        
    print(f"Estrutura: {line.LineType[0]}")
    return model[line.LineType[0]]

def get_links_coordinates(model: orca.Model) -> dict:
    """
    Get the links coordinates - fixed end on the line.

    Args:
        model: it is the python representation of the model file.

    Returns:
        a dict of the coordinates
    """
    link = get_links(model)

    link_dict = {}

    for item in link:
        obj = model[item.Name]
        link_dict[obj.Name] = {
            "X": obj.TimeHistory("End B X", orca.PeriodNum.StaticState), 
            "Y": obj.TimeHistory("End B Y", orca.PeriodNum.StaticState), 
            "Z": obj.TimeHistory("End B Z", orca.PeriodNum.StaticState) + obj.UnstretchedLength,
        }
    
    return link_dict

def generate_cases_4_5(model_file: str, dvc_type: int, data_et_cases: dict) -> None:
    """
    Generate the cases 4 and 5 - ET of DVC.

    Args:
        model_file: it is the orcaflex model file (layaway).
        dvc_type: 1 to 1st dvc or 2 to 2nd dvc.
        data_et_cases: dict of stiffness curve, pressure and density for cases 4 and 5.

    Returns:
        None
    """
    sim_file = model_file.replace("dat", "sim")

    model = orcaflex.load_model(sim_file)

    if "SimulationStopped" not in model.state.name:
        error_msg("É preciso rodar o dinâmico do arquivo 'Caso3_lançamento.dat' para gerar os casos 4 e 5.")

    winch_ar, ar_length = get_winch_ar_length(model)
    coordinates_buoys3d = get_links_coordinates(model)

    # Before changes the model, set lines to user specified starting shape
    model.UseCalculatedPositions(SetLinesToUserSpecifiedStartingShape=True)

    line = model[LINE_NAME]
    general = model.general

    # ET - Item 6.4 (Update Line)
    line.FullStaticsTolerance = ET_CASE_4_5_LINE_FULL_STATICS_TOLERANCE
    # To avoid moving the line
    line.StaticsStep2 = ET_CASES_4_5_LINE_STATICS_STEP2
    general.WholeSystemStaticsEnabled = ET_CASES_4_5_WHOLE_SYSTEM_STATICS_ENABLE

    # Due to the change in the stiffness curve
    general.ImplicitConstantMaxNumOfIterations = CASES_4_5_MAX_ITERATIONS

    # ET - Item 6.4 (Update General)
    general.StageCount = ET_CASES_4_5_STAGE_COUNT
    general.StageDuration[1] = ET_STAGE_DURATION

    # Remove objects - both dvc types
    model.DestroyObject(model[WINCH_NAME])

    if dvc_type == 1:
        plsv_constr = model[PLSV_NAME]
        winch_ar.StageValue[0] = ar_length
        winch_ar.StageValue[2] = 0
        winch_ar.Connection[0] = "Fixed"
        winch_ar.ConnectionZ[0] = plsv_constr.InitialZ
        winch_ar.ConnectionX[0] = plsv_constr.TimeHistoryDatax[-1] + plsv_constr.InitialX
        model.DestroyObject(plsv_constr)
    elif dvc_type == 2:
        # Remove objects - only 2nd dvc
        for item in OBJ_REMOVE_2ND_DVD:
            model.DestroyObject(model[item])

    # Get the flexible linetype
    flex_linetype = get_structure(model, line)

    """With buoys - Case 4 (laying and test)"""
    if coordinates_buoys3d:
        model = remove_release_links(model)
        model = update_coordinates_buoys3d(model, coordinates_buoys3d)
        for case in ["lan", "hid"]:
            model = create_new_case(model, line, flex_linetype, data_et_cases[case], True)

        # Remove buoys and dead weights for the next step
        model = remove_buoys_dead_weights(model)
    
    """Case 4 (laying and test) and case 5 without buoys"""
    for case in ["lan", "hid", "ope"]:
        model = create_new_case(model, line, flex_linetype, data_et_cases[case], False)

    return None

"""Contigency Functions"""

def generate_contingency_model(file_names: dict) -> None:
    """
    Generate the contingency case.
    Note: this function DOES NOT added contingency buoys in the model.

    Args:
        file_names: it is a dict of the names of the analysis files.

    Returns:
        None
    """
    # Prepare model
    model = orcaflex.load_model(file_names["file_dynamic"])

    # Get winch length
    winch_ar, winch_pos_z = get_winch_ar_length(model)

    # Before changes the model, set lines to user specified starting shape
    model.UseCalculatedPositions(SetLinesToUserSpecifiedStartingShape=True)

    winch_length = winch_pos_z - winch_ar.ConnectionZ[0]
    lda = abs(model.environment.depth)
    # Avoid the winch ar length being greater than lda depth.
    winch_pos_z = winch_pos_z if winch_length < lda else lda + 0.9 * winch_ar.ConnectionZ[0]

    # ET - Item 6.4 (Pay AR cable)
    winch_ar.StageValue[0] = winch_pos_z
    winch_ar.StageValue[-1] = 0

    model.SaveData(file_names["file_contingency"])

    return None

"""Layaway Functions"""

def release_stages(
        model: orca.Model,
        dvc_type: int, 
        attach_z: set,
        winch_ar: orca.ObjectType.Winch,
    ) -> orca.Model:
    """
    Create the stages to release the buoys or dead weights.

    Args:
        model: it is the python representation of the model file.
        dvc_type: 1 to 1st dvc and 2 to 2nd dvc.
        attach_z: it is the attachment Z coordinate.
        winch_ar: orcaflex ar cable object.

    Returns:
        None
    """
    link_list = get_links(model)
    sorted_list = sorted(attach_z, reverse=True)
    len_list = len(sorted_list)

    # Stages to release the buoys
    start_release = model.general.StageCount - 2
    if len_list > 0:
        start_release = start_release - len_list + 1

    stage = {sorted_list[i]: i + start_release + 1 for i in range(len_list)}

    for link in link_list:
        link.ReleaseStage = stage[link.EndBZ]

    if dvc_type == 2:
        # Do not forget - the first index is 0
        model[SLING1_NAME].ReleaseStage = start_release
        model[SLING2_NAME].ReleaseStage = start_release
        # Pay out AR Cable - move away from the line
        winch_ar.StageValue[start_release + 1] = -AR_RECOVERED_LENGTH

    return model

def create_stages(model: orca.Model, dvc_type: int, n_attach: int) -> orca.Model:
    """
    Create the simulation stages, according to the ET. 

    Args:
        model: it is the python representation of the model file.
        dvc_type: 1 to 1st dvc and 2 to 2nd dvc.
        n_attach: number of buoys or dead weights.

    Returns:
        None
    """
    # Number of stage to release one set of buoys at a time.
    n_stages_release_buoys = n_attach - 1 if n_attach > 1 else 0

    # ET - Item 6.3 - Stages
    n_stages = model.general.StageCount + n_stages_release_buoys
    # Update the simulation stages
    model.general.StageCount = n_stages + 3 if dvc_type == 1 else n_stages + 2

    # Time for line stabilization
    model.general.StageDuration[model.general.StageCount - n_attach - 2] = ET_STAGE_DURATION

    # Release set of buoys - time step
    if n_attach > 1:
        model.general.StageDuration[-n_attach:] = [ET_STABILIZATION_TIME] * n_attach
    else:
        model.general.StageDuration[-1] = ET_STABILIZATION_TIME

    return model

def create_base_link(
        model: orca.Model, line: orca.ObjectType.Line,
    ) -> orca.ObjectType.Link:
    """
    Create a Link object with the reference document (ET) data. 

    Args:
        model: it is the python representation of the model file.
        line: orcaflex line object.

    Returns:
        None
    """
    link = model.CreateObject(orca.ObjectType.Link)
    
    link.UnstretchedLength = ET_BUOY_LINK_LENGTH
    link.Stiffness = ET_BUOY_LINK_STIFFNESS
    link.EndBConnection = line.Name

    return link

def create_base_buoys3d(model: orca.Model) -> orca.ObjectType.Buoy3D:
    """
    Create a 3D buoys object with the reference document (ET) data. 

    Args:
        model: it is the python representation of the model file.

    Returns:
        None
    """
    buoys_3d = model.CreateObject(orca.ObjectType.Buoy3D)
    buoys_3d.Height = 1.7 # Arbitrary value

    return buoys_3d

def convert_attach_to_3dbuoys(
        model: orca.Model, line: orca.OrcaFlexLineObject, attach_list: list, 
    ) -> orca.Model:
    """
    Convert the attachment buoys and dead weights to 3D buoys.

    Args:
        model: it is the python representation of the model file.
        line: orcaflex line object.
        attach_list it is a list of buoys and dead weights.

    Returns:
        orca.Model - it is the model updated after the function is called.
    """

    base_link = create_base_link(model, line)
    base_buoys3d = create_base_buoys3d(model)

    counter = defaultdict(int)
    locale.setlocale(locale.LC_ALL, 'pt_BR.UTF-8')

    for item in attach_list["buoys_dw"]:

        attach_type, attach_value = item["name"].split("_")      
        # It is not possible to create objects with the same name
        # counter creates a dict with default values of 0 for any new key.
        item_name = f"{attach_value}_{counter[attach_value]}"
        # add one to item["name"] key 
        counter[attach_value] += 1

        # Convert "," to "." and get a float variable
        attach_value = locale.atof(attach_value)

        # If buoy, buoyancy (+) and "B". If dead weight, weight (-) and "P". 
        prefix, factor = ("B", 1) if "PESO" not in attach_type.upper() else ("P", -1)

        # New links and buoys3D objects
        new_buoys3d = base_buoys3d.CreateClone(name=f"{prefix}{item_name}")
        new_link = base_link.CreateClone(name=f"L{item_name}")

        # Inputs
        new_buoys3d.Volume = item["volume"] if "B" in prefix else 0

        # Calculte the buoys or dead weights mass
        displaced_mass = model.environment.Density * new_buoys3d.Volume
        # attach_value - from kg to Te
        new_buoys3d.Mass = displaced_mass - (factor * (attach_value / 1000))

        new_link.EndAConnection = new_buoys3d.Name
        # Coordinates - the constants are arbitrary to facilitate convergence
        new_buoys3d.InitialZ = item["coordinates"][1] + (factor * new_link.UnstretchedLength + 0.1)
        new_link.EndBzRelativeTo = item["relative"] 
        new_link.EndBZ = item["z"]
        new_buoys3d.InitialX = item["coordinates"][0] + 0.1
        new_buoys3d.InitialY = 0.0

        drag_data = item["drag_data"]
        new_buoys3d.DragAreaX = drag_data["drag_area_x"]
        new_buoys3d.DragAreaY = drag_data["drag_area_y"]
        new_buoys3d.DragAreaZ = drag_data["drag_area_z"]
        new_buoys3d.CdX = drag_data["cd_x"]
        new_buoys3d.CdY = drag_data["cd_y"]
        new_buoys3d.CdZ = drag_data["cd_z"]
        new_buoys3d.CaX = drag_data["ca_x"]
        new_buoys3d.CaY = drag_data["ca_y"]
        new_buoys3d.CaZ = drag_data["ca_z"]

        try:
            new_link.EndBX = new_link.EndBY = 0.0
        except AttributeError:
            error_msg("Verifique se a histerese da curva de lançamento está ativada.")
        
    model.DestroyObject(base_link.Name)
    model.DestroyObject(base_buoys3d.Name)

    line = update_attachment_list(line, attach_list["non_buoys_dw"])

    return model

def create_constraint(
        model: orca.Model, 
        winch_ar: orca.ObjectType.Winch,
        top_coord: tuple,
        case3_n_stages: int,
    ) -> orca.Model:
    """
    Create a constraint object to simulate the vessel movement. 

    Args:
        model: it is the python representation of the model file.
        winch_ar: orcaflex ar cable object.
        top_coord: constraint coordinates.
        case3_n_stages: it is the last stage of the case3. 

    Returns:
        orca.Model - it is the model updated after the function is called.
    """

    # Stage 4 - Laying line
    pay_line_stage = case3_n_stages + 1
    pay_line_length = ET_LINE_LAID_LENGTH
    # Pay out 50m of line at 0,1 m/s  
    model.general.StageDuration[pay_line_stage] = pay_line_length / ET_LAYING_SPEED

    # Create constraint
    constraint = model.CreateObject(orca.ObjectType.Constraint, PLSV_NAME) 
     
    # Constraint parameters
    constraint.InitialX, constraint.InitialY, constraint.InitialZ = top_coord
    constraint.ConstraintType = "Imposed motion"
    constraint.TimeHistoryDataSource = "Internal"
    constraint.TimeHistoryInterpolation = "Linear"

    # AR position
    winch_ar.Connection[0] = PLSV_NAME
    winch_ar.ConnectionX[0] = winch_ar.ConnectionY[0] = winch_ar.ConnectionZ[0] = 0.0
    winch_ar.StageValue[pay_line_stage + 1] = pay_line_length # Pay line - 50m

    # Constraint - Time history data
    constraint.TimeHistoryDataCount = model.general.StageCount + 1
    th_data_time = tuple(model.general.StageStartTime)
    constraint.TimeHistoryDataTime = th_data_time + (model.general.StageEndTime[-1],)
    # Number of itens between (pay_line_stage + 1) index and the last one.
    n_itens = len(constraint.TimeHistoryDatax) - (pay_line_stage + 1)
    constraint.TimeHistoryDatax[pay_line_stage + 1:] = [pay_line_length] * n_itens

    return model

def generate_layaway_model(file_names: dict, dvc_type: int) -> None:
    """
    Generate the layaway model file.

    Args:
        file_names: it is a dict of the names of the analysis files.
        dvc_type: 1 to 1st dvc and 2 to 2nd dvc.

    Returns:
        None
    """
    # Prepare model
    model = orcaflex.load_model(file_names["file_dynamic"])

    line = model[LINE_NAME]
    winch_ar = model[AR_NAME]
    # Get constraint's positions
    top_end_x = winch_ar.TimeHistory("X", orca.PeriodNum.StaticState, orca.oeWinch(1))
    top_end_z = winch_ar.TimeHistory("Z", orca.PeriodNum.StaticState, orca.oeWinch(1))
    top_coord = (top_end_x[0], 0.0, top_end_z[0])

    attach_z = []
    attach_list = split_buoys_and_non_buoys(model, line)

    # Before modifying the model, convert attachments to 3D buoys.
    if attach_list["buoys_dw"]:
        model = convert_attach_to_3dbuoys(model, line, attach_list)
        # Get the the attachment Z coordinate
        attach_z = set([att_dict.get("z", None) for att_dict in attach_list["buoys_dw"]])

    case3_n_stages = model.general.StageCount
    # ET - Item 6.3 - Simulation stages
    model = create_stages(model, dvc_type, len(attach_z))

    # Release links
    model = release_stages(model, dvc_type, attach_z, winch_ar)

    if dvc_type == 1:
        # Create Constraint
        model = create_constraint(model, winch_ar, top_coord, case3_n_stages)

    model.SaveData(file_names["file_case3_layaway"])

if __name__ == "__main__":

    """
    To run manually, 
    1st: replace sys.argv[1] to the dvc spreadsheet path.
    2nd: replace sys.argv[2] to the dvc type (boolean value).
    3th: replace sys.argv[3] to "layaway" or "cases4_5".
    For cases 4 and 5 only:
    4th: replace sys.argv[4] to case 4 pressure (line contents)
    5th: replace sys.argv[5] to case 5 pressure (line contents)
    6th: replace sys.argv[6] to case 5 density (line contents)
    """

    if not DEBUG_ENABLE:
        if len(sys.argv) <= 1:
            error_msg("Inputs not found! Check the VBA code.")

        ## sys.argv[1] - dvc spreadsheet path.
        spreadsheet_dir = sys.argv[1]
        ## sys.argv[2] - if 1st dvc, 1. If 2nd dvc, 2.
        dvc_type = int(sys.argv[2])
        ## sys.argv[3] - "layaway" or "cases4_5".
        function_name = sys.argv[3]
    else:
        spreadsheet_dir = DEBUG_SPREADSHEET_DIR
        dvc_type = DEBUG_DVC_TYPE
        function_name = DEBUG_FUNCTION_NAME

    print("Please wait, the cases are being created.")

    # Create the cases_4_5 folder. In addition, get the full path of the files.
    full_paths, data_et_cases = manager_workspace(spreadsheet_dir)

    if function_name.upper() in "LAYAWAY":
        # Generate the contingency BASE model
        generate_contingency_model(full_paths)
        # Generate the layaway model
        generate_layaway_model(full_paths, dvc_type)
    elif function_name.upper() in "CASES4_5":
        data_et_cases["hid"]["pressure"] = float(sys.argv[4].replace(",", ".")) 
        data_et_cases["ope"]["pressure"] = float(sys.argv[5].replace(",", "."))
        data_et_cases["ope"]["density"] = float(sys.argv[6].replace(",", "."))
        # Generate the cases 4 and 5 models
        generate_cases_4_5(
            model_file=full_paths["file_case3_layaway"],
            dvc_type=dvc_type,
            data_et_cases=data_et_cases,
        )

    print("The cases were created.")
    time.sleep(2)
