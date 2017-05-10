
# -------------------------------------------------------------------------------
# Name:        RVD
# Purpose:     Uses LANDFIRE inputs to assign a riparian condition score to
#              a segmented stream network based on a comparison between the
#              biophysical settings LANDFIRE layer and the existing vegetation
#              type LANDFIRE layer
#
# Author:      Jordan Gilbert
#
# Created:     10/15/2015
# Latest Update: 03/20/2017
# Copyright:   (c) Jordan Gilbert 2017
# Licence:     This work is licensed under the Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International
#              License. To view a copy of this license, visit http://creativecommons.org/licenses/by-nc-sa/4.0/.
# -------------------------------------------------------------------------------

import arcpy
from arcpy.sa import *
import os
import sys
import numpy as np
import projectxml
import uuid
import datetime


def main(
    projName,
    hucID,
    hucName,
    projPath,
    evt,
    bps,
    seg_network,
    valley,
    lg_river,
    outName,
    scratch):

    arcpy.env.overwriteOutput = True
    arcpy.CheckOutExtension("spatial")

    # create thiessen polygons from segmented network input
    arcpy.AddMessage("Creating thiessen polygons")
    midpoints = scratch + "/midpoints"
    arcpy.FeatureVerticesToPoints_management(seg_network, midpoints, "MID")
    midpoint_fields = [f.name for f in arcpy.ListFields(midpoints)]
    midpoint_fields.remove("OBJECTID")
    midpoint_fields.remove("Shape")
    midpoint_fields.remove("ORIG_FID")
    arcpy.DeleteField_management(midpoints, midpoint_fields)

    thiessen = scratch + "/thiessen"
    arcpy.CreateThiessenPolygons_analysis(midpoints, thiessen, "ALL")
    valley_buf = scratch + "/valley_buf"
    arcpy.Buffer_analysis(valley, valley_buf, "30 Meters", "FULL", "ROUND", "ALL")
    if not os.path.exists(os.path.dirname(seg_network) + "/Thiessen"):
        os.mkdir(os.path.dirname(seg_network) + "/Thiessen")
    thiessen_valley = os.path.dirname(seg_network) + "/Thiessen/Thiessen_Valley.shp"
    arcpy.Clip_analysis(thiessen, valley_buf, thiessen_valley)

    # give the landfire rasters riparian vegetation scores and conversion scores
    arcpy.AddMessage("Classifying vegetation data")
    score_vegetation(evt, bps)

    evt_lookup = Lookup(evt, "VEG_SCORE")
    if not os.path.exists(os.path.dirname(os.path.dirname(evt)) + "/Ex_Rasters"):
        os.mkdir(os.path.dirname(os.path.dirname(evt)) + "/Ex_Rasters")
    evt_lookup.save(os.path.dirname(os.path.dirname(evt)) + "/Ex_Rasters/Ex_Riparian.tif")
    bps_lookup = Lookup(bps, "VEG_SCORE")
    if not os.path.exists(os.path.dirname(os.path.dirname(bps)) + "/Hist_Rasters"):
        os.mkdir(os.path.dirname(os.path.dirname(bps)) + "/Hist_Rasters")
    bps_lookup.save(os.path.dirname(os.path.dirname(bps)) + "/Hist_Rasters/Hist_Riparian.tif")

    # create output network
    j = 1
    while os.path.exists(projPath + "/02_Analyses/Output_" + str(j)):
        j += 1

    os.mkdir(projPath + "/02_Analyses/Output_" + str(j))
    fcOut = projPath + "/02_Analyses/Output_" + str(j) + "/" + str(outName) + ".shp"
    tempOut = projPath + "/02_Analyses/Output_" + str(j) + "/tempout.shp"
    arcpy.CopyFeatures_management(seg_network, tempOut)

    # ----------------------------------------------###
    # RVD analysis for areas without large rivers   ###
    # ----------------------------------------------###

    if lg_river == None:
        arcpy.AddMessage("Calculating riparian vegetation departure")
        evt_zs = ZonalStatisticsAsTable(thiessen_valley, "ORIG_FID", evt_lookup, "evt_zs", statistics_type="MEAN")
        bps_zs = ZonalStatisticsAsTable(thiessen_valley, "ORIG_FID", bps_lookup, "bps_zs", statistics_type="MEAN")
        arcpy.JoinField_management(tempOut, "FID", evt_zs, "ORIG_FID", "MEAN")
        arcpy.AddField_management(tempOut, "EVT_MEAN", "DOUBLE")
        cursor = arcpy.da.UpdateCursor(tempOut, ["MEAN", "EVT_MEAN"])
        for row in cursor:
            row[1] = row[0]
            cursor.updateRow(row)
            if row[1] == 0:
                row[1] = 0.0001
            cursor.updateRow(row)
        del row
        del cursor
        arcpy.DeleteField_management(tempOut, "MEAN")
        arcpy.JoinField_management(tempOut, "FID", bps_zs, "ORIG_FID", "MEAN")
        arcpy.AddField_management(tempOut, "BPS_MEAN", "DOUBLE")
        cursor = arcpy.da.UpdateCursor(tempOut, ["MEAN", "BPS_MEAN"])
        for row in cursor:
            row[1] = row[0]
            cursor.updateRow(row)
            if row[1] == 0:
                row[1] = 0.0001
            cursor.updateRow(row)
        del row
        del cursor
        arcpy.DeleteField_management(tempOut, "MEAN")

        arcpy.AddField_management(tempOut, "DEP_RATIO", "DOUBLE")
        cursor = arcpy.da.UpdateCursor(tempOut, ["EVT_MEAN", "BPS_MEAN", "DEP_RATIO"])
        for row in cursor:
            index = row[0]/row[1]
            row[2] = index
            cursor.updateRow(row)
            if row[2] > 1 and row[1] == 0.0001:
                row[2] = 1
            cursor.updateRow(row)
        del row
        del cursor

    # -------------------------------------------###
    # RVD analysis for areas with large rivers   ###
    # -------------------------------------------###

    else:
        arcpy.AddMessage("Calculating riparian vegetation departure")
        arcpy.env.extent = thiessen_valley
        lg_river_raster = ExtractByMask(evt, lg_river)
        cursor5 = arcpy.UpdateCursor(lg_river_raster)
        for row in cursor5:
            row.setValue("VEG_SCORE", 8)
            cursor5.updateRow(row)
        del row
        del cursor5

        river_lookup = Lookup(lg_river_raster, "VEG_SCORE")
        river_reclass = Reclassify(river_lookup, "VALUE", "8 8; NODATA 0")
        evt_calc = river_reclass + evt_lookup
        bps_calc = river_reclass + bps_lookup
        evt_wo_rivers = Reclassify(evt_calc, "VALUE", "0 0; 1 1; 8 NODATA; 9 NODATA")
        bps_wo_rivers = Reclassify(bps_calc, "VALUE", "0 0; 1 1; 8 NODATA; 9 NODATA")

        evt_zs = ZonalStatisticsAsTable(thiessen_valley, "ORIG_FID", evt_wo_rivers, "evt_zs", statistics_type="MEAN")
        bps_zs = ZonalStatisticsAsTable(thiessen_valley, "ORIG_FID", bps_wo_rivers, "bps_zs", statistics_type="MEAN")
        arcpy.JoinField_management(tempOut, "FID", evt_zs, "ORIG_FID", "MEAN")
        arcpy.AddField_management(tempOut, "EVT_MEAN", "DOUBLE")
        cursor = arcpy.da.UpdateCursor(tempOut, ["MEAN", "EVT_MEAN"])
        for row in cursor:
            row[1] = row[0]
            cursor.updateRow(row)
            if row[1] == 0:
                row[1] = 0.0001
            cursor.updateRow(row)
        del row
        del cursor
        arcpy.DeleteField_management(tempOut, "MEAN")

        arcpy.JoinField_management(tempOut, "FID", bps_zs, "ORIG_FID", "MEAN")
        arcpy.AddField_management(tempOut, "BPS_MEAN", "DOUBLE")
        cursor = arcpy.da.UpdateCursor(tempOut, ["MEAN", "BPS_MEAN"])
        for row in cursor:
            row[1] = row[0]
            cursor.updateRow(row)
            if row[1] == 0:
                row[1] = 0.0001
            cursor.updateRow(row)
        del row
        del cursor
        arcpy.DeleteField_management(tempOut, "MEAN")

        arcpy.AddField_management(tempOut, "DEP_RATIO", "DOUBLE")
        cursor = arcpy.da.UpdateCursor(tempOut, ["EVT_MEAN", "BPS_MEAN", "DEP_RATIO"])
        for row in cursor:
            index = row[0]/row[1]
            row[2] = index
            cursor.updateRow(row)
            if row[2] > 1 and row[1] == 0.0001:
                row[2] = 1
            cursor.updateRow(row)
        del row
        del cursor

    # ------------------------------###
    # Riparian Conversion analysis  ###
    # ------------------------------###

    arcpy.AddMessage("Calculating riparian vegetation conversion types")
    evt_conversion_lookup = Lookup(evt, "CONVERSION")
    evt_conversion_lookup.save(os.path.dirname(os.path.dirname(evt)) + "/Ex_Rasters/Ex_Cover.tif")
    bps_conversion_lookup = Lookup(bps, "CONVERSION")
    bps_conversion_lookup.save(os.path.dirname(os.path.dirname(bps)) + "/Hist_Rasters/Hist_Cover.tif")
    conversion_raster = bps_conversion_lookup - evt_conversion_lookup
    int_conversion_raster = Int(conversion_raster)
    remap = "-460 NODATA; -450 NODATA; -400 NODATA; -480 NODATA; -80 NODATA; -60 NODATA; -50 NODATA; -30 NODATA; -20 NODATA; -10 NODATA; 0 0; 10 NODATA; 17 NODATA; 18 NODATA; 19 NODATA; " \
            "20 NODATA; 30 NODATA; 37 NODATA; 38 NODATA; 39 NODATA; 47 NODATA; 48 NODATA; 49 NODATA; 400 NODATA; 450 NODATA; 460 NODATA; 497 NODATA; 498 NODATA; 499 NODATA; 50 50; 60 60; 80 80; 97 97; 98 98; 99 99"
    final_conversion_raster = Reclassify(int_conversion_raster, "VALUE", remap, "NODATA")
    valueList = []
    vcursor = arcpy.SearchCursor(final_conversion_raster)
    for row in vcursor:
        valueList.append(row.getValue("VALUE"))
    if 0 in valueList:
        conversion_0 = Reclassify(final_conversion_raster, "VALUE", "0 1; 50 NODATA; 60 NODATA; 80 NODATA; 97 NODATA; 98 NODATA; 99 NODATA", "NODATA")
    if 50 in valueList:
        conversion_50 = Reclassify(final_conversion_raster, "VALUE", "0 NODATA; 50 1; 60 NODATA; 80 NODATA; 97 NODATA; 98 NODATA; 99 NODATA", "NODATA")
    if 60 in valueList:
        conversion_60 = Reclassify(final_conversion_raster, "VALUE", "0 NODATA; 50 NODATA; 60 1; 80 NODATA; 97 NODATA; 98 NODATA; 99 NODATA", "NODATA")
    if 80 in valueList:
        conversion_80 = Reclassify(final_conversion_raster, "VALUE", "0 NODATA; 50 NODATA; 60 NODATA; 80 1; 97 NODATA; 98 NODATA; 99 NODATA", "NODATA")
    if 97 in valueList:
        conversion_97 = Reclassify(final_conversion_raster, "VALUE", "0 NODATA; 50 NODATA; 60 NODATA; 80 NODATA; 97 1; 98 NODATA; 99 NODATA", "NODATA")
    if 98 in valueList:
        conversion_98 = Reclassify(final_conversion_raster, "VALUE", "0 NODATA; 50 NODATA; 60 NODATA; 80 NODATA; 97 NODATA; 98 1; 99 NODATA", "NODATA")
    if 99 in valueList:
        conversion_99 = Reclassify(final_conversion_raster, "VALUE", "0 NODATA; 50 NODATA; 60 NODATA; 80 NODATA; 97 NODATA; 98 NODATA; 99 1", "NODATA")

    out_conversion_raster = ExtractByMask(final_conversion_raster, valley_buf)

    out_conversion_raster.save(projPath + "/02_Analyses/Output_" + str(j) + "/Conversion_Raster.tif")

    count_table = ZonalStatisticsAsTable(thiessen_valley, "ORIG_FID", final_conversion_raster, "count_table", statistics_type="VARIETY")
    arcpy.JoinField_management(tempOut, "FID", count_table, "ORIG_FID", "COUNT")
    if 0 in valueList:
        table_0 = ZonalStatisticsAsTable(thiessen_valley, "ORIG_FID", conversion_0, "table_0", "", "SUM")
        arcpy.JoinField_management(tempOut, "FID", table_0, "ORIG_FID", "SUM")
        arcpy.AddField_management(tempOut, "sum_noch", "DOUBLE")
        cursor = arcpy.da.UpdateCursor(tempOut, ["SUM", "sum_noch"])
        for row in cursor:
            row[1] = row[0]
            cursor.updateRow(row)
        del row
        del cursor
        arcpy.DeleteField_management(tempOut, "SUM")
    else:
        arcpy.AddField_management(tempOut, "sum_noch", "DOUBLE")
        cursor = arcpy.da.UpdateCursor(tempOut, "sum_noch")
        for row in cursor:
            row[0] = 0
            cursor.updateRow(row)
        del row
        del cursor
    if 50 in valueList:
        table_50 = ZonalStatisticsAsTable(thiessen_valley, "ORIG_FID", conversion_50, "table_50", statistics_type="SUM")
        arcpy.JoinField_management(tempOut, "FID", table_50, "ORIG_FID", "SUM")
        arcpy.AddField_management(tempOut, "sum_grsh", "DOUBLE")
        cursor = arcpy.da.UpdateCursor(tempOut, ["SUM", "sum_grsh"])
        for row in cursor:
            row[1] = row[0]
            cursor.updateRow(row)
        del row
        del cursor
        arcpy.DeleteField_management(tempOut, "SUM")
    else:
        arcpy.AddField_management(tempOut, "sum_grsh", "DOUBLE")
        cursor = arcpy.da.UpdateCursor(tempOut, "sum_grsh")
        for row in cursor:
            row[0] = 0
            cursor.updateRow(row)
        del row
        del cursor
    if 60 in valueList:
        table_60 = ZonalStatisticsAsTable(thiessen_valley, "ORIG_FID", conversion_60, "table_60", statistics_type="SUM")
        arcpy.JoinField_management(tempOut, "FID", table_60, "ORIG_FID", "SUM")
        arcpy.AddField_management(tempOut, "sum_deveg", "DOUBLE")
        cursor = arcpy.da.UpdateCursor(tempOut, ["SUM", "sum_deveg"])
        for row in cursor:
            row[1] = row[0]
            cursor.updateRow(row)
        del row
        del cursor
        arcpy.DeleteField_management(tempOut, "SUM")
    else:
        arcpy.AddField_management(tempOut, "sum_deveg", "DOUBLE")
        cursor = arcpy.da.UpdateCursor(tempOut, "sum_deveg")
        for row in cursor:
            row[0] = 0
            cursor.updateRow(row)
        del row
        del cursor
    if 80 in valueList:
        table_80 = ZonalStatisticsAsTable(thiessen_valley, "ORIG_FID", conversion_80, "table_80", statistics_type="SUM")
        arcpy.JoinField_management(tempOut, "FID", table_80, "ORIG_FID", "SUM")
        arcpy.AddField_management(tempOut, "sum_con", "DOUBLE")
        cursor = arcpy.da.UpdateCursor(tempOut, ["SUM", "sum_con"])
        for row in cursor:
            row[1] = row[0]
            cursor.updateRow(row)
        del row
        del cursor
        arcpy.DeleteField_management(tempOut, "SUM")
    else:
        arcpy.AddField_management(tempOut, "sum_con", "DOUBLE")
        cursor = arcpy.da.UpdateCursor(tempOut, "sum_con")
        for row in cursor:
            row[0] = 0
            cursor.updateRow(row)
        del row
        del cursor
    if 97 in valueList:
        table_97 = ZonalStatisticsAsTable(thiessen_valley, "ORIG_FID", conversion_97, "table_97", statistics_type="SUM")
        arcpy.JoinField_management(tempOut, "FID", table_97, "ORIG_FID", "SUM")
        arcpy.AddField_management(tempOut, "sum_inv", "DOUBLE")
        cursor = arcpy.da.UpdateCursor(tempOut, ["SUM", "sum_inv"])
        for row in cursor:
            row[1] = row[0]
            cursor.updateRow(row)
        del row
        del cursor
        arcpy.DeleteField_management(tempOut, "SUM")
    else:
        arcpy.AddField_management(tempOut, "sum_inv", "DOUBLE")
        cursor = arcpy.da.UpdateCursor(tempOut, "sum_inv")
        for row in cursor:
            row[0] = 0
            cursor.updateRow(row)
        del row
        del cursor
    if 98 in valueList:
        table_98 = ZonalStatisticsAsTable(thiessen_valley, "ORIG_FID", conversion_98, "table_98", statistics_type="SUM")
        arcpy.JoinField_management(tempOut, "FID", table_98, "ORIG_FID", "SUM")
        arcpy.AddField_management(tempOut, "sum_dev", "DOUBLE")
        cursor = arcpy.da.UpdateCursor(tempOut, ["SUM", "sum_dev"])
        for row in cursor:
            row[1] = row[0]
            cursor.updateRow(row)
        del row
        del cursor
        arcpy.DeleteField_management(tempOut, "SUM")
    else:
        arcpy.AddField_management(tempOut, "sum_dev", "DOUBLE")
        cursor = arcpy.da.UpdateCursor(tempOut, "sum_dev")
        for row in cursor:
            row[0] = 0
            cursor.updateRow(row)
        del row
        del cursor
    if 99 in valueList:
        table_99 = ZonalStatisticsAsTable(thiessen_valley, "ORIG_FID", conversion_99, "table_99", statistics_type="SUM")
        arcpy.JoinField_management(tempOut, "FID", table_99, "ORIG_FID", "SUM")
        arcpy.AddField_management(tempOut, "sum_ag", "DOUBLE")
        cursor = arcpy.da.UpdateCursor(tempOut, ["SUM", "sum_ag"])
        for row in cursor:
            row[1] = row[0]
            cursor.updateRow(row)
        del row
        del cursor
        arcpy.DeleteField_management(tempOut, "SUM")
    else:
        arcpy.AddField_management(tempOut, "sum_ag", "DOUBLE")
        cursor = arcpy.da.UpdateCursor(tempOut, "sum_ag")
        for row in cursor:
            row[0] = 0
            cursor.updateRow(row)
        del row
        del cursor

    cursor = arcpy.da.UpdateCursor(tempOut, "COUNT")
    for row in cursor:
        if row[0] == 0:
            row[0] = 1
            cursor.updateRow(row)
    del row
    del cursor

    arcpy.AddField_management(tempOut, "prop_noch", "DOUBLE")
    cursor = arcpy.da.UpdateCursor(tempOut, ["COUNT", "sum_noch", "prop_noch"])
    for row in cursor:
        index = row[1] / row[0]
        row[2] = index
        cursor.updateRow(row)
    del row
    del cursor
    arcpy.AddField_management(tempOut, "prop_grsh", "DOUBLE")
    cursor = arcpy.da.UpdateCursor(tempOut, ["COUNT", "sum_grsh", "prop_grsh"])
    for row in cursor:
        index = row[1] / row[0]
        row[2] = index
        cursor.updateRow(row)
    del row
    del cursor
    arcpy.AddField_management(tempOut, "prop_deveg", "DOUBLE")
    cursor = arcpy.da.UpdateCursor(tempOut, ["COUNT", "sum_deveg", "prop_deveg"])
    for row in cursor:
        index = row[1] / row[0]
        row[2] = index
        cursor.updateRow(row)
    del row
    del cursor
    arcpy.AddField_management(tempOut, "prop_con", "DOUBLE")
    cursor = arcpy.da.UpdateCursor(tempOut, ["COUNT", "sum_con", "prop_con"])
    for row in cursor:
        index = row[1] / row[0]
        row[2] = index
        cursor.updateRow(row)
    del row
    del cursor
    arcpy.AddField_management(tempOut, "prop_inv", "DOUBLE")
    cursor = arcpy.da.UpdateCursor(tempOut, ["COUNT", "sum_inv", "prop_inv"])
    for row in cursor:
        index = row[1] / row[0]
        row[2] = index
        cursor.updateRow(row)
    del row
    del cursor
    arcpy.AddField_management(tempOut, "prop_dev", "DOUBLE")
    cursor = arcpy.da.UpdateCursor(tempOut, ["COUNT", "sum_dev", "prop_dev"])
    for row in cursor:
        index = row[1] / row[0]
        row[2] = index
        cursor.updateRow(row)
    del row
    del cursor
    arcpy.AddField_management(tempOut, "prop_ag", "DOUBLE")
    cursor = arcpy.da.UpdateCursor(tempOut, ["COUNT", "sum_ag", "prop_ag"])
    for row in cursor:
        index = row[1] / row[0]
        row[2] = index
        cursor.updateRow(row)
    del row
    del cursor

    prop0_array = arcpy.da.FeatureClassToNumPyArray(tempOut, "prop_noch")
    array0 = np.asarray(prop0_array, np.float64)
    prop50_array = arcpy.da.FeatureClassToNumPyArray(tempOut, "prop_grsh")
    array50 = np.asarray(prop50_array, np.float64)
    prop60_array = arcpy.da.FeatureClassToNumPyArray(tempOut, "prop_deveg")
    array60 = np.asarray(prop60_array, np.float64)
    prop80_array = arcpy.da.FeatureClassToNumPyArray(tempOut, "prop_con")
    array80 = np.asarray(prop80_array, np.float64)
    prop97_array = arcpy.da.FeatureClassToNumPyArray(tempOut, "prop_inv")
    array97 = np.asarray(prop97_array, np.float64)
    prop98_array = arcpy.da.FeatureClassToNumPyArray(tempOut, "prop_dev")
    array98 = np.asarray(prop98_array, np.float64)
    prop99_array = arcpy.da.FeatureClassToNumPyArray(tempOut, "prop_ag")
    array99 = np.asarray(prop99_array, np.float64)

    del prop0_array, prop50_array, prop60_array, prop80_array, prop97_array, prop98_array, prop99_array

    out_conv_code = np.zeros(len(array0), dtype=np.float64)
    for i in range(len(array0)):
        if array0[i] >= 0.85:  # if no change proportion is greater than or equal to 0.9
            out_conv_code[i] = 1  # no change
        else:  # if no change proportion is less than 0.9, move on to next greatest proportion
            if array50[i] > array60[i] and array50[i] > array80[i] and array50[i] > array97[i] and array50[i] > array98[i] and array50[i] > array99[i]:  # if grass/shrubland is next most dominant
                if array50[i] <= 0.25:
                    out_conv_code[i] = 11  # minor conversion to grass/shrubland
                elif array50[i] > 0.25 and array50[i] <= 0.5:
                    out_conv_code[i] = 12  # moderate conversion to grass/shrubland
                else:
                    out_conv_code[i] = 13  # significant conversion to grass/shrubland
            elif array60[i] > array50[i] and array60[i] > array80[i] and array60[i] > array97[i] and array60[i] > array98[i] and array60[i] > array99[i]:  # if barren is next most dominant
                if array60[i] <= 0.25:
                    out_conv_code[i] = 21  # minor devegetation
                elif array60[i] > 0.25 and array60[i] <= 0.5:
                    out_conv_code[i] = 22  # moderate devegetation
                else:
                    out_conv_code[i] = 23  # significant devegetation
            elif array80[i] > array50[i] and array80[i] > array60[i] and array80[i] > array97[i] and array80[i] > array98[i] and array80[i] > array99[i]:  # if conifer encroachment is next most dominant
                if array80[i] <= 0.25:
                    out_conv_code[i] = 31  # minor conifer encroachment
                elif array80[i] > 0.25 and array80[i] <= 0.5:
                    out_conv_code[i] = 32  # moderate conifer encroachment
                else:
                    out_conv_code[i] = 33  # significant conifer encroachment
            elif array97[i] > array50[i] and array97[i] > array60[i] and array97[i] > array80[i] and array97[i] > array98[i] and array97[i] > array99[i]:  # if conversion to invasive is next most dominant
                if array97[i] <= 0.25:
                    out_conv_code[i] = 41  # minor conversion to invasive
                elif array97[i] > 0.25 and array97[i] <= 0.5:
                    out_conv_code[i] = 42  # moderate conversion to invasive
                else:
                    out_conv_code[i] = 43  # significant conversion to invasive
            elif array98[i] > array50[i] and array98[i] > array60[i] and array98[i] > array80[i] and array98[i] > array97[i] and array98[i] > array99[i]:  # if urbanization is next most dominant
                if array98[i] <= 0.25:
                    out_conv_code[i] = 51  # minor urbanization
                elif array98[i] > 0.25 and array98[i] <= 0.5:
                    out_conv_code[i] = 52  # moderate urbanization
                else:
                    out_conv_code[i] = 53  # significant urbanization
            elif array99[i] > array50[i] and array99[i] > array60[i] and array99[i] > array80[i] and array99[i] > array97[i] and array99[i] > array98[i]:  # if conversion to agriculture is next most dominant
                if array99[i] <= 0.25:
                    out_conv_code[i] = 61  # minor conversion to agriculture
                elif array99[i] > 0.25 and array99[i] <= 0.5:
                    out_conv_code[i] = 62  # moderate conversion to agriculture
                else:
                    out_conv_code[i] = 63  # significant conversion to agriculture
            else:
                out_conv_code[i] = 0

    fid = np.arange(0, len(out_conv_code), 1)
    columns = np.column_stack((fid, out_conv_code))
    out_table = os.path.dirname(thiessen_valley) + "/Conv_Table.txt"
    np.savetxt(out_table, columns, delimiter=",", header="FID, conv_code", comments="")

    conv_code_table = scratch + "/conv_code_table"
    arcpy.CopyRows_management(out_table, conv_code_table)
    arcpy.JoinField_management(tempOut, "FID", conv_code_table, "FID", "conv_code")
    arcpy.Delete_management(out_table)

    arcpy.AddField_management(tempOut, "conv_type", "text", "", "", 50)
    cursor = arcpy.da.UpdateCursor(tempOut, ["conv_code", "conv_type"])
    for row in cursor:
        if row[0] == 1:
            row[1] = "No Change"
        elif row[0] == 11:
            row[1] = "Minor Conversion to Grass/Shrubland"
        elif row[0] == 12:
            row[1] = "Moderate Conversion to Grass/Shrubland"
        elif row[0] == 13:
            row[1] = "Significant Conversion to Grass/Shrubland"
        elif row[0] == 21:
            row[1] = "Minor Devegetation"
        elif row[0] == 22:
            row[1] = "Moderate Devegetation"
        elif row[0] == 23:
            row[1] = "Significant Devegetation"
        elif row[0] == 31:
            row[1] = "Minor Conifer Encroachment"
        elif row[0] == 32:
            row[1] = "Moderate Conifer Encroachment"
        elif row[0] == 33:
            row[1] = "Significant Conifer Encroachment"
        elif row[0] == 41:
            row[1] = "Minor Conversion to Invasive"
        elif row[0] == 42:
            row[1] = "Moderate Conversion to Invasive"
        elif row[0] == 43:
            row[1] = "Significant Conversion to Invasive"
        elif row[0] == 51:
            row[1] = "Minor Development"
        elif row[0] == 52:
            row[1] = "Moderate Development"
        elif row[0] == 53:
            row[1] = "Significant Development"
        elif row[0] == 61:
            row[1] = "Minor Conversion to Agriculture"
        elif row[0] == 62:
            row[1] = "Moderate Conversion to Agriculture"
        elif row[0] == 63:
            row[1] = "Significant Conversion to Agriculture"
        elif row[0] == 0:
            row[1] = "Multiple Dominant Conversion Types"
        cursor.updateRow(row)
    del row
    del cursor

    arcpy.MakeFeatureLayer_management(tempOut, "outlyr")
    arcpy.SelectLayerByLocation_management("outlyr", "HAVE_THEIR_CENTER_IN", valley)
    arcpy.SelectLayerByLocation_management("outlyr", selection_type="SWITCH_SELECTION")
    cursor = arcpy.da.UpdateCursor("outlyr", ["DEP_RATIO", "conv_code", "conv_type", "EVT_MEAN", "BPS_MEAN", "COUNT",
                                              "sum_noch", "sum_grsh", "sum_deveg", "sum_con", "sum_inv", "sum_dev",
                                              "sum_ag", "prop_noch", "prop_grsh", "prop_deveg", "prop_con", "prop_inv",
                                              "prop_dev", "prop_ag"])
    for row in cursor:
        row[0] = -9999
        row[1] = -9999
        row[2] = "NA"
        row[3] = -9999
        row[4] = -9999
        row[5] = -9999
        row[6] = -9999
        row[7] = -9999
        row[8] = -9999
        row[9] = -9999
        row[10] = -9999
        row[11] = -9999
        row[12] = -9999
        row[13] = -9999
        row[14] = -9999
        row[15] = -9999
        row[16] = -9999
        row[17] = -9999
        row[18] = -9999
        row[19] = -9999
        cursor.updateRow(row)
    del row
    del cursor
    arcpy.SelectLayerByAttribute_management("outlyr", "CLEAR_SELECTION")
    arcpy.CopyFeatures_management("outlyr", fcOut)
    arcpy.Delete_management(tempOut)

    # # # Write xml file # # #

    if not os.path.exists(projPath + "/project.rs.xml"):
        # xml file
        xmlfile = projPath + "/project.rs.xml"

        # initiate xml file creation
        newxml = projectxml.ProjectXML(xmlfile, "RVD", projName)

        if not hucID == None:
            newxml.addMeta("HUCID", hucID, newxml.project)
        if not hucID == None:
            idlist = [int(x) for x in str(hucID)]
            if idlist[0] == 1 and idlist[1] == 7:
                newxml.addMeta("Region", "CRB", newxml.project)
        if not hucName == None:
            newxml.addMeta("Watershed", hucName, newxml.project)

        newxml.addRVDRealization("RVD Realization 1", rid="RZ1", dateCreated=datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                 productVersion="1.0.5", guid=getUUID())

        # add inputs and outputs to xml file
        newxml.addProjectInput("Raster", "Existing Vegetation", evt[evt.find("01_Inputs"):], iid="EXVEG1", guid=getUUID())
        newxml.addRVDInput(newxml.RVDrealizations[0], "Existing Vegetation", ref="EXVEG1")

        newxml.addProjectInput("Raster", "Historic Vegetation", bps[bps.find("01_Inputs"):], iid="HISTVEG1", guid=getUUID())
        newxml.addRVDInput(newxml.RVDrealizations[0], "Historic Vegetation", ref="HISTVEG1")

        newxml.addProjectInput("Vector", "Segmented Network", seg_network[seg_network.find("01_Inputs"):], iid="NETWORK1", guid=getUUID())
        newxml.addRVDInput(newxml.RVDrealizations[0], "Network", ref="NETWORK1")

        newxml.addProjectInput("Vector", "Valley Bottom", valley[valley.find("01_Inputs"):], iid="VALLEY1", guid=getUUID())
        newxml.addRVDInput(newxml.RVDrealizations[0], "Valley", ref="VALLEY1")

        if lg_river is not None:
            newxml.addProjectInput("Vector", "Large River Polygon", lg_river[lg_river.find("01_Inputs"):], iid="LRP1", guid=getUUID())
            newxml.addRVDInput(newxml.RVDrealizations[0], "LRP", ref="LRP1")

        newxml.addRVDInput(newxml.RVDrealizations[0], "Existing Cover", "Existing Riparian",
                           path=os.path.dirname(os.path.dirname(evt[evt.find("01_Inputs"):])) + "/Ex_Rasters/Ex_Riparian.tif", guid=getUUID())
        newxml.addRVDInput(newxml.RVDrealizations[0], "Historic Cover", "Historic Riparian",
                           path=os.path.dirname(os.path.dirname(bps[bps.find("01_Inputs"):])) + "/Hist_Rasters/Hist_Riparian.tif", guid=getUUID())
        newxml.addRVDInput(newxml.RVDrealizations[0], "Existing Cover", "Existing Cover",
                           path=os.path.dirname(os.path.dirname(evt[evt.find("01_Inputs"):])) + "/Ex_Rasters/Ex_Cover.tif", guid=getUUID())
        newxml.addRVDInput(newxml.RVDrealizations[0], "Historic Cover", "Historic Cover",
                           path=os.path.dirname(os.path.dirname(bps[bps.find("01_Inputs"):])) + "/Hist_Rasters/Hist_Cover.tif", guid=getUUID())
        newxml.addRVDInput(newxml.RVDrealizations[0], "Thiessen Polygons", "Thiessen Polygons",
                           path=thiessen_valley[thiessen_valley.find("01_Inputs"):], guid=getUUID())

        newxml.addOutput("RVD Analysis", "Vector", "RVD", fcOut[fcOut.find("02_Analyses"):], newxml.RVDrealizations[0], guid=getUUID())
        newxml.addOutput("RVD Analysis", "Raster", "Conversion Raster",
                         os.path.dirname(fcOut[fcOut.find("02_Analyses"):]) + "/Converstion_Raster.tif", newxml.RVDrealizations[0], guid=getUUID())

        newxml.write()

    else:
        xmlfile = projPath + '/project.rs.xml'

        exxml = projectxml.ExistingXML(xmlfile)

        rvdr = exxml.rz.findall("RVD")
        rvdrf = rvdr[-1]
        rname = rvdrf.find("Name")
        k = 2
        while rname.text == "RVD Realization " + str(k):
            k += 1

        exxml.addRVDRealization("RVD Realization " + str(k), rid="RZ" + str(k),
                                dateCreated=datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), productVersion="1.0.5", guid=getUUID())

        inputs = exxml.root.find("Inputs")

        raster = inputs.findall("Raster")
        rasterid = range(len(raster))
        for i in range(len(raster)):
            rasterid[i] = raster[i].get("id")
        rasterpath = range(len(raster))
        for i in range(len(raster)):
            rasterpath[i] = raster[i].find("Path").text

        for i in range(len(rasterpath)):
            if os.path.abspath(rasterpath[i]) == os.path.abspath(evt[evt.find("01_Inputs"):]):
                EV = exxml.root.findall(".//ExistingVegetation")
                for x in range(len(EV)):
                    if EV[x].attrib['ref'] == rasterid[i]:
                        r = EV[x].findall(".//Raster")
                        exrip_guid = r[0].attrib['guid']
                        excov_guid = r[1].attrib['guid']
                    else:
                        r = []
                exxml.addRVDInput(exxml.RVDrealizations[0], "Existing Vegetation", ref=str(rasterid[i]))
                if len(r) > 0:
                    exxml.addRVDInput(exxml.RVDrealizations[0], "Existing Cover", "Existing Riparian",
                                      path=os.path.dirname(os.path.dirname(rasterpath[i][rasterpath[i].find("01_Inputs"):])) + "/Ex_Rasters/Ex_Riparian.tif",
                                      guid=exrip_guid)
                    exxml.addRVDInput(exxml.RVDrealizations[0], "Existing Cover", "Existing Cover",
                                      path=os.path.dirname(os.path.dirname(rasterpath[i][rasterpath[i].find("01_Inputs"):])) + "/Ex_Rasters/Ex_Cover.tif",
                                      guid=excov_guid)
                else:
                    exxml.addRVDInput(exxml.RVDrealizations[0], "Existing Cover", "Existing Riparian",
                                      path=os.path.dirname(os.path.dirname(rasterpath[i][rasterpath[i].find("01_Inputs"):])) + "/Ex_Rasters/Ex_Riparian.tif")
                    exxml.addRVDInput(exxml.RVDrealizations[0], "Existing Cover", "Existing Cover",
                                      path=os.path.dirname(os.path.dirname(rasterpath[i][rasterpath[i].find("01_Inputs"):])) + "/Ex_Rasters/Ex_Cover.tif")
            elif os.path.abspath(rasterpath[i]) == os.path.abspath(bps[bps.find("01_Inputs"):]):
                HV = exxml.root.findall(".//HistoricVegetation")
                for x in range(len(HV)):
                    if HV[x].attrib['ref'] == rasterid[i]:
                        r = HV[x].findall(".//Raster")
                        histrip_guid = r[0].attrib['guid']
                        histcov_guid = r[1].attrib['guid']
                    else:
                        r = []
                exxml.addRVDInput(exxml.RVDrealizations[0], "Historic Vegetation", ref=str(rasterid[i]))
                if len(r) > 0:
                    exxml.addRVDInput(exxml.RVDrealizations[0], "Historic Cover", "Historic Riparian",
                                      path=os.path.dirname(os.path.dirname(rasterpath[i][rasterpath[i].find("01_Inputs"):])) + "/Hist_Rasters/Hist_Riparian.tif",
                                      guid=histrip_guid)
                    exxml.addRVDInput(exxml.RVDrealizations[0], "Historic Cover", "Historic Cover",
                                      path=os.path.dirname(os.path.dirname(rasterpath[i][rasterpath[i].find("01_Inputs"):])) + "/Hist_Rasters/Hist_Cover.tif",
                                      guid=histcov_guid)
                else:
                    exxml.addRVDInput(exxml.RVDrealizations[0], "Historic Cover", "Historic Riparian",
                                      path=os.path.dirname(os.path.dirname(rasterpath[i][rasterpath[i].find("01_Inputs"):])) + "/Hist_Rasters/Hist_Riparian.tif")
                    exxml.addRVDInput(exxml.RVDrealizations[0], "Historic Cover", "Historic Cover",
                                      path=os.path.dirname(os.path.dirname(rasterpath[i][rasterpath[i].find("01_Inputs"):])) + "/Hist_Rasters/Hist_Cover.tif")

        nlist = []
        for j in rasterpath:
            if os.path.abspath(evt[evt.find("01_Inputs"):]) == os.path.abspath(j):
                nlist.append("yes")
            else:
                nlist.append("no")
        if "yes" in nlist:
            pass
        else:
            exxml.addProjectInput("Raster", "Existing Vegetation", evt[evt.find("01_Inputs"):], iid="EXVEG" + str(k), guid=getUUID())
            exxml.addRVDInput(exxml.RVDrealizations[0], "Existing Vegetation", ref="EXVEG" + str(k))
            exxml.addRVDInput(exxml.RVDrealizations[0], "Existing Cover", "Existing Riparian",
                              path=os.path.dirname(os.path.dirname(evt[evt.find("01_Inputs"):])) + "/Ex_Rasters/Ex_Riparian.tif",
                              guid=getUUID())
            exxml.addRVDInput(exxml.RVDrealizations[0], "Existing Cover", "Existing Cover",
                              path=os.path.dirname(os.path.dirname(evt[evt.find("01_Inputs"):])) + "/Ex_Rasters/Ex_Cover.tif",
                              guid=getUUID())
        nlist = []
        for j in rasterpath:
            if os.path.abspath(bps[bps.find("01_Inputs"):]) == os.path.abspath(j):
                nlist.append("yes")
            else:
                nlist.append("no")
        if "yes" in nlist:
            pass
        else:
            exxml.addProjectInput("Raster", "Historic Vegetation", bps[bps.find("01_Inputs"):], iid="HISTVEG" + str(k), guid=getUUID())
            exxml.addRVDInput(exxml.RVDrealizations[0], "HistoricVegetation", ref="HISTVEG" + str(k))
            exxml.addRVDInput(exxml.RVDrealizations[0], "Historic Cover", "Historic Riparian",
                              path=os.path.dirname(os.path.dirname(bps[bps.find("01_Inputs"):])) + "/Hist_Rasters/Hist_Riparian.tif",
                              guid=getUUID())
            exxml.addRVDInput(exxml.RVDrealizations[0], "Historic Cover", "Historic Cover",
                              path=os.path.dirname(os.path.dirname(bps[bps.find("01_Inputs"):])) + "/Hist_Rasters/Hist_Cover.tif",
                              guid=getUUID())
        del nlist

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
                exxml.addRVDInput(exxml.RVDrealizations[0], "Network", ref=str(vectorid[i]))
                if len(r) > 0:
                    exxml.addRVDInput(exxml.RVDrealizations[0], "Thiessen Polygons", "Thiessen Polygons",
                                      path=os.path.dirname(vectorpath[i][vectorpath[i].find("01_Inputs"):]) + "/Thiessen/Thiessen_Valley.shp",
                                      guid=thiessen_guid)
                else:
                    exxml.addRVDInput(exxml.RVDrealizations[0], "Thiessen Polygons", "Thiessen Polygons",
                                      path=os.path.dirname(vectorpath[i][vectorpath[i].find("01_Inputs"):]) + "/Thiessen/Thiessen_Valley.shp")
            elif os.path.abspath(vectorpath[i]) == os.path.abspath(valley[valley.find("01_Inputs"):]):
                exxml.addRVDInput(exxml.RVDrealizations[0], "Valley", ref=str(vectorid[i]))
            if lg_river is not None:
                if os.path.abspath(vectorpath[i]) == os.path.abspath(lg_river[lg_river.find("01_Inputs"):]):
                    exxml.addRVDInput(exxml.RVDrealizations[0], "LRP", ref=str(vectorid[i]))

        nlist = []
        for j in vectorpath:
            if os.path.abspath(seg_network[seg_network.find("01_Inputs"):]) == os.path.abspath(j):
                nlist.append("yes")
            else:
                nlist.append("no")
        if "yes" in nlist:
            pass
        else:
            exxml.addProjectInput("Vector", "Segmented Network", seg_network[seg_network.find("01_Inputs"):], iid="NETWORK" + str(k), guid=getUUID())
            exxml.addRVDInput(exxml.RVDrealizations[0], "Network", ref="NETWORK" + str(k))
            exxml.addRVDInput(exxml.RVDrealizations[0], "Thiessen Polygons", "Thiessen Polygons",
                              path=os.path.dirname(seg_network[seg_network.find("01_Inputs"):]) + "/Thiessen/Thiessen_Valley.shp",
                              guid=getUUID())
        nlist = []
        for j in vectorpath:
            if os.path.abspath(valley[valley.find("01_Inputs"):]) == os.path.abspath(j):
                nlist.append("yes")
            else:
                nlist.append("no")
        if "yes" in nlist:
            pass
        else:
            exxml.addProjectInput("Vector", "Valley Bottom", valley[valley.find("01_Inputs"):], iid="VALLEY" + str(k), guid=getUUID())
            exxml.addRVDInput(exxml.RVDrealizations[0], "Valley", ref="VALLEY" + str(k))

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
                exxml.addProjectInput("Vector", "Large River Polygon", lg_river[lg_river.find("01_Inputs"):], iid="LRP" + str(k), guid=getUUID())
                exxml.addRVDInput(exxml.RVDrealizations[0], "LRP", ref="LRP" + str(k))

        del nlist

        exxml.addOutput("RVD Analysis " + str(k), "Vector", "RVD Output", fcOut[fcOut.find("02_Analyses"):], exxml.RVDrealizations[0], guid=getUUID())
        exxml.addOutput("RVD Analysis " + str(k), "Raster", "Conversion Raster",
                         os.path.dirname(fcOut[fcOut.find("02_Analyses"):]) + "/Converstion_Raster.tif",
                         exxml.RVDrealizations[0], guid=getUUID())

        exxml.write()

    arcpy.CheckInExtension("spatial")

    return


