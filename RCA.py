# -----------------------------------------------------------------------------------------------------------------------
# Name:        Riparian Condition Assessment (RCA)
# Purpose:     Models floodplain/riparian area condition using three inputs: riparian departure,
#              land use intensity, and floodplain accessibility
#
# Author:      Jordan Gilbert
#
# Created:     11/2015
# Latest Update: 08/31/2017
# Copyright:   (c) Jordan Gilbert 2017
# Licence:     This work is licensed under the Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International
#              License. To view a copy of this license, visit http://creativecommons.org/licenses/by-nc-sa/4.0/.
# -----------------------------------------------------------------------------------------------------------------------

import arcpy
from arcpy.sa import *
import sys
import os
import numpy as np
import skfuzzy as fuzz
from skfuzzy import control as ctrl
from math import pi
import projectxml
import uuid
import datetime
from SupportingFunctions import *


def main(
    projName,
    hucID,
    hucName,
    output_folder,
    ex_veg,
    hist_veg,
    seg_network,
    frag_valley,
    lg_river,
    dredge_tailings,
    confin_thresh,
    outName):
    """ Calculates riparian condition for a stream network based on RVD, confinement, vegetation, and valley connectivity
    :param projName: Project name for XML metadata
    :param hucID: Huc ID for XML metadata
    :param hucName: watershed name for XML metadata
    :param output_folder: Output folder for current RCAT run with format "Output_**"
    :param ex_veg: Existing vegetation raster with VEGETATED field
    :param hist_veg: Historic vegetation raster with VEGETATED field
    :param seg_network: Segmented stream network from the confinement tool
    :param frag_valley: Fragmented valley bottom shapefile
    :param lg_river: Large river polygon shapefile
    :param dredge_tailings: Dredge tailings polygon shapefile
    :param confin_thresh: Confinement threshold for calculating riparian condition
    :param outName: Name for output network
    return: Output network with Riparian Condition fields
    """
    projPath = os.path.dirname(os.path.dirname(output_folder))
    scratch = os.path.join(projPath, 'Temp')
    if not os.path.exists(scratch):
        os.mkdir(scratch)
    arcpy.env.workspace = 'in_memory'
    
    arcpy.env.overwriteOutput = True
    arcpy.CheckOutExtension("spatial")

    # double check all needed fields
    check_fields(frag_valley, seg_network, ex_veg, hist_veg)

    # find thiessen polygons clipped to the extent of a buffered valley bottom, or create if not existent
    intermediates_folder = os.path.join(output_folder, "01_Intermediates")
    thiessen_valley = os.path.join(intermediates_folder, "02_ValleyThiessen/Thiessen_Valley_Clip.shp")
    if not os.path.exists(thiessen_valley):
        arcpy.AddMessage("Creating thiessen polygons...")
        create_thiessen_polygons_in_valley(seg_network, frag_valley, intermediates_folder, scratch)
    else:
        thiessen_fields = [f.name for f in arcpy.ListFields(thiessen_valley)]
        if "RCH_FID" not in thiessen_fields:
            arcpy.AddField_management(thiessen_valley, "RCH_FID", "SHORT")
            with arcpy.da.UpdateCursor(thiessen_valley, ["ORIG_FID", "RCH_FID"]) as cursor:
                for row in cursor:
                    row[1] = row[0]
                    cursor.updateRow(row)

    # rca output folder
    analysis_dir = os.path.join(output_folder, "02_Analyses")
    rca_out_dir = os.path.join(analysis_dir, find_available_num_prefix(analysis_dir)+"_RCA")
    make_folder(rca_out_dir)
    # create rca input network and output directory
    fcOut = output_folder + "/rca_table.shp"
    arcpy.CopyFeatures_management(seg_network, fcOut)

    # add model input attributes to input network
    arcpy.AddMessage("Assessing land use intensity...")
    calc_lui(ex_veg, thiessen_valley, intermediates_folder, fcOut)

    arcpy.AddMessage("Assessing floodplain connectivity...")
    calc_connectivity(frag_valley, thiessen_valley, fcOut, dredge_tailings, ex_veg, intermediates_folder, scratch)
    arcpy.AddMessage("Assessing overall vegetation departure...")
    calc_veg(ex_veg, hist_veg, thiessen_valley, intermediates_folder, fcOut)

    # # # calculate rca for segments in unconfined valleys # # #
    arcpy.AddMessage("Calculating riparian condition for segments in unconfined valleys...")

    arcpy.MakeFeatureLayer_management(fcOut, "rca_in_lyr")
    arcpy.SelectLayerByAttribute_management("rca_in_lyr", "NEW_SELECTION", '"CONF_RATIO" < {0}'.format(confin_thresh))
    #arcpy.SelectLayerByAttribute_management("rca_in_lyr", "NEW_SELECTION", """ Con_Type != "BOTH" """)
    arcpy.FeatureClassToFeatureClass_conversion("rca_in_lyr", scratch, "rca_u")
    rca_u = scratch + "/rca_u.shp"

    ct = arcpy.GetCount_management(rca_u)
    count = int(ct.getOutput(0))
    if count is not 0:

        # fix values outside of range of membership functions.
        cursor = arcpy.da.UpdateCursor(rca_u, ["NATIV_DEP", "LUI", "CONNECT"])
        for row in cursor:
            if row[0] < 0:
                row[0] = 0.01
            elif row[0] > 1:
                row[0] = 1
            elif row[1] < 0:
                row[1] = 0.01
            elif row[1] > 1:
                row[3] = 1
            elif row[2] < 0:
                row[2] = 0.01
            elif row[2] > 1:
                row[2] = 1
            cursor.updateRow(row)
        del row
        del cursor

        # get arrays from the fields of interest
        RVDa = arcpy.da.FeatureClassToNumPyArray(rca_u, "NATIV_DEP")
        LUIa = arcpy.da.FeatureClassToNumPyArray(rca_u, "LUI")
        CONNECTa = arcpy.da.FeatureClassToNumPyArray(rca_u, "CONNECT")

        # convert the data type of the arrays
        RVDarray = np.asarray(RVDa, np.float64)
        LUIarray = np.asarray(LUIa, np.float64)
        CONNECTarray = np.asarray(CONNECTa, np.float64)

        del RVDa, LUIa, CONNECTa

        # set up FIS
        RVD = ctrl.Antecedent(np.arange(0, 1, 0.01), "input1")
        LUI = ctrl.Antecedent(np.arange(0, 1, 0.01), "input2")
        CONNECT = ctrl.Antecedent(np.arange(0, 1, 0.01), "input3")
        CONDITION = ctrl.Consequent(np.arange(0, 1, 0.01), "result")

        RVD["large"] = fuzz.trapmf(RVD.universe, [0, 0, 0.3, 0.5])
        RVD["significant"] = fuzz.trimf(RVD.universe, [0.3, 0.5, 0.85])
        RVD["minor"] = fuzz.trimf(RVD.universe, [0.5, 0.85, 0.95])
        RVD["negligible"] = fuzz.trapmf(RVD.universe, [0.85, 0.95, 1, 1])

        LUI["low"] = fuzz.trapmf(LUI.universe, [0, 0, 0.017, 0.17])
        LUI["moderate"] = fuzz.trapmf(LUI.universe, [0.017, 0.17, 0.416, 0.583])
        LUI["high"] = fuzz.trapmf(LUI.universe, [0.416, 0.583, 1, 1])

        CONNECT["low"] = fuzz.trapmf(CONNECT.universe, [0, 0, 0.5, 0.7])
        CONNECT["moderate"] = fuzz.trapmf(CONNECT.universe, [0.5, 0.7, 0.9, 0.95])
        CONNECT["high"] = fuzz.trapmf(CONNECT.universe, [0.9, 0.95, 1, 1])

        CONDITION["very poor"] = fuzz.trapmf(CONDITION.universe, [0, 0, 0.1, 0.25])
        CONDITION["poor"] = fuzz.trapmf(CONDITION.universe, [0.1, 0.25, 0.35, 0.5])
        CONDITION["moderate"] = fuzz.trimf(CONDITION.universe, [0.35, 0.5, 0.8])
        CONDITION["good"] = fuzz.trimf(CONDITION.universe, [0.5, 0.8, 0.95])
        CONDITION["intact"] = fuzz.trapmf(CONDITION.universe, [0.8, 0.95, 1, 1])

        rule0 = ctrl.Rule(RVD['large'] & LUI['low'] & CONNECT['low'], CONDITION['poor'])
        rule1 = ctrl.Rule(RVD['large'] & LUI['low'] & CONNECT['moderate'], CONDITION['poor']) #
        rule2 = ctrl.Rule(RVD['large'] & LUI['low'] & CONNECT['high'], CONDITION['moderate']) #
        rule3 = ctrl.Rule(RVD['large'] & LUI['moderate'] & CONNECT['low'], CONDITION['poor'])
        rule4 = ctrl.Rule(LUI['moderate'] & CONNECT['moderate'], CONDITION['moderate'])
        rule5 = ctrl.Rule(RVD['large'] & LUI['moderate'] & CONNECT['high'], CONDITION['poor']) #
        rule6 = ctrl.Rule(RVD['large'] & LUI['high'] & CONNECT['low'], CONDITION['very poor'])
        rule6_1 = ctrl.Rule((RVD['significant'] | RVD['minor'] | RVD['negligible']) & LUI['high'] & CONNECT['low'], CONDITION['poor'])
        rule7 = ctrl.Rule(LUI['high'] & CONNECT['moderate'], CONDITION['poor'])
        rule8 = ctrl.Rule(LUI['high'] & CONNECT['high'], CONDITION['moderate'])
        rule9 = ctrl.Rule(RVD['significant'] & LUI['low'] & CONNECT['low'], CONDITION['moderate'])
        rule10 = ctrl.Rule(RVD['significant'] & LUI['low'] & CONNECT['moderate'], CONDITION['moderate'])
        rule11 = ctrl.Rule(RVD['significant'] & LUI['low'] & CONNECT['high'], CONDITION['good'])
        rule12 = ctrl.Rule(RVD['significant'] & LUI['moderate'] & CONNECT['low'], CONDITION['poor'])
        rule13 = ctrl.Rule(RVD['significant'] & LUI['moderate'] & CONNECT['high'], CONDITION['moderate'])
        rule14 = ctrl.Rule(RVD['minor'] & LUI['low'] & CONNECT['low'], CONDITION['moderate'])
        rule15 = ctrl.Rule(RVD['minor'] & LUI['low'] & CONNECT['moderate'], CONDITION['good'])
        rule16 = ctrl.Rule(RVD['minor'] & LUI['low'] & CONNECT['high'], CONDITION['intact'])
        rule17 = ctrl.Rule(RVD['minor'] & LUI['moderate'] & CONNECT['low'], CONDITION['moderate'])
        rule18 = ctrl.Rule(RVD['minor'] & LUI['moderate'] & CONNECT['high'], CONDITION['moderate'])
        rule19 = ctrl.Rule(RVD['negligible'] & LUI['low'] & CONNECT['low'], CONDITION['moderate'])
        rule20 = ctrl.Rule(RVD['negligible'] & LUI['low'] & CONNECT['moderate'], CONDITION['good'])
        rule21 = ctrl.Rule(RVD['negligible'] & LUI['low'] & CONNECT['high'], CONDITION['intact'])
        rule22 = ctrl.Rule(RVD['negligible'] & LUI['moderate'] & CONNECT['low'], CONDITION['moderate'])
        rule23 = ctrl.Rule(RVD['negligible'] & LUI['moderate'] & CONNECT['high'], CONDITION['good'])

        rca_ctrl = ctrl.ControlSystem([rule0, rule1, rule2, rule3, rule4, rule5, rule6, rule6_1, rule7, rule8, rule9, rule10, rule11, rule12, rule13, rule14, rule15, rule16, rule17, rule18, rule19, rule20, rule21, rule22, rule23])
        rca_fis = ctrl.ControlSystemSimulation(rca_ctrl)

        # Defuzzify
        out = np.zeros(len(RVDarray))
        for i in range(len(out)):
            rca_fis.input["input1"] = RVDarray[i]
            rca_fis.input["input2"] = LUIarray[i]
            rca_fis.input["input3"] = CONNECTarray[i]
            rca_fis.compute()
            out[i] = rca_fis.output["result"]

        # save the output text file and merge to network
        fid = np.arange(0, len(out), 1)
        columns = np.column_stack((fid, out))
        out_table = os.path.dirname(fcOut) + "/RCA_Table.txt"
        np.savetxt(out_table, columns, delimiter=",", header="ID, COND_VAL", comments="")

        final_table = scratch + "/final_table.dbf"
        arcpy.CopyRows_management(out_table, final_table)

        arcpy.JoinField_management(rca_u, "FID", final_table, "ID", "COND_VAL")
        rca_u_final = scratch + "/rca_u_final.shp"
        arcpy.CopyFeatures_management(rca_u, rca_u_final)

    else:
        raise Exception("There are no 'unconfined' segments to assess using FIS. Lower width threshold parameter.")

    # # # calculate rca for segments in confined valleys # # #
    arcpy.AddMessage("Calculating riparian condition for segments in confined valleys...")
    arcpy.SelectLayerByAttribute_management("rca_in_lyr", "NEW_SELECTION", '"CONF_RATIO" >= {0}'.format(confin_thresh))
    #arcpy.SelectLayerByAttribute_management("rca_in_lyr", "NEW_SELECTION", """ Con_Type == "BOTH" """)
    arcpy.FeatureClassToFeatureClass_conversion("rca_in_lyr", scratch, "rca_c.shp")
    rca_c = scratch + "/rca_c.shp"

    arcpy.AddField_management(rca_c, "CONDITION", "TEXT")
    cursor = arcpy.da.UpdateCursor(rca_c, ["LUI", "CONNECT", "VEG", "CONDITION"])
    for row in cursor:
        if row[0] <= 0.04 and row[1] == 1 and row[2] > 0.8:
            row[3] = "Confined - Unimpacted"
        else:
            row[3] = "Confined - Impacted"
        cursor.updateRow(row)
    del row
    del cursor

    # merge the results of the rca for confined and unconfined valleys
    if not outName.endswith(".shp"):
        outName = outName+".shp"
    tempOut = os.path.join(rca_out_dir, "tempout.shp")
    output = os.path.join(rca_out_dir, outName)

    arcpy.Merge_management([rca_u_final, rca_c], tempOut)

    # add final condition category for each segment
    cursor = arcpy.da.UpdateCursor(tempOut, ["COND_VAL", "CONDITION"])
    for row in cursor:
        if row[0] == 0:
            pass
        elif row[0] > 0 and row[0] <= 0.2:
            row[1] = "Very Poor"
        elif row[0] > 0.2 and row[0] <= 0.4:
            row[1] = "Poor"
        elif row[0] > 0.4 and row[0] <= 0.65:
            row[1] = "Moderate"
        elif row[0] > 0.65 and row[0] <= 0.85:
            row[1] = "Good"
        elif row[0] > 0.85:
            row[1] = "Intact"
        cursor.updateRow(row)
    del row
    del cursor

    # If any segments are found outside of the valley bottom, set the fields to a NoData value
    arcpy.MakeFeatureLayer_management(tempOut, "outlyr")
    arcpy.SelectLayerByLocation_management("outlyr", "HAVE_THEIR_CENTER_IN", frag_valley)
    arcpy.SelectLayerByLocation_management("outlyr", selection_type="SWITCH_SELECTION")
    getcount = arcpy.GetCount_management("outlyr")
    count = int(getcount.getOutput(0))
    if count != 0:
        cursor = arcpy.da.UpdateCursor("outlyr", ["COND_VAL", "CONDITION", "LUI", "EX_VEG", "HIST_VEG", "VEG"])
        for row in cursor:
            row[0] = -9999
            row[1] = "None"
            row[2] = -9999
            row[3] = -9999
            row[4] = -9999
            row[5] = -9999
            cursor.updateRow(row)
        del row
        del cursor
    arcpy.SelectLayerByAttribute_management("outlyr", "CLEAR_SELECTION")
    arcpy.CopyFeatures_management("outlyr", output)

    # temp output and environment clean up
    arcpy.Delete_management(tempOut)
    arcpy.Delete_management(fcOut)
    arcpy.Delete_management(out_table)
    arcpy.CheckInExtension('spatial')

    # write xml
    arcpy.AddMessage("Writing XML file. NOTE: This is the final step and non-critical to the outputs")
    try:
        write_xml(projName, hucID, hucName, projPath, ex_veg, hist_veg, seg_network, frag_valley, lg_river, dredge_tailings, confin_thresh, output)
    except Exception:
        arcpy.AddMessage("Writing the XML file has failed, but RVD outputs are saved. This is a known bug in RCAT and you can proceed to the next step without problems.")
    

