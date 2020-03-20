# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
# Name:        Valley Confinement Tool                                        #
# Purpose:     Calculate Valley Confinement Along a Stream Network            #
#                                                                             #
# Author:      Kelly Whitehead (kelly@southforkresearch.org)                  #
#              South Fork Research, Inc                                       #
#              Seattle, Washington                                            #
#                                                                             #
# Created:     2014-Nov-01                                                    #
# Version:     1.3                                                            #
# Modified:    2016-Feb-10                                                    #
#                                                                             #
# Updated:      2020-Mar-06 for RCAT                                          #
#               Maggie Hallerud maggie.hallerud@aggiemail.usu.edu             #
# Copyright:   (c) Kelly Whitehead 2016                                       #
#                                                                             #
# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
#!/usr/bin/env python

# load dependencies
import os
import arcpy
import glob
from SupportingFunctions import make_folder, find_available_num_prefix

         
def main(network,
         valley_bottom,
         bankfull_channel,
         output_folder,
         output_raw_confinement,
         output_confining_margins):
    """ """
    # set up folder structure
    intermediates_folder, confinement_dir, analysis_folder, temp_dir = build_folder_structure(output_folder)
    if not output_raw_confinement.endswith(".shp"):
        raw_confinement = os.path.join(analysis_folder, output_raw_confinement + ".shp")
    else:
        raw_confinement = os.path.join(analysis_folder, output_raw_confinement)
    if not output_confining_margins.endswith(".shp"):
        confining_margins = os.path.join(intermediates_folder, output_confining_margins + ".shp")
    else:
        confining_margins = os.path.join(intermediates_folder, output_confining_margins)

    # set environment parameters
    arcpy.env.overwriteOutput = True
    arcpy.env.outputZFlag = "Disabled"
    arcpy.env.workspace = 'in_memory'

    arcpy.AddMessage("Finding confining margins...")
    # Create confined channel polygon
    confined_channel = os.path.join(temp_dir, "confined_channel.shp")
    arcpy.Clip_analysis(bankfull_channel, valley_bottom, confined_channel)
    # Convert confined channel polygon to edges polyline
    channel_margins = os.path.join(confinement_dir, "ChannelMargins.shp")
    arcpy.PolygonToLine_management(confined_channel, channel_margins)
    # Create confinement edges
    confining_margins_multipart = os.path.join(temp_dir, "confining_margins_multipart.shp")
    arcpy.Intersect_analysis([confined_channel, valley_bottom], confining_margins_multipart, output_type="LINE")
    arcpy.MultipartToSinglepart_management(confining_margins_multipart, confining_margins)
    # Merge segments in Polyline Center to create Route Layer
    network_dissolve = os.path.join(temp_dir, "network_dissolve.shp")
    arcpy.Dissolve_management(network, network_dissolve, multi_part="SINGLE_PART", unsplit_lines="UNSPLIT_LINES") # one feature per 'section between trib or branch junctions'
    network_segment_points = os.path.join(temp_dir, "network_segment_points.shp")
    arcpy.FeatureVerticesToPoints_management(network, network_segment_points, "END")
    stream_network_dangles = os.path.join(temp_dir, "stream_network_dangles.shp")
    arcpy.FeatureVerticesToPoints_management(network, stream_network_dangles, "DANGLE")

    # Segment polgyons
    arcpy.AddMessage("Preparing segmented polygons...")
    channel_segment_polygons = os.path.join(confinement_dir, "ChannelSegmentPolygons.shp")
    arcpy.CopyFeatures_management(confined_channel, channel_segment_polygons)
    segment_polygon_lines = os.path.join(temp_dir, "channel_segment_polygon_lines.shp")
    arcpy.PolygonToLine_management(in_features=channel_segment_polygons, out_feature_class=segment_polygon_lines)
    segment_poly_lines_lyr = arcpy.MakeFeatureLayer_management(segment_polygon_lines, "channel_segment_polygon_lines_lyr")

    stream_network_dangles_lyr = arcpy.MakeFeatureLayer_management(stream_network_dangles, "strm_network_dangles_lyr")
    arcpy.SelectLayerByLocation_management(stream_network_dangles_lyr, "INTERSECT", confined_channel)
    arcpy.Near_analysis(stream_network_dangles_lyr, segment_poly_lines_lyr, location="LOCATION")
    arcpy.AddXY_management(stream_network_dangles_lyr)

    bank_nearlines = os.path.join(temp_dir, "channel_bank_nearlines.shp")
    arcpy.XYToLine_management(stream_network_dangles_lyr, bank_nearlines, "POINT_X", "POINT_Y", "NEAR_X", "NEAR_Y")

    channel_bank_lines = os.path.join(temp_dir, "channel_bank_lines.shp")
    arcpy.Merge_management([network, bank_nearlines, segment_polygon_lines], channel_bank_lines)
    channel_bank_polygons = os.path.join(confinement_dir, "channel_bank_polygons.shp")
    arcpy.FeatureToPolygon_management(channel_bank_lines, channel_bank_polygons)
        
    # # Intersect and Split Channel polygon Channel Edges and Polyline Confinement using cross section lines
    arcpy.AddMessage("Split channel polygons based on network segments...")
    points_confinement_margins = os.path.join(temp_dir, "intersect_pts_confining_margins.shp")
    arcpy.Intersect_analysis([confining_margins, segment_polygon_lines], points_confinement_margins, output_type="POINT")
    points_channel_margins = os.path.join(temp_dir, "intersect_pts_channel_margins.shp")
    arcpy.Intersect_analysis([channel_margins, segment_polygon_lines], points_channel_margins, output_type="POINT")
    confinement_margin_segments = os.path.join(confinement_dir, "confining_margin_segments.shp")
    arcpy.SplitLineAtPoint_management(confining_margins, points_confinement_margins, confinement_margin_segments, search_radius="10 Meters")
    channel_margin_segments = os.path.join(confinement_dir, "channel_margin_segments.shp")
    arcpy.SplitLineAtPoint_management(channel_margins, points_channel_margins, channel_margin_segments, search_radius="10 Meters")

    # Create River Side buffer to select right or left banks
    arcpy.AddMessage("Determining relative sides of bank...")
    determine_banks(network, channel_bank_polygons, temp_dir)

    # Prepare Layers for Segment Selection
    segment_polygons_lyr = arcpy.MakeFeatureLayer_management(channel_segment_polygons, "segment_polygons_lyr")
    confinement_edge_segments_lyr = arcpy.MakeFeatureLayer_management(confinement_margin_segments, "confinement_edge_segments_lyr")
    channel_edge_segments_lyr = arcpy.MakeFeatureLayer_management(channel_margin_segments, "channel_margin_segments_lyr")

    ## Prepare Filtered Margins
    filter_split_points = arcpy.FeatureVerticesToPoints_management(confinement_margin_segments, "filter_split_points", "BOTH_ENDS")

    # Transfer Confining Margins to Stream Network ##
    arcpy.AddMessage("Transferring confining margins to stream network...")
    confinement_margin_segments_bankside = os.path.join(temp_dir, "confinement_margin_segments_bankside.shp")
    arcpy.SpatialJoin_analysis(confinement_margin_segments, channel_bank_polygons, confinement_margin_segments_bankside,
                               "JOIN_ONE_TO_ONE", "KEEP_ALL")
    # clean up fields
    cms_bs_fields = [f.name for f in arcpy.ListFields(confinement_margin_segments_bankside)]
    remove_fields = ["FID_confin", "Id", "InPolyFID", "SmoPgnFlag", "FID_VBET", "Id_1", "InPoly_F_1", "SmoPgnFl_1", "Id_12"]
    for f in remove_fields:
        if f in cms_bs_fields:
            try:
                arcpy.DeleteField_management(confinement_margin_segments_bankside, f)
            except Exception as err:
                pass
    cms_bs_lyr = arcpy.MakeFeatureLayer_management(confinement_margin_segments_bankside, "confinement_margins_segments_bankside_lyr")

    arcpy.SelectLayerByAttribute_management(cms_bs_lyr, "NEW_SELECTION", """ "BankSide" = 'LEFT'""")
    network_confinement_left = transfer_line(cms_bs_lyr, network_dissolve, "LEFT", temp_dir)

    arcpy.SelectLayerByAttribute_management(cms_bs_lyr, "NEW_SELECTION", """ "BankSide" = 'RIGHT'""")
    network_confinement_right = transfer_line(cms_bs_lyr, network_dissolve, "RIGHT", temp_dir)

    confinement_network_intersect = os.path.join(confinement_dir, "ConfinementNetworkIntersect.shp")
    arcpy.Intersect_analysis([network_confinement_left, network_confinement_right],
                             confinement_network_intersect, "NO_FID") # TODO no fid?

    #Re-split centerline by segments
    arcpy.AddMessage("Determining confinement state on stream network...")
    raw_confining_network_split = os.path.join(temp_dir, "raw_confining_network_split.shp")
    arcpy.SplitLineAtPoint_management(confinement_network_intersect,
                                      network_segment_points,
                                      raw_confining_network_split,
                                      "0.01 Meters")

    #Table and Attributes
    arcpy.AddField_management(raw_confining_network_split, "Con_Type", "TEXT", field_length="6")
    arcpy.AddField_management(raw_confining_network_split, "IsConfined", "SHORT")
    fields = [f.name for f in arcpy.ListFields(raw_confining_network_split)]
    if "IsConstric" in fields:
        arcpy.DeleteField_management(raw_confining_network_split, "IsConstric")
    arcpy.AddField_management(raw_confining_network_split, "IsConstric", "SHORT")

    raw_confining_network_lyr = arcpy.MakeFeatureLayer_management(raw_confining_network_split, "raw_confining_network_lyr")

    arcpy.SelectLayerByAttribute_management(raw_confining_network_lyr, "NEW_SELECTION", """ "Con_LEFT" = 1""")
    arcpy.CalculateField_management(raw_confining_network_lyr, "Con_Type", "'LEFT'", "PYTHON")
    arcpy.SelectLayerByAttribute_management(raw_confining_network_lyr, "NEW_SELECTION", """ "Con_RIGHT" = 1""")
    arcpy.CalculateField_management(raw_confining_network_lyr, "Con_Type", "'RIGHT'", "PYTHON")
    arcpy.SelectLayerByAttribute_management(raw_confining_network_lyr, "NEW_SELECTION", """ "Con_LEFT" = 1 AND "Con_RIGHT" = 1""")
    arcpy.CalculateField_management(raw_confining_network_lyr, "Con_Type", "'BOTH'", "PYTHON")
    arcpy.CalculateField_management(raw_confining_network_lyr, "IsConstric", "1", "PYTHON")
    arcpy.SelectLayerByAttribute_management(raw_confining_network_lyr, "SWITCH_SELECTION")
    arcpy.CalculateField_management(raw_confining_network_lyr, "IsConstric", "0", "PYTHON")
    arcpy.SelectLayerByAttribute_management(raw_confining_network_lyr, "NEW_SELECTION", """ "Con_LEFT" = 1 OR "Con_RIGHT" = 1""")
    arcpy.CalculateField_management(raw_confining_network_lyr, "IsConfined", "1", "PYTHON")
    arcpy.SelectLayerByAttribute_management(raw_confining_network_lyr, "SWITCH_SELECTION")
    arcpy.CalculateField_management(raw_confining_network_lyr, "IsConfined", "0", "PYTHON")
    arcpy.CalculateField_management(raw_confining_network_lyr, "Con_Type", "'NONE'", "PYTHON")

    """# Integrated Width
    # REMOVED FROM CODE BECAUSE:
    # 1. Integrated width has little meaning (valley and channel widths calculated as AREA/LENGTH, which is going to be largely biased by segment length
    # 2. Spatial join creates messy output and many missing values
    intersect_line_network = network
    if integrate_width_attributes:
        arcpy.AddMessage("Calculating integrated width attributes...")
        integrated_channel = os.path.join(confinement_dir, "integrated_channel_width.shp")
        arcpy.AddMessage("...Calculating channel integrated width")
        fieldIWChannel = integrated_width(network, channel_segment_polygons, integrated_channel, "Channel", temp_dir, confinement_dir, False)
        arcpy.AddMessage("...Calculating valley integrated_width")
        integrated_valley = os.path.join(confinement_dir, "integrated_valley_width.shp")
        fieldIWValley = integrated_width(integrated_channel, valley_bottom, integrated_valley, "Valley", temp_dir, confinement_dir, False)

        arcpy.AddMessage("...Calculating integrated width ratio")
        fields = [f.name for f in arcpy.ListFields(integrated_valley)]
        if "IW_Ratio" in fields:
            arcpy.DeleteField_management(integrated_valley, "IW_Ratio")
        arcpy.AddField_management(integrated_valley, "IW_Ratio", "DOUBLE")
        with arcpy.da.UpdateCursor(integrated_valley, ["IW_Ratio", fieldIWChannel, fieldIWValley]) as cursor:
            for row in cursor:
                if row[1] == 0 and row[2] == 0:
                    row[0] = 0
                elif row[1] == 0 and row[2] > 0:
                    row[0] = 1.0
                else:
                    row[0] = row[2] / row[1]
        intersect_line_network = integrated_valley

    # Final Output
    arcpy.AddMessage("Preparing final output...")
    if arcpy.Exists(raw_confinement):
        arcpy.Delete_management(raw_confinement)
    arcpy.Intersect_analysis([raw_confining_network_split, intersect_line_network], raw_confinement, "NO_FID")"""

    return