def score_vegetation(evt, bps):

    lf1 = arcpy.ListFields(evt, "VEG_SCORE")
    if len(lf1) is not 1:
        arcpy.AddField_management(evt, "VEG_SCORE", "DOUBLE")

    cursor = arcpy.da.UpdateCursor(evt, ["EVT_PHYS", "EVT_GP", "VEG_SCORE"])
    for row in cursor:
        if row[0] == "Riparian":
            row[2] = 1
        elif row[0] == "Open Water":
            row[2] = 1
        elif row[0] == "Hardwood":
            row[2] = 1
        elif row[0] == "Conifer-Hardwood":
            row[2] = 1
        cursor.updateRow(row)
        if row[1] == "602":
            row[2] = 1
        elif row[1] == "701":
            row[2] = 0
        elif row[1] == "708":
            row[2] = 0
        elif row[1] == "709":
            row[2] = 0
        cursor.updateRow(row)
    del row
    del cursor

    lf2 = arcpy.ListFields(bps, "VEG_SCORE")
    if len(lf2) is not 1:
        arcpy.AddField_management(bps, "VEG_SCORE", "DOUBLE")

    cursor2 = arcpy.da.UpdateCursor(bps, ["GROUPVEG", "VEG_SCORE"])
    for row in cursor2:
        if row[0] == "Riparian":
            row[1] = 1
        elif row[0] == "Open Water":
            row[1] = 1
        elif row[0] == "Hardwood":
            row[1] = 1
        elif row[0] == "Hardwood-Conifer":
            row[1] = 1
        else:
            row[1] = 0
        cursor2.updateRow(row)
    del row
    del cursor2

    lf3 = arcpy.ListFields(evt, "CONVERSION")
    if len(lf3) is not 1:
        arcpy.AddField_management(evt, "CONVERSION", "DOUBLE")

    cursor3 = arcpy.da.UpdateCursor(evt, ["EVT_PHYS", "EVT_GP", "CONVERSION"])
    for row in cursor3:
        if row[0] == "Open Water":
            row[2] = 500
        elif row[0] == "Non-vegetated":
            row[2] = 40
        elif row[0] == "Snow-Ice":
            row[2] = 40
        elif row[0] == "Developed":
            row[2] = 2
        elif row[0] == "Developed-Low Intensity":
            row[2] = 2
        elif row[0] == "Developed-Medium Intensity":
            row[2] = 2
        elif row[0] == "Developed-High Intensity":
            row[2] = 2
        elif row[0] == "Developed-Roads":
            row[2] = 2
        elif row[0] == "Barren":
            row[2] = 40
        elif row[0] == "Quarries-Strip Mines-Gravel Pits":
            row[2] = 2
        elif row[0] == "Agricultural":
            row[2] = 1
        elif row[0] == "Grassland":
            row[2] = 50
        elif row[0] == "Hardwood":
            row[2] = 100
        elif row[0] == "Shrubland":
            row[2] = 50
        elif row[0] == "Conifer-Hardwood":
            row[2] = 20
        elif row[0] == "Conifer":
            row[2] = 20
        elif row[0] == "Riparian":
            row[2] = 100
        elif row[0] == "Sparsely Vegetated":
            row[2] = 40
        elif row[0] == "Exotic Tree-Shrub":
            row[2] = 3
        elif row[0] == "Exotic Herbaceous":
            row[2] = 3
        elif row[1] == "708":
            row[2] = 3
        elif row[1] == "709":
            row[2] = 3
        elif row[1] == "701":
            row[2] = 3
        elif row[1] == "705":
            row[2] = 3
        elif row[1] == "702":
            row[2] = 3
        elif row[1] == "703":
            row[2] = 3
        elif row[1] == "704":
            row[2] = 3
        elif row[1] == "706":
            row[2] = 3
        elif row[1] == "707":
            row[2] = 3
        cursor3.updateRow(row)
    del row
    del cursor3

    lf4 = arcpy.ListFields(bps, "CONVERSION")
    if len(lf4) is not 1:
        arcpy.AddField_management(bps, "CONVERSION", "DOUBLE")

    cursor4 = arcpy.da.UpdateCursor(bps, ["GROUPVEG", "CONVERSION"])
    for row in cursor4:
        if row[0] == "Riparian":
            row[1] = 100
        elif row[0] == "Open Water":
            row[1] = 500
        elif row[0] == "PerennialIce/Snow":
            row[1] = 40
        elif row[0] == "Barren-Rock/Sand/Clay":
            row[1] = 40
        elif row[0] == "Sparse":
            row[1] = 40
        elif row[0] == "Hardwood":
            row[1] = 100
        elif row[0] == "Conifer":
            row[1] = 20
        elif row[0] == "Shrubland":
            row[1] = 50
        elif row[0] == "Hardwood-Conifer":
            row[1] = 20
        elif row[0] == "Grassland":
            row[1] = 50
        else:
            row[1] = 50
        cursor4.updateRow(row)
    del row
    del cursor4

    return

def getUUID():
    return str(uuid.uuid4()).upper()

if __name__ == '__main__':
    main(
        sys.argv[1],
        sys.argv[2],
        sys.argv[3],
        sys.argv[4],
        sys.argv[5],
        sys.argv[6],
        sys.argv[7],
        sys.argv[8],
        sys.argv[9],
        sys.argv[10],
        sys.argv[11])
