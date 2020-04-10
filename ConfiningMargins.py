# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
# Name:        Confinement Index Tool                                         #
# Purpose:     Calculates Index of Valley Confinement Along a Stream Network  #
#                                                                             #
# Author:      Maggie Hallerud                                                #
#              maggie.hallerud@aggiemail.usu.edu                              #
#                                                                             #
# Created:     2020-Mar-26                                                    #                                                       #
#                                                                             #
# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #

# load dependencies
import os
import arcpy
import glob
from SupportingFunctions import make_folder, find_available_num_prefix
arcpy.env.overwriteOutput=True
         
def main(network,
         valley_bottom,
         bankfull_channel,
         output_folder,
         output_name):
    """Calculates an index of confinement by dividing bankfull channel width by valley bottom width for each reach
    :param network: Segmented stream network from RVD output
    :param valley_bottom: Valley bottom shapefile
    :param bankfull_channel: Bankfull channel polygon shapefile
    :param output_folder: Folder for RCAT run with format "Output_**"
    :param output_name: Name for output network with confinement fields
    return: Output network with confinement fields
    """
    # set environment parameters
    arcpy.env.overwriteOutput = True
    arcpy.env.outputZFlag = "Disabled"
    arcpy.env.workspace = 'in_memory'

    # set up folder structure
    intermediates_folder, confinement_dir, analysis_folder, temp_dir = build_folder_structure(output_folder)

    # copy input network to output lyr before editing
    out_lyr = arcpy.MakeFeatureLayer_management(network)

    # segment valley and bankfull polygons
    arcpy.AddMessage("Segmenting bankfull channel polygons by network...")
    bankfull_seg_polygons = os.path.join(confinement_dir, "Segmented_Bankfull_Channel.shp")
    divide_polygon_by_segmented_network(network, bankfull_channel, bankfull_seg_polygons, temp_dir, intermediates_folder, "BFC")
    arcpy.AddMessage("Segmenting valley bottom polygons by network...")
    valley_seg_polygons = os.path.join(confinement_dir, "Segmented_Valley_Bottom.shp")
    divide_polygon_by_segmented_network(network, valley_bottom, bankfull_seg_polygons, temp_dir, intermediates_folder, "VB")
    

    # calculate area for bankfull thiessen polygons and join to network
    arcpy.AddMessage("Calculating bankfull area per reach...")
    calculate_polygon_area(bankfull_seg_polygons, out_lyr, "BFC")
    # calculate area for valley thiessen polygons and join to network
    arcpy.AddMessage("Calculating valley area per reach...")
    calculate_polygon_area(valley_seg_polygons, out_lyr, "VAL")

    arcpy.AddMessage("Calculating bankfull and valley width per reach...")
    # calculate reach length
    arcpy.AddField_management(out_lyr, "Rch_Len", "DOUBLE")
    with arcpy.da.UpdateCursor(out_lyr, ["Rch_Len", "SHAPE@LENGTH"]) as cursor:
        for row in cursor:
            row[0] = row[1]
            cursor.updateRow(row)
    
    # calculate bankfull channel and valley bottom widths for each reach by dividing thiessen polygon area by reach length
    arcpy.AddField_management(out_lyr, "BFC_Width", "DOUBLE")
    arcpy.AddField_management(out_lyr, "VAL_Width", "DOUBLE")
    with arcpy.da.UpdateCursor(out_lyr, ["Rch_Len", "VAL_Area", "VAL_Width", "BFC_Area", "BFC_Width"]) as cursor:
        for row in cursor:
            row[2] = row[1] / row[0]
            row[4] = row[3] / row[0]
            cursor.updateRow(row)

    arcpy.AddMessage("Calculating confinement...")
    # calculate confinement ratio for each reach (bankfull width / valley width)
    arcpy.AddField_management(out_lyr, "CONF_RATIO", "DOUBLE")
    with arcpy.da.UpdateCursor(out_lyr, ["VAL_Width", "BFC_Width", "CONF_RATIO"]) as cursor:
        for row in cursor:
            if row[0] == 0:
                row[2] = -9999
            else:
                row[2] = row[1] / row[0]
            cursor.updateRow(row)

    # set confinement categories based on confinement ratio
    #arcpy.AddField_management(out_lyr, "CONFINEMNT", "TEXT")
    #with arcpy.da.UpdateCursor(out_lyr, ["CONF_RATIO", "CONFINEMENT"]) as cursor:
    #    for row in cursor:
    #        if row[0] > 0.5:
    #            row[1] = "confined"
    #        else:
    #            row[1] = "not confined"

    arcpy.AddMessage("Saving final output...")
    # save final output
    if not output_name.endswith(".shp"):
        output_network = os.path.join(analysis_folder, output_name + ".shp")
    else:
        output_network = os.path.join(analysis_folder, output_name)
    arcpy.CopyFeatures_management(out_lyr, output_network)


