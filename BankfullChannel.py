# ----------------------------------------------------------------------------------------------------------------------
# Name: Bankfull Channel
# Purpose: Creates a polygon representing the bankfull channel of a network. The equation/regression used to
#          derive the polygon was developed for the Interior Columbia River Basin by T. Beechie and H. Imaki.
# Author: Jordan Gilbert
# Created: 05/2015
# Updated: 01/2020 - Maggie Hallerud
# Adapted to RCAT: 03/2020 - Maggie Hallerud
# License:This work is licensed under the Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International
#              License. To view a copy of this license, visit http://creativecommons.org/licenses/by-nc-sa/4.0/.
# ----------------------------------------------------------------------------------------------------------------------

import arcpy
from arcpy.sa import *
import sys
import os
from SupportingFunctions import find_available_num_prefix, make_layer
arcpy.CheckOutExtension('Spatial')


def main(network, valleybottom, dem, drarea, precip, MinBankfullWidth, dblPercentBuffer, output_folder, out_polygon_name, out_network_name):
    """ Calculates bankfull channel width and creates a bankfull channel polygon
    :param network: Segmented stream network from RVD output, to calculate bankfull channel on
    :param valleybottom: Valley bottom for stream network
    :param dem: Elevation raster for stream network
    :param drarea: Drainage area raster for stream network (optional)
    :param precip: Precipitation raster for stream network
    :param MinBankfullWidth: Minimum bankfull channel width (in meters) (default 5)
    :param dblPercentBuffer: Percent buffer to multiply calculated channel widths by before buffering (default 100)
    :param output_folder: Output folder for RCAT run with format "Output_**"
    :param out_polygon_name: Name for output bankfull channel polygon
    :param out_network_name: Name for output network with bankfull channel fields
    return: Bankfull channel polygon and output network with bankfull channel fields
    """

    add_constant = False
    river_name = False

    # process inputs
    if drarea == "None" or add_constant:
        drarea = None

    # set up environment
    arcpy.env.overwriteOutput = True
    
    # set up folder structure
    intermediates_folder, temp_dir, analysis_dir, scratch = build_folder_structure(output_folder)
    
    # get thiessen polygons clipped to buffered valley bottom, or make new one if none exists
    thiessen_clip = os.path.join(intermediates_folder, "02_ValleyThiessen/Thiessen_Valley.shp")
    if not os.path.exists(thiessen_clip):
        arcpy.AddMessage("Creating thiessen polygons within valley bottom...")
        thiessen_clip, valley_buffer = create_thiessen_polygons_in_valley(network, valleybottom, intermediates_folder, scratch)

    # calculate drainage area
    if drarea is None:
        arcpy.AddMessage("Creating drainage area raster...")
        drarea = calc_drain_area(dem)
    
    # calculate precip and drarea values for each thiessen polygon
    arcpy.AddMessage("Adding drainage area values to thiessen polygons...")
    add_raster_values(thiessen_clip, drarea, "drarea", temp_dir)
    arcpy.AddMessage("Adding precipitation values to thiessen polygons...")
    add_raster_values(thiessen_clip, precip, "precip", temp_dir)
    
    # dissolve network 
    arcpy.AddMessage("Applying precip and drainage area data to line network...")
    #dissolved_network = os.path.join(temp_dir, "dissolved_network.shp")
    #arcpy.Dissolve_management(network, dissolved_network)

    # intersect dissolved network with thiessen polygons
    if not out_network_name.endswith(".shp"):
        valley_join = os.path.join(analysis_dir, "Intersect" + out_network_name + ".shp")
    else:
        valley_join = os.path.join(analysis_dir, "Intersect" + out_network_name)

    arcpy.AddMessage("Starting Spatial Join...")
    
    arcpy.SpatialJoin_analysis(network, thiessen_clip, valley_join, search_radius="5 Meters")

    arcpy.AddMessage("Finished Spatial Join")

    # intersect dissolved network with thiessen polygons
    if not out_network_name.endswith(".shp"):
        spatial_join_out = os.path.join(analysis_dir, out_network_name+".shp")
    else:
        spatial_join_out = os.path.join(analysis_dir, out_network_name)

    arcpy.SpatialJoin_analysis(valley_join, network, spatial_join_out, search_radius="5 Meters")

    if add_constant:
        did_change = False
        with arcpy.da.UpdateCursor(spatial_join_out, ["StreamName", "DRAREA"]) as cursor:
            for row in cursor:
                if row[0] == river_name:
                    arcpy.AddMessage("\tAdjusting value for {}".format(river_name))
                    row[1] += add_constant
                    did_change = True
                cursor.updateRow(row)
        if not did_change:
            arcpy.AddMessage("Could not find stream name")

    # calculate buffer width
    arcpy.AddMessage("Calculating bankfull buffer width...")
    calculate_buffer_width(spatial_join_out, MinBankfullWidth, dblPercentBuffer)

    # create final bankfull polygon
    arcpy.AddMessage("Creating final bankfull polygon...")
    bankfull = create_bankfull_polygon(network, spatial_join_out, MinBankfullWidth, analysis_dir, temp_dir, out_polygon_name)

    # making layers
    arcpy.AddMessage("Making layers...")
    make_layers(spatial_join_out, bankfull)