def check_fields(frag_valley, seg_network, ex_veg, hist_veg):
    # make sure that the fragmented valley input has a field called "connected"
    valley_fields = [f.name for f in arcpy.ListFields(frag_valley)]
    missing_fields = []
    if "Connected" not in valley_fields:
        missing_fields.append("Valley input has no field 'Connected'")
    # double check that input network has "NATIV_DEP" field from RVD
    network_fields = [f.name for f in arcpy.ListFields(seg_network)]
    if "NATIV_DEP" not in network_fields:
        missing_fields.append("Network has no field 'NATIV_DEP'. Rerun RVD on network")
    # double check that input existing veg has a "LU_CODE" field
    ex_veg_fields = [f.name for f in arcpy.ListFields(ex_veg)]
    if "LU_CODE" not in ex_veg_fields:
        missing_fields.append("Field 'LU_CODE' must be added to existing vegetation raster before RCA can be run")
    # double check both vegetation rasters have "VEGETATED" field
    if "VEGETATED" not in ex_veg_fields:
        missing_fields.append("Field 'VEGETATED' must be added to existing vegetation raster before RCA can be run")
    hist_veg_fields = [f.name for f in arcpy.ListFields(hist_veg)]
    if "VEGETATED" not in hist_veg_fields:
        missing_fields.append("Field 'VEGETATED' must be added to historic vegetation raster before RCA can be run")
    # return messages for each missing field and then raise exception to stop script
    if len(missing_fields) > 0:
        i = 0
        arcpy.AddMessage("------------------------------------------------------------------------------------------")
        while i+1 <= len(missing_fields):
            arcpy.AddMessage(missing_fields[i])
            i += 1
        raise Exception("Required fields missing from input files. See list above to fix missing fields in input data.")
        
    