def build_folder_structure(output_folder):
    """ """
    intermediates_folder = os.path.join(output_folder, "01_Intermediates")
    make_folder(intermediates_folder)
    confinement_dir = os.path.join(intermediates_folder, find_available_num_prefix(intermediates_folder)+"_Confinement")
    make_folder(confinement_dir)
    analysis_folder = os.path.join(output_folder, "02_Analyses")
    make_folder(analysis_folder)
    conf_analysis_folder = os.path.join(analysis_folder, find_available_num_prefix(analysis_folder)+"_Confinement")
    make_folder(conf_analysis_folder)
    temp_dir = os.path.join(os.path.dirname(os.path.dirname(output_folder)), "Temp")
    make_folder(temp_dir)
    return intermediates_folder, confinement_dir, conf_analysis_folder, temp_dir


def divide_polygon_by_segmented_network(segmented_network, polygons, out_polygons, temp_dir, intermediates_dir, polygon_type):
    """Author: Kelly Whitehead (kelly@southforkresearch.org) South Fork Research Inc., Seattle, WA
    Created: 2015-Jan-08
    Modified: 2015-Apr-27
    Copyright (c) Kelly Whitehead 2015"""
    # set up environment
    #arcpy.env.OutputMFlag = "Disabled"
    arcpy.env.OutputZFlag = "Disabled"
    arcpy.env.overwriteOutput = True

    trib_thiessen_edges = os.path.join(temp_dir, "dps_trib_thiessen_edges_"+polygon_type+".shp")
    densified_network = os.path.join(temp_dir, "dps_dens_network_"+polygon_type+".shp")
    if not os.path.exists(trib_thiessen_edges):
        print ".........Building thiessen polygons"
        arcpy.AddMessage(".........Building thiessen polygons")
        ## Build Thiessen Polygons
        arcpy.env.extent = polygons ## Set full extent to build Thiessan polygons over entire line network.
        densified_network = os.path.join(temp_dir, "dps_dens_network_"+polygon_type+".shp")
        arcpy.CopyFeatures_management(segmented_network, densified_network)
        arcpy.Densify_edit(densified_network, "DISTANCE", "20.0 METERS")
        
        trib_junction_pts =  os.path.join(temp_dir, "dps_trib_junction_pts_"+polygon_type+".shp")
        arcpy.Intersect_analysis(densified_network, trib_junction_pts, output_type="POINT")
        thiessen_points = os.path.join(temp_dir, "dps_thiessen_points_"+polygon_type+".shp")
        arcpy.FeatureVerticesToPoints_management(densified_network, thiessen_points, "ALL")

        thiessen_pts_lyr = arcpy.MakeFeatureLayer_management(thiessen_points, "thiessen_pts_lyr_"+polygon_type)
        arcpy.SelectLayerByLocation_management(thiessen_pts_lyr, "INTERSECT", trib_junction_pts, "120.0 METERS", "NEW_SELECTION")

        thiessen_polygons = os.path.join(temp_dir, "dps_thiessen_polygons_"+polygon_type+".shp")
        arcpy.CreateThiessenPolygons_analysis(thiessen_pts_lyr, thiessen_polygons, "ONLY_FID")

        thiessen_poly_clip = os.path.join(temp_dir, "dps_thiessen_poly_clip_"+polygon_type+".shp")
        arcpy.Clip_analysis(thiessen_polygons, polygons, thiessen_poly_clip)

        print ".........Splitting thiessen polygons at trib junctions"
        arcpy.AddMessage(".........Splitting thiessen polygons at trib junctions")
        # Code to Split the Junction Thiessen Polys
        trib_thiessen_poly_lyr = arcpy.MakeFeatureLayer_management(thiessen_poly_clip, "trib_thiessen_polygons_lyr")
        arcpy.SelectLayerByLocation_management(trib_thiessen_poly_lyr, "INTERSECT", trib_junction_pts, selection_type="NEW_SELECTION")

        split_points = os.path.join(temp_dir, "dps_split_points_"+polygon_type+".shp")
        arcpy.Intersect_analysis([trib_thiessen_poly_lyr, densified_network], split_points, output_type="POINT")

        print ".........Finding midlines of tributaries"
        arcpy.AddMessage(".........Finding midlines of tributaries")
        # Moving Starting Vertices of Junction Polygons
        changeStartingVertex(trib_junction_pts, trib_thiessen_poly_lyr)

        trib_thiessen_poly_edges = os.path.join(temp_dir, "dps_trib_thiessen_edges_"+polygon_type+".shp")
        arcpy.FeatureToLine_management(trib_thiessen_poly_lyr, trib_thiessen_poly_edges)

        split_lines = os.path.join(temp_dir, "dps_split_lines_"+polygon_type+".shp")
        arcpy.SplitLineAtPoint_management(trib_thiessen_poly_edges, split_points, split_lines, "0.1 METERS")

        midpoints = os.path.join(temp_dir, "dps_midpoints_"+polygon_type+".shp")
        arcpy.FeatureVerticesToPoints_management(split_lines, midpoints, "MID")
        arcpy.Near_analysis(midpoints, trib_junction_pts, location="LOCATION")
        arcpy.AddXY_management(midpoints)

        trib_midlines = os.path.join(temp_dir, "dps_trib_to_midlines_"+polygon_type+".shp")
        arcpy.XYToLine_management(midpoints, trib_midlines, "POINT_X", "POINT_Y", "NEAR_X", "NEAR_Y")

        ### Select Polygons by Centerline ###
        print ".........Selecting thiessen polygons by network"
        arcpy.AddMessage(".........Selecting thiessen polygons by network")
        thiessen_poly_clip_lyr = arcpy.MakeFeatureLayer_management(thiessen_poly_clip, "trib_thiessen_poly_clip_lyr_"+polygon_type)
        arcpy.SelectLayerByLocation_management(thiessen_poly_clip_lyr, "INTERSECT", segmented_network, selection_type='NEW_SELECTION')

        thiessen_edges = os.path.join(temp_dir, "dps_thiessen_edges_"+polygon_type+".shp")
        arcpy.FeatureToLine_management(thiessen_poly_clip_lyr, thiessen_edges)

    print ".........Merging thiessen and tributary edges with segmented network"
    arcpy.AddMessage(".........Merging thiessen and tributary edges with segmented network")
    thiessen_edges = os.path.join(temp_dir, "dps_thiessen_edges_"+polygon_type+".shp")
    trib_midlines = os.path.join(temp_dir, "dps_trib_to_midlines_"+polygon_type+".shp")
    trib_thiessen_edges = os.path.join(temp_dir, "dps_trib_thiessen_edges_"+polygon_type+".shp")
    arcpy.Merge_management([trib_midlines, thiessen_edges], trib_thiessen_edges)
    all_edges = os.path.join(temp_dir, "dps_all_edges_"+polygon_type+".shp")
    arcpy.Merge_management([trib_thiessen_edges, densified_network], all_edges)

    print ".........Creating polygons from merged edges"
    arcpy.AddMessage(".........Creating polygons from merged edges")
    all_edges_polygons = os.path.join(temp_dir, "dps_all_edges_polygons_"+polygon_type+".shp")
    arcpy.FeatureToPolygon_management(all_edges, all_edges_polygons)

    all_edges_poly_clip = os.path.join(temp_dir, "dps_all_edges_poly_clip_"+polygon_type+".shp")
    arcpy.Clip_analysis(all_edges_polygons, polygons, all_edges_poly_clip)

    print "..........Spatially joining all edges to input network"
    arcpy.AddMessage(".........Spatially joining all edges to input network")
    polygons_centerline_join = os.path.join(temp_dir, "dps_polygons_centerline_join_"+polygon_type+".shp")
    arcpy.SpatialJoin_analysis(all_edges_poly_clip, densified_network, polygons_centerline_join, "JOIN_ONE_TO_MANY",
                               "KEEP_ALL", match_option="SHARE_A_LINE_SEGMENT_WITH")

    print ".........Dissolving polygons for each segment"
    arcpy.AddMessage(".........Dissolving polygons for each segment")
    poly_dissolve = os.path.join(temp_dir, "dps_polygon_join_dissolve_"+polygon_type+".shp")
    arcpy.Dissolve_management(polygons_centerline_join, poly_dissolve, "JOIN_FID", multi_part="SINGLE_PART")

    poly_dissolve_lyr = arcpy.MakeFeatureLayer_management(poly_dissolve, "polygon_join_dissolved_lyr_"+polygon_type)
    arcpy.SelectLayerByAttribute_management(poly_dissolve_lyr, "NEW_SELECTION", """ "JOIN_FID" = -1 """)

    print ".........Creating final divided polygons"
    arcpy.AddMessage(".........Creating final divided polygons")
    arcpy.Eliminate_management(poly_dissolve_lyr, out_polygons, "LENGTH")


