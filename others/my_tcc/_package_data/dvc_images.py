"""Module to generate the 1st and 2nd DVC figures - All figures"""

__author__ = ["Mauro Rodrigues", "Yan Nascimento"]
__copyright__ = "TechnipFMC"
__credits__ = ""
__license__ = ""
__version__ = "2.0"
__maintainer__ = "Yan Nascimento"
__email__ = "yan.donascimento@technipfmc.com"
__status__ = "Developed"
__last_release__ = "May, 2026"

# Public Libraries (Python)
import os
import sys
import time
import glob
import OrcFxAPI as orca
from pathlib import Path
# Private Libraries (IAS)
from utils import excel_handler
from typing import Union
from libs import img_static as istc
from libs import img_cont as icnt
from libs import img_hmax as ihmax
from libs import img_puxada as ipux
from libs import img_dredging as idred

# Constants
LINE_NAME = "Line"
FONTSIZE = 6
USE_COMMA = True

# Only for debug or to run manually - Do not change!
DEBUG_ENABLE = False
DEBUG_DVC_TYPE = 2
DEBUG_SPREADSHEET_PATH = r"Testes\Teste1 - CVD 2a\Input_CVD_TESTE.xlsm"

######## ATTENTION - IT IS NOT NECESSARY TO CHANGE ANYTHING FROM HERE #########

"""General Functions"""
class GetDvcObjects():
    """Class to get DVC OrcaFlex objects"""

    DVC_OBJ_TYPES = [
        orca.ObjectType.Line, 
        orca.ObjectType.Buoy6D, 
        orca.ObjectType.Buoy3D, 
        orca.ObjectType.Link, 
        orca.ObjectType.Winch,
    ]

    def __init__(self, model: orca.Model, line_name: str = "Line"):

        self.line = line_name
        self._model = model
        self._obj_names = self._get_dvc_obj_names()
        self._check_dvc = self._check_line_name()
        self.dvc_type = self._get_dvc_type()
        self.bend_restrictor_name = self._get_dvc_bend_restrictor()
        self.vcm_name = self._get_dvc_vcm()
        self.crane_name, self.ar_name = self._get_winches()
        self.joint_name = self._get_buoy_3d()
        self.sling_names = self._get_links()

    def _get_dvc_obj_names(self) -> list:
        """Get the names of the DVC objects"""
        dev_objs = [obj for obj in self._model.objects if obj.type in self.DVC_OBJ_TYPES]
        return [obj.name for obj in dev_objs]

    def _get_dvc_type(self) -> int:
        """Get the dvc type - 1st or 2nd DVC"""
        line = self._model[self.line]
        return 2 if "Anchored" in [line.EndBConnection, line.EndAConnection] else 1

    def _check_line_name(self) -> bool:
        """Check whether the line_name input exists in the model"""
        if self.line not in self._obj_names:
            print("O objeto 'Line' não foi encontrado.")
            exit()
        return True

    def _get_dvc_bend_restrictor(self) -> str:
        """Get attachment - bend restrictor for both DVC"""
        line = self._model[self.line]
        return next(
            (item for item in line.AttachmentName if item in self._obj_names), 
            None,
        )
    
    def _get_dvc_vcm(self) -> str:
        """Get Buoys6D - vcm for Both DVC"""
        line = self._model[self.line]
        end_conn = [line.EndBConnection, line.EndAConnection]
        return next(
            (item for item in end_conn if item in self._obj_names),
            None
        )

    def _get_objects(self, obj_type: orca.ObjectType) -> list:
        """Get a list of a specific object type"""
        return [obj for obj in self._model.objects if obj.type in [obj_type]]

    def _get_winches(self) -> tuple:
        """Get Winches - crane and AR for Both DVC"""
        winches = self._get_objects(orca.ObjectType.Winch)
        # Crane - Connected to the vcm
        crane = next(
            (item for item in winches if item.Connection[0] or item.Connection[1] in self.vcm_name),
            None
        )
        # AR - Connected to the line
        ar = next((item for item in winches if crane.Name not in item.Name), None)

        return crane.Name, ar.Name

    def _get_buoy_3d(self) -> str:
        """Get Buoys3D - joint for 2nd DVC"""
        buoy_3d = self._get_objects(orca.ObjectType.Buoy3D)
        ar = self._model[self.ar_name]
        return next(
            (item.Name for item in buoy_3d if ar.Connection[0] or ar.Connection[1] in ar.Name),
            None
        )

    def _get_links(self) -> Union[dict, None]:
        """Get Links - slings for 2nd DVC"""
        links = self._get_objects(orca.ObjectType.Link)
        # The line links are connected to the joint
        line_links = [
            item for item in links if (item.EndAConnection or item.EndBConnection) in self.joint_name
        ]
        link1 = link2 = None
        if line_links and self.dvc_type == 2:
            # Sort the links by their End Z position
            link1, link2 = sorted(line_links, key=lambda x: max(x.EndAZ, x.EndBZ))
        
            return {"link1": link1.Name, "link2": link2.Name}
        return None