def build_folder_structure(output_folder):
    scratch = os.path.join(os.path.dirname(os.path.dirname(output_folder)), "Temp")
    make_folder(scratch)
    intermediates_folder = os.path.join(output_folder, "01_Intermediates")
    make_folder(intermediates_folder)
    temp_dir = os.path.join(intermediates_folder, find_available_num_prefix(intermediates_folder)+"_BankfullChannel")
    make_folder(temp_dir)
    analysis_folder = os.path.join(output_folder, "02_Analyses")
    make_folder(analysis_folder)
    bankfull_dir = os.path.join(analysis_folder, find_available_num_prefix(analysis_folder)+"_BankfullChannel")
    make_folder(bankfull_dir)
    return intermediates_folder, temp_dir, bankfull_dir, scratch


def create_thiessen_polygons_in_valley(seg_network, valley, intermediates_folder, scratch):
    # find midpoints of all reaches in segmented network
    seg_network_lyr = "seg_network_lyr"
    arcpy.MakeFeatureLayer_management(seg_network, seg_network_lyr)
    midpoints = scratch + "/midpoints.shp"
    arcpy.FeatureVerticesToPoints_management(seg_network, midpoints, "MID")

    # list all fields in midpoints file
    midpoint_fields = [f.name for f in arcpy.ListFields(midpoints)]
    # remove permanent fields from this list
    remove_list = ["FID", "Shape", "OID", "OBJECTID", "ORIG_FID"] # remove permanent fields from list
    for field in remove_list:
        if field in midpoint_fields:
            try:
                midpoint_fields.remove(field)
            except Exception:
                pass
    # delete all miscellaneous fields - with error handling in case Arc won't allow field deletion
    for f in midpoint_fields:
        try:
            arcpy.DeleteField_management(midpoints, f)
        except Exception as err:
            pass

    # create thiessen polygons surrounding reach midpoints
    thiessen_folder = os.path.join(intermediates_folder, "01_MidpointsThiessen")
    if not os.path.exists(thiessen_folder):
        os.mkdir(thiessen_folder)
    thiessen = thiessen_folder + "/midpoints_thiessen.shp"
    arcpy.CreateThiessenPolygons_analysis(midpoints, thiessen, "ALL")

    # buffer fragmented valley bottom
    valley_buf = scratch + "/valley_buf.shp"
    valley_lyr = 'valley_lyr'
    arcpy.MakeFeatureLayer_management(in_features=valley, out_layer=valley_lyr) #convert valley buffer to layer - JLW
    arcpy.Buffer_analysis(valley_lyr, valley_buf, "30 Meters", "FULL", "ROUND", "ALL")

    # clip thiessen polygons to buffered valley bottom
    thiessen_valley_multipart = scratch + "/Thiessen_Valley_Clip.shp"
    arcpy.Clip_analysis(thiessen, valley_buf, thiessen_valley_multipart)

    # convert multipart features to single part
    arcpy.AddField_management(thiessen_valley_multipart, "RCH_FID", "SHORT")
    with arcpy.da.UpdateCursor(thiessen_valley_multipart, ["ORIG_FID", "RCH_FID"]) as cursor:
        for row in cursor:
            row[1] = row[0]
            cursor.updateRow(row)
    thiessen_singlepart = scratch + "/Thiessen_Singlepart.shp"
    arcpy.MultipartToSinglepart_management(thiessen_valley_multipart, thiessen_singlepart)

    # Select only polygon features that intersect network midpoints
    thiessen_singlepart_lyr = arcpy.MakeFeatureLayer_management(in_features=thiessen_singlepart)
    midpoints_lyr = arcpy.MakeFeatureLayer_management(in_features=midpoints)
    thiessen_select = arcpy.SelectLayerByLocation_management(thiessen_singlepart_lyr, "INTERSECT", midpoints_lyr,
                                                             selection_type="NEW_SELECTION")

    # save new thiessen polygons
    thiessen_valley_folder = os.path.join(intermediates_folder, find_available_num_prefix(intermediates_folder)+"_ValleyThiessen")
    make_folder(thiessen_valley_folder)
    thiessen_valley = os.path.join(thiessen_valley_folder, "Thiessen_Valley.shp")
    arcpy.CopyFeatures_management(thiessen_select, thiessen_valley)

    return thiessen_valley, valley_buf