def changeStartingVertex(input_points, input_polygons):
    # set up environment
    #arcpy.env.OutputMFlag = "Disabled"
    arcpy.env.outputZFlag = "Disabled"
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


def calculate_polygon_area(polygons, network, type):
    arcpy.AddField_management(polygons, "AREA", "DOUBLE")
    with arcpy.da.UpdateCursor(polygons, ["AREA", "SHAPE@AREA"]) as cursor:
        for row in cursor:
            row[0] = row[1]
            cursor.updateRow(row)
    arcpy.JoinField_management(network, "FID", polygons, "JOIN_FID", "AREA")
    area_field = type+"_Area"
    arcpy.AddField_management(network, area_field, "DOUBLE")
    with arcpy.da.UpdateCursor(network, ["AREA", area_field]) as cursor:
        for row in cursor:
            row[1] = row[0]
            cursor.updateRow(row)
    arcpy.DeleteField_management(network, "AREA")


def create_clipped_thiessen_polygons(intermediates_folder, bankfull_channel, valley, temp_dir):
    # find midpoints of all reaches in segmented network
    seg_network_lyr = "seg_network_lyr"
    arcpy.MakeFeatureLayer_management(seg_network, seg_network_lyr)
    midpoints = scratch + "/midpoints.shp"
    arcpy.FeatureVerticesToPoints_management(seg_network, midpoints, "MID")

    # check for thiessen polygons
    thiessen_polygon_files = glob.glob(os.path.join(intermediates_folder, "*_MidpointsThiessen/midpoints_thiessen.shp"))
    # if no thiessen polygon files found, create new thiessen polygons
    if len(thiessen_polygon_files) == 0:
        thiessen_polygons = create_thiessen_polygons(network, intermediates_folder, temp_dir)
    # if thiessen polygon files found, use last file created
    else:
        thiessen_polygons = thiessen_polygon_files[-1] 

    # add RCH_FID field to thiessen polygons
    thiessen_fields = [f.name for f in arcpy.ListFields(thiessen_polygons)]
    if "RCH_FID" not in thiessen_fields:
        arcpy.AddField_management(thiessen_polygons, "RCH_FID")
    with arcpy.da.UpdateCursor(thiessen_polygons, ["ORIG_FID", "RCH_FID"]) as cursor:
        for row in cursor:
            row[1] = row[0]
            cursor.updateRow(row)

    # clip thiessen polygons to bankfull channel
    thiessen_bankfull_multi = os.path.join(temp_dir, "Conf_Thiessen_Bankfull_Multipart.shp")
    arcpy.Clip_analysis(thiessen_polygons, bankfull_channel, thiessen_bankfull_multi)
    thiessen_bankfull = os.path.join(confinement_dir, "Conf_Thiessen_Bankfull.shp")
    thiessen_bankfull_single = os.path.join(temp_dir, "Conf_Thiessen_Bankfull_Singlepart.shp")
    select_polygons_on_network(thiessen_bankfull_multi, midpoints, thiessen_bankfull_single, thiessen_bankfull, temp_dir)    

    # clip thiessen polygons to valley bottom  (different than RVD thiessen valley because that one's buffered)
    thiessen_valley_multi = os.path.join(temp_dir, "Conf_Thiessen_Valley_Multipart.shp")
    arcpy.Clip_analysis(thiessen_polygons, valley_bottom, thiessen_valley_multi)
    thiessen_valley = os.path.join(confinement_dir, "Conf_Thiessen_Valley.shp")
    thiessen_valley_single = os.path.join(temp_dir, "Conf_Thiessen_Valley_Singlepart.shp")
    select_polygons_on_network(thiessen_valley_multi, midpoints, thiessen_valley_single, thiessen_valley, temp_dir)

    return thiessen_valley, thiessen_bankfull

    
