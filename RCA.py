#-------------------------------------------------------------------------------
# Name:        Riparian Condition Assessment (RCA)
# Purpose:     Models floodplain/riparian area condition using three inputs: riparian departure,
#              land use intensity, and floodplain accessibility
#
# Author:      Jordan Gilbert
#
# Created:     11/2015
# Copyright:   (c) Jordan Gilbert 2015
# Licence:     <your licence>
#-------------------------------------------------------------------------------
import arcpy
from arcpy.sa import *
import sys
import os
import numpy as np
import skfuzzy as fuzz


def main(
    seg_network,
    frag_valley,
    evt,
    bps,
    lg_river,
    output,
    out_table,
    scratch = arcpy.env.scratchWorkspace):

    arcpy.env.overwriteOutput = True
    arcpy.CheckOutExtension("spatial")

    valley_fields = arcpy.ListFields(frag_valley, "Connected")
    if len(valley_fields) == 1:
        pass
    else:
        raise Exception("Valley input has no field 'Connected'")

    # create thiessen polygons clipped to the extent of a buffered valley bottom
    smooth_network = scratch + "/smooth_network"
    arcpy.SmoothLine_cartography(seg_network, smooth_network, "PAEK", "500 Meters")
    midpoints = scratch + "/midpoints"
    arcpy.FeatureVerticesToPoints_management(smooth_network, midpoints, "MID")
    thiessen = scratch + "/thiessen"
    arcpy.CreateThiessenPolygons_analysis(midpoints, thiessen)
    buf_valley = scratch + "/buf_valley"
    arcpy.Buffer_analysis(frag_valley, buf_valley, "30 Meters", "FULL", "ROUND", "ALL")
    thiessen_valley = scratch + "/thiessen_valley"
    arcpy.Clip_analysis(thiessen, buf_valley, thiessen_valley)

    arcpy.AddMessage('Classifying landfire rasters')
    score_landfire(evt, bps)

    arcpy.AddMessage('Calculating riparian departure')
    calc_rvd(evt, bps, thiessen_valley, lg_river, scratch)

    arcpy.AddMessage('Assessing land use intensity')
    calc_lui(evt, thiessen_valley, scratch)

    arcpy.AddMessage('Assessing floodplain connectivity')
    calc_connectivity(frag_valley, thiessen_valley, scratch)

    arcpy.AddMessage('Attributing stream network')
    diss_network = scratch + '/diss_network'
    arcpy.Dissolve_management(seg_network, diss_network)

    rvd_final = Raster(scratch + '/RVD_final')
    lui_final = Raster(scratch + '/Land_Use_Intensity')
    fp_conn_final = Raster(scratch + '/Floodplain_Connectivity')

    rvd100 = rvd_final * 100
    rvdint = Int(rvd100)
    rvd_poly = scratch + '/rvd_poly'
    arcpy.RasterToPolygon_conversion(rvdint, rvd_poly)

    lui100 = lui_final * 100
    luiint = Int(lui100)
    lui_poly = scratch + '/lui_poly'
    arcpy.RasterToPolygon_conversion(luiint, lui_poly)

    fp_conn100 = fp_conn_final * 100
    fp_connint = Int(fp_conn100)
    fp_conn_poly = scratch + '/fp_conn_poly'
    arcpy.RasterToPolygon_conversion(fp_connint, fp_conn_poly)

    intersect1 = scratch + '/intersect1'
    arcpy.Intersect_analysis([diss_network, rvd_poly], intersect1, "", "", "LINE")
    arcpy.AddField_management(intersect1, "GRID", "DOUBLE")
    arcpy.AddField_management(intersect1, "RVD", "DOUBLE")
    cursor = arcpy.da.UpdateCursor(intersect1, ["GRIDCODE", "GRID"])
    for row in cursor:
        row[1] = row[0]
        cursor.updateRow(row)
    del row
    del cursor
    cursor = arcpy.da.UpdateCursor(intersect1, ["GRID", "RVD"])
    for row in cursor:
        row[1] = row[0]/100
        cursor.updateRow(row)
    del row
    del cursor
    arcpy.DeleteField_management(intersect1, ["GRIDCODE", "GRID"])

    intersect2 = scratch + '/intersect2'
    arcpy.Intersect_analysis([intersect1, lui_poly], intersect2, "", "", "LINE")
    arcpy.AddField_management(intersect2, "GRID", "DOUBLE")
    arcpy.AddField_management(intersect2, "LUI", "DOUBLE")
    cursor = arcpy.da.UpdateCursor(intersect2, ["GRIDCODE", "GRID"])
    for row in cursor:
        row[1] = row[0]
        cursor.updateRow(row)
    del row
    del cursor
    cursor = arcpy.da.UpdateCursor(intersect2, ["GRID", "LUI"])
    for row in cursor:
        row[1] = row[0]/100
        cursor.updateRow(row)
    del row
    del cursor
    arcpy.DeleteField_management(intersect2, ["GRIDCODE", "GRID"])

    rca_final = output
    arcpy.Intersect_analysis([intersect2, fp_conn_poly], rca_final, "", "", "LINE")
    arcpy.AddField_management(rca_final, "GRID", "DOUBLE")
    arcpy.AddField_management(rca_final, "CONNECT", "DOUBLE")
    cursor = arcpy.da.UpdateCursor(rca_final, ["GRIDCODE", "GRID"])
    for row in cursor:
        row[1] = row[0]
        cursor.updateRow(row)
    del row
    del cursor
    cursor = arcpy.da.UpdateCursor(rca_final, ["GRID", "CONNECT"])
    for row in cursor:
        row[1] = row[0]/100
        cursor.updateRow(row)
    del row
    del cursor
    arcpy.DeleteField_management(rca_final, ["GRIDCODE", "GRID"])

    arcpy.DeleteField_management(rca_final, ["FID_inters", "FID_inte_1", "FID_diss_n", "FID_rvd_po", "FID_lui_po", "Id_1", "FID_fp_con", "Id_12", "Shape_Le_1"])

    arcpy.AddMessage('Calculating riparian condition')

    # get arrays from the fields of interest
    RVDarray = arcpy.da.FeatureClassToNumPyArray(rca_final, "RVD")
    LUIarray = arcpy.da.FeatureClassToNumPyArray(rca_final, "LUI")
    CONNECTarray = arcpy.da.FeatureClassToNumPyArray(rca_final, "CONNECT")

    # convert the data type of the arrays
    RVD = np.asarray(RVDarray, np.float64)
    LUI = np.asarray(LUIarray, np.float64)
    CONNECT = np.asarray(CONNECTarray, np.float64)
    CONDITION = np.linspace(0, 1, len(RVD))

    del RVDarray, LUIarray, CONNECTarray

    RVDrange = np.linspace(0, 1, len(RVD))
    LUIrange = np.linspace(0, 3, len(LUI))
    CONNECTrange = np.linspace(0, 1, len(CONNECT))

    # Define membership functions for each input
    RVDlarge = fuzz.trapmf(RVDrange, [0, 0, 0.3, 0.5])
    RVDsig = fuzz.trimf(RVDrange, [0.3, 0.5, 0.8])
    RVDminor = fuzz.trimf(RVDrange, [0.5, 0.85, 0.95])
    RVDneg = fuzz.trapmf(RVDrange, [0.85, 0.95, 1, 1])

    LUIhigh = fuzz.trapmf(LUIrange, [0, 0, 1.25, 1.75])
    LUImoderate = fuzz.trapmf(LUIrange, [1.25, 1.75, 2.5, 2.95])
    LUIlow = fuzz.trapmf(LUIrange, [2.5, 2.95, 3, 3])

    CONNECTlow = fuzz.trapmf(CONNECTrange, [0, 0, 0.5, 0.7])
    CONNECTmoderate = fuzz.trapmf(CONNECTrange, [0.5, 0.7, 0.9, 0.95])
    CONNECThigh = fuzz.trapmf(CONNECTrange, [0.9, 0.95, 1, 1])

    CONDpoor = fuzz.trapmf(CONDITION, [0, 0, 0.35, 0.5])
    CONDmod = fuzz.trimf(CONDITION, [0.35, 0.5, 0.8])
    CONDgood = fuzz.trimf(CONDITION, [0.5, 0.8, 0.95])
    CONDintact = fuzz.trapmf(CONDITION, [0.8, 0.95, 1, 1])

    # Create a copy of the relevant array for each MF and calculate membership in each
    RVDlarge_mem = np.copy(RVD)
    for i in np.nditer(RVDlarge_mem, op_flags=['readwrite']):
        i[...] = fuzz.interp_membership(RVDrange, RVDlarge, i)

    RVDsig_mem = np.copy(RVD)
    for i in np.nditer(RVDsig_mem, op_flags=['readwrite']):
        i[...] = fuzz.interp_membership(RVDrange, RVDsig, i)

    RVDminor_mem = np.copy(RVD)
    for i in np.nditer(RVDminor_mem, op_flags=['readwrite']):
        i[...] = fuzz.interp_membership(RVDrange, RVDminor, i)

    RVDneg_mem = np.copy(RVD)
    for i in np.nditer(RVDneg_mem, op_flags=['readwrite']):
        i[...] = fuzz.interp_membership(RVDrange, RVDneg, i)

    LUIhigh_mem = np.copy(LUI)
    for i in np.nditer(LUIhigh_mem, op_flags=['readwrite']):
        i[...] = fuzz.interp_membership(LUIrange, LUIhigh, i)

    LUImoderate_mem = np.copy(LUI)
    for i in np.nditer(LUImoderate_mem, op_flags=['readwrite']):
        i[...] = fuzz.interp_membership(LUIrange, LUImoderate, i)

    LUIlow_mem = np.copy(LUI)
    for i in np.nditer(LUIlow_mem, op_flags=['readwrite']):
        i[...] = fuzz.interp_membership(LUIrange, LUIlow, i)

    CONNECTlow_mem = np.copy(CONNECT)
    for i in np.nditer(CONNECTlow_mem, op_flags=['readwrite']):
        i[...] = fuzz.interp_membership(CONNECTrange, CONNECTlow, i)

    CONNECTmoderate_mem = np.copy(CONNECT)
    for i in np.nditer(CONNECTmoderate_mem, op_flags=['readwrite']):
        i[...] = fuzz.interp_membership(CONNECTrange, CONNECTmoderate, i)

    CONNECThigh_mem = np.copy(CONNECT)
    for i in np.nditer(CONNECThigh_mem, op_flags=['readwrite']):
        i[...] = fuzz.interp_membership(CONNECTrange, CONNECThigh, i)

    del LUI, CONNECT, RVDrange, LUIrange, CONNECTrange

    # rules
    rule1 = np.fmin(RVDlarge_mem, np.fmin(LUIlow_mem, CONNECTlow_mem))
    rule2 = np.fmin(RVDlarge_mem, np.fmin(LUIlow_mem, CONNECTmoderate_mem))
    rule3 = np.fmin(RVDlarge_mem, np.fmin(LUIlow_mem, CONNECThigh_mem))
    rule4 = np.fmin(RVDlarge_mem, np.fmin(LUImoderate_mem, CONNECTlow_mem))
    rule5 = np.fmin(LUImoderate_mem, CONNECTmoderate_mem)
    rule6 = np.fmin(RVDlarge_mem, np.fmin(LUImoderate_mem, CONNECThigh_mem))
    rule7 = np.fmin(LUIhigh_mem, CONNECTlow_mem)
    rule8 = np.fmin(LUIhigh_mem, CONNECTmoderate_mem)
    rule9 = np.fmin(LUIhigh_mem, CONNECThigh_mem)
    rule10 = np.fmin(RVDsig_mem, np.fmin(LUIlow_mem, CONNECTlow_mem))
    rule11 = np.fmin(RVDsig_mem, np.fmin(LUIlow_mem, CONNECTmoderate_mem))
    rule12 = np.fmin(RVDsig_mem, np.fmin(LUIlow_mem, CONNECThigh_mem))
    rule13 = np.fmin(RVDsig_mem, np.fmin(LUImoderate_mem, CONNECTlow_mem))
    rule14 = np.fmin(RVDsig_mem, np.fmin(LUImoderate_mem, CONNECThigh_mem))
    rule15 = np.fmin(RVDminor_mem, np.fmin(LUIlow_mem, CONNECTlow_mem))
    rule16 = np.fmin(RVDminor_mem, np.fmin(LUIlow_mem, CONNECTmoderate_mem))
    rule17 = np.fmin(RVDminor_mem, np.fmin(LUIlow_mem, CONNECThigh_mem))
    rule18 = np.fmin(RVDminor_mem, np.fmin(LUImoderate_mem, CONNECTlow_mem))
    rule19 = np.fmin(RVDminor_mem, np.fmin(LUImoderate_mem, CONNECThigh_mem))
    rule20 = np.fmin(RVDneg_mem, np.fmin(LUIlow_mem, CONNECTlow_mem))
    rule21 = np.fmin(RVDneg_mem, np.fmin(LUIlow_mem, CONNECTmoderate_mem))
    rule22 = np.fmin(RVDneg_mem, np.fmin(LUIlow_mem, CONNECThigh_mem))
    rule23 = np.fmin(RVDneg_mem, np.fmin(LUImoderate_mem, CONNECTlow_mem))
    rule24 = np.fmin(RVDneg_mem, np.fmin(LUImoderate_mem, CONNECThigh_mem))

    # output membership functions
    out_intact1 = fuzz.relation_min(rule17, CONDintact)
    out_intact2 = fuzz.relation_min(rule22, CONDintact)
    out_good1 = fuzz.relation_min(rule3, CONDgood)
    out_good2 = fuzz.relation_min(rule12, CONDgood)
    out_good3 = fuzz.relation_min(rule16, CONDgood)
    out_good4 = fuzz.relation_min(rule21, CONDgood)
    out_good5 = fuzz.relation_min(rule24, CONDgood)
    out_mod1 = fuzz.relation_min(rule2, CONDmod)
    out_mod2 = fuzz.relation_min(rule5, CONDmod)
    out_mod3 = fuzz.relation_min(rule6, CONDmod)
    out_mod4 = fuzz.relation_min(rule9, CONDmod)
    out_mod5 = fuzz.relation_min(rule10, CONDmod)
    out_mod6 = fuzz.relation_min(rule11, CONDmod)
    out_mod7 = fuzz.relation_min(rule14, CONDmod)
    out_mod8 = fuzz.relation_min(rule15, CONDmod)
    out_mod9 = fuzz.relation_min(rule18, CONDmod)
    out_mod10 = fuzz.relation_min(rule19, CONDmod)
    out_mod11 = fuzz.relation_min(rule20, CONDmod)
    out_mod12 = fuzz.relation_min(rule23, CONDmod)
    out_poor1 = fuzz.relation_min(rule1, CONDpoor)
    out_poor2 = fuzz.relation_min(rule4, CONDpoor)
    out_poor3 = fuzz.relation_min(rule7, CONDpoor)
    out_poor4 = fuzz.relation_min(rule8, CONDpoor)
    out_poor5 = fuzz.relation_min(rule13, CONDpoor)

    del rule1, rule2, rule3, rule4, rule5, rule6, rule7, rule8, rule9, rule10, rule11, rule12, rule13, rule14, rule15, rule16, rule17, rule18, rule19, rule20, rule21, rule22, rule23, rule24

    # aggregate output membership functions
    aggregated =  np.fmax(out_intact1, np.fmax(out_intact2, np.fmax(out_good1, np.fmax(out_good2, np.fmax(out_good3, np.fmax(out_good4, np.fmax(out_good5, np.fmax(out_mod1,
                  np.fmax(out_mod2, np.fmax(out_mod3, np.fmax(out_mod4, np.fmax(out_mod5, np.fmax(out_mod6, np.fmax(out_mod7, np.fmax(out_mod8, np.fmax(out_mod9,
                  np.fmax(out_mod10, np.fmax(out_mod11, np.fmax(out_mod12, np.fmax(out_poor1, np.fmax(out_poor2, np.fmax(out_poor3, np.fmax(out_poor4, out_poor5)))))))))))))))))))))))

    del out_intact1, out_intact2, out_good1, out_good2, out_good3, out_good4, out_good5, out_mod1, out_mod2, out_mod3, out_mod4, out_mod5, out_mod6, out_mod7, out_mod8, out_mod9, out_mod10, out_mod11, out_mod12, out_poor1, out_poor2, out_poor3, out_poor4, out_poor5

    # Defuzzify
    out = np.zeros_like(RVD)
    for i in range(len(out)):
        out[i] = fuzz.defuzz(CONDITION, aggregated[i, :], 'centroid')

    # save the output text file
    fid = np.arange(0, len(out), 1)
    columns = np.column_stack((fid, out))
    np.savetxt(out_table, columns, delimiter=',', header='FID, CONDITION', comments='')


    arcpy.CheckInExtension('spatial')

    return

