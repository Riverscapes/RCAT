# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
# Name:        Confinement Index Tool                                         #
# Purpose:     Calculates Index of Valley Confinement Along a Stream Network  #
#                                                                             #
# Author:      Maggie Hallerud                                                #
#              maggie.hallerud@aggiemail.usu.edu                              #
#                                                                             #
# Created:     2020-Mar-26                                                    #
#                                                                             #
# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #

# load dependencies
import os
import arcpy
import glob
from SupportingFunctions import make_folder, find_available_num_prefix, make_layer
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

    # find and make thiessen polygons
    arcpy.AddMessage("Creating thiessen polygons...")
    # pull thiessen polygon filenames from intermediates folder
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
    thiessen_bankfull = os.path.join(confinement_dir, "Conf_Thiessen_Bankfull.shp")
    arcpy.Clip_analysis(thiessen_polygons, bankfull_channel, thiessen_bankfull)

    # clip thiessen polygons to valley bottom  (different than RVD thiessen valley because that one's buffered)
    thiessen_valley = os.path.join(confinement_dir, "Conf_Thiessen_Valley.shp")
    arcpy.Clip_analysis(thiessen_polygons, valley_bottom, thiessen_valley)

    # calculate area for bankfull thiessen polygons and join to network
    arcpy.AddMessage("Calculating bankfull area per reach...")
    calculate_polygon_area(thiessen_bankfull, out_lyr, "BFC")
    # calculate area for valley thiessen polygons and join to network
    arcpy.AddMessage("Calculating valley area per reach...")
    calculate_polygon_area(thiessen_valley, out_lyr, "VAL")

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

    # make layers
    arcpy.AddMessage("Making layers...")
    make_layers(output_network, thiessen_bankfull, thiessen_valley)


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


def calculate_polygon_area(polygons, network, type):
    arcpy.AddField_management(polygons, "AREA", "DOUBLE")
    with arcpy.da.UpdateCursor(polygons, ["AREA", "SHAPE@AREA"]) as cursor:
        for row in cursor:
            row[0] = row[1]
            cursor.updateRow(row)
    arcpy.JoinField_management(network, "FID", polygons, "RCH_FID", "AREA")
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
    

def make_layers(output_network, thiessen_bankfull, thiessen_valley):
    source_code_folder = os.path.dirname(os.path.abspath(__file__))
    symbology_folder = os.path.join(source_code_folder, "RCATSymbology")
    # pull symbology
    confinement_ratio_symbology = os.path.join(symbology_folder, "ConfinementRatio.lyr")
    valley_symbology = os.path.join(symbology_folder, "BankfullChannelWidthPolygons.lyr")
    bankfull_symbology = os.path.join(symbology_folder, "ValleyBottomWidthPolygons.lyr")
    # make layers
    make_layer(os.path.dirname(output_network), output_network, "Confinement_Ratio", confinement_ratio_symbology, symbology_field="CONF_RATIO")
    make_layer(os.path.dirname(thiessen_bankfull), thiessen_bankfull, "Bankfull Channel Width Polygons", bankfull_symbology)
    make_layer(os.path.dirname(thiessen_valley), thiessen_valley, "Valley Bottom Width Polygons", valley_symbology)


if __name__ == "__main__":
    main(sys.argv[1],
         sys.argv[2],
         sys.argv[3],
         sys.argv[4],
         sys.argv[5])
