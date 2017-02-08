# -------------------------------------------------------------------------------
# Name:        Riparian Condition Assessment (RCA)
# Purpose:     Models floodplain/riparian area condition using three inputs: riparian departure,
#              land use intensity, and floodplain accessibility
#
# Author:      Jordan Gilbert
#
# Created:     11/2015
# Latest Update: 02/08/2017
# Copyright:   (c) Jordan Gilbert 2017
# Licence:     This work is licensed under the Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International
#              License. To view a copy of this license, visit http://creativecommons.org/licenses/by-nc-sa/4.0/.
# -------------------------------------------------------------------------------
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

def main(
    projName,
    hucID,
    hucName,
    projPath,
    evt,
    bps,
    seg_network,
    frag_valley,
    lg_river,
    width_thresh,
    outName,
    scratch):

    arcpy.env.overwriteOutput = True
    arcpy.CheckOutExtension("spatial")

    # make sure that the fragmented valley input has a field called "connected"
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
    arcpy.Buffer_analysis(frag_valley, buf_valley, "10 Meters", "FULL", "ROUND", "ALL")
    if not os.path.exists(os.path.dirname(seg_network) + "/Thiessen"):
        os.mkdir(os.path.dirname(seg_network) + "/Thiessen")
    thiessen_valley = os.path.dirname(seg_network) + "/Thiessen/Thiessen_Valley.shp"
    arcpy.Clip_analysis(thiessen, buf_valley, thiessen_valley)

    # Add width field to thiessen polygons
    arcpy.AddField_management(thiessen_valley, "Perim", "DOUBLE")
    arcpy.AddField_management(thiessen_valley, "Area", "DOUBLE")
    arcpy.CalculateField_management(thiessen_valley, "Perim", "!SHAPE.LENGTH@METERS!", "PYTHON_9.3")
    arcpy.CalculateField_management(thiessen_valley, "Area", "!SHAPE.AREA@SQUAREMETERS!", "PYTHON_9.3")
    arcpy.AddField_management(thiessen_valley, "Width", "DOUBLE")
    with arcpy.da.UpdateCursor(thiessen_valley, ["Perim", "Area", "Width"]) as cur:
        for row in cur:
            perim, area, width = row
            row[-1] = ((perim/pi) * area) / (perim**2 / (4 * pi))
            cur.updateRow(row)
    del row
    del cur

    # separate unconfined from confined portions of valley bottom
    arcpy.MakeFeatureLayer_management(thiessen_valley, "thiessen_lyr")
    arcpy.SelectLayerByAttribute_management("thiessen_lyr", "NEW_SELECTION", '"Width" > {0}'.format(width_thresh))
    arcpy.FeatureClassToFeatureClass_conversion("thiessen_lyr", scratch, "wide_valley")
    arcpy.SelectLayerByAttribute_management("thiessen_lyr", "NEW_SELECTION", '"Width" <= {0}'.format(width_thresh))
    arcpy.FeatureClassToFeatureClass_conversion("thiessen_lyr", scratch, "narrow_valley")

    arcpy.AddMessage("Classifying vegetation rasters")
    score_landfire(evt, bps)

    arcpy.AddMessage("Calculating riparian departure")
    calc_rvd(evt, bps, thiessen_valley, lg_river, scratch)

    arcpy.AddMessage("Assessing land use intensity")
    calc_lui(evt, thiessen_valley, scratch)

    arcpy.AddMessage("Assessing floodplain connectivity")
    calc_connectivity(frag_valley, thiessen_valley, scratch)

    arcpy.AddMessage("Calculating overall vegetation departure")
    calc_veg(evt, bps, thiessen_valley, scratch)

    # attribute the network with "RVD", "LUI", "CONNECT", and "VEG" fields
    arcpy.AddMessage("Attributing stream network")
    diss_network = scratch + "/diss_network"
    arcpy.Dissolve_management(seg_network, diss_network)

    rvd_final = Raster(scratch + "/RVD_final")
    lui_final = Raster(os.path.dirname(os.path.dirname(evt)) + "/Ex_Rasters/Land_Use_Intensity.tif")
    fp_conn_final = Raster(scratch + "/Floodplain_Connectivity")
    veg_final = Raster(scratch + "/veg_final")

    rvd100 = rvd_final * 100
    rvdint = Int(rvd100)
    rvd_poly = scratch + "/rvd_poly"
    arcpy.RasterToPolygon_conversion(rvdint, rvd_poly)

    lui100 = lui_final * 100
    luiint = Int(lui100)
    lui_poly = scratch + "/lui_poly"
    arcpy.RasterToPolygon_conversion(luiint, lui_poly)

    fp_conn100 = fp_conn_final * 100
    fp_connint = Int(fp_conn100)
    fp_conn_poly = scratch + "/fp_conn_poly"
    arcpy.RasterToPolygon_conversion(fp_connint, fp_conn_poly)

    veg100 = veg_final * 100
    veg_int = Int(veg100)
    veg_poly = scratch + "/veg_poly"
    arcpy.RasterToPolygon_conversion(veg_int, veg_poly)

    intersect1 = scratch + "/intersect1"
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

    intersect2 = scratch + "/intersect2"
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

    intersect3 = scratch + "/intersect3"
    arcpy.Intersect_analysis([intersect2, fp_conn_poly], intersect3, "", "", "LINE")
    arcpy.AddField_management(intersect3, "GRID", "DOUBLE")
    arcpy.AddField_management(intersect3, "CONNECT", "DOUBLE")
    cursor = arcpy.da.UpdateCursor(intersect3, ["GRIDCODE", "GRID"])
    for row in cursor:
        row[1] = row[0]
        cursor.updateRow(row)
    del row
    del cursor
    cursor = arcpy.da.UpdateCursor(intersect3, ["GRID", "CONNECT"])
    for row in cursor:
        row[1] = row[0]/100
        cursor.updateRow(row)
    del row
    del cursor
    arcpy.DeleteField_management(intersect3, ["GRIDCODE", "GRID"])

    rca_input = scratch + "/rca_input"
    arcpy.Intersect_analysis([intersect3, veg_poly], rca_input, "", "", "LINE")
    arcpy.AddField_management(rca_input, "GRID", "DOUBLE")
    arcpy.AddField_management(rca_input, "VEG", "DOUBLE")
    cursor = arcpy.da.UpdateCursor(rca_input, ["GRIDCODE", "GRID"])
    for row in cursor:
        row[1] = row[0]
        cursor.updateRow(row)
    del row
    del cursor
    cursor = arcpy.da.UpdateCursor(rca_input, ["GRID", "VEG"])
    for row in cursor:
        row[1] = row[0]/100
        cursor.updateRow(row)
    del row
    del cursor
    arcpy.DeleteField_management(rca_input, ["GRIDCODE", "GRID"])

    df = [f.name for f in arcpy.ListFields(rca_input, "FID_*")]
    df2 = [f.name for f in arcpy.ListFields(rca_input, "Id_*")]
    df.extend(df2)
    arcpy.DeleteField_management(rca_input, df)

    arcpy.AddMessage("Calculating riparian condition")

    # set up output
    j = 1
    while os.path.exists(projPath + "/02_Analyses/Output_" + str(j)):
        j += 1

    os.mkdir(projPath + "/02_Analyses/Output_" + str(j))
    output = projPath + "/02_Analyses/Output_" + str(j) + "/" + str(outName) + ".shp"

    # # # calculate rca for segments in unconfined valleys # # #
    arcpy.MakeFeatureLayer_management(rca_input, "rca_in_lyr")
    wide_valley = scratch + "/wide_valley"
    arcpy.SelectLayerByLocation_management("rca_in_lyr", "HAVE_THEIR_CENTER_IN", wide_valley)
    arcpy.FeatureClassToFeatureClass_conversion("rca_in_lyr", scratch, "rca_u")
    rca_u = scratch + "/rca_u"

    ct = arcpy.GetCount_management(rca_u)
    count = int(ct.getOutput(0))
    if count is not 0:

        # fix values outside of range of membership functions.
        cursor = arcpy.da.UpdateCursor(rca_u, ["RVD", "LUI", "CONNECT"])
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
        RVDa = arcpy.da.FeatureClassToNumPyArray(rca_u, "RVD")
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

        LUI["high"] = fuzz.trapmf(LUI.universe, [0, 0, 0.416, 0.583])
        LUI["moderate"] = fuzz.trapmf(LUI.universe, [0.416, 0.583, 0.83, 0.983])
        LUI["low"] = fuzz.trapmf(LUI.universe, [0.83, 0.983, 1, 1])

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
        out_table = os.path.dirname(output) + "/RCA_Table.txt"
        np.savetxt(out_table, columns, delimiter=",", header="ID, COND_VAL", comments="")
        arcpy.CopyRows_management(out_table, "final_table")

        final_table = scratch + "/final_table"
        arcpy.JoinField_management(rca_u, "OBJECTID", final_table, "OBJECTID", "COND_VAL")
        rca_u_final = scratch + "/rca_u_final"
        arcpy.CopyFeatures_management(rca_u, rca_u_final)

    else:
        pass

    # # # calculate rca for segments in confined valleys # # #
    narrow_valley = scratch + "/narrow_valley"
    arcpy.SelectLayerByLocation_management("rca_in_lyr", "HAVE_THEIR_CENTER_IN", narrow_valley)
    arcpy.FeatureClassToFeatureClass_conversion("rca_in_lyr", scratch, "rca_c")
    rca_c = scratch + "/rca_c"

    arcpy.AddField_management(rca_c, "CONDITION", "TEXT")
    cursor = arcpy.da.UpdateCursor(rca_c, ["LUI", "CONNECT", "VEG", "CONDITION"])
    for row in cursor:
        if row[0] >= 0.96 and row[1] == 1 and row[2] > 0.8:
            row[3] = "Confined - Unimpacted"
        else:
            row[3] = "Confined - Impacted"
        cursor.updateRow(row)
    del row
    del cursor

    # merge the results of the rca for confined and unconfined valleys
    arcpy.Merge_management([rca_u_final, rca_c], output)

    # add final condition category for each segment
    cursor = arcpy.da.UpdateCursor(output, ["COND_VAL", "CONDITION"])
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

    # # # Write xml file # # #

    if not os.path.exists(projPath + "/rca.xml"):
        # xml file
        xmlfile = projPath + "/rca.xml"

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
                                 productVersion="1.0.1", guid=getUUID())

        newxml.addParameter("width_thresh", width_thresh, newxml.RCArealizations[0])

        # add inputs and outputs to xml file
        newxml.addProjectInput("Raster", "Existing Cover", evt[evt.find("01_Inputs"):], iid="EXCOV1",
                               guid=getUUID())
        newxml.addRCAInput(newxml.RCArealizations[0], "Existing Vegetation", ref="EXCOV1")

        newxml.addProjectInput("Raster", "Historic Cover", bps[bps.find("01_Inputs"):], iid="HISTCOV1",
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

        newxml.addRCAInput(newxml.RCArealizations[0], "Existing Raster", "Existing Riparian",
                           path=os.path.dirname(os.path.dirname(evt[evt.find("01_Inputs"):])) + "/Ex_Rasters/Ex_Riparian.tif", guid=getUUID())
        newxml.addRCAInput(newxml.RCArealizations[0], "Historic Raster", "Historic Riparian",
                           path=os.path.dirname(os.path.dirname(bps[bps.find("01_Inputs"):])) + "/Hist_Rasters/Hist_Riparian.tif", guid=getUUID())
        newxml.addRCAInput(newxml.RCArealizations[0], "Existing Raster", "Existing Vegetation Cover",
                           path=os.path.dirname(os.path.dirname(evt[evt.find("01_Inputs"):])) + "/Ex_Rasters/Ex_Veg_Cover.tif", guid=getUUID())
        newxml.addRCAInput(newxml.RCArealizations[0], "Historic Raster", "Historic Vegetation Cover",
                           path=os.path.dirname(os.path.dirname(bps[bps.find("01_Inputs")])) + "/Hist_Rasters/Hist_Veg_Cover.tif", guid=getUUID())
        newxml.addRCAInput(newxml.RCArealizations[0], "Existing Raster", "Land Use Intensity",
                           path=os.path.dirname(os.path.dirname(evt[evt.find("01_Inputs"):])) + "/Ex_Rasters/Land_Use_Intensity.tif", guid=getUUID())
        newxml.addRCAInput(newxml.RCArealizations[0], "Thiessen Polygons", "Thiessen Polygons",
                           path=os.path.dirname(seg_network[seg_network.find("01_Inputs")]) + "/Thiessen/Thiessen_Valley.shp", guid=getUUID())

        newxml.addOutput("Analysis", "Vector", "RCA", output[output.find("02_Analyses"):], newxml.RCArealizations[0], guid=getUUID())

        newxml.write()

    else:
        xmlfile = projPath + "/rca.xml"

        exxml = projectxml.ExistingXML(xmlfile)

        rcar = exxml.rz.findall("RCA")
        rcarf = rcar[-1]
        rname = rcarf.find("Name")
        k = 2
        while rname.text == "RCA Realization " + str(k):
            k += 1

        exxml.addRCARealization("RCA Realization " + str(k), rid="RZ" + str(k),
                                dateCreated=datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), productVersion="1.0.1")

        exxml.addParameter("width_thresh", width_thresh, exxml.RCArealizations[0])

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
            elif os.path.abspath(rasterpath[i]) == os.path.abspath(bps[bps.find("01_Inputs"):]):
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
            if os.path.abspath(evt[evt.find("01_Inputs"):]) == os.path.abspath(j):
                nlist.append("yes")
            else:
                nlist.append("no")
        if "yes" in nlist:
            pass
        else:
            exxml.addProjectInput("Raster", "Existing Cover", evt[evt.find("01_Inputs"):], iid="EXCOV" + str(k), guid=getUUID())
            exxml.addRCAInput(exxml.RCArealizations[0], "Existing Vegetation", ref="EXCOV" + str(k))
            exxml.addRCAInput(exxml.RCArealizations[0], "Existing Raster", "Existing Riparian",
                              path=os.path.dirname(os.path.dirname(evt[evt.find("01_Inputs"):])) + "/Ex_Rasters/Ex_Riparian.tif",
                              guid=getUUID())
            exxml.addRCAInput(exxml.RCArealizations[0], "Existing Raster", "Existing Vegetation Cover",
                              path=os.path.dirname(os.path.dirname(evt[evt.find("01_Inputs"):])) + "/Ex_Rasters/Ex_Veg_Cover.tif",
                              guid=getUUID())
            exxml.addRCAInput(exxml.RCArealizations[0], "Existing Raster", "Land Use Intensity",
                              path=os.path.dirname(os.path.dirname(evt[evt.find("01_Inputs"):])) + "/Ex_Rasters/Land_Use_Intensity.tif",
                              guid=getUUID())
        nlist2 = []
        for j in rasterpath:
            if os.path.abspath(bps[bps.find("01_Inputs"):]) == os.path.abspath(j):
                nlist2.append("yes")
            else:
                nlist2.append("no")
        if "yes" in nlist2:
            pass
        else:
            exxml.addProjectInput("Raster", "Historic Cover", bps[bps.find("01_Inputs"):], iid="HISTCOV" + str(k), guid=getUUID())
            exxml.addRCAInput(exxml.RCArealizations[0], "Historic Vegetation", ref="HISTCOV" + str(k))
            exxml.addRCAInput(exxml.RCArealizations[0], "Historic Raster", "Historic Riparian",
                              path=os.path.dirname(os.path.dirname(bps[bps.find("01_Inputs"):])) + "/Hist_Rasters/Hist_Riparian.tif",
                              guid=getUUID())
            exxml.addRCAInput(exxml.RCArealizations[0], "Historic Raster", "Historic Vegetation Cover",
                              path=os.path.dirname(os.path.dirname(bps[bps.find("01_Inputs"):])) + "/Hist_Rasters/Hist_Veg_Cover.tif",
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

        del nlist

        exxml.addOutput("Analysis", "Vector", "RCA Output", output[output.find("02_Analyses"):],
                        exxml.RCArealizations[0], guid=getUUID())

        exxml.write()

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
            row[2] = 1
        elif row[0] == "Conifer":
            row[2] = 1
        elif row[0] == "Conifer-Hardwood":
            row[2] = 1
        elif row[0] == "Developed":
            row[2] = 0.5
        elif row[0] == "Developed-High Intensity":
            row[2] = 0
        elif row[0] == "Developed-Low Intensity":
            row[2] = 0
        elif row[0] == "Developed-Medium Intensity":
            row[2] = 0
        elif row[0] == "Developed-Roads":
            row[2] = 0
        elif row[0] == "Exotic Herbaceous":
            row[2] = 0.66
        elif row[0] == "Exotic Tree-Shrub":
            row[2] = 0.66
        elif row[0] == "Grassland":
            row[2] = 1
        elif row[0] == "Hardwood":
            row[2] = 1
        elif row[0] == "Open Water":
            row[2] = 1
        elif row[0] == "Quarries-Strip Mines-Gravel Pits":
            row[2] = 0.33
        elif row[0] == "Riparian":
            row[2] = 1
        elif row[0] == "Shrubland":
            row[2] = 1
        elif row[0] == "Snow-Ice":
            row[2] = 1
        elif row[0] == "Sparsely Vegetated":
            row[2] = 1
        elif row[1] == "60":
            row[2] = 0.33
        elif row[1] == "61":
            row[2] = 0.33
        elif row[1] == "62":
            row[2] = 0.33
        elif row[1] == "63":
            row[2] = 0.33
        elif row[1] == "64":
            row[2] = 0.33
        elif row[1] == "65":
            row[2] = 0.33
        elif row[1] == "66":
            row[2] = 0.66
        elif row[1] == "67":
            row[2] = 0.66
        elif row[1] == "68":
            row[2] = 0.33
        elif row[1] == "69":
            row[2] = 0.33
        elif row[1] == "81":
            row[2] = 0.66
        elif row[1] == "82":
            row[2] = 0.33
        cursor3.updateRow(row)
    del row
    del cursor3

    evt_fields3 = arcpy.ListFields(evt, "VEGETATED")
    if len(evt_fields3) is not 1:
        arcpy.AddField_management(evt, "VEGETATED", "SHORT")

    cursor4 = arcpy.da.UpdateCursor(evt, ["EVT_PHYS", "VEGETATED"])
    for row in cursor4:
        if row[0] == "Open Water":
            row[1] = 0
        elif row[0] == "Non-vegetated":
            row[1] = 0
        elif row[0] == "Snow-Ice":
            row[1] = 0
        elif row[0] == "Developed-Low Intensity":
            row[1] = 0
        elif row[0] == "Developed-Medium Intensity":
            row[1] = 0
        elif row[0] == "Developed-High Intensity":
            row[1] = 0
        elif row[0] == "Developed-Roads":
            row[1] = 0
        elif row[0] == "Barren":
            row[1] = 0
        elif row[0] == "Quarries-Strip Mines-Gravel Pits":
            row[1] = 0
        elif row[0] == "Agricultural":
            row[1] = 0
        elif row[0] == "Exotic Herbaceous":
            row[1] = 0
        elif row[0] == "Exotic Tree-Shrub":
            row[0] = 0
        else:
            row[1] = 1
        cursor4.updateRow(row)
    del row
    del cursor4

    bps_fields2 = arcpy.ListFields(bps, "VEGETATED")
    if len(bps_fields2) is not 1:
        arcpy.AddField_management(bps, "VEGETATED", "SHORT")

    cursor5 = arcpy.da.UpdateCursor(bps, ["GROUPVEG", "VEGETATED"])
    for row in cursor5:
        if row[0] == "Open Water":
            row[1] = 0
        elif row[0] == "Perrennial Ice/Snow":
            row[1] = 0
        elif row[0] == "Barren-Rock/Sand/Clay":
            row[1] = 0
        elif row[0] == "Sparse":
            row[1] = 0
        else:
            row[1] = 1
        cursor5.updateRow(row)
    del row
    del cursor5


def calc_rvd(evt, bps, thiessen_valley, lg_river, scratch):
    evt_lookup = Lookup(evt, "VEG_SCORE")
    if not os.path.exists(os.path.dirname(os.path.dirname(evt)) + "/Ex_Rasters"):
        os.mkdir(os.path.dirname(os.path.dirname(evt)) + "/Ex_Rasters")
    evt_lookup.save(os.path.dirname(os.path.dirname(evt)) + "/Ex_Rasters/Ex_Riparian.tif")
    bps_lookup = Lookup(bps, "VEG_SCORE")
    if not os.path.exists(os.path.dirname(os.path.dirname(bps)) + "/Hist_Rasters"):
        os.mkdir(os.path.dirname(os.path.dirname(bps)) + "/Hist_Rasters")
    bps_lookup.save(os.path.dirname(os.path.dirname(bps)) + "/Hist_Rasters/Hist_Riparian.tif")

    if lg_river == None:
        # create raster output of riparian vegetation departure for areas without large rivers
        evt_zs = ZonalStatistics(thiessen_valley, "FID", evt_lookup, "MEAN", "DATA")
        bps_zs = ZonalStatistics(thiessen_valley, "FID", bps_lookup, "MEAN", "DATA")

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

        evt_zs = ZonalStatistics(thiessen_valley, "FID", evt_wo_rivers, "MEAN", "DATA")
        bps_zs = ZonalStatistics(thiessen_valley, "FID", bps_wo_rivers, "MEAN", "DATA")

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
    lui_zs = ZonalStatistics(thiessen_valley, "FID", lui_lookup, "MEAN", "DATA")
    if not os.path.exists(os.path.dirname(os.path.dirname(evt)) + "/Ex_Rasters"):
        os.mkdir(os.path.dirname(os.path.dirname(evt)) + "/Ex_Rasters")
    lui_zs.save(os.path.dirname(os.path.dirname(evt)) + "/Ex_Rasters/Land_Use_Intensity.tif")

    return lui_zs


def calc_connectivity(frag_valley, thiessen_valley, scratch):
    fp_conn = scratch + '/fp_conn'
    arcpy.PolygonToRaster_conversion(frag_valley, "Connected", fp_conn, "", "", 30)
    fp_conn_zs = ZonalStatistics(thiessen_valley, "FID", fp_conn, "MEAN", "DATA")
    fp_conn_zs.save(scratch + '/Floodplain_Connectivity')

    return fp_conn_zs


def calc_veg(evt, bps, thiessen_valley, scratch):
    exveg_lookup = Lookup(evt, "VEGETATED")
    if not os.path.exists(os.path.dirname(os.path.dirname(evt)) + "/Ex_Rasters"):
        os.mkdir(os.path.dirname(os.path.dirname(evt)) + "/Ex_Rasters")
    exveg_lookup.save(os.path.dirname(os.path.dirname(evt)) + "/Ex_Rasters/Ex_Veg_Cover.tif")
    histveg_lookup = Lookup(bps, "VEGETATED")
    if not os.path.exists(os.path.dirname(os.path.dirname(bps)) + "/Hist_Rasters"):
        os.mkdir(os.path.dirname(os.path.dirname(bps)) + "/Hist_Rasters")
    histveg_lookup.save(os.path.dirname(os.path.dirname(bps)) + "/Hist_Rasters/Hist_Veg_Cover.tif")

    exveg_zs = ZonalStatistics(thiessen_valley, "FID", exveg_lookup, "MEAN", "DATA")
    histveg_zs = ZonalStatistics(thiessen_valley, "FID", histveg_lookup, "MEAN", "DATA")

    exvegx100 = exveg_zs * 100
    exveg_int = Int(exvegx100)

    arcpy.AddField_management(exveg_int, "NEWVALUE", "SHORT")
    cursor = arcpy.UpdateCursor(exveg_int)
    for row in cursor:
        row.NEWVALUE = row.Value
        cursor.updateRow(row)
    del row
    del cursor
    cursor2 = arcpy.UpdateCursor(exveg_int)
    for row in cursor2:
        if row.Value == 0:
            row.NEWVALUE = 1
            cursor2.updateRow(row)
    del row
    del cursor2

    exveg_int_lookup = Lookup(exveg_int, "NEWVALUE")
    exveg_float = Float(exveg_int_lookup)
    exveg_final = exveg_float/100

    histvegx100 = histveg_zs * 100
    histveg_int = Int(histvegx100)

    arcpy.AddField_management(histveg_int, "NEWVALUE", "SHORT")
    cursor3 = arcpy.UpdateCursor(histveg_int)
    for row in cursor3:
        row.NEWVALUE = row.Value
        cursor3.updateRow(row)
    del row
    del cursor3
    cursor4 = arcpy.UpdateCursor(histveg_int)
    for row in cursor4:
        if row.Value == 0:
            row.NEWVALUE = 1
            cursor4.updateRow(row)
    del row
    del cursor4

    histveg_int_lookup = Lookup(histveg_int, "NEWVALUE")
    histveg_float = Float(histveg_int_lookup)
    histveg_final = histveg_float/100

    veg_init = exveg_final/histveg_final
    vegx100 = veg_init * 100
    veg_int = Int(vegx100)

    arcpy.AddField_management(veg_int, "NEWVALUE", "SHORT")
    cursor5 = arcpy.UpdateCursor(veg_int)
    for row in cursor5:
        row.NEWVALUE = row.Value
        cursor5.updateRow(row)
    del row
    del cursor5
    cursor6 = arcpy.UpdateCursor(veg_int)
    for row in cursor6:
        if row.Value > 100:
            row.NEWVALUE = 100
            cursor6.updateRow(row)
    del row
    del cursor6

    veg_lookup = Lookup(veg_int, "NEWVALUE")
    veg_float = Float(veg_lookup)
    veg_final = veg_float/100
    veg_final.save(scratch + "/veg_final")

    return veg_final

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
        sys.argv[11],
        sys.argv[12])