def calc_drain_area(DEM):
    """
    Calculate drainage area function
    :param DEM: The original input DEM
    :return:
    """
    #  --smooth input dem by 3x3 cell window--
    #  define raster environment settings
    desc = arcpy.Describe(DEM)
    arcpy.env.extent = desc.Extent
    arcpy.env.outputCoordinateSystem = desc.SpatialReference
    arcpy.env.cellSize = desc.meanCellWidth
    # calculate mean z over 3x3 cell window
    neighborhood = NbrRectangle(3, 3, "CELL")
    tmp_dem = FocalStatistics(DEM, neighborhood, 'MEAN')
    # clip smoothed dem to input dem
    smoothedDEM = ExtractByMask(tmp_dem, DEM)
    #  define raster environment settings
    desc = arcpy.Describe(smoothedDEM)
    arcpy.env.extent = desc.Extent
    arcpy.env.outputCoordinateSystem = desc.SpatialReference
    arcpy.env.cellSize = desc.meanCellWidth
    #  calculate cell area for use in drainage area calcultion
    height = desc.meanCellHeight
    width = desc.meanCellWidth
    cell_area = height * width
    # derive drainage area raster (in square km) from input DEM
    # note: draiange area calculation assumes input dem is in meters
    filledDEM = Fill(smoothedDEM) # fill sinks in dem
    flow_direction = FlowDirection(filledDEM) # calculate flow direction
    flow_accumulation = FlowAccumulation(flow_direction) # calculate flow accumulation
    drain_area = flow_accumulation * cell_area / 1000000 # calculate drainage area in square kilometers
    # save drainage area raster
    drain_area_path = os.path.dirname(DEM) + "/Flow/DrainArea_sqkm.tif"
    if os.path.exists(drain_area_path):
        arcpy.Delete_management(drain_area_path)
        drain_area.save(drain_area_path)
    else:
        os.mkdir(os.path.dirname(DEM) + "/Flow")
        drain_area.save(drain_area_path)
    return drain_area_path