def create_thiessen_polygons(seg_network, midpoints, intermediates_folder, scratch):
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
    thiessen_multipart = scratch + "/Midpoints_Thiessen_Multipart.shp"
    arcpy.CreateThiessenPolygons_analysis(midpoints, thiessen, "ALL")

    # convert multipart features to single part
    arcpy.AddField_management(thiessen_multipart, "RCH_FID", "SHORT")
    with arcpy.da.UpdateCursor(thiessen_multipart, ["ORIG_FID", "RCH_FID"]) as cursor:
        for row in cursor:
            row[1] = row[0]
            cursor.updateRow(row)
    thiessen_singlepart = scratch + "/Thiessen_Singlepart.shp"
    arcpy.MultipartToSinglepart_management(thiessen_multipart, thiessen_singlepart)

    # Select only polygon features that intersect network midpoints
    thiessen_singlepart_lyr = arcpy.MakeFeatureLayer_management(in_features=thiessen_singlepart)
    midpoints_lyr = arcpy.MakeFeatureLayer_management(in_features=midpoints)
    thiessen_select = arcpy.SelectLayerByLocation_management(thiessen_singlepart_lyr, "INTERSECT", midpoints_lyr,
                                                             selection_type="NEW_SELECTION")

    # save new thiessen polygons in intermediates
    thiessen_folder = os.path.join(intermediates_folder, find_available_num_prefix(intermediates_folder)+"_MidpointsThiessen")
    make_folder(thiessen_folder)
    thiessen_polygons = thiessen_folder + "/Midpoints_Thiessen.shp"
    thiessen_singlepart = scratch + "/Thiessen_Singlepart.shp"
    select_polygons_on_network(thiessen_multipart, midpoints, thiessen_singlepart, thiessen_polygons, scratch)
    
    return thiessen_polygons