def score_landfire(evt, bps):
    evt_fields = arcpy.ListFields(evt, "VEG_SCORE")
    if len(evt_fields) is not 1:
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
        elif row[1] == 708:
            row[2] = 0
        elif row[1] == 709:
            row[2] = 0
        elif row[1] == 701:
            row[2] = 0
        elif row[1] == 602:
            row[2] = 1
        elif row[1] == 603:
            row[2] = 1
        else:
            row[2] = 0
        cursor.updateRow(row)
    del row
    del cursor

    bps_fields = arcpy.ListFields(bps, "VEG_SCORE")
    if len(bps_fields) is not 1:
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

    evt_fields2 = arcpy.ListFields(evt, "LUI")
    if len(evt_fields2) is not 1:
        arcpy.AddField_management(evt, "LUI", "DOUBLE")

    cursor3 = arcpy.da.UpdateCursor(evt, ["EVT_PHYS", "EVT_GP", "LUI"])
    for row in cursor3:
        if row[0] == "Barren":
            row[2] = 3
        elif row[0] == "Conifer":
            row[2] = 3
        elif row[0] == "Conifer-Hardwood":
            row[2] = 3
        elif row[0] == "Developed":
            row[2] = 1.5
        elif row[0] == "Developed-High Intensity":
            row[2] = 0
        elif row[0] == "Developed-Low Intensity":
            row[2] = 0
        elif row[0] == "Developed-Medium Intensity":
            row[2] = 0
        elif row[0] == "Developed-Roads":
            row[2] = 0
        elif row[0] == "Exotic Herbaceous":
            row[2] = 2
        elif row[0] == "Exotic Tree-Shrub":
            row[2] = 2
        elif row[0] == "Grassland":
            row[2] = 3
        elif row[0] == "Hardwood":
            row[2] = 3
        elif row[0] == "Open Water":
            row[2] = 3
        elif row[0] == "Quarries-Strip Mines-Gravel Pits":
            row[2] = 1
        elif row[0] == "Riparian":
            row[2] = 3
        elif row[0] == "Shrubland":
            row[2] = 3
        elif row[0] == "Snow-Ice":
            row[2] = 3
        elif row[0] == "Sparsely Vegetated":
            row[2] = 3
        elif row[1] == "60":
            row[2] = 1
        elif row[1] == "61":
            row[2] = 1
        elif row[1] == "62":
            row[2] = 1
        elif row[1] == "63":
            row[2] = 1
        elif row[1] == "64":
            row[2] = 1
        elif row[1] == "65":
            row[2] = 1
        elif row[1] == "66":
            row[2] = 2
        elif row[1] == "67":
            row[2] = 2
        elif row[1] == "68":
            row[2] = 1
        elif row[1] == "69":
            row[2] = 1
        elif row[1] == "81":
            row[2] = 2
        elif row[1] == "82":
            row[2] = 1
        cursor3.updateRow(row)
    del row
    del cursor3