def build_folder_structure(output_folder):
    """ """
    intermediates_folder = os.path.join(output_folder, "01_Intermediates")
    make_folder(intermediates_folder)
    confinement_dir = os.path.join(intermediates_folder, find_available_num_prefix(intermediates_folder)+"_Confinement")
    make_folder(confinement_dir)
    analysis_folder = os.path.join(output_folder, "02_Analysis")
    make_folder(analysis_folder)
    temp_dir = os.path.join(os.path.dirname(os.path.dirname(output_folder)), "Temp")
    make_folder(temp_dir)
    return intermediates_folder, confinement_dir, analysis_folder, temp_dir


def determine_banks(network, channel_bank_polygons, temp_dir):
    """ """
    channel_bankside_buffer = os.path.join(temp_dir, "channel_bankside_buffer.shp")
    arcpy.Buffer_analysis(network, channel_bankside_buffer, "1 Meter", "LEFT", "FLAT", "NONE")
    channel_bankside_points = os.path.join(temp_dir, "channel_bankside_pts.shp")
    arcpy.FeatureToPoint_management(channel_bankside_buffer, channel_bankside_points, "INSIDE")
    arcpy.AddField_management(channel_bank_polygons, "BankSide", "TEXT", "10")
    channel_banks_lyr = arcpy.MakeFeatureLayer_management(channel_bank_polygons, "channel_banks_lyr")
    arcpy.SelectLayerByLocation_management(channel_banks_lyr, "INTERSECT", channel_bankside_points, selection_type="NEW_SELECTION")
    arcpy.CalculateField_management(channel_banks_lyr, "BankSide", "'LEFT'", "PYTHON")
    arcpy.SelectLayerByAttribute_management(channel_banks_lyr, "SWITCH_SELECTION")
    arcpy.CalculateField_management(channel_banks_lyr, "BankSide", "'RIGHT'", "PYTHON")
    return 