def create_thiessen_polygons_in_valley(seg_network, valley, intermediates_folder, scratch):
    # find midpoints of all reaches in segmented network
    seg_network_lyr = "seg_network_lyr"
    arcpy.MakeFeatureLayer_management(seg_network, seg_network_lyr)
    midpoints = scratch + "/midpoints.shp"
    arcpy.FeatureVerticesToPoints_management(seg_network, midpoints, "MID")

    # list all fields in midpoints file
    midpoint_fields = [f.name for f in arcpy.ListFields(midpoints)]
    # remove permanent fields from this list
    remove_list = ["FID", "Shape", "OID", "OBJECTID", "ORIG_FID"] # remove permanent fields from list
    for field in remove_list:
        if field in midpoint_fields:
            try:
                midpoint_fields.remove(field)
            except Exception:
                pass
    # delete all miscellaneous fields - with error handling in case Arc won't allow field deletion
    for f in midpoint_fields:
        try:
            arcpy.DeleteField_management(midpoints, f)
        except Exception as err:
            pass
    # create layer from midpoints
    midpoints_lyr = "midpoints_lyr"
    arcpy.MakeFeatureLayer_management(midpoints, midpoints_lyr)

    # create thiessen polygons surrounding reach midpoints
    thiessen_folder = os.path.join(intermediates_folder, "01_MidpointsThiessen")
    if not os.path.exists(thiessen_folder):
        os.mkdir(thiessen_folder)
    thiessen = thiessen_folder + "/midpoints_thiessen.shp"
    arcpy.CreateThiessenPolygons_analysis(midpoints, thiessen, "ALL")

    # buffer fragmented valley bottom
    valley_buf = scratch + "/valley_buf.shp"
    valley_lyr = 'valley_lyr'
    arcpy.MakeFeatureLayer_management(in_features=valley, out_layer=valley_lyr) #convert valley buffer to layer - JLW
    arcpy.Buffer_analysis(valley_lyr, valley_buf, "30 Meters", "FULL", "ROUND", "ALL")

    # clip thiessen polygons to buffered valley bottom
    thiessen_valley_folder = os.path.join(intermediates_folder, "02_ValleyThiessen")
    if not os.path.exists(thiessen_valley_folder):
        os.mkdir(thiessen_valley_folder)
    thiessen_clip = thiessen_valley_folder + "/Thiessen_Valley_Clip.shp"
    arcpy.Clip_analysis(thiessen, valley_buf, thiessen_clip)

    # convert multipart features to single part
    arcpy.AddField_management(thiessen_clip, "RCH_FID", "SHORT")
    with arcpy.da.UpdateCursor(thiessen_clip, ["ORIG_FID", "RCH_FID"]) as cursor:
        for row in cursor:
            row[1] = row[0]
            cursor.updateRow(row)
    thiessen_singlepart = scratch + "/Thiessen_Valley_Singlepart.shp"
    arcpy.MultipartToSinglepart_management(thiessen_clip, thiessen_singlepart)
    valley_single_lyr = arcpy.MakeFeatureLayer_management(in_features=thiessen_singlepart)

    # Select only polygon features that intersect network midpoints
    thiessen_select = arcpy.SelectLayerByLocation_management(valley_single_lyr, "INTERSECT", midpoints_lyr,
                                                             selection_type="NEW_SELECTION")
    thiessen_valley = thiessen_valley_folder + "/Thiessen_Valley.shp"
    arcpy.CopyFeatures_management(thiessen_select, thiessen_valley)
    return thiessen_valley, valley_buf


