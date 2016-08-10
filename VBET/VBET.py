#-------------------------------------------------------------------------------
# Name:        Valley Bottom Extraction Tool (V-BET)
# Purpose:     Uses a stream network and a DEM to extract a polygon representing
#              the valley bottom
# Author:      Jordan Gilbert
#
# Created:     09/25/2015
# Latest Update: 05/12/2016
# Copyright:   (c) Jordan Gilbert 2016
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
    high_da_thresh,
    low_da_thresh,
    lg_buf_size,
    med_buf_size,
    sm_buf_size,
    min_buf_size,
    lg_slope_thresh,
    med_slope_thresh,
    sm_slope_thresh,
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

    # check that input network is segmented
    ct = arcpy.GetCount_management(fcNetwork)
    count = int(ct.getOutput(0))
    if count < 30:
        raise Exception("Input stream network must have more than 30 segments")

    # calculate flow accumulation and convert to drainage area, or input drainage area raster
    if FlowAcc == None:
        arcpy.AddMessage("calculating drainage area")
        calc_drain_area(DEM)
    else:
        pass

    if FlowAcc == None:
        DEM_dirname = os.path.dirname(DEM)
        DrAr = DEM_dirname + "/DrainArea_sqkm.tif"
        DrArea = Raster(DrAr)
    else:
        DrArea = Raster(FlowAcc)

    # check that da thresholds are not larger than the da of the inputs
    if float(DrArea.maximum) > float(high_da_thresh) and float(DrArea.maximum) > float(low_da_thresh):
        pass
    else:
        raise Exception('drainage area threshold value is greater than highest network drainage area value')

    if float(DrArea.minimum) < float(low_da_thresh):
        pass
    else:
        raise Exception('low drainage area threshold is lower than lowest network drainage area value')


    arcpy.AddMessage("segmenting stream network by drainage area")

    # This strange workflow extracts drainage area values from the raster to an attribute for each network segment.
    network_midpoints = scratch + "/network_midpoints"
    arcpy.FeatureVerticesToPoints_management(fcNetwork, network_midpoints, "MID")
    midpoint_fields = [f.name for f in arcpy.ListFields(network_midpoints)]
    midpoint_fields.remove('OBJECTID')
    midpoint_fields.remove('Shape')
    midpoint_fields.remove('ORIG_FID')
    arcpy.DeleteField_management(network_midpoints, midpoint_fields)

    midpoint_buffer = scratch + "/midpoint_buffer"
    arcpy.Buffer_analysis(network_midpoints, midpoint_buffer, "100 Meters", "", "", "NONE")
    drarea_zs = ZonalStatistics(midpoint_buffer, "OBJECTID", DrArea, "MAXIMUM", "DATA")
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


    if DrArea.maximum >= int(high_da_thresh):
        # create buffers around the different network segments
        arcpy.AddMessage("creating buffers")
        arcpy.MakeFeatureLayer_management(fcNetwork, "network_lyr")
        lg_buffer = scratch + "/lg_buffer"
        arcpy.SelectLayerByAttribute_management("network_lyr", "NEW_SELECTION", '"DA_sqkm" >= {0}'.format(high_da_thresh))
        arcpy.Buffer_analysis("network_lyr", lg_buffer, lg_buf_size, "FULL", "ROUND", "ALL")
        med_buffer = scratch + "/med_buf"
        arcpy.SelectLayerByAttribute_management("network_lyr", "NEW_SELECTION", '"DA_sqkm" >= {0} AND "DA_sqkm" < {1}'.format(low_da_thresh, high_da_thresh))
        arcpy.Buffer_analysis("network_lyr", med_buffer, med_buf_size, "FULL", "ROUND", "ALL")
        sm_buffer = scratch + "/sm_buf"
        arcpy.SelectLayerByAttribute_management("network_lyr", "NEW_SELECTION", '"DA_sqkm" < {0}'.format(low_da_thresh))
        arcpy.Buffer_analysis("network_lyr", sm_buffer, sm_buf_size, "FULL", "ROUND", "ALL")
        min_buffer = scratch + "/min_buffer"
        arcpy.Buffer_analysis(fcNetwork, min_buffer, min_buf_size, "FULL", "ROUND", "ALL")

        # Slope analysis
        arcpy.AddMessage("creating slope raster")
        slope_raster = Slope(DEM, "DEGREE", "")

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
        arcpy.SmoothPolygon_cartography(aggregated_valley, fcOutput, "PAEK", "65 Meters", "FIXED_ENDPOINT", "NO_CHECK")

    elif DrArea.maximum >= int(low_da_thresh) and DrArea.maximum < int(high_da_thresh):
        # create buffers around the different network segments
        arcpy.AddMessage("creating buffers")
        arcpy.MakeFeatureLayer_management(fcNetwork, "network_lyr")
        med_buffer = scratch + "/med_buf"
        arcpy.SelectLayerByAttribute_management("network_lyr", "NEW_SELECTION", '"DA_sqkm" >= {0} AND "DA_sqkm" < {1}'.format(low_da_thresh, high_da_thresh))
        arcpy.Buffer_analysis("network_lyr", med_buffer, med_buf_size, "FULL", "ROUND", "ALL")
        sm_buffer = scratch + "/sm_buf"
        arcpy.SelectLayerByAttribute_management("network_lyr", "NEW_SELECTION", '"DA_sqkm" < {0}'.format(low_da_thresh))
        arcpy.Buffer_analysis("network_lyr", sm_buffer, sm_buf_size, "FULL", "ROUND", "ALL")
        min_buffer = scratch + "/min_buffer"
        arcpy.Buffer_analysis(fcNetwork, min_buffer, min_buf_size, "FULL", "ROUND", "ALL")

        # Slope analysis
        arcpy.AddMessage("creating slope raster")
        slope_raster = Slope(DEM, "DEGREE", "")

        arcpy.AddMessage("clipping slope raster")
        med_buf_slope = ExtractByMask(slope_raster, med_buffer)
        sm_buf_slope = ExtractByMask(slope_raster, sm_buffer)

        # reclassify slope rasters for each of the buffers
        arcpy.AddMessage("reclassifying slope rasters")
        med_valley_raster = Reclassify(med_buf_slope, "VALUE", "0 {0} 1; {0} 100 NODATA".format(med_slope_thresh), "NODATA")
        sm_valley_raster = Reclassify(sm_buf_slope, "VALUE", "0 {0} 1; {0} 100 NODATA".format(sm_slope_thresh), "NODATA")

        # convert valley rasters into polygons
        arcpy.AddMessage("converting valley rasters into polygons")
        med_polygon = scratch + "/med_polygon"
        sm_polygon = scratch + "/sm_polygon"
        arcpy.RasterToPolygon_conversion(med_valley_raster, med_polygon, "SIMPLIFY")
        arcpy.RasterToPolygon_conversion(sm_valley_raster, sm_polygon, "SIMPLIFY")

        # merge and clean valley bottom polygons
        merged_polygon = scratch + "/merged_polygon"
        arcpy.Merge_management([med_polygon, sm_polygon, min_buffer], merged_polygon)

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

    elif DrArea.maximum < int(low_da_thresh):
        # create buffers around the different network segments
        arcpy.AddMessage("creating buffers")
        arcpy.MakeFeatureLayer_management(fcNetwork, "network_lyr")
        sm_buffer = scratch + "/sm_buf"
        arcpy.SelectLayerByAttribute_management("network_lyr", "NEW_SELECTION", '"DA_sqkm" < {0}'.format(low_da_thresh))
        arcpy.Buffer_analysis("network_lyr", sm_buffer, sm_buf_size, "FULL", "ROUND", "ALL")
        min_buffer = scratch + "/min_buffer"
        arcpy.Buffer_analysis(fcNetwork, min_buffer, min_buf_size, "FULL", "ROUND", "ALL")

        # Slope analysis
        arcpy.AddMessage("creating slope raster")
        slope_raster = Slope(DEM, "DEGREE", "")

        arcpy.AddMessage("clipping slope raster")
        sm_buf_slope = ExtractByMask(slope_raster, sm_buffer)

        # reclassify slope rasters for each of the buffers
        arcpy.AddMessage("reclassifying slope rasters")
        sm_valley_raster = Reclassify(sm_buf_slope, "VALUE", "0 {0} 1; {0} 100 NODATA".format(sm_slope_thresh), "NODATA")

        # convert valley rasters into polygons
        arcpy.AddMessage("converting valley rasters into polygons")
        sm_polygon = scratch + "/sm_polygon"
        arcpy.RasterToPolygon_conversion(sm_valley_raster, sm_polygon, "SIMPLIFY")

        # merge and clean valley bottom polygons
        merged_polygon = scratch + "/merged_polygon"
        arcpy.Merge_management([sm_polygon, min_buffer], merged_polygon)

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
        sys.argv[12],
        sys.argv[13],
        sys.argv[14],
        sys.argv[15],
        sys.argv[16],
        sys.argv[17])