def calc_rvd(evt, bps, thiessen_valley, lg_river, scratch):
    evt_lookup = Lookup(evt, "VEG_SCORE")
    bps_lookup = Lookup(bps, "VEG_SCORE")

    if lg_river == None:
         # create raster output of riparian vegetation departure for areas without large rivers
        evt_zs = ZonalStatistics(thiessen_valley, "OBJECTID", evt_lookup, "MEAN", "DATA")
        bps_zs = ZonalStatistics(thiessen_valley, "OBJECTID", bps_lookup, "MEAN", "DATA")

        evtx100 = evt_zs * 100
        evt_int = Int(evtx100)

        arcpy.AddField_management(evt_int, "NEWVALUE", "SHORT")
        cursor = arcpy.UpdateCursor(evt_int)
        for row in cursor:
            row.NEWVALUE = row.Value
            cursor.updateRow(row)
        del row
        del cursor
        cursor2 = arcpy.UpdateCursor(evt_int)
        for row in cursor2:
            if row.Value == 0:
                row.NEWVALUE = 1
                cursor2.updateRow(row)
        del row
        del cursor2

        evt_int_lookup = Lookup(evt_int, "NEWVALUE")
        evt_float = Float(evt_int_lookup)
        evt_final = evt_float/100

        bpsx100 = bps_zs * 100
        bps_int = Int(bpsx100)

        arcpy.AddField_management(bps_int, "NEWVALUE", "SHORT")
        cursor3 = arcpy.UpdateCursor(bps_int)
        for row in cursor3:
            row.NEWVALUE = row.Value
            cursor3.updateRow(row)
        del row
        del cursor3
        cursor4 = arcpy.UpdateCursor(bps_int)
        for row in cursor4:
            if row.Value == 0:
                row.NEWVALUE = 1
                cursor4.updateRow(row)
        del row
        del cursor4

        bps_int_lookup = Lookup(bps_int, "NEWVALUE")
        bps_float = Float(bps_int_lookup)
        bps_final = bps_float/100

        rvd_init = evt_final/bps_final
        rvdx100 = rvd_init * 100
        rvd_int = Int(rvdx100)

        arcpy.AddField_management(rvd_int, "NEWVALUE", "SHORT")
        cursor5 = arcpy.UpdateCursor(rvd_int)
        for row in cursor5:
            row.NEWVALUE = row.Value
            cursor5.updateRow(row)
        del row
        del cursor5
        cursor6 = arcpy.UpdateCursor(rvd_int)
        for row in cursor6:
            if row.Value > 100:
                row.NEWVALUE = 100
                cursor6.updateRow(row)
        del row
        del cursor6

        rvd_lookup = Lookup(rvd_int, "NEWVALUE")
        rvd_float = Float(rvd_lookup)
        rvd_final = rvd_float/100
        rvd_final.save(scratch + "/RVD_final")

    else:
        # create raster output of riparian vegetation departure for areas with large rivers
        arcpy.env.extent = thiessen_valley
        lg_river_raster = ExtractByMask(evt, lg_river)
        cursor = arcpy.UpdateCursor(lg_river_raster)
        for row in cursor:
            row.setValue("VEG_SCORE", 8)
            cursor.updateRow(row)
        del row
        del cursor

        river_lookup = Lookup(lg_river_raster, "VEG_SCORE")
        river_reclass = Reclassify(river_lookup, "VALUE", "8 8; NODATA 0")
        evt_calc = river_reclass + evt_lookup
        bps_calc = river_reclass + bps_lookup
        evt_wo_rivers = Reclassify(evt_calc, "VALUE", "0 0; 1 1; 8 NODATA; 9 NODATA")
        bps_wo_rivers = Reclassify(bps_calc, "VALUE", "0 0; 1 1; 8 NODATA; 9 NODATA")

        evt_zs = ZonalStatistics(thiessen_valley, "OBJECTID", evt_wo_rivers, "MEAN", "DATA")
        bps_zs = ZonalStatistics(thiessen_valley, "OBJECTID", bps_wo_rivers, "MEAN", "DATA")

        evtx100 = evt_zs * 100
        evt_int = Int(evtx100)

        arcpy.AddField_management(evt_int, "NEWVALUE", "SHORT")
        cursor = arcpy.UpdateCursor(evt_int)
        for row in cursor:
            row.NEWVALUE = row.Value
            cursor.updateRow(row)
        del row
        del cursor
        cursor2 = arcpy.UpdateCursor(evt_int)
        for row in cursor2:
            if row.Value == 0:
                row.NEWVALUE = 1
                cursor2.updateRow(row)
        del row
        del cursor2

        evt_int_lookup = Lookup(evt_int, "NEWVALUE")
        evt_float = Float(evt_int_lookup)
        evt_final = evt_float/100

        bpsx100 = bps_zs * 100
        bps_int = Int(bpsx100)

        arcpy.AddField_management(bps_int, "NEWVALUE", "SHORT")
        cursor3 = arcpy.UpdateCursor(bps_int)
        for row in cursor3:
            row.NEWVALUE = row.Value
            cursor3.updateRow(row)
        del row
        del cursor3
        cursor4 = arcpy.UpdateCursor(bps_int)
        for row in cursor4:
            if row.Value == 0:
                row.NEWVALUE = 1
                cursor4.updateRow(row)
        del row
        del cursor4

        bps_int_lookup = Lookup(bps_int, "NEWVALUE")
        bps_float = Float(bps_int_lookup)
        bps_final = bps_float/100

        rvd_init = evt_final/bps_final
        rvdx100 = rvd_init * 100
        rvd_int = Int(rvdx100)

        arcpy.AddField_management(rvd_int, "NEWVALUE", "SHORT")
        cursor5 = arcpy.UpdateCursor(rvd_int)
        for row in cursor5:
            row.NEWVALUE = row.Value
            cursor5.updateRow(row)
        del row
        del cursor5
        cursor6 = arcpy.UpdateCursor(rvd_int)
        for row in cursor6:
            if row.Value > 100:
                row.NEWVALUE = 100
                cursor6.updateRow(row)
        del row
        del cursor6

        rvd_lookup = Lookup(rvd_int, "NEWVALUE")
        rvd_float = Float(rvd_lookup)
        rvd_final = rvd_float/100
        rvd_final.save(scratch + "/RVD_final")

    return rvd_final

def calc_lui(evt, thiessen_valley, scratch):
    lui_lookup = Lookup(evt, "LUI")
    lui_zs = ZonalStatistics(thiessen_valley, "OBJECTID", lui_lookup, "MEAN", "DATA")
    lui_zs.save(scratch + '/Land_Use_Intensity')

    return lui_zs

def calc_connectivity(frag_valley, thiessen_valley, scratch):
    fp_conn = scratch + '/fp_conn'
    arcpy.PolygonToRaster_conversion(frag_valley, "Connected", fp_conn, "", "", 30)
    fp_conn_zs = ZonalStatistics(thiessen_valley, "OBJECTID", fp_conn, "MEAN", "DATA")
    fp_conn_zs.save(scratch + '/Floodplain_Connectivity')

    return fp_conn_zs





if __name__ == '__main__':
    main(
        sys.argv[1],
        sys.argv[2],
        sys.argv[3],
        sys.argv[4],
        sys.argv[5],
        sys.argv[6],
        sys.argv[7],
        sys.argv[8])
