
#-------------------------------------------------------------------------------
# Name:        RVCA
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
import sys


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
    smooth_network = scratch + "/smooth_network"
    arcpy.SmoothLine_cartography(seg_network, smooth_network, "PAEK", "500 Meters")
    midpoints = scratch + "/midpoints"
    arcpy.FeatureVerticesToPoints_management(smooth_network, midpoints, "MID")
    thiessen = scratch + "/thiessen"
    arcpy.CreateThiessenPolygons_analysis(midpoints, thiessen)
    valley_buf = scratch + "/valley_buf"
    arcpy.Buffer_analysis(valley, valley_buf, "30 Meters", "FULL", "ROUND", "ALL")
    thiessen_valley = scratch + "/thiessen_valley"
    arcpy.Clip_analysis(thiessen, valley_buf, thiessen_valley)
    thiessen_valley2 = scratch + "/thiessen_valley2"
    arcpy.Clip_analysis(thiessen, valley, thiessen_valley2)

    # give the landfire rasters riparian vegetation scores and conversion scores
    score_vegetation(evt, bps)

    evt_lookup = Lookup(evt, "VEG_SCORE")
    bps_lookup = Lookup(bps, "VEG_SCORE")

    ###----------------------------------------------###
    ### RVCA analysis for areas without large rivers ###
    ###----------------------------------------------###

    if lg_river == None:
        evt_zs = ZonalStatistics(thiessen_valley, "OBJECTID", evt_lookup, "MEAN", "DATA")
        bps_zs = ZonalStatistics(thiessen_valley, "OBJECTID", bps_lookup, "MEAN", "DATA")
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
    ### RVCA analysis for areas with large rivers ###
    ###-------------------------------------------###

    else:
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

        evt_zs = ZonalStatistics(thiessen_valley, "OBJECTID", evt_wo_rivers, "MEAN", "DATA")
        bps_zs = ZonalStatistics(thiessen_valley, "OBJECTID", bps_wo_rivers, "MEAN", "DATA")
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

    evt_conversion_lookup = Lookup(evt, "CONVERSION")
    bps_conversion_lookup = Lookup(bps, "CONVERSION")
    conversion_raster = bps_conversion_lookup - evt_conversion_lookup
    int_conversion_raster = Int(conversion_raster)

    conversion_zs = ZonalStatistics(thiessen_valley2, "OBJECTID", int_conversion_raster, "MAJORITY", "DATA")
    int_conversion_zs = Int(conversion_zs)
    conversion_poly = scratch + "/conversion_poly"
    arcpy.RasterToPolygon_conversion(int_conversion_zs, conversion_poly)


    arcpy.Intersect_analysis([intersect2, conversion_poly], fcOut, "", "", "LINE")
    arcpy.AddField_management(fcOut, "CONV_CODE", "DOUBLE")

    cursor12 = arcpy.da.UpdateCursor(fcOut, ["GRIDCODE", "CONV_CODE"])
    for row in cursor12:
        row[1] = row[0]
        cursor12.updateRow(row)
    del row
    del cursor12

    arcpy.DeleteField_management(fcOut, "GRIDCODE")

    arcpy.AddField_management(fcOut, "CONV_TYPE", "TEXT")

    cursor13 = arcpy.da.UpdateCursor(fcOut, ["CONV_CODE", "CONV_TYPE"])
    for row in cursor13:
        if row[0] == 0:
            row[1] = "No Change"
        elif row[0] == 99:
            row[1] = "Conversion to Agriculture"
        elif row[0] == 98:
            row[1] = "Conversion to Developed"
        elif row[0] == 97:
            row[1] = "Conversion to Invasive Vegetation"
        elif row[0] == 80:
            row[1] = "Conifer Encroachment"
        elif row[0] == 60:
            row[1] = "Conversion to Barren"
        elif row[0] == 50:
            row[1] = "Upland Encroachment"
        elif row[0] == -400:
            row[1] = "Flooded"
        elif row[0] == -80:
            row[1] = "Non-Riparian to Riparian"
        elif row[0] == 19:
            row[1] = "Conversion to Agriculture"
        elif row[0] == 18:
            row[1] = "Conversion to Developed"
        elif row[0] == 17:
            row[1] = "Conversion to Invasive Vegetation"
        elif row[0] == -20:
            row[1] = "Conversion to Barren"
        elif row[0] == -30:
            row[1] = "Upland Encroachment"
        elif row[0] == -480:
            row[1] = "Flooded"
        elif row[0] == -60:
            row[1] = "Non-Riparian to Riparian"
        elif row[0] == 39:
            row[1] = "Conversion to Agriculture"
        elif row[0] == 38:
            row[1] = "Conversion to Developed"
        elif row[0] == 37:
            row[1] = "Conversion to Invasive Vegetation"
        elif row[0] == 20:
            row[1] = "Conifer Encroachment"
        elif row[0] == -10:
            row[1] = "Upland Encroachment"
        elif row[0] == -50:
            row[1] = "Non-Riparian to Riparian"
        elif row[0] == 49:
            row[1] = "Conversion to Agriculture"
        elif row[0] == 48:
            row[1] = "Conversion to Developed"
        elif row[0] == 47:
            row[1] = "Conversion to Invasive Vegetation"
        elif row[0] == 30:
            row[1] = "Conifer Encroachment"
        elif row[0] == 10:
            row[1] = "Conversion to Barren"
        elif row[0] == -450:
            row[1] = "Flooded"
        else:
            row[1] ="Water Conversions"
        cursor13.updateRow(row)
    del row
    del cursor13

    arcpy.DeleteField_management(fcOut, ["FID_inters", "FID_inte_1", "FID_evt_me", "FID_diss_n", "FID_bps_me", "Id_1", "FID_conver", "Id_12", "Shape_Le_1"])

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
        sys.argv[6])