def transfer_line(in_line, join_line, side, temp_dir):
    """ """
    # Split Line Network by Line Ends 
    split_pts = os.path.join(temp_dir, "split_points_"+side+".shp")
    arcpy.FeatureVerticesToPoints_management(in_line, split_pts, "BOTH_ENDS")
    near_pts_confinement_tbl = os.path.join(temp_dir, "near_points_confinement_table_"+side+".dbf")
    arcpy.GenerateNearTable_analysis(split_pts, join_line, near_pts_confinement_tbl, location="LOCATION", angle="ANGLE")
    near_pts_confinement_lyr = arcpy.MakeXYEventLayer_management(near_pts_confinement_tbl, "NEAR_X", "NEAR_Y", "near_points_confinement_lyr_"+side, join_line)
    transfer_line = os.path.join(temp_dir, "transfer_line_"+side+".shp")
    arcpy.SplitLineAtPoint_management(join_line, near_pts_confinement_lyr, transfer_line, search_radius="0.01 Meters")
    
    # Prepare Fields
    confinement_field = "Con_" + side
    arcpy.AddField_management(transfer_line, confinement_field, "LONG")

    # Transfer Attributes by Centroids
    centroids = os.path.join(temp_dir, "confinement_points_"+side+".shp")
    arcpy.FeatureVerticesToPoints_management(in_line, centroids, "MID")
    near_centroids_tbl = os.path.join(temp_dir, "near_pts_centroid_tbl_"+side+".dbf")
    arcpy.GenerateNearTable_analysis(centroids, join_line, near_centroids_tbl, location="LOCATION", angle="ANGLE")
    near_centroids_lyr = arcpy.MakeXYEventLayer_management(near_centroids_tbl, "NEAR_X", "NEAR_Y", "near_pts_centroids_lyr_"+side, join_line)
    transfer_line_lyr = arcpy.MakeFeatureLayer_management(transfer_line, "transfer_line_lyr_"+side)
    
    arcpy.SelectLayerByLocation_management(transfer_line_lyr, "INTERSECT", near_centroids_lyr, selection_type="NEW_SELECTION")#"0.01 Meter","NEW_SELECTION")
    arcpy.CalculateField_management(transfer_line_lyr, confinement_field, 1, "PYTHON")
    
    return transfer_line


