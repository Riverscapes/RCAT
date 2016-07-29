
#-------------------------------------------------------------------------------
# Name:        RVD
# Purpose:     Uses LANDFIRE inputs to assign a riparian condition score to
#              a segmented stream network based on a comparison between the
#              biophysical settings LANDFIRE layer and the existing vegetation
#              type LANDFIRE layer
#
# Author:      Jordan Gilbert
#
# Created:     15/10/2015
# Copyright:   (c) Jordan 2015
# Licence:     <your licence>
#-------------------------------------------------------------------------------

import arcpy
from arcpy.sa import *
import os
import sys
import numpy as np


def main(
    evt,
    bps,
    seg_network,
    valley,
    lg_river,
    fcOut,
    scratch = arcpy.env.scratchWorkspace):

    arcpy.env.overwriteOutput = True
    arcpy.CheckOutExtension("spatial")

    # create thiessen polygons from segmented network input
    arcpy.AddMessage('Creating thiessen polygons')
    smooth_network = scratch + "/smooth_network"
    arcpy.SmoothLine_cartography(seg_network, smooth_network, "PAEK", "500 Meters")
    midpoints = scratch + "/midpoints"
    arcpy.FeatureVerticesToPoints_management(smooth_network, midpoints, "MID")
    thiessen = scratch + "/thiessen"
    arcpy.CreateThiessenPolygons_analysis(midpoints, thiessen)
    valley_buf = scratch + "/valley_buf"
    arcpy.Buffer_analysis(valley, valley_buf, "30 Meters", "FULL", "ROUND", "ALL")
    thiessen_valley = os.path.dirname(seg_network) + "/thiessen_valley.shp"
    arcpy.Clip_analysis(thiessen, valley_buf, thiessen_valley)

    # give the landfire rasters riparian vegetation scores and conversion scores
    arcpy.AddMessage('Classifying vegetation data')
    score_vegetation(evt, bps)

    evt_lookup = Lookup(evt, "VEG_SCORE")
    bps_lookup = Lookup(bps, "VEG_SCORE")

    ###----------------------------------------------###
    ### RVD analysis for areas without large rivers ###
    ###----------------------------------------------###

    if lg_river == None:
        arcpy.AddMessage('calculating riparian vegetation departure')
        evt_zs = ZonalStatistics(thiessen_valley, "FID", evt_lookup, "MEAN", "DATA")
        bps_zs = ZonalStatistics(thiessen_valley, "FID", bps_lookup, "MEAN", "DATA")
        evt_raster_calc = evt_zs*100
        bps_raster_calc = bps_zs*100
        evt_int = Int(evt_raster_calc)
        bps_int = Int(bps_raster_calc)

        evt_mean_poly = scratch + "/evt_mean_poly"
        bps_mean_poly = scratch + "/bps_mean_poly"
        arcpy.RasterToPolygon_conversion(evt_int, evt_mean_poly)
        arcpy.RasterToPolygon_conversion(bps_int, bps_mean_poly)

        diss_network = scratch + "/diss_network"
        arcpy.Dissolve_management(seg_network, diss_network)
        intersect1 = scratch + "/intersect1"
        arcpy.Intersect_analysis([evt_mean_poly, diss_network], intersect1, "", "", "LINE")
        arcpy.AddField_management(intersect1, "EVT_MEAN", "DOUBLE")
        cursor = arcpy.da.UpdateCursor(intersect1, ["GRIDCODE", "EVT_MEAN"])
        for row in cursor:
            row[1] = row[0]
            cursor.updateRow(row)
        del row
        del cursor
        arcpy.DeleteField_management(intersect1, "GRIDCODE")

        cursor2 = arcpy.da.UpdateCursor(intersect1, ["EVT_MEAN"])
        for row in cursor2:
            if row[0] == 0:
                row[0] = 0.0001
                cursor2.updateRow(row)
        del row
        del cursor2

        intersect2 = scratch + "/intersect2"
        arcpy.Intersect_analysis([intersect1, bps_mean_poly], intersect2, "", "", "LINE")
        arcpy.AddField_management(intersect2, "BPS_MEAN", "DOUBLE")
        cursor3 = arcpy.da.UpdateCursor(intersect2, ["GRIDCODE", "BPS_MEAN"])
        for row in cursor3:
            row[1] = row[0]
            cursor3.updateRow(row)
        arcpy.DeleteField_management(intersect2, "GRIDCODE")

        cursor4 = arcpy.da.UpdateCursor(intersect2, ["BPS_MEAN"])
        for row in cursor4:
            if row[0] == 0:
                row[0] = 0.0001
                cursor4.updateRow(row)
        del row
        del cursor4

        arcpy.AddField_management(intersect2, "DEP_RATIO", "DOUBLE")
        cursor5 = arcpy.da.UpdateCursor(intersect2, ["EVT_MEAN", "BPS_MEAN", "DEP_RATIO"])
        for row in cursor5:
            index = row[0]/row[1]
            row[2] = index
            cursor5.updateRow(row)
        del row
        del cursor5

    ###-------------------------------------------###
    ### RVD analysis for areas with large rivers ###
    ###-------------------------------------------###

    else:
        arcpy.AddMessage('Calculating riparian vegetation departure')
        arcpy.env.extent = thiessen_valley
        lg_river_raster = ExtractByMask(evt, lg_river)
        cursor6 = arcpy.UpdateCursor(lg_river_raster)
        for row in cursor6:
            row.setValue("VEG_SCORE", 8)
            cursor6.updateRow(row)
        del row
        del cursor6

        river_lookup = Lookup(lg_river_raster, "VEG_SCORE")
        river_reclass = Reclassify(river_lookup, "VALUE", "8 8; NODATA 0")
        evt_calc = river_reclass + evt_lookup
        bps_calc = river_reclass + bps_lookup
        evt_wo_rivers = Reclassify(evt_calc, "VALUE", "0 0; 1 1; 8 NODATA; 9 NODATA")
        bps_wo_rivers = Reclassify(bps_calc, "VALUE", "0 0; 1 1; 8 NODATA; 9 NODATA")

        evt_zs = ZonalStatistics(thiessen_valley, "FID", evt_wo_rivers, "MEAN", "DATA")
        bps_zs = ZonalStatistics(thiessen_valley, "FID", bps_wo_rivers, "MEAN", "DATA")
        evt_raster_calc = evt_zs*100
        bps_raster_calc = bps_zs*100
        evt_int = Int(evt_raster_calc)
        bps_int = Int(bps_raster_calc)

        evt_mean_poly = scratch + "/evt_mean_poly"
        bps_mean_poly = scratch + "/bps_mean_poly"
        arcpy.RasterToPolygon_conversion(evt_int, evt_mean_poly)
        arcpy.RasterToPolygon_conversion(bps_int, bps_mean_poly)

        diss_network = scratch + "/diss_network"
        arcpy.Dissolve_management(seg_network, diss_network)
        intersect1 = scratch + "/intersect1"
        arcpy.Intersect_analysis([evt_mean_poly, diss_network], intersect1, "", "", "LINE")
        arcpy.AddField_management(intersect1, "EVT_MEAN", "DOUBLE")
        cursor7 = arcpy.da.UpdateCursor(intersect1, ["GRIDCODE", "EVT_MEAN"])
        for row in cursor7:
            row[1] = row[0]
            cursor7.updateRow(row)
        del row
        del cursor7
        arcpy.DeleteField_management(intersect1, "GRIDCODE")
        cursor8 = arcpy.da.UpdateCursor(intersect1, "EVT_MEAN")
        for row in cursor8:
            if row[0] == 0:
                row[0] = 0.0001
                cursor8.updateRow(row)
        del row
        del cursor8

        intersect2 = scratch + "/intersect2"
        arcpy.Intersect_analysis([intersect1, bps_mean_poly], intersect2, "", "", "LINE")
        arcpy.AddField_management(intersect2, "BPS_MEAN", "DOUBLE")
        cursor9 = arcpy.da.UpdateCursor(intersect2, ["GRIDCODE", "BPS_MEAN"])
        for row in cursor9:
            row[1] = row[0]
            cursor9.updateRow(row)
        del row
        del cursor9
        arcpy.DeleteField_management(intersect2, "GRIDCODE")
        cursor10 = arcpy.da.UpdateCursor(intersect2, ["BPS_MEAN"])
        for row in cursor10:
            if row[0] == 0:
                row[0] = 0.0001
                cursor10.updateRow(row)
        del row
        del cursor10

        arcpy.AddField_management(intersect2, "DEP_RATIO", "DOUBLE")
        cursor11 = arcpy.da.UpdateCursor(intersect2, ["EVT_MEAN", "BPS_MEAN", "DEP_RATIO"])
        for row in cursor11:
            index = row[0]/row[1]
            row[2] = index
            cursor11.updateRow(row)
        del row
        del cursor11

    ###------------------------------###
    ### Riparian Conversion analysis ###
    ###------------------------------###

    arcpy.AddMessage('Calculating riparian vegetation conversion types')
    evt_conversion_lookup = Lookup(evt, "CONVERSION")
    bps_conversion_lookup = Lookup(bps, "CONVERSION")
    conversion_raster = bps_conversion_lookup - evt_conversion_lookup
    int_conversion_raster = Int(conversion_raster)
    remap = "-450 NODATA; -400 NODATA; -480 NODATA; -80 NODATA; -60 NODATA; -50 NODATA; -30 NODATA; -20 NODATA; -10 NODATA; 0 0; 10 NODATA; 17 NODATA; 18 NODATA; 19 NODATA; 20 NODATA; 30 NODATA; 37 NODATA; 38 NODATA; 39 NODATA; 47 NODATA; 48 NODATA; 49 NODATA; 50 50; 60 60; 80 80; 97 97; 98 98; 99 99"
    final_conversion_raster = Reclassify(int_conversion_raster, "VALUE", remap, "NODATA")
    conversion_0 = Reclassify(final_conversion_raster, "VALUE", "0 1; 50 NODATA; 60 NODATA; 80 NODATA; 97 NODATA; 98 NODATA; 99 NODATA", "NODATA")
    conversion_50 = Reclassify(final_conversion_raster, "VALUE", "0 NODATA; 50 1; 60 NODATA; 80 NODATA; 97 NODATA; 98 NODATA; 99 NODATA", "NODATA")
    conversion_60 = Reclassify(final_conversion_raster, "VALUE", "0 NODATA; 50 NODATA; 60 1; 80 NODATA; 97 NODATA; 98 NODATA; 99 NODATA", "NODATA")
    conversion_80 = Reclassify(final_conversion_raster, "VALUE", "0 NODATA; 50 NODATA; 60 NODATA; 80 1; 97 NODATA; 98 NODATA; 99 NODATA", "NODATA")
    conversion_97 = Reclassify(final_conversion_raster, "VALUE", "0 NODATA; 50 NODATA; 60 NODATA; 80 NODATA; 97 1; 98 NODATA; 99 NODATA", "NODATA")
    conversion_98 = Reclassify(final_conversion_raster, "VALUE", "0 NODATA; 50 NODATA; 60 NODATA; 80 NODATA; 97 NODATA; 98 1; 99 NODATA", "NODATA")
    conversion_99 = Reclassify(final_conversion_raster, "VALUE", "0 NODATA; 50 NODATA; 60 NODATA; 80 NODATA; 97 NODATA; 98 NODATA; 99 1", "NODATA")

    out_conversion_raster = ExtractByMask(final_conversion_raster, valley_buf)
    out_dirname = os.path.dirname(fcOut)
    if os.path.exists(out_dirname + "/Conversion_Raster.tif"):
        arcpy.Delete_management(out_dirname + "/Conversion_Raster.tif")
        conv_rast_path = out_dirname + "/Conversion_Raster.tif"
        out_conversion_raster.save(conv_rast_path)
    else:
        conv_rast_path = out_dirname + "/Conversion_Raster.tif"
        out_conversion_raster.save(conv_rast_path)

    count_table = ZonalStatisticsAsTable(thiessen_valley, "FID", final_conversion_raster, "count_table", "", "VARIETY")
    arcpy.JoinField_management(thiessen_valley, "FID", count_table, "FID", "COUNT")
    table_0 = ZonalStatisticsAsTable(thiessen_valley, "FID", conversion_0, "table_0", "", "SUM")
    arcpy.JoinField_management(thiessen_valley, "FID", table_0, "FID", "SUM")
    arcpy.AddField_management(thiessen_valley, "sum_noch", "DOUBLE")
    cursor = arcpy.da.UpdateCursor(thiessen_valley, ["SUM", "sum_noch"])
    for row in cursor:
        row[1] = row[0]
        cursor.updateRow(row)
    del row
    del cursor
    arcpy.DeleteField_management(thiessen_valley, "SUM")
    table_50 = ZonalStatisticsAsTable(thiessen_valley, "FID", conversion_50, "table_50", "", "SUM")
    arcpy.JoinField_management(thiessen_valley, "FID", table_50, "FID", "SUM")
    arcpy.AddField_management(thiessen_valley, "sum_grsh", "DOUBLE")
    cursor = arcpy.da.UpdateCursor(thiessen_valley, ["SUM", "sum_grsh"])
    for row in cursor:
        row[1] = row[0]
        cursor.updateRow(row)
    del row
    del cursor
    arcpy.DeleteField_management(thiessen_valley, "SUM")
    table_60 = ZonalStatisticsAsTable(thiessen_valley, "FID", conversion_60, "table_60", "", "SUM")
    arcpy.JoinField_management(thiessen_valley, "FID", table_60, "FID", "SUM")
    arcpy.AddField_management(thiessen_valley, "sum_deveg", "DOUBLE")
    cursor = arcpy.da.UpdateCursor(thiessen_valley, ["SUM", "sum_deveg"])
    for row in cursor:
        row[1] = row[0]
        cursor.updateRow(row)
    del row
    del cursor
    arcpy.DeleteField_management(thiessen_valley, "SUM")
    table_80 = ZonalStatisticsAsTable(thiessen_valley, "FID", conversion_80, "table_80", "", "SUM")
    arcpy.JoinField_management(thiessen_valley, "FID", table_80, "FID", "SUM")
    arcpy.AddField_management(thiessen_valley, "sum_con", "DOUBLE")
    cursor = arcpy.da.UpdateCursor(thiessen_valley, ["SUM", "sum_con"])
    for row in cursor:
        row[1] = row[0]
        cursor.updateRow(row)
    del row
    del cursor
    arcpy.DeleteField_management(thiessen_valley, "SUM")
    table_97 = ZonalStatisticsAsTable(thiessen_valley, "FID", conversion_97, "table_97", "", "SUM")
    arcpy.JoinField_management(thiessen_valley, "FID", table_97, "FID", "SUM")
    arcpy.AddField_management(thiessen_valley, "sum_inv", "DOUBLE")
    cursor = arcpy.da.UpdateCursor(thiessen_valley, ["SUM", "sum_inv"])
    for row in cursor:
        row[1] = row[0]
        cursor.updateRow(row)
    del row
    del cursor
    arcpy.DeleteField_management(thiessen_valley, "SUM")
    table_98 = ZonalStatisticsAsTable(thiessen_valley, "FID", conversion_98, "table_98", "", "SUM")
    arcpy.JoinField_management(thiessen_valley, "FID", table_98, "FID", "SUM")
    arcpy.AddField_management(thiessen_valley, "sum_dev", "DOUBLE")
    cursor = arcpy.da.UpdateCursor(thiessen_valley, ["SUM", "sum_dev"])
    for row in cursor:
        row[1] = row[0]
        cursor.updateRow(row)
    del row
    del cursor
    arcpy.DeleteField_management(thiessen_valley, "SUM")
    table_99 = ZonalStatisticsAsTable(thiessen_valley, "FID", conversion_99, "table_99", "", "SUM")
    arcpy.JoinField_management(thiessen_valley, "FID", table_99, "FID", "SUM")
    arcpy.AddField_management(thiessen_valley, "sum_ag", "DOUBLE")
    cursor = arcpy.da.UpdateCursor(thiessen_valley, ["SUM", "sum_ag"])
    for row in cursor:
        row[1] = row[0]
        cursor.updateRow(row)
    del row
    del cursor
    arcpy.DeleteField_management(thiessen_valley, "SUM")

    cursor = arcpy.da.UpdateCursor(thiessen_valley, "COUNT")
    for row in cursor:
        if row[0] == 0:
            row[0] = 1
            cursor.updateRow(row)
    del row
    del cursor

    arcpy.AddField_management(thiessen_valley, "prop_noch", "DOUBLE")
    cursor = arcpy.da.UpdateCursor(thiessen_valley, ["COUNT", "sum_noch", "prop_noch"])
    for row in cursor:
        index = row[1] / row[0]
        row[2] = index
        cursor.updateRow(row)
    del row
    del cursor
    arcpy.AddField_management(thiessen_valley, "prop_grsh", "DOUBLE")
    cursor = arcpy.da.UpdateCursor(thiessen_valley, ["COUNT", "sum_grsh", "prop_grsh"])
    for row in cursor:
        index = row[1] / row[0]
        row[2] = index
        cursor.updateRow(row)
    del row
    del cursor
    arcpy.AddField_management(thiessen_valley, "prop_deveg", "DOUBLE")
    cursor = arcpy.da.UpdateCursor(thiessen_valley, ["COUNT", "sum_deveg", "prop_deveg"])
    for row in cursor:
        index = row[1] / row[0]
        row[2] = index
        cursor.updateRow(row)
    del row
    del cursor
    arcpy.AddField_management(thiessen_valley, "prop_con", "DOUBLE")
    cursor = arcpy.da.UpdateCursor(thiessen_valley, ["COUNT", "sum_con", "prop_con"])
    for row in cursor:
        index = row[1] / row[0]
        row[2] = index
        cursor.updateRow(row)
    del row
    del cursor
    arcpy.AddField_management(thiessen_valley, "prop_inv", "DOUBLE")
    cursor = arcpy.da.UpdateCursor(thiessen_valley, ["COUNT", "sum_inv", "prop_inv"])
    for row in cursor:
        index = row[1] / row[0]
        row[2] = index
        cursor.updateRow(row)
    del row
    del cursor
    arcpy.AddField_management(thiessen_valley, "prop_dev", "DOUBLE")
    cursor = arcpy.da.UpdateCursor(thiessen_valley, ["COUNT", "sum_dev", "prop_dev"])
    for row in cursor:
        index = row[1] / row[0]
        row[2] = index
        cursor.updateRow(row)
    del row
    del cursor
    arcpy.AddField_management(thiessen_valley, "prop_ag", "DOUBLE")
    cursor = arcpy.da.UpdateCursor(thiessen_valley, ["COUNT", "sum_ag", "prop_ag"])
    for row in cursor:
        index = row[1] / row[0]
        row[2] = index
        cursor.updateRow(row)
    del row
    del cursor

    prop0_array = arcpy.da.FeatureClassToNumPyArray(thiessen_valley, "prop_noch")
    array0 = np.asarray(prop0_array, np.float64)
    prop50_array = arcpy.da.FeatureClassToNumPyArray(thiessen_valley, "prop_grsh")
    array50 = np.asarray(prop50_array, np.float64)
    prop60_array = arcpy.da.FeatureClassToNumPyArray(thiessen_valley, "prop_deveg")
    array60 = np.asarray(prop60_array, np.float64)
    prop80_array = arcpy.da.FeatureClassToNumPyArray(thiessen_valley, "prop_con")
    array80 = np.asarray(prop80_array, np.float64)
    prop97_array = arcpy.da.FeatureClassToNumPyArray(thiessen_valley, "prop_inv")
    array97 = np.asarray(prop97_array, np.float64)
    prop98_array = arcpy.da.FeatureClassToNumPyArray(thiessen_valley, "prop_dev")
    array98 = np.asarray(prop98_array, np.float64)
    prop99_array = arcpy.da.FeatureClassToNumPyArray(thiessen_valley, "prop_ag")
    array99 = np.asarray(prop99_array, np.float64)

    del prop0_array, prop50_array, prop60_array, prop80_array, prop97_array, prop98_array, prop99_array

    out_conv_code = np.zeros(len(array0), dtype=np.float64)
    for i in range(len(array0)):
        if array0[i] >= 0.85:  #if no change proportion is greater than or equal to 0.9
            out_conv_code[i] = 1 # no change
        else:  #if no change proportion is less than 0.9, move on to next greatest proportion
            if array50[i] > array60[i] and array50[i] > array80[i] and array50[i] > array97[i] and array50[i] > array98[i] and array50[i] > array99[i]: # if grass/shrubland is next most dominant
                if array50[i] <= 0.25:
                    out_conv_code[i] = 11 # minor conversion to grass/shrubland
                elif array50[i] > 0.25 and array50[i] <= 0.5:
                    out_conv_code[i] = 12 # moderate conversion to grass/shrubland
                else:
                    out_conv_code[i] = 13 # significant conversion to grass/shrubland
            elif array60[i] > array50[i] and array60[i] > array80[i] and array60[i] > array97[i] and array60[i] > array98[i] and array60[i] > array99[i]: # if barren is next most dominant
                if array60[i] <= 0.25:
                    out_conv_code[i] = 21 # minor devegetation
                elif array60[i] > 0.25 and array60[i] <= 0.5:
                    out_conv_code[i] = 22 # moderate devegetation
                else:
                    out_conv_code[i] = 23 # significant devegetation
            elif array80[i] > array50[i] and array80[i] > array60[i] and array80[i] > array97[i] and array80[i] > array98[i] and array80[i] > array99[i]: # if conifer encoachment is next most dominant
                if array80[i] <= 0.25:
                    out_conv_code[i] = 31 # minor conifer encroachment
                elif array80[i] > 0.25 and array80[i] <= 0.5:
                    out_conv_code[i] = 32 # moderate conifer encroachment
                else:
                    out_conv_code[i] = 33 # significant conifer encroachment
            elif array97[i] > array50[i] and array97[i] > array60[i] and array97[i] > array80[i] and array97[i] > array98[i] and array97[i] > array99[i]: # if conversion to invasive is next most dominant
                if array97[i] <= 0.25:
                    out_conv_code[i] = 41 # minor conversion to invasive
                elif array97[i] > 0.25 and array97[i] <= 0.5:
                    out_conv_code[i] = 42 # moderate conversion to invasive
                else:
                    out_conv_code[i] = 43 # significant conversion to invasive
            elif array98[i] > array50[i] and array98[i] > array60[i] and array98[i] > array80[i] and array98[i] > array97[i] and array98[i] > array99[i]: # if urbanization is next most dominant
                if array98[i] <= 0.25:
                    out_conv_code[i] = 51 # minor urbanization
                elif array98[i] > 0.25 and array98[i] <= 0.5:
                    out_conv_code[i] = 52 # moderate urbanization
                else:
                    out_conv_code[i] = 53 # significant urbanization
            elif array99[i] > array50[i] and array99[i] > array60[i] and array99[i] > array80[i] and array99[i] > array97[i] and array99[i] > array98[i]: # if conversion to agriculture is next most dominant
                if array99[i] <= 0.25:
                    out_conv_code[i] = 61 # minor conversion to agriculture
                elif array99[i] > 0.25 and array99[i] <= 0.5:
                    out_conv_code[i] = 62 # moderate conversion to agriculture
                else:
                    out_conv_code[i] = 63 # significant conversion to agriculture
            else:
                out_conv_code[i] = 0

    fid = np.arange(0, len(out_conv_code), 1)
    columns = np.column_stack((fid, out_conv_code))
    out_table = os.path.dirname(thiessen_valley) + '/Conv_Table.txt'
    np.savetxt(out_table, columns, delimiter=',', header='FID, conv_code', comments='')

    conv_code_table = scratch + '/conv_code_table'
    arcpy.CopyRows_management(out_table, conv_code_table)
    arcpy.JoinField_management(thiessen_valley, 'FID', conv_code_table, 'FID', 'conv_code')
    arcpy.Delete_management(out_table)

    arcpy.AddField_management(thiessen_valley, "conv_type", "text", "", "", 50)
    cursor = arcpy.da.UpdateCursor(thiessen_valley, ['conv_code', 'conv_type'])
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

    arcpy.Intersect_analysis([intersect2, thiessen_valley], fcOut, "ALL", "", "LINE")

    arcpy.Delete_management(thiessen_valley)

    d_fields = [f.name for f in arcpy.ListFields(fcOut, "FID_*")]
    arcpy.DeleteField_management(fcOut, d_fields)
    arcpy.DeleteField_management(fcOut, ["Id_1", "Shape_Le_1", "Input_FID"])


    return


