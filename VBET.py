# -------------------------------------------------------------------------------
# Name:        Valley Bottom Extraction Tool (V-BET)
# Purpose:     Uses a stream network and a DEM to extract a polygon representing
#              the valley bottom
# Author:      Jordan Gilbert
#
# Created:     09/25/2015
# Latest Update: 06/20/2017
# Copyright:   (c) Jordan Gilbert 2017
# Licence:     This work is licensed under the Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International
#              License. To view a copy of this license, visit http://creativecommons.org/licenses/by-nc-sa/4.0/.
# -------------------------------------------------------------------------------

# import modules
import arcpy
import os
from arcpy.sa import *
import datetime
import uuid
import projectxml
import RCAT_Drainage_Area_Check as DA_Check
from shutil import rmtree
import glob
arcpy.CheckOutExtension("Spatial")


def parseInputBool(given_input):
    if given_input == 'false' or given_input is None:
        return False
    else:
        return True


# calculate drainage area function
def calc_drain_area(smDEM, flowDir):

    #  define raster environment settings
    desc = arcpy.Describe(smDEM)
    arcpy.env.cellSize = desc.meanCellWidth

    #  calculate cell area for use in drainage area calcultion
    height = desc.meanCellHeight
    width = desc.meanCellWidth
    cellArea = height * width

    # derive drainage area raster (in square km) from input DEM
    # note: draiange area calculation assumes input dem is in meters
    filled_DEM = Fill(smDEM)  # fill sinks in dem
    flow_direction = FlowDirection(filled_DEM) # calculate flow direction
    flow_accumulation = FlowAccumulation(flow_direction) # calculate flow accumulattion
    DrainArea = flow_accumulation * cellArea / 1000000 # calculate drainage area in square kilometers

    # save drainage area raster
    if os.path.exists(os.path.join(flowDir, "DrainArea_sqkm.tif")):
        arcpy.Delete_management(os.path.join(flowDir, "DrainArea_sqkm.tif"))
        arcpy.CopyRaster_management(DrainArea, os.path.join(flowDir, "DrainArea_sqkm.tif"))
    else:
        arcpy.CopyRaster_management(DrainArea, os.path.join(flowDir, "DrainArea_sqkm.tif"))


def getUUID():
    return str(uuid.uuid4()).upper()