def calc_lui(ex_veg, thiessen_valley, intermediates_folder, fcOut):
    lui_lookup = Lookup(ex_veg, "LU_CODE")
    lui_zs = ZonalStatisticsAsTable(thiessen_valley, "RCH_FID", lui_lookup, "lui_zs", statistics_type="MEAN")
    ex_veg_folder = os.path.join(intermediates_folder, "03_VegetationRasters", "01_Ex_Veg")
    lui_lookup.save(ex_veg_folder + "/Land_Use_Intensity.tif")
    arcpy.JoinField_management(fcOut, "FID", lui_zs, "RCH_FID", "MEAN")
    arcpy.AddField_management(fcOut, "LUI", "DOUBLE")
    cursor = arcpy.da.UpdateCursor(fcOut, ["MEAN", "LUI"])
    for row in cursor:
        row[1] = row[0]
        cursor.updateRow(row)
    del row
    del cursor
    arcpy.DeleteField_management(fcOut, "MEAN")

    return


def calc_connectivity(frag_valley, thiessen_valley, fcOut, dredge_tailings, ex_veg, intermediates_folder, scratch):
    # set raster environment
    arcpy.env.extent = ex_veg
    arcpy.env.snapRaster = ex_veg
    
    # set up folder structure
    connect_folder = os.path.join(intermediates_folder, find_available_num_prefix(intermediates_folder)+ "_Connectivity")
    make_folder(connect_folder)
    if dredge_tailings is not None:
        fp_conn = scratch + '/fp_conn'
        arcpy.PolygonToRaster_conversion(frag_valley, "Connected", fp_conn, "", "", 10)

        dredge_tailings_dissolved = arcpy.Dissolve_management(dredge_tailings)
        arcpy.env.extent = thiessen_valley
        dredge_tailings_raster = ExtractByMask(fp_conn, dredge_tailings_dissolved)

        dredge_tailings_reclass = Reclassify(dredge_tailings_raster, "VALUE", "0 8; 1 8; NODATA 0")
        connect_mine_calc = dredge_tailings_reclass + fp_conn
        fp_conn_out = Reclassify(connect_mine_calc, "VALUE", "0 0; 1 1; 8 0; 9 0")
        fp_conn_out.save(connect_folder + '/Floodplain_Connectivity.tif')
    else:
        fp_conn_out = connect_folder + '/Floodplain_Connectivity.tif'
        arcpy.PolygonToRaster_conversion(frag_valley, "Connected", fp_conn_out, "", "", 10)

    fp_conn_zs = ZonalStatisticsAsTable(thiessen_valley, "RCH_FID", fp_conn_out, "fp_conn_zs", statistics_type="MEAN")

    arcpy.JoinField_management(fcOut, "FID", fp_conn_zs, "RCH_FID", "MEAN")
    arcpy.AddField_management(fcOut, "CONNECT", "DOUBLE")
    cursor = arcpy.da.UpdateCursor(fcOut, ["MEAN", "CONNECT"])
    for row in cursor:
        row[1] = row[0]
        cursor.updateRow(row)
    del row
    del cursor
    arcpy.DeleteField_management(fcOut, "MEAN")

    return