def add_raster_values(thiessen_clip, raster, field_type, temp_dir):
    """thiessen_clip : thiessen polygons clipped to buffered valley bottom which values will be added to
    raster : raster from which values are extracted
    field_type : "drarea" or "precip"
    """
    # set output field names based on field_type
    if field_type == "drarea":
        field_name = "DRAREA"
    if field_type == "precip":
        field_name = "PRECIP"

    # Zonal statistics of drainage area and precip using thiessen polygons
    tbl_out = os.path.join(temp_dir, "zonal_tbl_" + field_type + ".dbf")
    tbl_zs = ZonalStatisticsAsTable(thiessen_clip, "RCH_FID", raster, tbl_out, "DATA", "MAXIMUM")
    # delete required fields if already in thiessen fields
    thiessen_fields = [f.name for f in arcpy.ListFields(thiessen_clip)]
    if "MAX" in thiessen_fields:
        arcpy.DeleteField_management(thiessen_clip, "MAX")
    if field_name in thiessen_fields:
        arcpy.DeleteField_management(thiessen_clip, field_name)
        
    # join thiessen clip to zonal statas table and calculate raster value for each thiessen polygon
    arcpy.JoinField_management(thiessen_clip, "RCH_FID", tbl_zs, "RCH_FID", "MAX")
    arcpy.AddField_management(thiessen_clip, field_name, "FLOAT")
    with arcpy.da.UpdateCursor(thiessen_clip, ["MAX", field_name]) as cursor:
        for row in cursor:
            row[1] = row[0]
            cursor.updateRow(row)
    arcpy.DeleteField_management(thiessen_clip, "MAX")
  
    ## We're going to extract raster values to the center of each thiessen polygon that did not
    ## receive a value using zonal statistics. Most polygons are being "missed" for precip and some
    ## for drainage area since the raster resolution is larger than many of these tiny thiessen polygons -
    ## especially with the 800 meters-squared PRISM data.

    # get list of original fields before anything else
    thiessen_fields = [f.name for f in arcpy.ListFields(thiessen_clip)]
    # select thiessen polygons with no drainage area data
    no_data = arcpy.Select_analysis(thiessen_clip, None, """ %s = 0 """ % field_name)
    # convert selected polygons to centroid points
    missing_pts = os.path.join(temp_dir, "missing_" + field_type + "_pts.shp")
    arcpy.FeatureToPoint_management(no_data, missing_pts, "INSIDE")
    # extract values from raster to points
    missing_data = os.path.join(temp_dir, "missing_" + field_type + "_data.shp")
    arcpy.sa.ExtractValuesToPoints(missing_pts, raster, missing_data)
    # join points to selected polygons
    filled_missing_thiessen = os.path.join(temp_dir, "filled_missing_" + field_type + ".shp")
    needed_fields = thiessen_fields.append("RASTERVALU")
    arcpy.SpatialJoin_analysis(no_data, missing_data, filled_missing_thiessen,
                               join_operation="JOIN_ONE_TO_ONE", join_type="KEEP_ALL",
                               field_mapping=needed_fields, match_option="CONTAINS")
    # join selected polygons to original thiessen polygons
    arcpy.JoinField_management(thiessen_clip, "RCH_FID", filled_missing_thiessen, "Input_FID")
    # fill in missing DRAREA values based on raster values extracted to points
    with arcpy.da.UpdateCursor(thiessen_clip, [field_name, "RASTERVALU"]) as cursor:
        for row in cursor:
            if row[0] == 0:
                row[0] = row[1]
            cursor.updateRow(row)
    # delete all extra fields joined to original thiessen polygons
    arcpy.DeleteField_management(thiessen_clip, "RASTERVALU")
    all_fields = [f.name for f in arcpy.ListFields(thiessen_clip)]
    for f in all_fields:
        if f not in thiessen_fields:
            try:
                arcpy.DeleteField_management(thiessen_clip, f)
            except Exception as err:
                arcpy.AddMessage("Could not delete unnecessary field " + f + " from thiessen_clip.shp")
                arcpy.AddMessage("Error thrown was")
                arcpy.AddMessage(err)


