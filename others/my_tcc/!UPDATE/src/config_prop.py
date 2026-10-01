#!/usr/bin/env python3.12

"""
DVC AUTO CONFIG TOOL
SECTION: CONFIG PROPERTIES

GOALS:
    Handle Configuration Properties class
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
from itertools import takewhile, accumulate, repeat, product, combinations
from collections import defaultdict, Counter
from math import isclose
import numpy as np
import OrcFxAPI as orca
import os
import json
import shutil
from glob import glob

# IAS Private libraries
from utils.orcaflex import license_handler
from utils.orcaflex import load_model
from utils.utils_constants import SEAWATER_DENSITY_ORCA

# Tool inputs
from inputs import (flexible_length, dredging_bathymetry, vessel_initialism,
                    weights, links_positions, max_n_buoy_sets, vessel_buoys)
# Tool constants
from src.constants import (vcm_rotation, clearance, ATOL, dvc_obj_type, 
                           vcm_displacement, vcm_dof, N_ITERATION_LIMIT,
                           damping_multiple, seabed_stiffness, DAMPING,
                           N_RUN_LIMIT, ADM_ERROR, NOT_ADM_ERROR, N_ITERATION,
                           over_length, camelback_rel_height, buoyancy_variation,
                           buoyancy_limit, buoyancy_increase_factor, new_buoy,
                           buoyancy_reduce_factor, N_BUOY_P_SET_LIMIT,
                           buoy_position_variation, small_buoy, SUBM_MASS_LIMIT,
                           payout_retrieve)
# Tool xlsx_data
from src.xlsx_data import (water_depth, vcm_a, br_bm_limit, br_sf_limit)


# ---
# --------
# ------------------
# --------------------------------------
# -----------------------------------------------------------------------------
# --------------------------------------
# ------------------
# --------
# ---


class ConfigProp():
    """
    Description:
        Handle properties for each single configuration from batch of
        simulations while running them in parallel
    """
    def __init__(self, path):
        # Configuration path id
        self.path = path
        self.case = os.path.basename(path)
        self.model_path = glob(os.path.join(self.path, "*.yml"))[0]
        # Nested list to save attachments properties
        # (Sometimes attachments are removed to solve convergence issues)
        self.attachments = list()
        # Actual configuration in the model
        self.actual_config = list()
        # Actual configuration reference
        self.actual_ref = list()
        # Nested list to save buoy sets already tested
        # (Avoid testing the same configurations reppeatedly)
        self.configs = list()
        # Nested list to save links positions already tested
        # (Avoid testing the same configuration x links positions, reppeatedly)
        # NOTE: Applicable only for 2nd End DVC Analyses
        self.links_positions = list()
        # Maximum number of buoy sets considered when generating and testing 
        # buoys combinations 
        self.n_buoy_p_set = 1
        # Static Calculation Counter 
        # (If major than N_RUN_LIMIT, aborts automation flow)
        self.run_counter = 0
        # Convergence error treatment Counter
        # (If major than N_RUN_ERROR_LIMIT, aborts automation flow)
        self.run_error_counter = 0
        # VCM's rotation [°] (updated every iteration)
        self.vcm_rotation = None
        # Flexible clearance to seabed [m] (updated every iteration)
        self.clearance = None
        # VCM flange connection height error [m] (updated every iteration)
        self.delta_flange = None
        # Camelback height [m]
        # NOTE: Applicable only for 2nd End DVC Analyses
        self.camelback_height = None
        # Over length [m]
        # NOTE: Applicable only for 2nd End DVC Analyses
        self.over_length = None
        # Line Normalised Curvature
        self.l_norm_curv = None
        # Bend Restrictor Normalised Curvature
        self.br_norm_curve = None
        # Bend Restrictor Loads
        self.br_sf = None   # kN
        self.br_bm = None   # kN.m
        # Flange loads
        self.axial_force = None     # kN
        self.shear_force = None     # kN
        self.bend_moment = None     # kN.m

        # Aprooved?
        self.aprooved = False
        # Aborted
        self.stop_running = False

    def get_elements(self) -> None:
        """
        Description:
            Get model elements and set it as class parameters
        """
        self.model = load_model(file=self.model_path)
    
        # Mapping model elements
        dvc_objects = [object 
                       for object in self.model.objects 
                       if object.type in dvc_obj_type]
        object_names = [object.name for object in dvc_objects]
    
        self.line = self.model['Line']
    
        self.dvc_type = 1 if "Anchored" not in [
            self.line.EndAConnection, self.line.EndBConnection
            ] else 2
        
        stiffener_name = next(
            (item 
             for item in self.line.AttachmentName if item in object_names),
            None
            )
        if stiffener_name:
            self.bend_restrictor = self.model[stiffener_name]
    
        vcm_name = next(
            (item 
             for item in [self.line.EndBConnection, self.line.EndAConnection] 
             if item in object_names),
            None
            )
        if vcm_name:
            self.vcm = self.model[vcm_name]
    
        winches = [object for object in dvc_objects 
                   if object.type == orca.ObjectType.Winch.value]
        self.winch = next(
            (item for item in winches 
             if item.Connection[0] or item.Connection[1] in vcm_name), None
            )
    
        self.a_r = next(
            (item for item in winches if self.winch.Name not in item.Name), 
            None
            )
    
        self.general = self.model['General']
        self.general.StaticsMaxIterations = 400
        self.environment = self.model['Environment']
    
        buoy_3d = [object for object in dvc_objects 
                   if object.type == orca.ObjectType.Buoy3D.value]
    
        self.link1, self.link2 = None, None
        if buoy_3d:
            joint_name = next(
                (item 
                 for item in buoy_3d 
                 if self.a_r.Connection[0] \
                    or self.a_r.Connection[1] in self.a_r.Name)
                )
    
            links = [object for object in dvc_objects 
                        if object.type == orca.ObjectType.Link.value]
            line_links = [
                item 
                for item in links 
                if item.EndAConnection \
                    or item.EndBConnection in joint_name.Name
                ]
            
            if line_links and self.dvc_type == 2:
                self.link1, self.link2 = sorted(
                    line_links, key=lambda x: max(x.EndAz, x.EndBz)
                    )
                
        self.clumps = [clump.Name for clump in self.model.objects
                       if clump.type in [orca.ObjectType.ClumpType]]    


    def StaticProgHandler(
            self,
            _,
            progress
        ) -> bool:
        """
        Description:
            Handle static calculation progress

        Parameters:
            _
                OrcaFlex model
            progress
                Convergence error calculated in each iteration
        
        Return:
            True - Aborts calculation (did not converged)
            False - Stay running (searching for convergence)
        """
        try:
            static_error = progress.split()
            
            index = 0
            if progress.startswith('Full statics for Line (no torsion)'):
                index = 10
            elif progress.startswith('Full statics for Line'):
                index = 8
            elif progress.startswith('Whole system statics'):
                index = 7
            elif progress.startswith('Converged with error'):
                index = 4

            if index != 0:
                error = static_error[index].replace(',', '.')
                final_error = float(error)
                
                if final_error < ADM_ERROR:
                    if index == 4:
                        print(
                            "\n"
                            f"Whole system statics converged"
                            )
                        # return False

                if final_error > NOT_ADM_ERROR:
                    print(
                        "\n"
                        f"Convergence failed."
                        )
                    return True
            
        except Exception as e:
            print(f"\n{e}")


    def static_run(self, key) -> None:
        """
        Description:
            Run the analysis and check configuration state
        
        Parameter:
            key
                0 - General static calculation;
                1 - Static calculation called from error_treatment function.
        """
        try:
            print(
                "\n"
                f"{self.case} - Static Calculation starting"
                )

            self.model.staticsProgressHandler = self.StaticProgHandler
            self.model.CalculateStatics()

            self.verify_vcm_rotation()
            self.verify_clearance()
            self.verify_delta_flange()
            self.verify_flange_loads()
            self.verify_normalised_curvature()
            if self.br_norm_curve >= 1:
                self.verify_br_loads()
            if self.dvc_type == 2:
                self.verify_camelback_height()
                self.verify_over_length()

            if self.l_norm_curv >= 1:
                print(
                    "\n"
                    "Non-physical static shape\n"
                    f"{self.case} - Static Calculation restarting"
                    )

                self.line.StaticsStep1 = 'Catenary'
                self.model.staticsProgressHandler = self.StaticProgHandler
                self.model.CalculateStatics()

                self.verify_vcm_rotation()
                self.verify_clearance()
                self.verify_delta_flange()
                self.verify_flange_loads()
                self.verify_normalised_curvature()
                if self.br_norm_curve >= 1:
                    self.verify_br_loads()
                if self.dvc_type == 2:
                    self.verify_camelback_height()
                    self.verify_over_length()

            if self.run_counter >= N_RUN_LIMIT:
                self.stop_running = True
            else:
                self.run_counter += 1

            self.model.SaveSimulation(os.path.join(
                self.path, f"{str(self.run_counter)}_Static.sim"
            ))
            self.model.UseCalculatedPositions(
                SetLinesToUserSpecifiedStartingShape=True)

            if key == 1:
                self.general.StaticsMaxIterations = N_ITERATION                 # Verificar se não gera loop infinito
                self.general.StaticsMinDamping = DAMPING[0]
                self.general.StaticsMaxDamping = DAMPING[1]
                self.environment.SeabedNormalStiffness = seabed_stiffness[0]
                self.vcm.DegreesOfFreedomInStatics = vcm_dof[0]

                self.model.staticsProgressHandler = self.StaticProgHandler
                self.model.CalculateStatics()

                self.model.SaveSimulation(os.path.join(
                    self.path, f"{str(self.run_counter)}_Static.sim"
                ))
                self.model.UseCalculatedPositions(
                    SetLinesToUserSpecifiedStartingShape=True)

                shutil.rmtree(os.path.join(self.path, "error"))

        except Exception as e:
            print(
                "\n"
                f"{self.case} \n {e}"
                )
            
            if key == 0:
                error_path = os.path.join(self.path, "error")
                os.makedirs(error_path, exist_ok=True)
                self.error_treatment()
            if key == 1:
                self.stop_running == True


    def error_treatment(self) -> None:
        """
        Description
            Set configurations trying to make an unstable model to converge
            1. Impose traction (avoiding compression);
                Flexible elements, when submited to compression, will bend.
                The convergence in this case is difficult because of the 
                enormous numbers of combinations of possible bending directions
                and ways to bend.
            2. Start calculation with elements already near of the convergence 
            final position;
                In that case we need to find out how to implement;
                NOTE: 1 and 2 seems to be concurrent/divergent solutions.
            3. Static Step 1 in 'Catenary' mode;
            4. Model simplification;
                4.1. Removing bend restrictor;
                4.2. Removing soil stiffness;
                4.3. Removing attachments;
                4.4. Removing VCM degrees of freedom;
            5. Static Damping Range Changing;
                Min Damping varying from 1 to 10, in steps of 1;
                Max Damping varying from 10 to 100, in steps of 10;
            6. Increasing max number of iteration
        """
        combinations = list(product(
            vcm_displacement,
            damping_multiple,
            seabed_stiffness,
            vcm_dof,
            ))

        for combination in combinations:

            if "error" in os.listdir(self.path):

                min_damping = combination[1] * DAMPING[0]
                max_damping = combination[1] * DAMPING[1]
                seabed_stiffness_print = "On" if combination[2] else "Off"

                self.general.StaticsMaxIterations = N_ITERATION_LIMIT
                self.general.StaticsMinDamping = min_damping
                self.general.StaticsMaxDamping = max_damping
                self.environment.SeabedNormalStiffness = combination[2]
                self.vcm.InitialX = combination[0]
                self.vcm.DegreesOfFreedomInStatics = combination[3]
                self.line.StaticsStep1 = "Catenary"

                print(
                    "\n"
                    "Applying Convergence Error Treatment\n"
                    f"Statics Max Iterations: {N_ITERATION_LIMIT}\n"
                    f"Statics Damping: {min_damping} / {max_damping}\n"
                    f"Seabed Stiffness: {seabed_stiffness_print}\n"
                    f"VCM Displacement: {combination[0]}\n"
                    f"VCM DOF: {combination[3]}\n"
                    f"Line Static Step: Catenary\n"
                    )

                self.static_run(1)

            else:
                break


    def final_check(self) -> None:
        """
        Description:
            Check if every DVC analysis criterion was achieved
        """
        self.aprooved = all([
            abs(self.vcm_rotation) < vcm_rotation[1],
            self.clearance > max(clearance),
            self.clearance < min(clearance),
            np.isclose(self.delta_flange, 0, atol=ATOL),
            self.norm_curv <= 1,
            all([self.br_sf < br_sf_limit, self.br_bm < br_bm_limit])
        ])


    def verify_vcm_rotation(self) -> None:
        """
        Description:
            Updates VCM rotation (in degrees)
        """
        self.vcm_rotation = round(self.vcm.StaticResult(varNames="Rotation 2"),
                                  ATOL)


    def verify_clearance(self) -> None:
        """
        Description:
            Updates line element clerance to seabed (in meters)
        """
        if self.dvc_type == 1:
            line_clearance = self.line.RangeGraph('Seabed clearance').Mean
        else:
            line_clearance = self.line.RangeGraph(
                varName='Seabed clearance',
                arclengthRange=orca.arSpecifiedArclengths(
                    self.line.NodeArclengths[-1] - self.link1.EndBZ,
                    self.line.NodeArclengths[-1] - 3
                )
            ).Mean
        bend_restrictor_clearance = self.bend_restrictor.RangeGraph(
            'Seabed clearance'
        ).Mean
        clearance = min(min(line_clearance), min(bend_restrictor_clearance))
        self.clearance = round(clearance, ATOL)


    def verify_delta_flange(self) -> None:
        """
        Description:
            Updates flange height connection error (in meters)
        """
        correct_depth = vcm_a - water_depth
        depth_verified = self.line.StaticResult('Z', orca.oeEndB)
        self.delta_flange = round(correct_depth - depth_verified, ATOL)


    def verify_camelback_height(self) -> None:
        """
        Description:
            Updates camelback height (in meters)
        """
        z_points = self.line.RangeGraph(
            varName='Z',
            arclengthRange=orca.arSpecifiedArclengths(
                FromArclength=self.line.NodeArclengths[-1] - self.link2.EndBZ,
                ToArclength=self.line.NodeArclengths[-1] - self.link1.EndBZ
            )
        ).Mean
        self.camelback_height = round(max(z_points) + water_depth, ATOL)


    def verify_over_length(self) -> None:
        """
        Description:
            Updates over length (in meters)
        """
        tdp_x_position = self.line.StaticResult('X', 
                                                objectExtra=orca.oeTouchdown)

        layed_length = self.line.StaticResult('Arc length', 
                                              objectExtra=orca.oeTouchdown)
        total_length = self.line.CumulativeLength[-1]
        lifted_length = total_length - layed_length

        flange_x_position = self.line.StaticResult(varNames='X', 
                                                   objectExtra=orca.oeEndB)

        tdp_to_flange_distance = tdp_x_position - flange_x_position

        self.over_length = round(lifted_length - tdp_to_flange_distance, ATOL)


    def verify_normalised_curvature(self) -> None:
        """
        Description:
            Updates normalised curvature
        """
        line_norm_curve = self.line.RangeGraph('Normalised curvature').Mean
        bend_restrictor_norm_curve = self.bend_restrictor.RangeGraph(
            'Normalised curvature'
        ).Mean
        self.l_norm_curv = round(max(line_norm_curve), ATOL)
        self.br_norm_curve = round(max(bend_restrictor_norm_curve), ATOL)


    def verify_flange_loads(self) -> None:
        """
        Description:
            Updates Flange Loads
        """
        af = self.line.StaticResult("End Ez force", orca.oeEndB)
        sf = self.line.StaticResult("End Ex force", orca.oeEndB)
        bm = self.line.StaticResult("End Ey moment", orca.oeEndB)
        self.axial_force = round(af, ATOL)
        self.shear_force = round(sf, ATOL)
        self.bend_moment = round(bm, ATOL)


    def verify_br_loads(self) -> None:
        """
        Description:
            Updates Bend Restrictor Loads
        """
        shear = self.bend_restrictor.RangeGraph("Shear Force").Mean
        self.br_sf = round(max(abs(min(shear)), abs(max(shear))), ATOL)

        moment = self.bend_restrictor.RangeGraph("Bend moment").Mean
        self.br_bm = round(max(abs(min(moment)), max(moment)), ATOL)


    def jumper_length_adjustment(self) -> None:
        """
        Description:
            According to flexible jumper length inputed,
            Apply an adjustment in Line and A&R lengths
        """
        a_r_length = self.line.CumulativeLength[-1] - flexible_length

        # A&R adjustment
        self.a_r.StageValue[0] = a_r_length

        # Line adjustment
        self.line.Length[0] -= a_r_length - self.Line.Length[-1]

        # in case of BR Rigid Zone AND Flange Adapter
        if self.line.NumberOfSections == 9:
            self.line.Length[0] += self.line.Length[-2] + self.line.Length[-3]

        # in acse of BR Rigid Zone OR Flange Adapter
        elif self.line.NumberOfSections == 8:
            self.line.Length[0] += self.line.Length[-2]

        # adjusting line EndA position
        self.line.EndAZ = - self.a_r.StageValue[0]


    def bathymetry_adjust(self) -> None:
        """
        Description:
            According to bathymetry data inputed,
            Apply an adjustment in seabed bathymetry
        """
        p1 = dredging_bathymetry['A']
        p2 = dredging_bathymetry['A'] + dredging_bathymetry['B']
        p3 = dredging_bathymetry['A'] + dredging_bathymetry['C']
        p4 = p3 - dredging_bathymetry['D']
        
        self.environment.SeabedProfileNumberOfPoints = len(dredging_bathymetry)
        self.environment.SeabedProfileDistanceFromSeabedOrigin[1] = p1
        self.environment.SeabedProfileDistanceFromSeabedOrigin[2] = p2
        self.environment.SeabedProfileDistanceFromSeabedOrigin[3] = p4
        self.environment.SeabedProfileDistanceFromSeabedOrigin[4] = p2

        self.environment.SeabedProfileZ[2] -= dredging_bathymetry['E2']
        self.environment.SeabedProfileZ[3] -= dredging_bathymetry['F2']


    def insert_buoys(self, selection: dict, n_buoys: int) -> None:
        """
        Description:
            Insert buoys in the model,
            according to the buoy set defined
        Parameters:
            selection [dict]
                Buoy selection (formated) to input into Orcaflex model
            n_buoys [int]
                Number of attachments to input into Orcaflex model
        """
        # removing buoys installed
        new_type = list(); new_z = list(); new_z_rel_to = list()
        new_name = list()
        for type, z, z_rel_to, name in zip(self.line.AttachmentType,
                                           self.line.Attachmentz,
                                           self.line.AttachmentzRelativeTo,
                                           self.line.AttachmentName):
            if not type.startswith(vessel_initialism):
                new_type.append(type); new_z.append(z)
                new_z_rel_to.append(z_rel_to); new_name.append(name)

        self.line.AttachmentType = new_type; self.line.Attachmentz = new_z
        self.line.AttachmentzRelativeTo = new_z_rel_to
        self.line.AttachmentName = new_name

        # Number of initial attachments
        n_ini_att = 0
        # Counting anodes, dead weight and bend restrictor
        for weight in weights:
            if weight["Name"]:
                if weight["Name"] in self.line.AttachmentType:
                    n_ini_att += weight["Quantity"]
        n_ini_att += 1 if 'Vert' in self.line.AttachmentType else 0

        self.line.NumberOfAttachments = n_buoys + n_ini_att

        att_pos = tuple(selection.keys())        # positions
        att_buo = tuple(selection.values())      # buoyancyes

        for buo in att_buo:
            for b in buo:
                if b not in self.clumps:
                    self.clumps.append(b)
                    new_buo = self.model.CreateObject(orca.ObjectType.ClumpType)
                    new_buo.Name = b
                    new_buo.Volume = 1
                    new_buo.Height = 1
                    # new_buo.Mass = SEAWATER_DENSITY_ORCA - (float(b.split("_")[1]) / 1_000)

        print(
            f"\n"
            f"\n{self.case}"
            f"\nSetting {att_buo} kg at {att_pos} m from VCM"
        )

        # Setting buoy configuration
        k = n_ini_att
        while k < self.line.NumberOfAttachments:
            for i in range(len(att_buo)):
                for j in range(len(att_buo[i])):
                    self.line.AttachmentType[k] = att_buo[i][j]
                    # insert attachments
                    self.line.Attachmentz[k] = att_pos[i]
                    # insert attachment's position
                    self.line.AttachmentzRelativeTo[k] = "End B"
                    k += 1


    def insert_weights(self) -> None:
        """
        Description:
            Insert weights in the model,
            according to the weights set defined
        """
        anodes, dead_weights = weights

        def insertion(weight: dict) -> None:
            clumps = [obj.Name 
                      for obj in self.model 
                      if obj.type == orca.ObjectType.ClumpType.value]

            name = weight["Name"]; subm_mass = weight["Submerged_Mass"]
            ini_pos = weight["Initial position"]; space = weight["Space"]
            qtt = weight["Quantity"]
            
            if name not in clumps:
                subm_weight = self.model.CreateObject(orca.ObjectType.ClumpType)
                subm_weight.Name = name
                subm_weight.Mass = subm_mass / 1_000
                subm_weight.Volume = 0
                subm_weight.Height = 1

            i = 0
            while i < qtt:
                position = round(i * space + ini_pos, ATOL)
                self.line.NumberOfAttachments += 1
                self.line.AttachmentType[-1] = name
                self.line.Attachmentz[-1] = position

        if anodes["Name"]:
            insertion(anodes)
        if dead_weights["Name"]:
            insertion(anodes)


    def move_links(self) -> None:
        """
        Description:
            Move camelback slings
        """
        actual_state = [(abs(self.link1.EndBZ - pos[0])) 
                        for pos in links_positions]
        link_idx = actual_state.index(min(actual_state))

        min_over_length, max_over_length = over_length

        if self.over_length < min_over_length:
            error_idx = -1
            choice_idx = link_idx + 1
        elif self.over_length > max_over_length:
            error_idx = 0
            choice_idx = link_idx - 1

        # if actual_state == links_positions[error_idx]:
        if self.link1.EndBZ == links_positions[error_idx][0]:
            self.stop_running = True
        else:

            delta = 1 if choice_idx > link_idx else -1
            direction = "RIGHT" if delta == 1 else "LEFT"

            print(
                f"\n{self.case}"
                f"Moving camelback slings" 
                f"({[self.link1.EndBZ, self.link2.EndBZ]})"
                f"1.0 m to the {direction}"
            )

            self.link1.EndBZ += delta
            self.link2.EndBZ += delta


    def payout_retrieve(self, delta: float) -> None:
        """
        Description:
            Controls how to payout or retrieve fleible pip
        Parameters: 
            delta [float]
                How much will be changed in Pipe's length
        """
        action = "Paying" if delta > 0 else "Retrieving"
        print(
            f"{self.case}"
            f"{action} {abs(delta)} m of line"
            )

        if not flexible_length and self.dvc_type == 1:
            new_length = self.line.Length[0] + delta
            self.line.Length[0] = round(new_length, ATOL)

        else:
            new_length = self.a_r.StageValue[0] + delta
            self.a_r.StageValue[0] = round(new_length, ATOL)


    def make_pointer(self, 
                     positions: list) -> int:
        """
        Description:
            Generates a pointer for a buoy set position, 
            prioritizing that position when choosing where some changing will 
            be applied
                In case of buoyancy addition, it prioritizes the position near 
                to VCM, since that is possible move it away from VCM without 
                infringe the minimum distance between buoys positions.
                Otherwise, in case of buoyancy reduction, the opposite occurs.        
        Parameter:
            positions [list]
                Positions where actual configuration buoys are installed
        """
        near_limit, far_limit = near_far_positions(positions)        

        min_rel_height, max_rel_height = camelback_rel_height
        min_over_length, max_over_length = over_length
        n_positions = len(positions)

        if self.vcm_rotation > 0 or (
            self.dvc_type == 2 and (
                (self.camelback_height > vcm_a + max_rel_height)
                or (self.over_length > max_over_length)
                )
            ):

            pointer = 0
            if n_positions == 2:
                if positions[pointer] <= near_limit[pointer]:
                    pointer = 1

            if n_positions == 3:
                if positions[pointer] <= near_limit[pointer]:
                    pointer = 1
                if positions[pointer] <= near_limit[pointer]:
                    pointer = 2

        elif self.vcm_rotation < 0 or(
            self.dvc_type == 2 and (
                (self.camelback_height < vcm_a + min_rel_height)
                or (self.over_length < min_over_length)
                )
            ):
            pointer = n_positions - 1
            if n_positions == 2:
                if positions[pointer] >= far_limit[pointer]:
                    pointer = 0

            elif n_positions == 3:
                if positions[pointer] >= far_limit[pointer]:
                    pointer = 1
                if positions[pointer] >= far_limit[pointer]:
                    pointer = 0

        return pointer, near_limit, far_limit


    def move_buoys(self, new_positions: list, pointer: int) -> None:
        """
        Description:
            Move buoys to new positions
        Parameters:
            new_positions [list]
                New positions to move buoys
            pointer [int]
                Pointer to the position that will be changed
        """
        old_z = self.line.Attachmentz
        pos_changed = list(set(self.line.Attachmentz))[pointer]
        new_z = list()

        print(
            f"{self.case}"
            f"Moving buoys from {self.actual_config[0]} m"
            f"to {new_positions} m"
            )

        for z in old_z:
            if z == pos_changed:
                new_z.append(new_positions[pointer])
            else:
                new_z.append(z)
        self.line.Attachmentz = new_z


    def change_buoyancy(self) -> list:
        """
        Description:
            Manage how buoyancy is changed in configuration reference
            NOTE: Buoyancy is changed following the next rules:
                1. Buoyancy is changed in steps of 50 kg;
                2. When increasing buoyancy, is verifyed if a previous set is 
                at least 1.5 times more than the next, if not, increase that 
                previous set, otherwise, increase the next set;
                3. When reducing buoyancy, is verifyed if a previous set is at 
                least 2 times more than the next, if yes, reduce that previous 
                set, otherwise, reduce the next set.
        Parameters:
            reference [list]                
        """
        n = len(self.actual_ref[1])

        buoyancy_var = buoyancy_variation if self.vcm_rotation > 0 else \
            - buoyancy_variation

        factor = buoyancy_increase_factor if self.vcm_rotation > 0 else \
            buoyancy_reduce_factor

        if n == 1:
            if 0 < (total := self.actual_ref[1][0] + buoyancy_var) <= buoyancy_limit:
                self.actual_ref[1][0] = total
            else:
                return []
        elif n == 2:
            if self.actual_ref[1][0] >= factor * self.actual_ref[1][1]:
                if 0 < (total := self.actual_ref[1][1] + buoyancy_var) <= buoyancy_limit:               # need to rethink this
                    self.actual_ref[1][1] = total
                else:
                    return []
            else:
                if 0 < (total := self.actual_ref[1][0] + buoyancy_var) <= buoyancy_limit:
                    self.actual_ref[1][0] = total
                else:
                    return []
        elif n == 3:
            if self.actual_ref[1][0] >= factor * self.actual_ref[1][1]:
                if self.actual_ref[1][1] >= factor * self.actual_ref[1][2]:
                    if 0 < (total := self.actual_ref[1][2] + buoyancy_var) <= buoyancy_limit:
                        self.actual_ref[1][2] = total
                    else:
                        return []
                else:
                    if 0 < (total := self.actual_ref[1][1] + buoyancy_var) <= buoyancy_limit:
                        self.actual_ref[1][1] = total
                    else:
                        return []
            else:
                if 0 < (total := self.actual_ref[1][0] + buoyancy_var) <= buoyancy_limit:
                    self.actual_ref[1][0] = total
                else:
                    return []

        elif n == 4:
            if self.actual_ref[1][0] >= factor * self.actual_ref[1][1]:
                if self.actual_ref[1][1] >= factor * self.actual_ref[1][2]:
                    if self.actual_ref[1][2] >= factor * self.actual_ref[1][3]:
                        if 0 < (total := self.actual_ref[1][3] + buoyancy_var) <= buoyancy_limit:
                            self.actual_ref[1][3] = total
                        else:
                            return []
                    else:
                        if 0 < (total := self.actual_ref[1][2] + buoyancy_var) <= buoyancy_limit:
                            self.actual_ref[1][2] = total
                        else:
                            return []
                else:
                    if 0 < (total := self.actual_ref[1][1] + buoyancy_var) <= buoyancy_limit:
                        self.actual_ref[1][1] = total
                    else:
                        return []

        return self.actual_ref


    def manage_buoy_changing(self) -> None:
        """
        Description:
            Manage buoys changing to a new configuration.
            NOTE: Every new configuration is saved in a list to avoid testing 
            the same configuration reppeatedly;
            
            1st -> Actual configuration is compared to last tested configuration;
            2nd -> If True...
                   A change is made in buoyancy magnitude of configuration 
                   reference;
                   If False...
                   A change is made in 1) number of buoys considered in each 
                   buoy set or 2) number of buoy sets considered in the 
                   configuration reference
            NOTE: Configuration reference is used to generate new configurations.
        """


        def change_buoys() -> None:
            """
            Description:
                Calling functions set to change buoys
            """
            selection = select_buoy_combination(new_ref, self.n_buoy_p_set)
            selection, n_buoys = selection_treatment(new_ref, selection)

            if selection == self.actual_config:
                self.run_counter -= 1
            else:
                self.actual_config = selection
                self.insert_buoys(selection, n_buoys)


        if self.actual_config == self.configs[-1]:
            new_ref = self.change_buoyancy()

            if new_ref:
                change_buoys()

            else:

                if len(self.actual_config) < max_n_buoy_sets:

                    if self.n_buoy_p_set < N_BUOY_P_SET_LIMIT:
                        # Try configurations with more buoys                            # can be optimized
                        self.n_buoy_p_set += 1
                        change_buoys()

                    elif self.n_buoy_p_set == N_BUOY_P_SET_LIMIT:
                        # try increase a new set of buoys
                        if self.vcm_rotation > 0:
                            new_position = self.actual_ref[0][-1] + 3
                            self.actual_ref[0].append(new_position)
                            self.actual_ref[1].append(new_buoy)
                        # otherwise we need to reduce sets of buoys
                        # if we only have one, it fails...
                        elif len(self.actual_config) == 1:
                            self.stop_running = True
                        # try to reduce one set of buoys
                        else:
                            del self.actual_ref[0][-1]
                            del self.actual_ref[1][-1]

                        self.n_buoy_p_set -= 1
                        change_buoys()

                if len(self.actual_config) == max_n_buoy_sets:

                    if self.n_buoy_p_set < N_BUOY_P_SET_LIMIT:
                        self.n_buoy_p_set += 1
                        change_buoys()
                    
                    elif self.n_buoy_p_set == N_BUOY_P_SET_LIMIT:
                        self.stop_running = True 

        else:

            if len(self.actual_config) < max_n_buoy_sets:

                if self.n_buoy_p_set < N_BUOY_P_SET_LIMIT:
                    self.n_buoy_p_set += 1
                    change_buoys()

                elif self.n_buoy_p_set == N_BUOY_P_SET_LIMIT:
                    # try increase a new set of buoys
                    if self.vcm_rotation > 0:
                        new_position = self.actual_ref[0][-1] + 3
                        self.actual_ref[0].append(new_position)
                        self.actual_ref[1].append(new_buoy)
                    # otherwise we need to reduce sets of buoys
                    # if we only have one, it fails...
                    elif len(self.actual_config) == 1:
                        self.stop_running = True
                    # try to reduce one set of buoys
                    else:
                        del self.actual_ref[0][-1]
                        del self.actual_ref[1][-1]

                    self.n_buoy_p_set -= 1
                    change_buoys()

            if len(self.actual_config) == max_n_buoy_sets:

                if self.n_buoy_p_set < N_BUOY_P_SET_LIMIT:
                    self.n_buoy_p_set += 1
                    change_buoys()
                
                elif self.n_buoy_p_set == N_BUOY_P_SET_LIMIT:
                    self.stop_running = True 


# ---
# --------
# ------------------
# --------------------------------------
# -----------------------------------------------------------------------------
# --------------------------------------
# ------------------
# --------
# ---


def near_far_positions(position_ref: list) -> list | list:
    """
    Description:
        Generate near and far limit position to set buoy set in.
    Parameters:
        position_ref [list]
            Positions of buoy sets in the reference configuration
    """
    near = [3 * i for i in range(1, len(position_ref) + 1)]
    far = sorted([18 - 3 * i for i in range(1, len(position_ref) + 1)])
    return near, far


def generate_config(rl_config: tuple, n_cases: int) -> list:
    """
    Description:
        Generate start configurantions to be tested.
        Each configuration is created as a variation of rl_config.

    Parameters:
        rl_config: tuple
            Nested tuple containing a configuration reference.
            Can be some user suggestion or RL configuration reference.
            Example:
                rl_config = (
                    [3.0, 6.0]              Buoy sets positions [m]
                    [1_400, 500]            Buoy sets total buoyancy [kg]
                )
                there is 1.4 Te of buoyancy 3 m next VCM and 0.5 Te next 6 m
        n_cases: int
            Maximum number of cases to be generated

    Return:
        Configurations generated
    """
    rl_positions, rl_buoyancies = rl_config

    near_vcm_limit_pos, far_vcm_limit_pos = near_far_positions(rl_positions)

    position_ranges = [
        [round(p, 1)
         for p in list(takewhile(lambda x: x <= far, 
                                 accumulate(repeat(buoy_position_variation), 
                                            initial=near)))
         if near <= p <= far] 
        for near, far in zip(near_vcm_limit_pos, far_vcm_limit_pos)
        ]

    generated_positions = [
        list(combo) 
        for combo in product(*position_ranges) 
        if all(combo[i + 1] - combo[i] >= 3 for i in range(len(combo) - 1))
        ]


    def distance_to_original(p: list) -> float:
        """
        Description:
            Calculates the sum of Euclidyan distances

        Parameters:
            p: list
                generated lists with new positions

        Return:
            "Distance" between generated positions and rl_config positions
        """
        return sum((p[i] - rl_positions[i]) ** 2 for i in range(len(p)))

    # sort with euclidyan distance
    generated_positions.sort(key=distance_to_original)
    generated_positions = generated_positions[:n_cases]

    moment = [p * b for p, b in zip(rl_positions, rl_buoyancies)]

    generated_buoyancies = list()
    for pos in generated_positions:
        buoys = list()
        for i in range(len(moment)):
            bm = moment[i]
            reductor = pos[i] / rl_positions[i]
            buoys.append(round((bm / pos[i]) * reductor, 0))
        generated_buoyancies.append(buoys)

    return [[generated_positions[i], generated_buoyancies[i]]
            for i in range(len(generated_positions))]





def selection_treatment(config: list, selection: dict) -> dict:
    """
    Description:
        Rewrite selection in format ready to input in Orcaflex
    Parameters:
        config [list]
            configuration reference
        selection [dict]
            A dict with this format: {pos1: ['b1'+b2'], ...}
            (that approximates to configuration reference)
    Returns:
        treated_selection
            Buoy selection (formated) to input into Orcaflex model
            {pos1: ['SKA_100', 'SKA_200'], ...}
            Example
                {3: ['SKRO_100', 'SKRO_200'], 
                 6: ['SKRO_100', 'SKRO_100'], 
                 10.0: ['SKRO_100']}
        n_buoys
            Number of attachments to input into Orcaflex model
    """
    keys = [[f"{vessel_initialism}_{buoy.strip()}"      # SKA_500 for example
             for buoy in key.split("+")]
             for key in selection.keys()]
    
    treated_selection = {config[0][i]: keys[i] for i in range(len(keys))}
    n_buoys = len([buoy[i] 
                   for buoy in treated_selection.values() 
                   for i in range(len(buoy))])

    return treated_selection, n_buoys





def select_buoy_combination(config: list, n_buoy_p_set: int) -> dict:
    """
    Description:
        Generates combinations of buoys,
        then select the most similar to the configuration reference
    Parameters:
        config [list]
            configuration reference
        n_buoy_p_set [int]
            Maximum number of buoys per set when generating combinations
    Return:
        A dict with this format: {'b1+b2': b1+b2, ...}
        (that approximates to configuration reference)
        Example:
            {'100+200': 300, '100+100': 200, '100': 100}
    """


    def buoy_combinations(buoys: list, n_buoy_p_set: int) -> dict:
        """
        Description:
            Make buoy combination, following next rules:
            1. Each combination must have less than 2 Te of subm. mass
            2. Combinations always are generated prioritizing the usage of one 
            or two buoys per set and the less number of sets
            3. Combinations are generated considering vessel availability (in
            terms of which buoys will be chosen and its quantityes)
            4. Combinations generated with three buoys has, at least, one of
            them as a small buoy
        Parameters:
            buoys [list]
                List of available buoys, according to vessel availability
            n_buoy_p_set [int]
                Maximum number of buoys per set when generating combinations
        Return:
            A dict with this format: {'b1+b2': b1+b2, ...}
        """
        combination = list(combinations(buoys, 1))
        if 1 < n_buoy_p_set <= N_BUOY_P_SET_LIMIT:
            combination += list(combinations(buoys, 2))
        if n_buoy_p_set == N_BUOY_P_SET_LIMIT:
            combination += list(combinations(buoys, 3))

        # avoiding reppeated combinations
        combination_dict = defaultdict(float)

        for comb in combination:

            # 1 buoy
            if len(comb) == 1:
                val = comb[0]
                key = str(val)
                combination_dict[key] = val

            # 2 buoys
            elif len(comb) == 2:
                if (val := comb[0] + comb[1]) < SUBM_MASS_LIMIT:
                    key = str(comb[0]) + "+" + str(comb[1])
                    combination_dict[key] = val

            # 3 buoys
            elif len(comb) == 3:
                # at least one of them must be a small buoy
                if any([comb[i] <= small_buoy for i in range(len(comb))]):
                    if (val := comb[0] + comb[1] + comb[2]) < SUBM_MASS_LIMIT:
                        key = str(comb[0]) + "+" + str(comb[1]) \
                            + "+" + str(comb[2])
                        combination_dict[key] = val

        return dict(sorted(combination_dict.items(),
                           key=lambda val: val[1],
                           reverse=True))

    b = [int(key) for key, count in vessel_buoys.items() for _ in range(count)]

    selection = dict()

    for ref in config[1]:
        # treating possible errors
        ref = .9 * ref if ref == SUBM_MASS_LIMIT else ref

        # bring all possible combinations of until n_buoy_p_set buoys
        buoy_comb = buoy_combinations(b, n_buoy_p_set)

        buoys = list(buoy_comb.keys())
        sum_buoys = list(buoy_comb.values())

        sum_buoys.append(ref)
        sum_buoys.sort(reverse=True)
        i = sum_buoys.index(ref)

        # reference is bigger than our options
        if i == 0:
            index = i + 1
            key = buoys[index]

        # reference is smaller tha our options
        elif i == len(sum_buoys) - 1:
            index = i - 1
            key = buoys[index]

        # reference is into our range of options
        else:
            options = [sum_buoys[i - 1], sum_buoys[i + 1]]
            if abs(ref - options[0]) < abs(ref - options[1]):
                index = i - 1
                key = buoys[index]
            else:
                index = i + 1
                key = buoys[i]

        if key in selection.keys():
            # for cases when keys are reppeated
            # dict must accept it and we don't want to subscribe values
            key += " "

        selection[key] = sum_buoys[index]

        buoys = key.split("+")
        for buoy in buoys:
            b.remove(int(buoy))     # excludes chosen buoys, for next selection

    return selection


@license_handler
def automation_starter_flow(path: str) -> None:
    """
    Description:
        Starts automation flow process for each single configuration case

    Parameters:
        path: str
            User\\AppData\\Local\\Temp\\LTC_DVC_Configuration\\Case_XX path...
    """
    model_prop = ConfigProp(path)
    model_prop.get_elements()

    initial_configuration_js = glob(os.path.join(path, "*.json"))[0]
    with open(initial_configuration_js, 'r', encoding='utf-8') as f:
        initial_configuration = json.load(f)

    # Saving reference
    model_prop.actual_reference = initial_configuration

    # Initial Static Calculation
    model_prop.static_run(0)
    if model_prop.stop_running:
        print(f"\n{model_prop.case} - Failed.")
        return

    # Adjusting jumper length
    if model_prop.dvc_type == 1 and flexible_length:
        print(
            "\n"
            f"Adjusting flexible jumper length"
            )
        model_prop.jumper_length_adjustment()

        model_prop.static_run(0)
        if model_prop.stop_running:
            print(f"\n{model_prop.case} - Failed.")
            return

    # Adjusting bathymetry
    if isinstance(dredging_bathymetry['A'], (float, int)):
        print(
            "\n"
            "Adjusting seabed bathymetry"
            )
        model_prop.bathymetry_adjust()

        model_prop.static_run(0)
        if model_prop.stop_running:
            print(f"\n{model_prop.case} - Failed.")
            return

    # Inserting buoys
    # Buoys are inserted in increments and sequentially, one by one
    n_increment = int(max(model_prop.actual_reference[1]) / 250)
    k = n_increment // n_increment
    while k <= n_increment:
        partial_config = [
            model_prop.actual_reference[0],
            [round(k * x / n_increment, 0) 
             for x in model_prop.actual_reference[1]]
            ]
        selection = select_buoy_combination(partial_config,
                                            model_prop.n_buoy_p_set)
        selection, n_buoys = selection_treatment(partial_config, selection)

        model_prop.actual_config = selection

        model_prop.insert_buoys(selection, n_buoys)

        model_prop.static_run(0)
        if model_prop.stop_running:
            print(f"\n{model_prop.case} - Failed.")
            return

        k += 1

    # Setting anodes, dead weights, if applicable
    model_prop.insert_weights()

    min_over_length, max_over_length = over_length
    min_clearance, max_clearance = clearance
    min_vcm_rotation, max_vcm_rotation = vcm_rotation
    min_rel_height, max_rel_height = camelback_rel_height

    while not model_prop.aprooved or not model_prop.stop_running:

        model_prop.static_run(0)
        if model_prop.stop_running:
            print(f"\n{model_prop.case} - Failed.")
            return

        # CRITERIA - Clearance between line and seabed
        if model_prop.clearance < min_clearance \
            or model_prop.clearance > max_clearance:

            if model_prop.clearance < min_clearance / 2:
                delta = - payout_retrieve

            elif model_prop.clearance < min_clearance:
                delta = - payout_retrieve / 5

            elif model_prop.clearance > max_clearance:

                if model_prop.dvc_type == 2 \
                    and model_prop.over_length < min_over_length:
                    model_prop.move_links()

                elif model_prop.dvc_type == 2:
                    delta = payout_retrieve

                else:
                    delta = model_prop.clearance

            model_prop.payout_retrieve(delta)
            model_prop.run_counter -= 1

            continue

        # CRITERIA - VCM rotation closest to 0
        if model_prop.vcm_rotation > max_vcm_rotation \
            or model_prop.vcm_rotation < min_vcm_rotation:

            # buoys position (without reppeated values)
            unique_positions = list(
                Counter(model_prop.actual_config[0]).keys())

            # Saves configurations already tested
            if model_prop.actual_config not in model_prop.configs:
                model_prop.configs.append(model_prop.actual_config)

            # Define idx where to change buoy position or increase buoyancy
            ptr, near_limit, far_limit = model_prop.make_pointer(unique_positions)

            if model_prop.vcm_rotation > max_vcm_rotation:

                if unique_positions[ptr] > far_limit[ptr]:

                    new_pos = [b_pos - buoy_position_variation 
                               for b_pos in unique_positions]
                    model_prop.move_buoys(new_pos, ptr)
                    model_prop.run_counter -= 1

                else:
                    model_prop.manage_buoy_changing()

            elif model_prop.vcm_rotation < min_vcm_rotation \
                or (model_prop.dvc_type == 2 \
                    and (model_prop.camelback_height < vcm_a + min_rel_height \
                         or model_prop.over_length < min_over_length)):

                if unique_positions[ptr] < near_limit[ptr]:

                    new_pos = [b_pos + buoy_position_variation
                               for b_pos in unique_positions]
                    model_prop.move_buoys(new_pos, ptr)
                    model_prop.run_counter -= 1

                else:
                    model_prop.manage_buoy_changing()

        # CRITERIA - Over Length
        elif model_prop.dvc_type == 2 \
            and (max_over_length < model_prop.over_length < min_over_length):

            model_prop.move_links()

        # CRITERIA - Final adjustment of flange's height
        elif isclose(model_prop.delta_flange, 0, abs_tol=ATOL):

            # Sometimes, is good to retry some tentatives
            if model_prop.delta_flange > .1:
                model_prop.configs.clear()

            old_length = round(model_prop.winch.StageValue[0], ATOL)
            new_length = round(
                model_prop.winch.StageValue[0] + model_prop.delta_flange, ATOL)

            model_prop.winch.StageValue[0] = round(
                model_prop.winch.StageValue[0] - model_prop.delta_flange, ATOL)

            print(
                "\n"
                f"{model_prop.case} - Adjusting winch length"
                f"{old_length} -> {new_length}"
                )

        else:
            model_prop.final_check()

    if model_prop.aprooved:
        print(
            f"\n"
            f"{model_prop.case} - Static Calculation Succesful"
        )

        destiny_path = os.path.join()