def calc_veg(ex_veg, hist_veg, thiessen_valley, intermediates_folder, fcOut):
    # set up vegetation intermediates folder structure
    veg_rasters_folder = intermediates_folder + "/03_VegetationRasters"
    ex_veg_folder = veg_rasters_folder + "/01_Ex_Veg"
    hist_veg_folder = veg_rasters_folder + "/02_Hist_Veg"
    folders = veg_rasters_folder, ex_veg_folder, hist_veg_folder
    for f in folders:
        if not os.path.exists(f):
            os.mkdir(f)
    # make lookup raster for existing and historic VEGETATED
    exveg_lookup = Lookup(ex_veg, "VEGETATED")
    exveg_lookup.save(ex_veg_folder+"/Existing_Vegetated.tif")
    histveg_lookup = Lookup(hist_veg, "VEGETATED")
    histveg_lookup.save(hist_veg_folder+"/Hist_Vegetated.tif")

    exveg_zs = ZonalStatisticsAsTable(thiessen_valley, "RCH_FID", exveg_lookup, "exveg_zs", statistics_type="MEAN")
    histveg_zs = ZonalStatisticsAsTable(thiessen_valley, "RCH_FID", histveg_lookup, "histveg_zs", statistics_type="MEAN")

    arcpy.JoinField_management(fcOut, "FID", exveg_zs, "RCH_FID", "MEAN")
    arcpy.AddField_management(fcOut, "EX_VEG", "DOUBLE")
    cursor = arcpy.da.UpdateCursor(fcOut, ["MEAN", "EX_VEG"])
    for row in cursor:
        row[1] = row[0]
        cursor.updateRow(row)
        if row[1] == 0:
            row[1] = 0.0001
        cursor.updateRow(row)
    del row
    del cursor
    arcpy.DeleteField_management(fcOut, "MEAN")

    arcpy.JoinField_management(fcOut, "FID", histveg_zs, "RCH_FID", "MEAN")
    arcpy.AddField_management(fcOut, "HIST_VEG", "DOUBLE")
    cursor = arcpy.da.UpdateCursor(fcOut, ["MEAN", "HIST_VEG"])
    for row in cursor:
        row[1] = row[0]
        cursor.updateRow(row)
        if row[1] == 0:
            row[1] = 0.0001
        cursor.updateRow(row)
    del row
    del cursor
    arcpy.DeleteField_management(fcOut, "MEAN")

    arcpy.AddField_management(fcOut, "VEG", "DOUBLE")
    cursor = arcpy.da.UpdateCursor(fcOut, ["EX_VEG", "HIST_VEG", "VEG"])
    for row in cursor:
        row[2] = row[0] / row[1]
        cursor.updateRow(row)
    del row
    del cursor

    return