def error_msg(msg: str) -> None:
    """Show error message"""
    print(f"ERRO: {msg}")
    time.sleep(5)
    exit()

def manager_workspace(spreadsheet_dir: str, figure_path: str = "Figuras") -> dict:
    """
    Get the file paths

    Args:
        spreadsheet_dir: DVC spreadsheet directory.
        figure_path: path of the figure path.

    Returns:
        A dict of the file paths - absolute paths
    """
    # Get the path
    root_path = os.path.dirname(spreadsheet_dir)
    png_path = os.path.join(root_path, figure_path) 
    
    # Create the figures path
    Path(png_path).mkdir(parents=True, exist_ok=True)

    # Get the OrcaFlex file paths from the spreadsheet
    df_files = excel_handler.load_data_range_to_df(        
            xlsx_file=spreadsheet_dir, 
            range_name="data_tab_files_path",
            is_table=True,
        )
    df_files = df_files.set_index(df_files.columns[0])
    paths = df_files["filename"].to_dict()

    return {
        "xlsx_file": spreadsheet_dir,
        "dynamic_sim": os.path.join(root_path, paths["file_dynamic"] + ".sim"),
        "layaway_sim": os.path.join(root_path, paths["file_case3_layaway"] + ".sim"),
        "cont1_sim": os.path.join(root_path, paths["file_contingency"] + "1.sim"),
        "cont2_sim": os.path.join(root_path, paths["file_contingency"] + "2.sim"),
        "hmax1_sim": os.path.join(root_path, paths["file_hmax"] + "_cinta.sim"),
        "hmax2_sim": os.path.join(root_path, paths["file_hmax"] + "_proliprop.sim"),
        "puxada_sim": os.path.join(root_path, paths["file_puxada"] + ".sim"),
        "static_png": os.path.join(png_path, paths["file_static"] + ".png"),
        "static_zoom_png": os.path.join(png_path, paths["file_static"] + "_zoom.png"),
        "cont1_png": os.path.join(png_path, paths["file_contingency"] + "1.png"),
        "cont2_png": os.path.join(png_path, paths["file_contingency"] + "2.png"),
        "hmax1_png": os.path.join(png_path, paths["file_hmax"] + "_cinta.png"),
        "hmax2_png": os.path.join(png_path, paths["file_hmax"] + "_proliprop.png"),
        "puxada_png": os.path.join(png_path, paths["file_puxada"] + ".png"),
        "dredging_png": os.path.join(png_path, "Perfil_dragagem.png"),
    }