def integrated_width(in_lines, in_polygons, out_network, field_name, temp_dir, intermediates_folder, boolSegmentPolygon=False):
    """ """
    #arcpy.AddMessage("......Adding fields")
    fields = [f.name for f in arcpy.ListFields(in_lines)]
    if "IW_Length" in fields:
        arcpy.DeleteField_management(in_lines, "IW_Length")
    arcpy.AddField_management(in_lines,"IW_Length", "DOUBLE")
    arcpy.CalculateField_management(in_lines, "IW_Length", "!Shape!.length", "PYTHON")

    if boolSegmentPolygon:
        #arcpy.AddMessage("......Segmenting polygons")
        segmented_polygons = DividePolygonBySegment(in_lines, in_polygons, temp_dir, intermediates_folder, type="Valley")
    else:
        segmented_polygons = in_polygons

    #arcpy.AddMessage("......Calculating area field")
    poly_fields = [f.name for f in arcpy.ListFields(segmented_polygons)]
    area_field = field_name[0:6]+"Area"
    if area_field in fields:
        arcpy.DeleteField_management(segmented_polygons, area_field)
    arcpy.AddField_management(segmented_polygons, area_field, "DOUBLE")
    arcpy.CalculateField_management(segmented_polygons, area_field, "!Shape!.area", "PYTHON")

    f_mappings = arcpy.FieldMappings()
    f_mappings.addTable(in_lines)
    fmap_area = arcpy.FieldMap()
    fmap_area.addInputField(segmented_polygons, area_field)
    f_mappings.addFieldMap(fmap_area)

    #arcpy.AddMessage("......Spatial join")
    arcpy.SpatialJoin_analysis(in_lines, segmented_polygons, out_network, "JOIN_ONE_TO_ONE", "KEEP_ALL",
                               match_option="WITHIN")

    #arcpy.AddMessage("......Adding IW field")
    IW_field = "IW" + field_name[0:8]
    out_fields = [f.name for f in arcpy.ListFields(out_network)]
    if IW_field in out_fields:
        arcpy.DeleteField_management(out_network, IW_field)
    arcpy.AddField_management(out_network, IW_field, "DOUBLE")
    exp = "!" + area_field + r"! / !" + "IW_length" + "!"
    arcpy.CalculateField_management(out_network, IW_field, exp, "PYTHON_9.3")

    return IW_field


