# -------------------------------------------------------------------------------
# Name:        Valley Bottom Extraction Tool (V-BET)
# Purpose:     Uses a stream network and a DEM to extract a polygon representing
#              the valley bottom
# Author:      Jordan Gilbert
#
# Created:     09/25/2015
# Latest Update: 01/18/2017
# Copyright:   (c) Jordan Gilbert 2017
# Licence:     <your licence>
# -------------------------------------------------------------------------------

# import modules
import arcpy
import sys
import os
from arcpy.sa import *
import datetime
import uuid
import projectxml


def main(
    projName,
    hucID,
    hucName,
    projPath,
    DEM,
    fcNetwork,
    FlowAcc,
    outName,
    high_da_thresh,
    low_da_thresh,
    lg_buf_size,
    med_buf_size,
    sm_buf_size,
    min_buf_size,
    lg_slope_thresh,
    med_slope_thresh,
    sm_slope_thresh,
    scratch,
    ag_distance,
    min_area,
    min_hole):

    arcpy.env.overwriteOutput = True
    arcpy.CheckOutExtension("spatial")

    # check that input data is in projected coordinate system
    networkSR = arcpy.Describe(fcNetwork).spatialReference
    if networkSR.type == "Projected":
        pass
    else:
        raise Exception("Input stream network must have a projected coordinate system")

    # check that input network is segmented and is a shapefile (ie has no OBJECTID field)
    ct = arcpy.GetCount_management(fcNetwork)
    count = int(ct.getOutput(0))
    if count < 30:
        raise Exception("Input stream network must have more than 30 segments")
    network_fields = [f.name for f in arcpy.ListFields(fcNetwork)]
    if "OBJECTID" in network_fields:
        raise Exception("Input stream network cannot not have field 'OBJECTID' (use shapefile)")

    # calculate flow accumulation and convert to drainage area, or input drainage area raster
    if FlowAcc == None:
        arcpy.AddMessage("calculating drainage area")
        calc_drain_area(DEM)
    elif os.path.exists(os.path.dirname(DEM) + "/Flow"):
        pass
    else:
        os.mkdir(projPath + os.path.dirname(DEM) + "/Flow")
        arcpy.CopyRaster_management(FlowAcc, os.path.dirname(DEM) + "/Flow/" + os.path.basename(FlowAcc))

    if FlowAcc == None:
        DrAr = os.path.dirname(DEM) + "/Flow/DrainArea_sqkm.tif"
        inFlow = Raster(DrAr)
    else:
        DrAr = os.path.dirname(DEM) + "/Flow/" + os.path.basename(FlowAcc)
        inFlow = Raster(DrAr)

    # check that da thresholds are not larger than the da of the inputs
    if float(inFlow.maximum) > float(high_da_thresh) and float(inFlow.maximum) > float(low_da_thresh):
        pass
    else:
        raise Exception("drainage area threshold value is greater than highest network drainage area value")

    if float(inFlow.minimum) < float(low_da_thresh):
        pass
    else:
        raise Exception("low drainage area threshold is lower than lowest network drainage area value")

    arcpy.AddMessage("segmenting stream network by drainage area")

    # This strange workflow extracts drainage area values from the raster to an attribute for each network segment.
    network_midpoints = scratch + "/network_midpoints"
    arcpy.FeatureVerticesToPoints_management(fcNetwork, network_midpoints, "MID")
    midpoint_fields = [f.name for f in arcpy.ListFields(network_midpoints)]
    midpoint_fields.remove("OBJECTID")
    midpoint_fields.remove("Shape")
    midpoint_fields.remove("ORIG_FID")
    arcpy.DeleteField_management(network_midpoints, midpoint_fields)

    midpoint_buffer = scratch + "/midpoint_buffer"
    arcpy.Buffer_analysis(network_midpoints, midpoint_buffer, "100 Meters", "", "", "NONE")
    drarea_zs = ZonalStatistics(midpoint_buffer, "OBJECTID", inFlow, "MAXIMUM", "DATA")
    drarea_int = Int(drarea_zs)
    drarea_poly = scratch + "/drarea_poly"
    arcpy.RasterToPolygon_conversion(drarea_int, drarea_poly)
    poly_point_join = scratch + "/poly_point_join"
    arcpy.SpatialJoin_analysis(drarea_poly, network_midpoints, poly_point_join, "JOIN_ONE_TO_MANY", "KEEP_COMMON", "", "INTERSECT")
    arcpy.DeleteField_management(poly_point_join, ["Id", "JOIN_FID", "Join_Count", "TARGET_FID"])
    arcpy.JoinField_management(fcNetwork, "FID", poly_point_join, "ORIG_FID")

    lf = arcpy.ListFields(fcNetwork, "DA_sqkm")
    if len(lf) is 1:
        arcpy.DeleteField_management(fcNetwork, "DA_sqkm")
    else:
        pass

    arcpy.AddField_management(fcNetwork, "DA_sqkm", "SHORT")
    cursor = arcpy.da.UpdateCursor(fcNetwork, ["gridcode", "DA_sqkm"])
    for row in cursor:
        row[1] = row[0]
        cursor.updateRow(row)
    del row
    del cursor

    delete_fields = [f.name for f in arcpy.ListFields(fcNetwork, "*_1")]
    other_fields = ["gridcode", "ORIG_FID"]
    delete_fields.extend(other_fields)
    arcpy.DeleteField_management(fcNetwork, delete_fields)

    # create buffers around the different network segments
    arcpy.AddMessage("creating buffers")
    if not os.path.exists(os.path.dirname(fcNetwork) + "/Buffers"):
        os.mkdir(os.path.dirname(fcNetwork) + '/Buffers')
    arcpy.MakeFeatureLayer_management(fcNetwork, "network_lyr")
    lg_buffer = os.path.dirname(fcNetwork) + "/Buffers/lg_buffer.shp"
    arcpy.SelectLayerByAttribute_management("network_lyr", "NEW_SELECTION", '"DA_sqkm" >= {0}'.format(high_da_thresh))
    arcpy.Buffer_analysis("network_lyr", lg_buffer, lg_buf_size, "FULL", "ROUND", "ALL")
    med_buffer = os.path.dirname(fcNetwork) + "/Buffers/med_buf.shp"
    arcpy.SelectLayerByAttribute_management("network_lyr", "NEW_SELECTION", '"DA_sqkm" >= {0} AND "DA_sqkm" < {1}'.format(low_da_thresh, high_da_thresh))
    arcpy.Buffer_analysis("network_lyr", med_buffer, med_buf_size, "FULL", "ROUND", "ALL")
    sm_buffer = os.path.dirname(fcNetwork) + "/Buffers/sm_buf.shp"
    arcpy.SelectLayerByAttribute_management("network_lyr", "NEW_SELECTION", '"DA_sqkm" < {0}'.format(low_da_thresh))
    arcpy.Buffer_analysis("network_lyr", sm_buffer, sm_buf_size, "FULL", "ROUND", "ALL")
    min_buffer = scratch + "/min_buffer"
    arcpy.Buffer_analysis(fcNetwork, min_buffer, min_buf_size, "FULL", "ROUND", "ALL")

    # Slope analysis
    arcpy.AddMessage("creating slope raster")
    if not os.path.exists(os.path.dirname(DEM) + "/Slope"):
        os.mkdir(os.path.dirname(DEM) + "/Slope")
    slope_raster = Slope(DEM, "DEGREE", "")
    slope_raster.save(os.path.dirname(DEM) + "/Slope/slope.tif")
    inSlope = os.path.dirname(DEM) + "/Slope/slope.tif"

    arcpy.AddMessage("clipping slope raster")
    lg_buf_slope = ExtractByMask(slope_raster, lg_buffer)
    med_buf_slope = ExtractByMask(slope_raster, med_buffer)
    sm_buf_slope = ExtractByMask(slope_raster, sm_buffer)

    # reclassify slope rasters for each of the buffers
    arcpy.AddMessage("reclassifying slope rasters")
    lg_valley_raster = Reclassify(lg_buf_slope, "VALUE", "0 {0} 1; {0} 100 NODATA".format(lg_slope_thresh), "NODATA")
    med_valley_raster = Reclassify(med_buf_slope, "VALUE", "0 {0} 1; {0} 100 NODATA".format(med_slope_thresh), "NODATA")
    sm_valley_raster = Reclassify(sm_buf_slope, "VALUE", "0 {0} 1; {0} 100 NODATA".format(sm_slope_thresh), "NODATA")

    # convert valley rasters into polygons
    arcpy.AddMessage("converting valley rasters into polygons")
    lg_polygon = scratch + "/lg_polygon"
    med_polygon = scratch + "/med_polygon"
    sm_polygon = scratch + "/sm_polygon"
    arcpy.RasterToPolygon_conversion(lg_valley_raster, lg_polygon, "SIMPLIFY")
    arcpy.RasterToPolygon_conversion(med_valley_raster, med_polygon, "SIMPLIFY")
    arcpy.RasterToPolygon_conversion(sm_valley_raster, sm_polygon, "SIMPLIFY")

    # merge and clean valley bottom polygons
    merged_polygon = scratch + "/merged_polygon"
    arcpy.Merge_management([lg_polygon, med_polygon, sm_polygon, min_buffer], merged_polygon)

    arcpy.AddMessage("cleaning outputs for final valley bottom")
    cleaned_valley = scratch + "/cleaned_valley"
    arcpy.MakeFeatureLayer_management(merged_polygon, "merged_polygon_lyr")
    arcpy.SelectLayerByLocation_management("merged_polygon_lyr", "INTERSECT", fcNetwork)
    arcpy.CopyFeatures_management("merged_polygon_lyr", cleaned_valley)

    # dissolve and aggregate valley bottom
    dissolved_valley = scratch + "/dissolved_valley"
    arcpy.Dissolve_management(cleaned_valley, dissolved_valley)
    aggregated_valley = scratch + "/aggregated_valley"
    arcpy.AggregatePolygons_cartography(dissolved_valley, aggregated_valley, ag_distance, min_area, min_hole)

    # smooth final valley bottom
    j = 1
    while os.path.exists(projPath + "/02_Analyses/Output_" + str(j)):
        j += 1

    os.mkdir(projPath + "/02_Analyses/Output_" + str(j))
    fcOutput = projPath + "/02_Analyses/Output_" + str(j) + "/" + outName + ".shp"
    arcpy.SmoothPolygon_cartography(aggregated_valley, fcOutput, "PAEK", "65 Meters", "FIXED_ENDPOINT", "NO_CHECK")

    # # # Write xml file # # #

    if not os.path.exists(projPath + "/vbet.xml"):

        # xml file
        xmlfile = projPath + "/vbet.xml"

        # initiate xml file creation
        newxml = projectxml.ProjectXML(xmlfile, "VBET", projName)

        if not hucID == None:
            newxml.addMeta("HUCID", hucID, newxml.project)
        if not hucID == None:
            idlist = [int(x) for x in str(hucID)]
            if idlist[0] == 1 and idlist[1] == 7:
                newxml.addMeta("Region", "CRB", newxml.project)
        if not hucName == None:
            newxml.addMeta("Watershed", hucName, newxml.project)

        mainguid = getUUID()

        newxml.addVBETRealization("VBET Realization 1", dateCreated=datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                  productVersion="1.0", guid=mainguid)

        newxml.addParameter("high_da", high_da_thresh, newxml.VBETrealizations[0])
        newxml.addParameter("low_da", low_da_thresh, newxml.VBETrealizations[0])
        newxml.addParameter("lg_buf", lg_buf_size, newxml.VBETrealizations[0])
        newxml.addParameter("med_buf", med_buf_size, newxml.VBETrealizations[0])
        newxml.addParameter("sm_buf", sm_buf_size, newxml.VBETrealizations[0])
        newxml.addParameter("min_buf", min_buf_size, newxml.VBETrealizations[0])
        newxml.addParameter("lg_slope", lg_slope_thresh, newxml.VBETrealizations[0])
        newxml.addParameter("med_slope", med_slope_thresh, newxml.VBETrealizations[0])
        newxml.addParameter("sm_slope", sm_slope_thresh, newxml.VBETrealizations[0])
        newxml.addParameter("ag_distance", ag_distance, newxml.VBETrealizations[0])
        newxml.addParameter("min_area", min_area, newxml.VBETrealizations[0])
        newxml.addParameter("min_hole", min_hole, newxml.VBETrealizations[0])

        # add inputs and outputs to xml file
        newxml.addProjectInput("DEM", "DEM", DEM[DEM.find("01_Inputs"):], iid="DEM1", guid=mainguid)
        newxml.addVBETInput(newxml.VBETrealizations[0], "DEM", ref="DEM1")

        newxml.addProjectInput("Vector", "Drainage Network", fcNetwork[fcNetwork.find("01_Inputs"):], iid="DN1", guid=mainguid)
        newxml.addVBETInput(newxml.VBETrealizations[0], "Network", ref="DN1")

        if FlowAcc == None:
            newxml.addVBETInput(newxml.VBETrealizations[0], "Flow", name="Drainage Area", path=DrAr[DrAr.find("01_Inputs"):], guid=mainguid)
        else:
            newxml.addProjectInput("Raster", "Drainage Area", DrAr[DrAr.find("01_Inputs"):], iid="DA1", guid=mainguid)
            newxml.addVBETInput(newxml.VBETrealizations[0], "Flow", ref="DA1")

        newxml.addVBETInput(newxml.VBETrealizations[0], "Slope", name="Slope", path=inSlope[inSlope.find("01_Inputs"):], guid=mainguid)

        newxml.addVBETInput(newxml.VBETrealizations[0], "Buffer", name="Large Buffer", path=lg_buffer[lg_buffer.find("01_Inputs"):], guid=mainguid)
        newxml.addVBETInput(newxml.VBETrealizations[0], "Buffer", name="Medium Buffer", path=med_buffer[med_buffer.find("01_Inputs"):], guid=mainguid)
        newxml.addVBETInput(newxml.VBETrealizations[0], "Buffer", name="Small Buffer", path=sm_buffer[sm_buffer.find("01_Inputs"):], guid=mainguid)

        newxml.addOutput("Analysis", "Vector", "Unedited Valley Bottom", fcOutput[fcOutput.find("02_Analyses"):], newxml.VBETrealizations[0])

        newxml.write()

    else:
        # xml file
        xmlfile = projPath + "/vbet.xml"

        exxml = projectxml.ExistingXML(xmlfile)

        vb = exxml.rz.findall("VBET")
        vbf = vb[-1]
        rname = vbf.find("Name")
        k = 2
        while rname.text == "VBET Realization " + str(k):
            k += 1

        exxml.addVBETRealization("VBET Realization " + str(k), dateCreated=datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                 productVersion="1.0")

        exxml.addParameter("high_da", high_da_thresh, exxml.VBETrealizations[0])
        exxml.addParameter("low_da", low_da_thresh, exxml.VBETrealizations[0])
        exxml.addParameter("lg_buf", lg_buf_size, exxml.VBETrealizations[0])
        exxml.addParameter("med_buf", med_buf_size, exxml.VBETrealizations[0])
        exxml.addParameter("sm_buf", sm_buf_size, exxml.VBETrealizations[0])
        exxml.addParameter("min_buf", min_buf_size, exxml.VBETrealizations[0])
        exxml.addParameter("lg_slope", lg_slope_thresh, exxml.VBETrealizations[0])
        exxml.addParameter("med_slope", med_slope_thresh, exxml.VBETrealizations[0])
        exxml.addParameter("sm_slope", sm_slope_thresh, exxml.VBETrealizations[0])
        exxml.addParameter("ag_distance", ag_distance, exxml.VBETrealizations[0])
        exxml.addParameter("min_area", min_area, exxml.VBETrealizations[0])
        exxml.addParameter("min_hole", min_hole, exxml.VBETrealizations[0])

        inputs = exxml.root.find("Inputs")

        dem = inputs.findall("DEM")
        demid = range(len(dem))
        for i in range(len(dem)):
            demid[i] = dem[i].get("id")
        dempath = range(len(dem))
        for i in range(len(dem)):
            dempath[i] = dem[i].find("Path").text

        for i in range(len(dempath)):
            if os.path.abspath(dempath[i]) == os.path.abspath(DEM[DEM.find("01_Inputs"):]):
                exxml.addVBETInput(exxml.VBETrealizations[0], "DEM", ref=str(demid[i]))
        nlist = []
        for j in dempath:
            if os.path.abspath(DEM[DEM.find("01_Inputs"):]) == os.path.abspath(j):
                nlist.append("yes")
            else:
                nlist.append("no")
        if "yes" in nlist:
            pass
        else:
            exxml.addProjectInput("DEM", "DEM", DEM[DEM.find("01_Inputs"):], iid="DEM" + str(k))
            exxml.addVBETInput(exxml.VBETrealizations[0], "DEM", ref="DEM" + str(k))
        del nlist

        vector = inputs.findall("Vector")
        dnid = range(len(vector))
        for i in range(len(vector)):
            dnid[i] = vector[i].get("id")
        dnpath = range(len(vector))
        for i in range(len(vector)):
            dnpath[i] = vector[i].find("Path").text

        for i in range(len(dnpath)):
            if os.path.abspath(dnpath[i]) == os.path.abspath(fcNetwork[fcNetwork.find("01_Inputs"):]):
                exxml.addVBETInput(exxml.VBETrealizations[0], "Network", ref=str(dnid[i]))
                exxml.addVBETInput(exxml.VBETrealizations[0], "Buffer", name="Large Buffer", path=lg_buffer[lg_buffer.find("01_Inputs"):])
                exxml.addVBETInput(exxml.VBETrealizations[0], "Buffer", name="Medium Buffer", path=med_buffer[med_buffer.find("01_Inputs"):])
                exxml.addVBETInput(exxml.VBETrealizations[0], "Buffer", name="Small Buffer", path=sm_buffer[sm_buffer.find("01_Inputs"):])
        nlist = []
        for j in dnpath:
            if os.path.abspath(fcNetwork[fcNetwork.find("01_Inputs"):]) == os.path.abspath(j):
                nlist.append("yes")
            else:
                nlist.append("no")
        if "yes" in nlist:
            pass
        else:
            exxml.addProjectInput("Vector", "Drainage Network", fcNetwork[fcNetwork.find("01_Inputs"):], iid="DN" + str(k))
            exxml.addVBETInput(exxml.VBETrealizations[0], "Network", ref="DN" + str(k))
            exxml.addVBETInput(exxml.VBETrealizations[0], "Buffer", name="Large Buffer", path=lg_buffer[lg_buffer.find("01_Inputs"):])
            exxml.addVBETInput(exxml.VBETrealizations[0], "Buffer", name="Medium Buffer", path=med_buffer[med_buffer.find("01_Inputs"):])
            exxml.addVBETInput(exxml.VBETrealizations[0], "Buffer", name="Small Buffer", path=sm_buffer[sm_buffer.find("01_Inputs"):])
        del nlist

        if FlowAcc == None:
            exxml.addVBETInput(exxml.VBETrealizations[0], "Flow", name="Drainage Area", path=DrAr[DrAr.find("01_Inputs"):])
        else:
            raster = inputs.findall("Raster")
            daid = range(len(raster))
            for i in range(len(raster)):
                daid[i] = raster[i].get("id")
            dapath = range(len(raster))
            for i in range(len(raster)):
                dapath[i] = raster[i].find("Path").text

            for i in range(len(dapath)):
                if os.path.abspath(dapath[i]) == os.path.abspath(DrAr[DrAr.find("01_Inputs"):]):
                    exxml.addVBETInput(exxml.VBETrealizations[0], "Flow", ref=str(daid[i]))
            nlist = []
            for j in dapath:
                if os.path.abspath(DrAr[DrAr.find("01_Inputs"):]) == os.path.abspath(j):
                    nlist.append("yes")
                else:
                    nlist.append("no")
            if "yes" in nlist:
                pass
            else:
                exxml.addProjectInput("Raster", "Drainage Area", DrAr[DrAr.find("01_Inputs"):], iid="DA" + str(k))
                exxml.addVBETInput(exxml.VBETrealizations[0], "Flow", ref="DA" + str(k))

        exxml.addOutput("Analysis", "Vector", "Unedited Valley Bottom", fcOutput[fcOutput.find("02_Analyses"):], exxml.VBETrealizations[0])

        exxml.write()

    arcpy.CheckInExtension("spatial")