def calculate_buffer_width(intersect, MinBankfullWidth, dblPercentBuffer):
    arcpy.AddField_management(intersect, "BFWIDTH", "FLOAT")
    with arcpy.da.UpdateCursor(intersect, ["DRAREA", "PRECIP", "BFWIDTH"])as cursor:
        for row in cursor:
            # calculate bankfull width
            drarea = row[0]
            precip_cm = row[1]/10
            if precip_cm > 0 and drarea > 0:
                row[2] = 0.177*(pow(drarea,0.397))*(pow(precip_cm,0.453))
            else:
                row[2] = -9999
            # adjust for min bankfull width
            if row[2] < float(MinBankfullWidth):
                row[2] = float(MinBankfullWidth)
            cursor.updateRow(row)

    # adjust buffer width based on percent buffer
    arcpy.AddField_management(intersect, "BUFWIDTH", "DOUBLE")
    with arcpy.da.UpdateCursor(intersect, ["BFWIDTH", "BUFWIDTH"]) as cursor:
        for row in cursor:
            if row[0] > 0:
                row[1] = row[0]/2 + ((row[0]/2) * (float(dblPercentBuffer)/100))
            cursor.updateRow(row)


def create_bankfull_polygon(network, intersect, MinBankfullWidth, bankfull_folder, temp_dir, out_name):
    # buffer network by bufwidth field to create bankfull polygon
    arcpy.AddMessage("Buffering network...")
    bankfull = os.path.join(temp_dir, "bankfull.shp")
    arcpy.Buffer_analysis(intersect, bankfull, "BUFWIDTH", "FULL", "ROUND", "ALL")

    # merge buffer with min buffer
    bankfull_min_buffer = os.path.join(temp_dir, "min_buffer.shp")
    bankfull_merge = os.path.join(temp_dir, "bankfull_merge.shp")
    #bankfull_dissolve = os.path.join(temp_dir, "bankfull_dissolve.shp")
    arcpy.Buffer_analysis(network, bankfull_min_buffer, str(MinBankfullWidth), "FULL", "ROUND", "ALL")
    arcpy.Merge_management([bankfull, bankfull_min_buffer], bankfull_merge)

    # dissolve polygon buffers
    if not out_name.endswith(".shp"):
        output = os.path.join(bankfull_folder, out_name + ".shp")
    else:
        output = os.path.join(bankfull_folder, out_name)

    arcpy.Dissolve_management(bankfull_merge, output)

    #smooth for final bankfull polygon
    #arcpy.AddMessage("Smoothing final bankfull polygon...")
    
    #if not out_name.endswith(".shp"):
    #    output = os.path.join(bankfull_folder, out_name+".shp")
    #else:
    #    output = os.path.join(bankfull_folder, out_name)

    #arcpy.SmoothPolygon_cartography(bankfull_dissolve, output, "PAEK", "10 METERS") # TODO: Expose parameter?
    
    # Todo: add params as fields to shp.
    return output


def make_layers(network, bankfull_polygon):
    source_code_folder = os.path.dirname(os.path.abspath(__file__))
    symbology_folder = os.path.join(source_code_folder, "RCATSymbology")
    # pull symbology
    bankfull_network_symbology = os.path.join(symbology_folder, "BankfullChannelNetwork.lyr")
    bankfull_polygon_symbology = os.path.join(symbology_folder, "BankfullChannelPolygon.lyr")
    drain_area_symbology = os.path.join(symbology_folder, "UpstreamDrainageArea.lyr")
    precip_symbology = os.path.join(symbology_folder, "PrecipitationByReach.lyr")
    # make layers
    make_layer(os.path.dirname(network), network, "Bankfull Channel Network", bankfull_network_symbology, symbology_field="BUFWIDTH")
    make_layer(os.path.dirname(network), network, "Upstream Drainage Area", drain_area_symbology, symbology_field="DRAREA")
    make_layer(os.path.dirname(network), network, "Precipitation By Reach", precip_symbology, symbology_field="PRECIP")
    make_layer(os.path.dirname(bankfull_polygon), bankfull_polygon, "Bankfull Channel Polygon", bankfull_polygon_symbology)


def make_folder(folder):
    """
    Makes folder if it doesn't exist already
    """
    if not os.path.exists(folder):
        os.mkdir(folder)
    return


    
if __name__ == '__main__':
    main(sys.argv[1],
         sys.argv[2],
         sys.argv[3],
         sys.argv[4],
         sys.argv[5],
         sys.argv[6],
         sys.argv[7],
         sys.argv[8],
         sys.argv[9],
         sys.argv[10])