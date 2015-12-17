#-------------------------------------------------------------------------------
# Name:        Valley Bottom Extraction Tool (V-BET)
# Purpose:     Uses a stream network and a DEM to extract a polygon representing
#              the valley bottom
# Author:      Jordan Gilbert
#
# Created:     25/09/2015
# Copyright:   (c) Jordan Gilbert 2015
# Licence:     <your licence>
#-------------------------------------------------------------------------------

#import modules
import arcpy
import sys
import os
from arcpy.sa import *


def main(
    DEM,
    fcNetwork,
    FlowAcc,
    fcOutput,
    lg_buf_size,
    med_buf_size,
    sm_buf_size,
    min_buf_size,
    scratch = arcpy.env.scratchWorkspace,
    ag_distance = 150.0,
    min_area = 30000.0,
    min_hole = 30000.0):

    arcpy.env.overwriteOutput = True
    arcpy.CheckOutExtension("spatial")

    # check that input data is in projected coordinate system
    networkSR = arcpy.Describe(fcNetwork).spatialReference
    if networkSR.type == "Projected":
        pass
    else:
        raise Exception("Input stream network must have a projected coordinate system")

    # calculate flow accumulation and convert to drainage area, or input drainage area raster
    if FlowAcc == None:
        arcpy.AddMessage("calculating drainage area")
        calc_drain_area(DEM)
    else:
        pass

    # extract "large" and "medium" portions of the network from the drainage area raster
    if FlowAcc == None:
        DEM_dirname = os.path.dirname(DEM)
        DrArea = DEM_dirname + "/DrainArea_sqkm.tif"
    else:
        DrArea = Raster(FlowAcc)

    arcpy.AddMessage("segmenting stream network by drainage area")
    lg_polyline = scratch + "/lg_polyline"
    med_polyline = scratch + "/med_polyline"

    lg_reclass = Reclassify(DrArea, "VALUE", "0 250 NODATA; 250 10000000 1", "NODATA")   #look into using dataset max instead of 10000000
    med_reclass = Reclassify(DrArea, "VALUE", "0 25 NODATA; 25 250 1; 250 10000000 NODATA", "NODATA")

    arcpy.RasterToPolyline_conversion(lg_reclass, lg_polyline, "NODATA")
    arcpy.RasterToPolyline_conversion(med_reclass, med_polyline, "NODATA")

    # create buffers around the different network segments
    arcpy.AddMessage("creating buffers")
    lg_buffer = scratch + "/lg_buffer"
    med_buffer = scratch + "/med_buffer"
    sm_buffer = scratch + "/sm_buffer"
    min_buffer = scratch + "/min_buffer"
    arcpy.Buffer_analysis(lg_polyline, lg_buffer, lg_buf_size, "", "ROUND", "ALL")
    arcpy.Buffer_analysis(med_polyline, med_buffer, med_buf_size, "", "ROUND", "ALL")
    arcpy.Buffer_analysis(fcNetwork, sm_buffer, sm_buf_size, "", "ROUND", "ALL")
    arcpy.Buffer_analysis(fcNetwork, min_buffer, min_buf_size, "", "ROUND", "ALL")

    # Slope analysis
    arcpy.AddMessage("creating slope raster")
    slope_raster = Slope(DEM, "DEGREE", "")

    arcpy.AddMessage("clipping slope raster")
    lg_buf_slope = ExtractByMask(slope_raster, lg_buffer)
    med_buf_slope = ExtractByMask(slope_raster, med_buffer)
    sm_buf_slope = ExtractByMask(slope_raster, sm_buffer)

    # reclassify slope rasters for each of the buffers
    arcpy.AddMessage("reclassifying slope rasters")
    lg_valley_raster = Reclassify(lg_buf_slope, "VALUE", "0 5 1; 5 100 NODATA", "NODATA")
    med_valley_raster = Reclassify(med_buf_slope, "VALUE", "0 7 1; 7 100 NODATA", "NODATA")
    sm_valley_raster = Reclassify(sm_buf_slope, "VALUE", "0 12 1; 12 100 NODATA", "NODATA")

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
    arcpy.SmoothPolygon_cartography(aggregated_valley, fcOutput, "PAEK", "65 Meters", "FIXED_ENDPOINT", "NO_CHECK")


    return fcOutput

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

    DEM_dirname = os.path.dirname(DEM)
    if os.path.exists(DEM_dirname + "/DrainArea_sqkm.tif"):
        arcpy.Delete_management(DEM_dirname + "/DrainArea_sqkm.tif")
        DrArea_path = DEM_dirname + "/DrainArea_sqkm.tif"
        DrainArea.save(DrArea_path)
    else:
        DrArea_path = DEM_dirname + "/DrainArea_sqkm.tif"
        DrainArea.save(DrArea_path)

    return


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
