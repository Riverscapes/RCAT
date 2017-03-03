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
    midpoints = scratch + "/midpoints"
    arcpy.FeatureVerticesToPoints_management(seg_network, midpoints, "MID")
    thiessen = scratch + "/thiessen"
    arcpy.CreateThiessenPolygons_analysis(midpoints, thiessen, "ALL")
    buf_valley = scratch + "/buf_valley"
    arcpy.Buffer_analysis(frag_valley, buf_valley, "10 Meters", "FULL", "ROUND", "ALL")
    if not os.path.exists(os.path.dirname(seg_network) + "/Thiessen"):
        os.mkdir(os.path.dirname(seg_network) + "/Thiessen")
    thiessen_valley = os.path.dirname(seg_network) + "/Thiessen/Thiessen_Valley.shp"
    arcpy.Clip_analysis(thiessen, buf_valley, thiessen_valley)

    # create rca input network and output directory
    j = 1
    while os.path.exists(projPath + "/02_Analyses/Output_" + str(j)):
        j += 1

    os.mkdir(projPath + "/02_Analyses/Output_" + str(j))
    fcOut = projPath + "/02_Analyses/Output_" + str(j) + "/rca_table.shp"
    arcpy.CopyFeatures_management(seg_network, fcOut)

    # Add width field to thiessen polygons and then output network
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

    arcpy.JoinField_management(fcOut, "FID", thiessen_valley, "ORIG_FID", "Width")

    # add model input attributes to input network

    arcpy.AddMessage("Classifying vegetation rasters")
    score_landfire(evt, bps)

    arcpy.AddMessage("Calculating riparian departure")
    calc_rvd(evt, bps, thiessen_valley, fcOut, lg_river, scratch)

    arcpy.AddMessage("Assessing land use intensity")
    calc_lui(evt, thiessen_valley, fcOut)

    arcpy.AddMessage("Assessing floodplain connectivity")
    calc_connectivity(frag_valley, thiessen_valley, fcOut, scratch)

    arcpy.AddMessage("Calculating overall vegetation departure")
    calc_veg(evt, bps, thiessen_valley, fcOut)

    # # # calculate rca for segments in unconfined valleys # # #

    arcpy.AddMessage("Calculating riparian condition")

    arcpy.MakeFeatureLayer_management(fcOut, "rca_in_lyr")
    arcpy.SelectLayerByAttribute_management("rca_in_lyr", "NEW_SELECTION", '"Width" >= {0}'.format(width_thresh))
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
        out_table = os.path.dirname(fcOut) + "/RCA_Table.txt"
        np.savetxt(out_table, columns, delimiter=",", header="ID, COND_VAL", comments="")
        arcpy.CopyRows_management(out_table, "final_table")

        final_table = scratch + "/final_table"
        arcpy.JoinField_management(rca_u, "OBJECTID", final_table, "OBJECTID", "COND_VAL")
        rca_u_final = scratch + "/rca_u_final"
        arcpy.CopyFeatures_management(rca_u, rca_u_final)

    else:
        raise Exception("There are no 'unconfined' segments to assess using FIS. Lower width threshold parameter.")

    # # # calculate rca for segments in confined valleys # # #

    arcpy.SelectLayerByAttribute_management("rca_in_lyr", "NEW_SELECTION", '"Width" < {0}'.format(width_thresh))
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
    output = projPath + "/02_Analyses/Output_" + str(j) + "/" + str(outName) + ".shp"

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

    arcpy.Delete_management(fcOut)
    arcpy.Delete_management(out_table)

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
            row[2] = 0.6
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
            row[2] = 1
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


def calc_rvd(evt, bps, thiessen_valley, fcOut, lg_river, scratch):
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
        evt_zs = ZonalStatisticsAsTable(thiessen_valley, "ORIG_FID", evt_lookup, "evt_zs", statistics_type="MEAN")
        bps_zs = ZonalStatisticsAsTable(thiessen_valley, "ORIG_FID", bps_lookup, "bps_zs", statistics_type="MEAN")

        arcpy.JoinField_management(fcOut, "FID", evt_zs, "ORIG_FID", "MEAN")
        arcpy.AddField_management(fcOut, "EVT_MEAN", "DOUBLE")
        cursor = arcpy.da.UpdateCursor(fcOut, ["MEAN", "EVT_MEAN"])
        for row in cursor:
            row[1] = row[0]
            cursor.updateRow(row)
            if row[1] == 0:
                row[1] = 0.0001
            cursor.updateRow(row)
        del row
        del cursor
        arcpy.DeleteField_management(fcOut, "MEAN")

        arcpy.JoinField_management(fcOut, "FID", bps_zs, "ORIG_FID", "MEAN")
        arcpy.AddField_management(fcOut, "BPS_MEAN", "DOUBLE")
        cursor = arcpy.da.UpdateCursor(fcOut, ["MEAN", "BPS_MEAN"])
        for row in cursor:
            row[1] = row[0]
            cursor.updateRow(row)
            if row[1] == 0:
                row[1] = 0.0001
            cursor.updateRow(row)
        del row
        del cursor
        arcpy.DeleteField_management(fcOut, "MEAN")

        arcpy.AddField_management(fcOut, "RVD", "DOUBLE")
        cursor = arcpy.da.UpdateCursor(fcOut, ["EVT_MEAN", "BPS_MEAN", "RVD"])
        for row in cursor:
            index = row[0] / row[1]
            row[2] = index
            cursor.updateRow(row)
            if row[2] > 1 and row[1] == 0.0001:
                row[2] = 1
            cursor.updateRow(row)
        del row
        del cursor

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

        evt_zs = ZonalStatisticsAsTable(thiessen_valley, "ORIG_FID", evt_wo_rivers, "evt_zs", statistics_type="MEAN")
        bps_zs = ZonalStatisticsAsTable(thiessen_valley, "ORIG_FID", bps_wo_rivers, "bps_zs", statistics_type="MEAN")

        arcpy.JoinField_management(fcOut, "FID", evt_zs, "ORIG_FID", "MEAN")
        arcpy.AddField_management(fcOut, "EVT_MEAN", "DOUBLE")
        cursor = arcpy.da.UpdateCursor(fcOut, ["MEAN", "EVT_MEAN"])
        for row in cursor:
            row[1] = row[0]
            cursor.updateRow(row)
            if row[1] == 0:
                row[1] = 0.0001
            cursor.updateRow(row)
        del row
        del cursor
        arcpy.DeleteField_management(fcOut, "MEAN")

        arcpy.JoinField_management(fcOut, "FID", bps_zs, "ORIG_FID", "MEAN")
        arcpy.AddField_management(fcOut, "BPS_MEAN", "DOUBLE")
        cursor = arcpy.da.UpdateCursor(fcOut, ["MEAN", "BPS_MEAN"])
        for row in cursor:
            row[1] = row[0]
            cursor.updateRow(row)
            if row[1] == 0:
                row[1] = 0.0001
            cursor.updateRow(row)
        del row
        del cursor
        arcpy.DeleteField_management(fcOut, "MEAN")

        arcpy.AddField_management(fcOut, "RVD", "DOUBLE")
        cursor = arcpy.da.UpdateCursor(fcOut, ["EVT_MEAN", "BPS_MEAN", "RVD"])
        for row in cursor:
            index = row[0] / row[1]
            row[2] = index
            cursor.updateRow(row)
            if row[2] > 1 and row[1] == 0.0001:
                row[2] = 1
            cursor.updateRow(row)
        del row
        del cursor

    return