def DividePolygonBySegment(input_centerline, input_polygons, temp_dir, intermediates, type):#dblPointDensity=10.0, dblJunctionBuffer=120.00):
    """ Divides a channel or valley polygon by centerline segments """
    # find midpoints of centerline
    midpoints = os.path.join(temp_dir, "midpoints_"+type+".shp")
    arcpy.FeatureVerticesToPoints_management(input_centerline, midpoints, "MID")
    midpoints_lyr = arcpy.MakeFeatureLayer_management(midpoints, "midpoints_lyr")

    # create thiessen polygons surrounding reach midpoints
    thiessen = os.path.join(temp_dir, "midpoints_thiessen_"+type+".shp")
    arcpy.CreateThiessenPolygons_analysis(midpoints, thiessen, "ALL")

    # clip thiessen polygons to input polygons
    thiessen_clip = os.path.join(intermediates, "thiessen_clip_"+type+".shp")
    arcpy.Clip_analysis(thiessen, input_polygons, thiessen_clip)

    return thiessen_clip

##""" Original DividePolygonBySegment from ConfinementToolbox - seems overly complicated and was throwing errors so rewrote as above
##        Author: Kelly Whitehead (kelly@southforkresearch.org) South Fork Research Inc., Seattle, WA
##        Created: 2015-Jan-08
##        Modified: 2015-Apr-27
##        Copyright (c) Kelly Whitehead 2015
##    
##    arcpy.env.OutputMFlag = "Disabled"
##    arcpy.env.OutputZFlag = "Disabled"
##    arcpy.env.overwriteOutput = True
##    
##    arcpy.AddMessage(".........Building thiessen polygons")
##    ## Build Thiessen Polygons
##    arcpy.env.extent = input_polygons ## Set full extent to build Thiessan polygons over entire line network.
##    arcpy.Densify_edit(input_centerline, "DISTANCE", str(dblPointDensity) + " METERS")
##    
##    trib_junction_pts =  os.path.join(temp_dir, "dps_trib_junction_pts.shp")
##    arcpy.Intersect_analysis(input_centerline, trib_junction_pts, output_type="POINT")
##    thiessen_points = os.path.join(temp_dir, "dps_thiessen_points.shp")
##    arcpy.FeatureVerticesToPoints_management(input_centerline, thiessen_points, "ALL")
##
##    thiessen_pts_lyr = arcpy.MakeFeatureLayer_management(thiessen_points, "thiessen_pts_lyr")
##    arcpy.SelectLayerByLocation_management(thiessen_pts_lyr, "INTERSECT", trib_junction_pts, str(dblJunctionBuffer)+ " METERS", "NEW_SELECTION")
##
##    thiessen_polygons = os.path.join(temp_dir, "dps_thiessen_polygons.shp")
##    arcpy.CreateThiessenPolygons_analysis(thiessen_pts_lyr, thiessen_polygons, "ONLY_FID")
##
##    thiessen_poly_clip = check_file(os.path.join(temp_dir, "dps_thiessen_poly_clip.shp"))
##    arcpy.Clip_analysis(thiessen_polygons, input_polygons, thiessen_poly_clip)
##
##    arcpy.AddMessage("..........Splitting junction thiessen polygons")
##    ### Code to Split the Junction Thiessen Polys ###
##    trib_thiessen_poly_lyr = arcpy.MakeFeatureLayer_management(thiessen_poly_clip, "trib_thiessen_polygons_lyr")
##    arcpy.SelectLayerByLocation_management(trib_thiessen_poly_lyr, "INTERSECT", trib_junction_pts, selection_type="NEW_SELECTION")
##
##    split_points = os.path.join(temp_dir, "dps_split_points.shp")
##    arcpy.Intersect_analysis([trib_thiessen_poly_lyr, input_centerline], split_points, output_type="POINT")
##
##    arcpy.AddMessage(".........Moving starting vertices")
##    # Moving Starting Vertices of Junction Polygons
##    changeStartingVertex(trib_junction_pts, trib_thiessen_poly_lyr)
##
##    trib_thiessen_poly_edges = os.path.join(temp_dir, "dps_trib_thiessen_edges.shp")
##    arcpy.FeatureToLine_management(trib_thiessen_poly_lyr, trib_thiessen_poly_edges)
##
##    split_lines = os.path.join(temp_dir, "dps_split_lines.shp")
##    arcpy.SplitLineAtPoint_management(trib_thiessen_poly_edges, split_points, split_lines, "0.1 METERS")
##
##    midpoints = os.path.join(temp_dir, "dps_midpoints.shp")
##    arcpy.FeatureVerticesToPoints_management(split_lines, midpoints, "MID")
##    arcpy.Near_analysis(midpoints, trib_junction_pts, location="LOCATION")
##    arcpy.AddXY_management(midpoints)
##
##    trib_midlines = os.path.join(temp_dir, "dps_trib_to_midlines.shp")
##    arcpy.XYToLine_management(midpoints, trib_midlines, "POINT_X", "POINT_Y", "NEAR_X", "NEAR_Y")
##
##    ### Select Polygons by Centerline ###
##    arcpy.AddMessage(".........GNAT DPS: Select Polygons By Centerline")
##    arcpy.SelectLayerByLocation_management(thiessen_poly_clip, "INTERSECT", input_centerline, selection_type='NEW_SELECTION')
##
##    thiessen_edges = os.path.join(temp_dir, "dps_thiessen_edges.shp")
##    arcpy.FeatureToLine_management(thiessen_poly_clip, thiessen_edges)
##
##    all_edges = os.path.join(temp_dir, "dps_all_edges.shp")
##    arcpy.Merge_management([trib_midlines, thiessen_edges, input_centerline], all_edges)# include fcCenterline if needed
##
##    all_edges_polygons = os.path.join(temp_dir, "dps_all_edges_polygons.shp")
##    arcpy.FeatureToPolygon_management(all_edges, all_edges_polygons)
##
##    all_edges_poly_clip = os.path.join(temp_dir, "dps_all_edges_poly_clip.shp")
##    arcpy.Clip_analysis(all_edges_polygons, input_polygons, all_edges_poly_clip)
##
##    arcpy.AddMessage("..........Spatial join centerline to all edges clip")
##    polygons_centerline_join = os.path.join(temp_dir, "dps_polygons_centerline_join.shp")
##    arcpy.SpatialJoin_analysis(all_edges_poly_clip, input_centerline, polygons_centerline_join, "JOIN_ONE_TO_MANY",
##                               "KEEP_ALL", match_option="SHARE_A_LINE_SEGMENT_WITH")
##
##    poly_dissolve = os.path.join(temp_dir, "dps_polygon_join_dissolve.shp")
##    arcpy.Dissolve_management(polygons_centerline_join, polygon_dissolve, "JOIN_FID", multi_part="SINGLE_PART")
##
##    poly_dissolve_lyr = arcpy.MakeFeatureLayer_management(poly_dissolve, "polygon_join_dissolved_lyr")
##    arcpy.SelectLayerByAttribute_management(poly_dissolve_lyr, "NEW_SELECTION", """ "JOIN_FID" = -1 """)
##
##    arcpy.Eliminate_management(poly_dissolve_lyr, segmented_polygons, "LENGTH")
##
##    return
##"""