# zonal statistics within buffer function
# dictionary join field function
def zonalStatsWithinBuffer(buffer, ras, statType, statField, outFC, outFCField, scratch):
    # get input raster stat value within each buffer
    # note: zonal stats as table does not support overlapping polygons so we will check which
    #       reach buffers output was produced for and which we need to run tool on again
    if 'NHDPlusID' in arcpy.ListFields(buffer):
        id_field = 'NHDPlusID'
    else:
        id_field = 'ReachID'
    statTbl = arcpy.sa.ZonalStatisticsAsTable(buffer, id_field, ras, os.path.join(scratch, 'statTbl'), 'DATA', statType)
    # get list of segment buffers where zonal stats tool produced output
    haveStatList = [row[0] for row in arcpy.da.SearchCursor(statTbl, id_field)]
    # create dictionary to hold all reach buffer min dem z values
    statDict = {}
    # add buffer raster stat values to dictionary
    with arcpy.da.SearchCursor(statTbl, [id_field, statField]) as cursor:
        for row in cursor:
            statDict[row[0]] = row[1]
    # create list of overlapping buffer reaches (i.e., where zonal stats tool did not produce output)
    needStatList = []
    with arcpy.da.SearchCursor(buffer, [id_field]) as cursor:
        for row in cursor:
            if row[0] not in haveStatList:
                needStatList.append(row[0])
    # run zonal stats until we have output for each overlapping buffer segment
    stat = None
    tmp_buff_lyr = None

    # create tuple of segment ids where still need raster values
    needStat = ()
    for reach in needStatList:
        if reach not in needStat:
            needStat += (reach,)
    # use the segment id tuple to create selection query and run zonal stats tool
    if len(needStat) == 1:
        quer = '"{}" = '.format(id_field) + str(needStat[0])
    else:
        quer = '"{}" IN '.format(id_field) + str(needStat)
    tmp_buff_lyr = arcpy.MakeFeatureLayer_management(buffer, 'tmp_buff_lyr')
    arcpy.SelectLayerByAttribute_management(tmp_buff_lyr, 'NEW_SELECTION', quer)
    stat = arcpy.sa.ZonalStatisticsAsTable(tmp_buff_lyr, id_field, ras, os.path.join(scratch, 'stat'), 'DATA', statType)
    # add segment stat values from zonal stats table to main dictionary
    with arcpy.da.SearchCursor(stat, [id_field, statField]) as cursor:
        for row in cursor:
            statDict[row[0]] = row[1]
    # create list of reaches that were run and remove from 'need to run' list
    haveStatList2 = [row[0] for row in arcpy.da.SearchCursor(stat, id_field)]
    for reach in haveStatList2:
        needStatList.remove(reach)

    # populate dictionary value to output field by ReachID
    with arcpy.da.UpdateCursor(outFC, [id_field, outFCField]) as cursor:
        for row in cursor:
            try:
                aKey = row[0]
                row[1] = statDict[aKey]
                cursor.updateRow(row)
            except:
                pass
    statDict.clear()
    # delete temp fcs, tbls, etc.
    items = [statTbl, stat, tmp_buff_lyr]
    for item in items:
        if item is not None:
            arcpy.Delete_management(item)


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
    ag_distance,
    min_area,
    min_hole,
    check_drain_area):

    arcpy.AddMessage("Running VBET...")

    arcpy.env.parallelProcessingFactor = "0"
    
    check_drain_area = parseInputBool(check_drain_area)

    # create temporary directory
    tempDir = os.path.join(projPath, 'Temp')
    if os.path.exists(tempDir):
        rmtree(tempDir)
    os.mkdir(tempDir)

    # define workspace environment settings
    arcpy.env.workspace = tempDir
    arcpy.env.scratchWorkspace = tempDir
    arcpy.env.overwriteOutput = True

    # set DEM path to variable for xml
    dem_path = DEM

    # read in DEM as raster object
    DEM = arcpy.sa.Raster(DEM)

    #  define raster environment settings
    desc = arcpy.Describe(DEM)
    arcpy.env.extent = desc.Extent
    arcpy.env.outputCoordinateSystem = desc.SpatialReference
    arcpy.env.cellSize = desc.meanCellWidth

    # --check whether input network is projected--
    networkSR = arcpy.Describe(fcNetwork).spatialReference
    if networkSR.type == "Projected":
        pass
    else:
        raise Exception("Input stream network must have a projected coordinate system")

    # --check number of segments in input network--
    result = arcpy.GetCount_management(fcNetwork)
    count = int(result[0])

    if count < 30:
        raise Exception("Input stream network must have more than 30 segments")

    # --check that input network is shapefile--
    if fcNetwork.endswith(".shp"):
        pass
    else:
        raise Exception("Input stream network must be a shapefile (.shp)")

    # --check input network fields--
    # add flowline segment id field ('ReachID') if it doens't already exist
    # this field allows for more for more 'stable' joining
    fields = [f.name for f in arcpy.ListFields(fcNetwork)]
    oid_field = arcpy.Describe(fcNetwork).OIDFieldName
    if 'ReachID' not in fields:
        arcpy.AddField_management(fcNetwork, 'ReachID', 'LONG')
        with arcpy.da.UpdateCursor(fcNetwork, [oid_field, 'ReachID']) as cursor:
            for row in cursor:
                row[1] = row[0]
                cursor.updateRow(row)

    # --smooth input dem to remove any anomolies--
    neighborhood = NbrRectangle(3, 3, "CELL")
    smDEM_raw = FocalStatistics(DEM, neighborhood, 'MEAN')
    smDEM = ExtractByMask(smDEM_raw, DEM)
    arcpy.Delete_management(smDEM_raw)

    # --calculate drainage area values for each network segment--

    # calculate drainage area raster if not specified
    # load drainage area raster if file specified by user
    DEMDir = arcpy.Describe(DEM).path
    flowDir = os.path.join(DEMDir, 'Flow')
    if not os.path.exists(flowDir):
        os.mkdir(flowDir)
    if FlowAcc is None:
        arcpy.AddMessage("Calculating drainage area...")
        calc_drain_area(smDEM, flowDir)
        DrAr = os.path.join(flowDir, 'DrainArea_sqkm.tif')
        inFlow = Raster(DrAr)
    else:
        arcpy.AddMessage("Getting path to existing drainage area raster...")
        DrAr = FlowAcc
        inFlow = Raster(DrAr)

    # check that da thresholds are larger than the drainage area raster values
    arcpy.AddMessage("Checking drainage area thresholds...")

    #arcpy.AddMessage(type(inFlow.maximum))
    #arcpy.AddMessage(type(high_da_thresh))
    #arcpy.AddMessage(type(low_da_thresh))
    #arcpy.AddMessage(inFlow.maximum)
    #arcpy.AddMessage(high_da_thresh)
    #arcpy.AddMessage(low_da_thresh)

    if float(inFlow.maximum) > float(high_da_thresh) and float(inFlow.maximum) > float(low_da_thresh):
        pass
    else:
        raise Exception("High drainage area threshold value is greater than the largest network drainage area value")

    if float(inFlow.minimum) < float(low_da_thresh):
        pass
    else:
        raise Exception("Low drainage area threshold is less than the lowest network drainage area value")

    arcpy.AddMessage("Calculating stream network drainage area values...")

    # create network segment midpoints
    network_midpoints = os.path.join(tempDir, "network_midpoints.shp")
    arcpy.FeatureVerticesToPoints_management(fcNetwork, network_midpoints, "MID")

    # create midpoint 100 m buffer
    midpoint_buffer = arcpy.Buffer_analysis(network_midpoints, os.path.join(tempDir, "midpoint_buffer.shp"), "100 Meters")
    arcpy.Delete_management(network_midpoints)

    # check 'DA_sqkm' field exists in flowline network attribute table
    # if it does delete it
    lf = arcpy.ListFields(fcNetwork, "DA_sqkm")
    if len(lf) is 1:
        arcpy.DeleteField_management(fcNetwork, "DA_sqkm")
    else:
        pass
    # add drainage area 'DA_sqkm' field to flowline network
    arcpy.AddField_management(fcNetwork, "DA_sqkm", "DOUBLE")
    # get max drainage area within 100 m midpoint buffer
    zonalStatsWithinBuffer(midpoint_buffer, inFlow, "MAXIMUM", 'MAX', fcNetwork, "DA_sqkm", tempDir)
    arcpy.Delete_management(midpoint_buffer)


    # replace '0' drainage area values with tiny value
    with arcpy.da.UpdateCursor(fcNetwork, ["DA_sqkm"]) as cursor:
        for row in cursor:
            if row[0] == 0:
                row[0] = 0.00000001
            cursor.updateRow(row)

    # run da check
    fc_fields = [field.name for field in arcpy.ListFields(fcNetwork)]
    if check_drain_area and "ReachDist" in fc_fields:
        DA_Check.main(fcNetwork)

    # --create network buffers for analyses--
    # create 'Buffers' folder if it doesn't exist
    arcpy.MakeFeatureLayer_management(fcNetwork, "network_lyr")
    h = 1
    while os.path.exists(os.path.dirname(fcNetwork) + "/Buffers_" + str(h)):
        h += 1
    buffDir = os.path.join(os.path.dirname(fcNetwork), "Buffers_" + str(h))
    if not os.path.exists(buffDir):
        os.mkdir(buffDir)
    arcpy.AddMessage("Creating buffers...")
    # create large network segment buffers
    lg_buffer = os.path.join(buffDir, "lg_buffer.shp")
    arcpy.SelectLayerByAttribute_management("network_lyr", "NEW_SELECTION", '"DA_sqkm" >= {0}'.format(high_da_thresh))
    arcpy.Buffer_analysis("network_lyr", lg_buffer, lg_buf_size, "FULL", "ROUND", "ALL")
    # create medium network segment buffers
    med_buffer = os.path.join(buffDir, "med_buffer.shp")
    arcpy.SelectLayerByAttribute_management("network_lyr", "NEW_SELECTION", '"DA_sqkm" >= {0} AND "DA_sqkm" < {1}'.format(low_da_thresh, high_da_thresh))
    arcpy.Buffer_analysis("network_lyr", med_buffer, med_buf_size, "FULL", "ROUND", "ALL")
    # create small network segment buffers
    sm_buffer = os.path.join(buffDir, "sm_buffer.shp")
    arcpy.SelectLayerByAttribute_management("network_lyr", "NEW_SELECTION", '"DA_sqkm" < {0}'.format(low_da_thresh))
    arcpy.Buffer_analysis("network_lyr", sm_buffer, sm_buf_size, "FULL", "ROUND", "ALL")
    # create minimum (tiny) network segment buffers
    min_buffer = os.path.join(buffDir, "min_buffer.shp")
    arcpy.Buffer_analysis(fcNetwork, min_buffer, min_buf_size, "FULL", "ROUND", "ALL")

    # --dem slope analysis--
    arcpy.AddMessage("Creating slope raster...")
    # create 'Slope' folder if it doesn't exist
    slopeDir = os.path.join(DEMDir, 'Slope')
    if not os.path.exists(slopeDir):
        os.mkdir(slopeDir)
    # create slope raster and save to 'Slope' folder
    slope_raster = Slope(smDEM, "DEGREE")
    arcpy.CopyRaster_management(slope_raster, os.path.join(slopeDir, 'slope.tif'))
    # save slope path as separate object for xml purposes
    inSlope = os.path.join(slopeDir, 'slope.tif')
    arcpy.Delete_management(slope_raster)
    arcpy.Delete_management(smDEM)

    # clip slope raster to each of the small, large, medium network segment buffers
    lg_buf_slope = ExtractByMask(inSlope, lg_buffer)
    med_buf_slope = ExtractByMask(inSlope, med_buffer)
    sm_buf_slope = ExtractByMask(inSlope, sm_buffer)

    # reclassify slope rasters for each of the buffers
    lg_valley_raster = Con(lg_buf_slope <= float(lg_slope_thresh), 1)
    lg_valley_raster.save(os.path.join(tempDir, "lg_valley_raster.tif"))
    med_valley_raster = Con(med_buf_slope <= float(med_slope_thresh), 1)
    med_valley_raster.save(os.path.join(tempDir, "med_valley_raster.tif"))
    sm_valley_raster = Con(sm_buf_slope <= float(sm_slope_thresh), 1)
    sm_valley_raster.save(os.path.join(tempDir, "sm_valley_raster.tif"))

    # convert into polygons
    lg_polygon = os.path.join(tempDir, "lg_polygon.shp")
    med_polygon = os.path.join(tempDir, "med_polygon.shp")
    sm_polygon = os.path.join(tempDir, "sm_polygon.shp")
    arcpy.RasterToPolygon_conversion(lg_valley_raster, lg_polygon, "SIMPLIFY")
    arcpy.RasterToPolygon_conversion(med_valley_raster, med_polygon, "SIMPLIFY")
    arcpy.RasterToPolygon_conversion(sm_valley_raster, sm_polygon, "SIMPLIFY")

    # delete rasters that are no longer needed
    items = [lg_buf_slope, med_buf_slope, sm_buf_slope, lg_valley_raster, med_valley_raster, sm_valley_raster]
    for item in items:
        try:
            arcpy.Delete_management(item)
        except Exception as e:
            print e.args[0]

    # select polygons that intersect the input network
    arcpy.MakeFeatureLayer_management(fcNetwork, "fcNetwork_lyr")

    lg_valley_polygon = os.path.join(tempDir, "lg_valley_polygon.shp")
    arcpy.MakeFeatureLayer_management(lg_polygon, "lg_polygon_lyr")
    quer = '"DA_sqkm" >= ' + str(high_da_thresh)
    arcpy.SelectLayerByAttribute_management('fcNetwork_lyr', 'NEW_SELECTION', quer)
    arcpy.SelectLayerByLocation_management("lg_polygon_lyr", "INTERSECT", 'fcNetwork_lyr')
    arcpy.CopyFeatures_management("lg_polygon_lyr", lg_valley_polygon)
    lg_valley_elim = os.path.join(tempDir, "lg_valley_elim.shp")
    arcpy.EliminatePolygonPart_management(lg_valley_polygon, lg_valley_elim, 'AREA', min_hole)
    arcpy.SelectLayerByAttribute_management("lg_polygon_lyr", 'CLEAR_SELECTION')
    arcpy.Delete_management("lg_polygon_lyr")

    med_valley_polygon = os.path.join(tempDir, "med_valley_polygon.shp")
    arcpy.MakeFeatureLayer_management(med_polygon, "med_polygon_lyr")
    quer = '"DA_sqkm" < ' + str(high_da_thresh) + 'AND "DA_sqkm" >= ' + str(low_da_thresh)
    arcpy.SelectLayerByAttribute_management('fcNetwork_lyr', 'NEW_SELECTION', quer)
    arcpy.SelectLayerByLocation_management("med_polygon_lyr", "INTERSECT", 'fcNetwork_lyr')
    arcpy.CopyFeatures_management("med_polygon_lyr", med_valley_polygon)
    med_valley_elim = os.path.join(tempDir, "med_valley_elim.shp")
    arcpy.EliminatePolygonPart_management(med_valley_polygon, med_valley_elim, 'AREA', min_hole)
    arcpy.Delete_management("med_polygon_lyr")

    sm_valley_polygon = os.path.join(tempDir, "sm_valley_polygon.shp")
    arcpy.MakeFeatureLayer_management(sm_polygon, "sm_polygon_lyr")
    quer = '"DA_sqkm" < ' + str(low_da_thresh)
    arcpy.SelectLayerByAttribute_management('fcNetwork_lyr', 'NEW_SELECTION', quer)
    arcpy.SelectLayerByLocation_management("sm_polygon_lyr", "INTERSECT", 'fcNetwork_lyr')
    arcpy.CopyFeatures_management("sm_polygon_lyr", sm_valley_polygon)
    arcpy.Delete_management("sm_polygon_lyr")

    # merge and clean valley bottom polygons
    print "Merging outputs for final valley bottom..."
    merged_polygon = os.path.join(tempDir, "merged_polygon.shp")
    arcpy.Merge_management([lg_valley_elim, med_valley_elim, sm_valley_polygon, min_buffer], merged_polygon)

    # dissolve and aggregate valley bottom
    dissolved_valley = os.path.join(tempDir, "dissolved_valley.shp")
    arcpy.Dissolve_management(merged_polygon, dissolved_valley, '', '', 'SINGLE_PART')

    elim_valley = os.path.join(tempDir, "elim_valley.shp")
    arcpy.EliminatePolygonPart_management(dissolved_valley, elim_valley, 'AREA', min_hole)

    # commented out this block as it was throwing errors in newer versions of ArcMap
    # try:
    #     aggregated_valley = os.path.join(projPath, "aggregated_valley.shp")  # ToDo: change to tempDir and/or delete after testing
    #     arcpy.AggregatePolygons_cartography(dissolved_valley, aggregated_valley, ag_distance, min_area, min_hole)
    #     aggregated_valley_sm = os.path.join(projPath, "aggregated_valley_smoothed.shp")
    #     arcpy.SmoothPolygon_cartography(aggregated_valley, aggregated_valley_sm, "PAEK", "65 Meters", "FIXED_ENDPOINT", "NO_CHECK")
    # except:
    #     print "!!Warning: Aggregating valley bottom failed..."
    #     pass

    # smooth final valley bottom
    j = 1
    while os.path.exists(os.path.join(projPath, "02_Analyses/Output_" + str(j))):
        j += 1

    # save final valley bottom
    outDir = os.path.join(projPath, "02_Analyses\\Output_" + str(j))
    os.mkdir(outDir)
    fcOutput = os.path.join(outDir, outName)

    arcpy.SmoothPolygon_cartography(elim_valley, fcOutput, "PAEK", "65 Meters", "FIXED_ENDPOINT", "NO_CHECK")
    arcpy.CopyFeatures_management(fcOutput, os.path.join(outDir, "Unfragmented_Valley.shp"))
    arcpy.AddMessage("Successfully saved valley bottom output shapefile...")

    # temporary code to copy fcs with issues to output folder
    # arcpy.CopyFeatures_management(merged_polygon, os.path.join(outDir, "merged_polygon.shp"))


    # delete temporary files and workspace...
    arcpy.AddMessage("Removing scratch files...")

    temp_files = glob.glob(os.path.join(tempDir, '*'))
    for temp_file in temp_files:
        try:
            arcpy.Delete_management(temp_file)
        except:
            pass
    rmtree(tempDir)


    # --write xml--
    arcpy.AddMessage("Writing xml...")
    if not os.path.exists(projPath + "/project.rs.xml"):

        # xml file
        xmlfile = projPath + "/project.rs.xml"

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

        newxml.addVBETRealization("VBET Realization 1", rid="RZ1", dateCreated=datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                  productVersion="1.0.11", guid=getUUID())

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
        newxml.addProjectInput("DEM", "DEM", dem_path[dem_path.find("01_Inputs"):], iid="DEM1", guid=getUUID())
        newxml.addVBETInput(newxml.VBETrealizations[0], "DEM", ref="DEM1")

        newxml.addProjectInput("Vector", "Drainage Network", fcNetwork[fcNetwork.find("01_Inputs"):], iid="DN1", guid=getUUID())
        newxml.addVBETInput(newxml.VBETrealizations[0], "Network", ref="DN1")

        if FlowAcc == None:
            newxml.addVBETInput(newxml.VBETrealizations[0], "Flow", name="Drainage Area", path=DrAr[DrAr.find("01_Inputs"):], guid=getUUID())
        else:
            newxml.addProjectInput("Raster", "Drainage Area", DrAr[DrAr.find("01_Inputs"):], iid="DA1", guid=getUUID())
            newxml.addVBETInput(newxml.VBETrealizations[0], "Flow", ref="DA1")

        newxml.addVBETInput(newxml.VBETrealizations[0], "Slope", name="Slope", path=inSlope[inSlope.find("01_Inputs"):], guid=getUUID())

        newxml.addVBETInput(newxml.VBETrealizations[0], "Buffer", name="Large Buffer", path=lg_buffer[lg_buffer.find("01_Inputs"):], guid=getUUID())
        newxml.addVBETInput(newxml.VBETrealizations[0], "Buffer", name="Medium Buffer", path=med_buffer[med_buffer.find("01_Inputs"):], guid=getUUID())
        newxml.addVBETInput(newxml.VBETrealizations[0], "Buffer", name="Small Buffer", path=sm_buffer[sm_buffer.find("01_Inputs"):], guid=getUUID())

        newxml.addOutput("VBET Analysis", "Vector", "Unedited Valley Bottom", fcOutput[fcOutput.find("02_Analyses"):], newxml.VBETrealizations[0], guid=getUUID())

        newxml.write()

    else:
        # xml file
        xmlfile = projPath + "/project.rs.xml"

        exxml = projectxml.ExistingXML(xmlfile)

        vbetr = exxml.rz.findall("VBET")

        rname = []
        for x in range(len(vbetr)):
            name = vbetr[x].find("Name")
            rname.append(name.text)
        rnum = []
        for y in range(len(rname)):
            num = int(rname[y][-1])
            rnum.append(num)

        k = 2
        while k in rnum:
            k += 1

        exxml.addVBETRealization("VBET Realization " + str(k), rid="RZ" + str(k), dateCreated=datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                 productVersion="1.0.11", guid=getUUID())

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
            if os.path.abspath(dempath[i]) == os.path.abspath(dem_path[dem_path.find("01_Inputs"):]):
                exxml.addVBETInput(exxml.VBETrealizations[0], "DEM", ref=str(demid[i]))
        nlist = []
        for j in dempath:
            if os.path.abspath(dem_path[dem_path.find("01_Inputs"):]) == os.path.abspath(j):
                nlist.append("yes")
            else:
                nlist.append("no")
        if "yes" in nlist:
            pass
        else:
            exxml.addProjectInput("DEM", "DEM", dem_path[dem_path.find("01_Inputs"):], iid="DEM" + str(k), guid=getUUID())
            exxml.addVBETInput(exxml.VBETrealizations[0], "DEM", ref="DEM" + str(k))

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
                exxml.addVBETInput(exxml.VBETrealizations[0], "Buffer", name="Large Buffer", path=lg_buffer[lg_buffer.find("01_Inputs"):], guid=getUUID())
                exxml.addVBETInput(exxml.VBETrealizations[0], "Buffer", name="Medium Buffer", path=med_buffer[med_buffer.find("01_Inputs"):], guid=getUUID())
                exxml.addVBETInput(exxml.VBETrealizations[0], "Buffer", name="Small Buffer", path=sm_buffer[sm_buffer.find("01_Inputs"):], guid=getUUID())
        nlist = []
        for j in dnpath:
            if os.path.abspath(fcNetwork[fcNetwork.find("01_Inputs"):]) == os.path.abspath(j):
                nlist.append("yes")
            else:
                nlist.append("no")
        if "yes" in nlist:
            pass
        else:
            exxml.addProjectInput("Vector", "Drainage Network", fcNetwork[fcNetwork.find("01_Inputs"):], iid="DN" + str(k), guid=getUUID())
            exxml.addVBETInput(exxml.VBETrealizations[0], "Network", ref="DN" + str(k))
            exxml.addVBETInput(exxml.VBETrealizations[0], "Buffer", name="Large Buffer", path=lg_buffer[lg_buffer.find("01_Inputs"):], guid=getUUID())
            exxml.addVBETInput(exxml.VBETrealizations[0], "Buffer", name="Medium Buffer", path=med_buffer[med_buffer.find("01_Inputs"):], guid=getUUID())
            exxml.addVBETInput(exxml.VBETrealizations[0], "Buffer", name="Small Buffer", path=sm_buffer[sm_buffer.find("01_Inputs"):], guid=getUUID())
        del nlist

        if FlowAcc is None:
            exxml.addVBETInput(exxml.VBETrealizations[0], "Flow", name="Drainage Area", path=DrAr[DrAr.find("01_Inputs"):], guid=getUUID())
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
                flows = exxml.rz.findall(".//Flow")
                flowpath = range(len(flows))
                for i in range(len(flows)):
                    if flows[i].find("Path").text:
                        flowpath[i] = flows[i].find("Path").text
                        if os.path.abspath(flowpath[i]) == os.path.abspath(DrAr[DrAr.find("01_Inputs"):]):
                            flowguid = flows[i].attrib['guid']
                            exxml.addVBETInput(exxml.VBETrealizations[0], "Flow", "Drainage Area", path=DrAr[DrAr.find("01_Inputs"):], guid=flowguid)
                    else:
                        pass

        exxml.addOutput("VBET Analysis " + str(k), "Vector", "Unedited Valley Bottom",
                        fcOutput[fcOutput.find("02_Analyses"):], exxml.VBETrealizations[0], guid=getUUID())

        exxml.write()

    arcpy.CheckInExtension("Spatial")

if __name__ == "__main__":
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