def score_vegetation(evt, bps):
    lf1 = arcpy.ListFields(evt, "VEG_SCORE")
    if len(lf1) is not 1:
        arcpy.AddField_management(evt, "VEG_SCORE", "DOUBLE")

    cursor = arcpy.da.UpdateCursor(evt, ["EVT_PHYS", "VEG_SCORE"])
    for row in cursor:
        if row[0] == "Riparian":
            row[1] = 1
        elif row[0] == "Open Water":
            row[1] = 1
        elif row[0] == "Hardwood":
            row[1] = 1
        elif row[0] == "Conifer-Hardwood":
            row[1] = 1
        cursor.updateRow(row)
    del row
    del cursor

    cursor1 = arcpy.da.UpdateCursor(evt, ["EVT_GP", "VEG_SCORE"])
    for row in cursor1:
        if row[0] == "602":
            row[1] = 1
        elif row[0] == "701":
            row[1] = 0
        elif row[0] == "708":
            row[1] = 0
        elif row[0] == "709":
            row[1] = 0
        cursor1.updateRow(row)
    del row
    del cursor1

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
        else:
            row[2] = 50
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

if __name__ == '__main__':
    main(
        sys.argv[1],
        sys.argv[2],
        sys.argv[3],
        sys.argv[4],
        sys.argv[5],
        sys.argv[6],
        sys.argv[7])