def changeStartingVertex(input_points, input_polygons):
    """ """
    ## Create Geometry Object for Processing input points.
    g = arcpy.Geometry()
    geomPoints = arcpy.CopyFeatures_management(input_points, g)

    listPointCoords = []
    for point in geomPoints:
        listPointCoords.append([point.centroid.X,point.centroid.Y])
        #arcpy.AddMessage(str(point.centroid.X) + ","+ str(point.centroid.Y))

    with arcpy.da.UpdateCursor(input_polygons, ["OID@", "SHAPE@"]) as ucPolygons:
        for featPolygon in ucPolygons:
            vertexList = []
            #arcpy.AddMessage("Feature: " + str(featPolygon[0]))
            i = 0
            iStart = 0
            for polygonVertex in featPolygon[1].getPart(0): # shape,firstpart
                if polygonVertex:
                    #arcpy.AddMessage(' Vertex:' + str(i))
                    vertexList.append([polygonVertex.X,polygonVertex.Y])
                    if [polygonVertex.X,polygonVertex.Y] in listPointCoords:
                        #arcpy.AddMessage("  Point-Vertex Match!")
                        iStart = i
                    else:
                        pass
                        #arcpy.AddMessage("  No Match")
                i = i + 1
            if iStart == 0:
                newVertexList = vertexList
                #arcpy.AddMessage("No Change for: " + str(featPolygon[0]))
            else:
                #arcpy.AddMessage("Changing Vertex List for: " + str(featPolygon[0]))
                newVertexList = vertexList[iStart:i]+vertexList[0:iStart]
                for v in newVertexList:
                    arcpy.AddMessage(str(v[0]) + "," +str(v[1]))
                #listVertexPointObjects = []
                newShapeArray = arcpy.Array()
                for newVertex in newVertexList:
                    #arcpy.AddMessage("Changing Vertex: " + str(newVertex[0]) + ',' + str(newVertex[1]))
                    newShapeArray.add(arcpy.Point(newVertex[0],newVertex[1]))
                    #listVertexPointObjects.append(arcpy.Point(newVertex[0],newVertex[1]))
                #newShapeArray = arcpy.Array(listVertexPointObjects)
                newPolygonArray = arcpy.Polygon(newShapeArray)

                ucPolygons.updateRow([featPolygon[0],newPolygonArray])

    return


if __name__ == "__main__":

    main(sys.argv[1],
         sys.argv[2],
         sys.argv[3],
         sys.argv[4],
         sys.argv[5],
         sys.argv[6],
         sys.argv[7])