def calc_lui(evt, thiessen_valley, fcOut):
    lui_lookup = Lookup(evt, "LUI")
    lui_zs = ZonalStatisticsAsTable(thiessen_valley, "ORIG_FID", lui_lookup, "lui_zs", statistics_type="MEAN")
    if not os.path.exists(os.path.dirname(os.path.dirname(evt)) + "/Ex_Rasters"):
        os.mkdir(os.path.dirname(os.path.dirname(evt)) + "/Ex_Rasters")
    lui_lookup.save(os.path.dirname(os.path.dirname(evt)) + "/Ex_Rasters/Land_Use_Intensity.tif")

    arcpy.JoinField_management(fcOut, "FID", lui_zs, "ORIG_FID", "MEAN")
    arcpy.AddField_management(fcOut, "LUI", "DOUBLE")
    cursor = arcpy.da.UpdateCursor(fcOut, ["MEAN", "LUI"])
    for row in cursor:
        row[1] = row[0]
        cursor.updateRow(row)
    del row
    del cursor
    arcpy.DeleteField_management(fcOut, "MEAN")

    return


def calc_connectivity(frag_valley, thiessen_valley, fcOut, scratch):
    fp_conn = scratch + '/fp_conn'
    arcpy.PolygonToRaster_conversion(frag_valley, "Connected", fp_conn, "", "", 10)
    fp_conn_zs = ZonalStatisticsAsTable(thiessen_valley, "ORIG_FID", fp_conn, "fp_conn_zs", statistics_type="MEAN")
    #fp_conn.save(scratch + '/Floodplain_Connectivity')

    arcpy.JoinField_management(fcOut, "FID", fp_conn_zs, "ORIG_FID", "MEAN")
    arcpy.AddField_management(fcOut, "CONNECT", "DOUBLE")
    cursor = arcpy.da.UpdateCursor(fcOut, ["MEAN", "CONNECT"])
    for row in cursor:
        row[1] = row[0]
        cursor.updateRow(row)
    del row
    del cursor
    arcpy.DeleteField_management(fcOut, "MEAN")

    return


def calc_veg(evt, bps, thiessen_valley, fcOut):
    exveg_lookup = Lookup(evt, "VEGETATED")
    if not os.path.exists(os.path.dirname(os.path.dirname(evt)) + "/Ex_Rasters"):
        os.mkdir(os.path.dirname(os.path.dirname(evt)) + "/Ex_Rasters")
    exveg_lookup.save(os.path.dirname(os.path.dirname(evt)) + "/Ex_Rasters/Ex_Veg_Cover.tif")
    histveg_lookup = Lookup(bps, "VEGETATED")
    if not os.path.exists(os.path.dirname(os.path.dirname(bps)) + "/Hist_Rasters"):
        os.mkdir(os.path.dirname(os.path.dirname(bps)) + "/Hist_Rasters")
    histveg_lookup.save(os.path.dirname(os.path.dirname(bps)) + "/Hist_Rasters/Hist_Veg_Cover.tif")

    exveg_zs = ZonalStatisticsAsTable(thiessen_valley, "ORIG_FID", exveg_lookup, "exveg_zs", statistics_type="MEAN")
    histveg_zs = ZonalStatisticsAsTable(thiessen_valley, "ORIG_FID", histveg_lookup, "histveg_zs", statistics_type="MEAN")

    arcpy.JoinField_management(fcOut, "FID", exveg_zs, "ORIG_FID", "MEAN")
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

    arcpy.JoinField_management(fcOut, "FID", histveg_zs, "ORIG_FID", "MEAN")
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
        index = row[0] / row[1]
        row[2] = index
        cursor.updateRow(row)
    del row
    del cursor

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
        sys.argv[11],
        sys.argv[12])