def select_polygons_on_network(thiessen_multipart, midpoints, thiessen_singlepart, thiessen_output, scratch):
    # convert multipart features to single part
    arcpy.AddField_management(thiessen_multipart, "RCH_FID", "SHORT")
    with arcpy.da.UpdateCursor(thiessen_multipart, ["ORIG_FID", "RCH_FID"]) as cursor:
        for row in cursor:
            row[1] = row[0]
            cursor.updateRow(row)
    arcpy.MultipartToSinglepart_management(thiessen_multipart, thiessen_singlepart)
    # Select only polygon features that intersect network midpoints
    thiessen_singlepart_lyr = arcpy.MakeFeatureLayer_management(in_features=thiessen_singlepart)
    midpoints_lyr = arcpy.MakeFeatureLayer_management(in_features=midpoints)
    thiessen_select = arcpy.SelectLayerByLocation_management(thiessen_singlepart_lyr, "INTERSECT", midpoints_lyr,
                                                             selection_type="NEW_SELECTION")
    # save new thiessen polygons in intermediates
    arcpy.CopyFeatures_management(thiessen_select, thiessen_output)
    

if __name__ == "__main__":
    main(sys.argv[1],
         sys.argv[2],
         sys.argv[3],
         sys.argv[4],
         sys.argv[5])