def calc_drain_area(DEM):
    DEMdesc = arcpy.Describe(DEM)
    height = DEMdesc.meanCellHeight
    width = DEMdesc.meanCellWidth
    res = height * width
    resolution = int(res)

    # derive a flow accumulation raster from input DEM and covert to units of square kilometers
    filled_DEM = Fill(DEM, "")
    flow_direction = FlowDirection(filled_DEM, "NORMAL", "")
    flow_accumulation = FlowAccumulation(flow_direction, "", "FLOAT")
    DrainArea = flow_accumulation * resolution / 1000000

    if os.path.exists(os.path.dirname(DEM) + "/Flow/DrainArea_sqkm.tif"):
        arcpy.Delete_management(os.path.dirname(DEM) + "/Flow/DrainArea_sqkm.tif")
        DrArea_path = os.path.dirname(DEM) + "/Flow/DrainArea_sqkm.tif"
        DrainArea.save(DrArea_path)
    else:
        os.mkdir(os.path.dirname(DEM) + "/Flow")
        DrArea_path = os.path.dirname(DEM) + "/Flow/DrainArea_sqkm.tif"
        DrainArea.save(DrArea_path)


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
        sys.argv[12],
        sys.argv[13],
        sys.argv[14],
        sys.argv[15],
        sys.argv[16],
        sys.argv[17],
        sys.argv[18],
        sys.argv[19],
        sys.argv[20],
        sys.argv[21])