def write_xml(projName, hucID, hucName, projPath, ex_veg, hist_veg, seg_network, frag_valley, lg_river, dredge_tailings, confin_thresh, output):
    """ Writes project XML file to document all input paths and other metadata """
    xmlfile = projPath + "/RCAproject.rs.xml" # xml file name
    if not os.path.exists(projPath + "/project.rs.xml"):
        # initiate xml file creation
        newxml = projectxml.ProjectXML(xmlfile, "RCA", projName)

        if not hucID == None:
            newxml.addMeta("HUCID", hucID, newxml.project)
        if not hucID == None:
            idlist = [int(x) for x in str(hucID)]
            if idlist[0] == 1 and idlist[1] == 7:
                newxml.addMeta("Region", "CRB", newxml.project)
        if not hucName == None:
            newxml.addMeta("Watershed", hucName, newxml.project)

        newxml.addRCARealization("RCA Realization 1", rid="RZ1", dateCreated=datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                 productVersion="1.0.11", guid=getUUID())

        newxml.addParameter("confin_thresh", confin_thresh, newxml.RCArealizations[0])

        # add inputs and outputs to xml file
        newxml.addProjectInput("Raster", "Existing Cover", ex_veg[ex_veg.find("01_Inputs"):], iid="EXCOV1",
                               guid=getUUID())
        newxml.addRCAInput(newxml.RCArealizations[0], "Existing Vegetation", ref="EXCOV1")

        newxml.addProjectInput("Raster", "Historic Cover", hist_veg[hist_veg.find("01_Inputs"):], iid="HISTCOV1",
                               guid=getUUID())
        newxml.addRCAInput(newxml.RCArealizations[0], "Historic Vegetation", ref="HISTCOV1")

        newxml.addProjectInput("Vector", "Segmented Network", seg_network[seg_network.find("01_Inputs"):], iid="NETWORK1",
                               guid=getUUID())
        newxml.addRCAInput(newxml.RCArealizations[0], "Network", ref="NETWORK1")

        newxml.addProjectInput("Vector", "Fragmented Valley Bottom", frag_valley[frag_valley.find("01_Inputs"):], iid="VALLEY1",
                               guid=getUUID())
        newxml.addRCAInput(newxml.RCArealizations[0], "Fragmented Valley", ref="VALLEY1")

        if lg_river is not None:
            newxml.addProjectInput("Vector", "Large River Polygon", lg_river[lg_river.find("01_Inputs"):], iid="LRP1", guid=getUUID())
            newxml.addRCAInput(newxml.RCArealizations[0], "LRP", ref="LRP1")

        if dredge_tailings is not None:
            newxml.addProjectInput("Vector", "Mining Polygon", dredge_tailings[dredge_tailings.find("01_Inputs"):], iid="dredge_tailings1", guid=getUUID())
            newxml.addRCAInput(newxml.RCArealizations[0], "dredge_tailings", ref="dredge_tailings1")

        newxml.addRCAInput(newxml.RCArealizations[0], "Existing Raster", "Existing Riparian",
                           path=os.path.dirname(os.path.dirname(ex_veg[ex_veg.find("01_Inputs"):])) + "/Ex_Rasters/Ex_Riparian.tif", guid=getUUID())
        newxml.addRCAInput(newxml.RCArealizations[0], "Historic Raster", "Historic Riparian",
                           path=os.path.dirname(os.path.dirname(hist_veg[hist_veg.find("01_Inputs"):])) + "/Hist_Rasters/Hist_Riparian.tif", guid=getUUID())
        newxml.addRCAInput(newxml.RCArealizations[0], "Existing Raster", "Existing Vegetation Cover",
                           path=os.path.dirname(os.path.dirname(ex_veg[ex_veg.find("01_Inputs"):])) + "/Ex_Rasters/Ex_Veg_Cover.tif", guid=getUUID())
        newxml.addRCAInput(newxml.RCArealizations[0], "Historic Raster", "Historic Vegetation Cover",
                           path=os.path.dirname(os.path.dirname(hist_veg[hist_veg.find("01_Inputs")])) + "/Hist_Rasters/Hist_Veg_Cover.tif", guid=getUUID())
        newxml.addRCAInput(newxml.RCArealizations[0], "Existing Raster", "Land Use Intensity",
                           path=os.path.dirname(os.path.dirname(ex_veg[ex_veg.find("01_Inputs"):])) + "/Ex_Rasters/Land_Use_Intensity.tif", guid=getUUID())
        newxml.addRCAInput(newxml.RCArealizations[0], "Thiessen Polygons", "Thiessen Polygons",
                           path=os.path.dirname(seg_network[seg_network.find("01_Inputs")]) + "/Thiessen/Thiessen_Valley.shp", guid=getUUID())

        newxml.addOutput("RCA Analysis", "Vector", "RCA", output[output.find("02_Analyses"):], newxml.RCArealizations[0], guid=getUUID())

        newxml.write()

    else:
        exxml = projectxml.ExistingXML(xmlfile)

        rcar = exxml.rz.findall("RCA")

        rname = []
        for x in range(len(rcar)):
            name = rcar[x].find("Name")
            rname.append(name.text)
        rnum = []
        for y in range(len(rname)):
            num = int(rname[y][-1])
            rnum.append(num)

        k = 2
        while k in rnum:
            k += 1

        exxml.addRCARealization("RCA Realization " + str(k), rid="RZ" + str(k),
                                dateCreated=datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), productVersion="1.0.11",
                                guid=getUUID())

        exxml.addParameter("confin_thresh", confin_thresh, exxml.RCArealizations[0])

        inputs = exxml.root.find("Inputs")

        raster = inputs.findall("Raster")
        rasterid = range(len(raster))
        for i in range(len(raster)):
            rasterid[i] = raster[i].get("id")
        rasterpath = range(len(raster))
        for i in range(len(raster)):
            rasterpath[i] = raster[i].find("Path").text

        for i in range(len(rasterpath)):
            if os.path.abspath(rasterpath[i]) == os.path.abspath(ex_veg[ex_veg.find("01_Inputs"):]):
                EV = exxml.root.findall(".//ExistingVegetation")
                for x in range(len(EV)):
                    if EV[x].attrib['ref'] == rasterid[i]:
                        r = EV[x].findall(".//Raster")
                        exrip_guid = r[0].attrib['guid']
                        excov_guid = r[1].attrib['guid']
                        exlui_guid = r[2].attrib['guid']
                    else:
                        r = []
                exxml.addRCAInput(exxml.RCArealizations[0], "Existing Vegetation", ref=str(rasterid[i]))
                if len(r) > 0:
                    exxml.addRCAInput(exxml.RCArealizations[0], "Existing Raster", "Existing Riparian",
                                      path=os.path.dirname(os.path.dirname(rasterpath[i][rasterpath[i].find("01_Inputs"):])) + "/Ex_Rasters/Ex_Riparian.tif",
                                      guid=exrip_guid)
                    exxml.addRCAInput(exxml.RCArealizations[0], "Existing Raster", "Existing Vegetation Cover",
                                      path=os.path.dirname(os.path.dirname(rasterpath[i][rasterpath[i].find("01_Inputs"):])) + "/Ex_Rasters/Ex_Veg_Cover.tif",
                                      guid=excov_guid)
                    exxml.addRCAInput(exxml.RCArealizations[0], "Existing Raster", "Land Use Intensity",
                                      path=os.path.dirname(os.path.dirname(rasterpath[i][rasterpath[i].find("01_Inputs"):])) + "/Ex_Rasters/Land_Use_Intensity.tif",
                                      guid=exlui_guid)
                else:
                    exxml.addRCAInput(exxml.RCArealizations[0], "Existing Raster", "Existing Riparian",
                                      path=os.path.dirname(os.path.dirname(rasterpath[i][rasterpath[i].find("01_Inputs"):])) + "/Ex_Rasters/Ex_Riparian.tif")
                    exxml.addRCAInput(exxml.RCArealizations[0], "Existing Raster", "Existing Vegetation Cover",
                                      path=os.path.dirname(os.path.dirname(rasterpath[i][rasterpath[i].find("01_Inputs"):])) + "/Ex_Rasters/Ex_Veg_Cover.tif")
                    exxml.addRCAInput(exxml.RCArealizations[0], "Existing Raster", "Land Use Intensity",
                                      path=os.path.dirname(os.path.dirname(rasterpath[i][rasterpath[i].find("01_Inputs"):])) + "/Ex_Rasters/Land_Use_Intensity.tif")
            elif os.path.abspath(rasterpath[i]) == os.path.abspath(hist_veg[hist_veg.find("01_Inputs"):]):
                HV = exxml.root.findall(".//HistoricVegetation")
                for x in range(len(HV)):
                    if HV[x].attrib['ref'] == rasterid[i]:
                        r = HV[x].findall(".//Raster")
                        histrip_guid = r[0].attrib['guid']
                        histcov_guid = r[1].attrib['guid']
                    else:
                        r = []
                exxml.addRCAInput(exxml.RCArealizations[0], "Historic Vegetation", ref=str(rasterid[i]))
                if len(r) > 0:
                    exxml.addRCAInput(exxml.RCArealizations[0], "Historic Raster", "Historic Riparian",
                                      path=os.path.dirname(os.path.dirname(rasterpath[i][rasterpath[i].find("01_Inputs"):])) + "/Hist_Rasters/Hist_Riparian.tif",
                                      guid=histrip_guid)
                    exxml.addRCAInput(exxml.RCArealizations[0], "Historic Raster", "Historic Vegetation Cover",
                                      path=os.path.dirname(os.path.dirname(rasterpath[i][rasterpath[i].find("01_Inputs"):])) + "/Hist_Rasters/Hist_Veg_Cover.tif",
                                      guid=histcov_guid)
                else:
                    exxml.addRCAInput(exxml.RCArealizations[0], "Historic Raster", "Historic Riparian",
                                      path=os.path.dirname(os.path.dirname(rasterpath[i][rasterpath[i].find("01_Inputs"):])) + "/Hist_Rasters/Hist_Riparian.tif")
                    exxml.addRCAInput(exxml.RCArealizations[0], "Historic Raster", "Historic Vegetation Cover",
                                      path=os.path.dirname(os.path.dirname(rasterpath[i][rasterpath[i].find("01_Inputs"):])) + "/Hist_Rasters/Hist_Veg_Cover.tif")

        nlist = []
        for j in rasterpath:
            if os.path.abspath(ex_veg[ex_veg.find("01_Inputs"):]) == os.path.abspath(j):
                nlist.append("yes")
            else:
                nlist.append("no")
        if "yes" in nlist:
            pass
        else:
            exxml.addProjectInput("Raster", "Existing Cover", ex_veg[ex_veg.find("01_Inputs"):], iid="EXCOV" + str(k), guid=getUUID())
            exxml.addRCAInput(exxml.RCArealizations[0], "Existing Vegetation", ref="EXCOV" + str(k))
            exxml.addRCAInput(exxml.RCArealizations[0], "Existing Raster", "Existing Riparian",
                              path=os.path.dirname(os.path.dirname(ex_veg[ex_veg.find("01_Inputs"):])) + "/Ex_Rasters/Ex_Riparian.tif",
                              guid=getUUID())
            exxml.addRCAInput(exxml.RCArealizations[0], "Existing Raster", "Existing Vegetation Cover",
                              path=os.path.dirname(os.path.dirname(ex_veg[ex_veg.find("01_Inputs"):])) + "/Ex_Rasters/Ex_Veg_Cover.tif",
                              guid=getUUID())
            exxml.addRCAInput(exxml.RCArealizations[0], "Existing Raster", "Land Use Intensity",
                              path=os.path.dirname(os.path.dirname(ex_veg[ex_veg.find("01_Inputs"):])) + "/Ex_Rasters/Land_Use_Intensity.tif",
                              guid=getUUID())
        nlist2 = []
        for j in rasterpath:
            if os.path.abspath(hist_veg[hist_veg.find("01_Inputs"):]) == os.path.abspath(j):
                nlist2.append("yes")
            else:
                nlist2.append("no")
        if "yes" in nlist2:
            pass
        else:
            exxml.addProjectInput("Raster", "Historic Cover", hist_veg[hist_veg.find("01_Inputs"):], iid="HISTCOV" + str(k), guid=getUUID())
            exxml.addRCAInput(exxml.RCArealizations[0], "Historic Vegetation", ref="HISTCOV" + str(k))
            exxml.addRCAInput(exxml.RCArealizations[0], "Historic Raster", "Historic Riparian",
                              path=os.path.dirname(os.path.dirname(hist_veg[hist_veg.find("01_Inputs"):])) + "/Hist_Rasters/Hist_Riparian.tif",
                              guid=getUUID())
            exxml.addRCAInput(exxml.RCArealizations[0], "Historic Raster", "Historic Vegetation Cover",
                              path=os.path.dirname(os.path.dirname(hist_veg[hist_veg.find("01_Inputs"):])) + "/Hist_Rasters/Hist_Veg_Cover.tif",
                              guid=getUUID())
        del nlist, nlist2

        vector = inputs.findall("Vector")
        vectorid = range(len(vector))
        for i in range(len(vector)):
            vectorid[i] = vector[i].get("id")
        vectorpath = range(len(vector))
        for i in range(len(vector)):
            vectorpath[i] = vector[i].find("Path").text

        for i in range(len(vectorpath)):
            if os.path.abspath(vectorpath[i]) == os.path.abspath(seg_network[seg_network.find("01_Inputs"):]):
                DN = exxml.root.findall(".//Network")
                for x in range(len(DN)):
                    if DN[x].attrib['ref'] == vectorid[i]:
                        r = DN[x].findall(".//ThiessenPolygons")
                        thiessen_guid = r[0].attrib['guid']
                    else:
                        r = []
                exxml.addRCAInput(exxml.RCArealizations[0], "Network", ref=str(vectorid[i]))
                if len(r) > 0:
                    exxml.addRCAInput(exxml.RCArealizations[0], "Thiessen Polygons", "Thiessen Polygons",
                                      path=os.path.dirname(vectorpath[i][vectorpath[i].find("01_Inputs"):]) + "/Thiessen/Thiessen_Valley.shp",
                                      guid=thiessen_guid)
                else:
                    exxml.addRCAInput(exxml.RCArealizations[0], "Thiessen Polygons", "Thiessen Polygons",
                                      path=os.path.dirname(vectorpath[i][vectorpath[i].find("01_Inputs"):]) + "/Thiessen/Thiessen_Valley.shp")
            elif os.path.abspath(vectorpath[i]) == os.path.abspath(frag_valley[frag_valley.find("01_Inputs"):]):
                exxml.addRCAInput(exxml.RCArealizations[0], "Fragmented Valley", ref=str(vectorid[i]))
            if lg_river is not None:
                if os.path.abspath(vectorpath[i]) == os.path.abspath(lg_river[lg_river.find("01_Inputs"):]):
                    exxml.addRCAInput(exxml.RCArealizations[0], "LRP", ref=str(vectorid[i]))
            if dredge_tailings is not None:
                if os.path.abspath(vectorpath[i]) == os.path.abspath(dredge_tailings[dredge_tailings.find("01_Inputs"):]):
                    exxml.addRVDInput(exxml.RCArealizations[0], "dredge_tailings", ref=str(vectorid[i]))
        nlist = []
        for j in vectorpath:
            if os.path.abspath(seg_network[seg_network.find("01_Inputs"):]) == os.path.abspath(j):
                nlist.append("yes")
            else:
                nlist.append("no")
        if "yes" in nlist:
            pass
        else:
            exxml.addProjectInput("Vector", "Segmented Network", seg_network[seg_network.find("01_Inputs"):],
                                  iid="NETWORK" + str(k), guid=getUUID())
            exxml.addRCAInput(exxml.RCArealizations[0], "Network", ref="NETWORK" + str(k))
            exxml.addRCAInput(exxml.RCArealizations[0], "Thiessen Polygons", "Thiessen Polygons",
                              path=os.path.dirname(seg_network[seg_network.find("01_Inputs"):]) + "/Thiessen/Thiessen_Valley.shp",
                              guid=getUUID())
        nlist = []
        for j in vectorpath:
            if os.path.abspath(frag_valley[frag_valley.find("01_Inputs"):]) == os.path.abspath(j):
                nlist.append("yes")
            else:
                nlist.append("no")
        if "yes" in nlist:
            pass
        else:
            exxml.addProjectInput("Vector", "Valley Bottom", frag_valley[frag_valley.find("01_Inputs"):],
                                  iid="VALLEY" + str(k), guid=getUUID())
            exxml.addRCAInput(exxml.RCArealizations[0], "Fragmented Valley", ref="VALLEY" + str(k))

        if lg_river is not None:
            nlist = []
            for j in vectorpath:
                if os.path.abspath(lg_river[lg_river.find("01_Inputs"):]) == os.path.abspath(j):
                    nlist.append("yes")
                else:
                    nlist.append("no")
            if "yes" in nlist:
                pass
            else:
                exxml.addProjectInput("Vector", "Large River Polygon", lg_river[lg_river.find("01_Inputs"):],
                                      iid="LRP" + str(k), guid=getUUID())
                exxml.addRCAInput(exxml.RCArealizations[0], "LRP", ref="LRP" + str(k))

        if dredge_tailings is not None:
            nlist = []
            for j in vectorpath:
                if os.path.abspath(dredge_tailings[dredge_tailings.find("01_Inputs"):]) == os.path.abspath(j):
                    nlist.append("yes")
                else:
                    nlist.append("no")
            if "yes" in nlist:
                pass
            else:
                exxml.addProjectInput("Vector", "Mining Polygon", dredge_tailings[dredge_tailings.find("01_Inputs"):], iid="dredge_tailings" + str(k), guid=getUUID())
                exxml.addRVDInput(exxml.RVDrealizations[0], "dredge_tailings", ref="dredge_tailings" + str(k))

        del nlist

        exxml.addOutput("RCA Analysis " + str(k), "Vector", "RCA Output", output[output.find("02_Analyses"):],
                        exxml.RCArealizations[0], guid=getUUID())

        exxml.write()


def getUUID():
    return str(uuid.uuid4()).upper()


if __name__ == '__main__':
    main(sys.argv[1],
        sys.argv[2],
        sys.argv[3],
        sys.argv[4],
        sys.argv[5],
        sys.argv[6],
        sys.argv[7],
        sys.argv[8],
        sys.argv[9],
        sys.argv[10],
        sys.argv[11],
        sys.argv[12])