if __name__ == "__main__":
    """
    To run manually, 
    1st: replace sys.argv[1] to the dvc spreadsheet path.
    2nd: replace sys.argv[2] to the dvc type.    
    """

    if not DEBUG_ENABLE:
        if len(sys.argv) <= 1:
            error_msg("Inputs not found! Check the VBA code.")

        # sys.argv[1] - dvc spreadsheet path.
        spreadsheet_dir = sys.argv[1]
        # sys.argv[2] - if 1st dvc, 1. If 2nd dvc, 2.
        cvd_type = sys.argv[2]
    else:
        spreadsheet_dir = DEBUG_SPREADSHEET_PATH
        cvd_type = DEBUG_DVC_TYPE

    print("Please wait, the cases are being created.")

    file_paths = manager_workspace(spreadsheet_dir)

    # Workspace path
    filename_layaway = glob.glob(file_paths["layaway_sim"])
    filename_dynamic = glob.glob(file_paths["dynamic_sim"])

    if not filename_layaway or not filename_dynamic:
        error_msg("O arquivo layaway e/ou dinamico não foi encontrado!")
        exit()

    model = orca.Model(filename_layaway[0])

    dvc_objs = GetDvcObjects(model)
    dvc_type = dvc_objs.dvc_type
    obj_names = {
        "line": dvc_objs.line,
        "vcm": dvc_objs.vcm_name,
        "bend_restrictor": dvc_objs.bend_restrictor_name,
        "crane": dvc_objs.crane_name,
        "ar": dvc_objs.ar_name,
        "joint": dvc_objs.joint_name if dvc_type == 2 else None,
        "link1":  dvc_objs.sling_names["link1"] if dvc_type == 2 else None,
        "link2": dvc_objs.sling_names["link2"] if dvc_type == 2 else None,
    }
    
    istc.generate_static(
        model, file_paths, obj_names, dvc_type, 
        detailed=False, 
        fontsize=FONTSIZE, 
        use_comma=USE_COMMA,
    )
    print("Estatico - A figura da verticalização foi gerada")

    # Draw the static zoom picture
    istc.generate_static(
        model, file_paths, obj_names, dvc_type, 
        detailed=True, 
        fontsize=FONTSIZE, 
        use_comma=USE_COMMA,
    )
    print("Estatico - A figura DETALHADA da verticalização foi gerada") 

    idred.generate_dredging(model, file_paths, obj_names)
    print("Estatico - A figura da dragagem foi gerada") 

    if glob.glob(file_paths["cont1_sim"]):
        cont_paths = {"cont_sim": file_paths["cont1_sim"], "cont_png": file_paths["cont1_png"]}
        icnt.generate_cont(cont_paths, obj_names, dvc_type, FONTSIZE, USE_COMMA)
        print("Contingência1 - A figura foi gerada")

    if glob.glob(file_paths["cont2_sim"]):
        cont_paths = {"cont_sim": file_paths["cont2_sim"], "cont_png": file_paths["cont2_png"]}
        icnt.generate_cont(cont_paths, obj_names, dvc_type, FONTSIZE, USE_COMMA)
        print("Contingência2 - A figura foi gerada")

    if glob.glob(file_paths["hmax1_sim"]) and dvc_type == 2:
        hmax_paths = {"hmax_sim": file_paths["hmax1_sim"], "hmax_png": file_paths["hmax1_png"]}
        ihmax.generate_hmax(model, hmax_paths, obj_names, FONTSIZE*0.7, USE_COMMA)
        print("Hmax1 - A figura foi gerada")

    if glob.glob(file_paths["hmax2_sim"]) and dvc_type == 2:
        hmax_paths = {"hmax_sim": file_paths["hmax2_sim"], "hmax_png": file_paths["hmax2_png"]}
        ihmax.generate_hmax(model, hmax_paths, obj_names, FONTSIZE*0.7, USE_COMMA)
        print("Hmax2 - A figura foi gerada")

    if glob.glob(file_paths["puxada_sim"]) and dvc_type == 2:
        ipux.generate_puxada(file_paths, obj_names, FONTSIZE, USE_COMMA)
        print("Puxada - A figura foi gerada")
