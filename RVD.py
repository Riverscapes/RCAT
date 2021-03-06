
# --------------------------------------------------------------------------------------------------------------------------
# Name:        RVD
# Purpose:     Uses LANDFIRE inputs to assign a riparian condition score to
#              a segmented stream network based on a comparison between the
#              biophysical settings LANDFIRE layer and the existing vegetation
#              type LANDFIRE layer
#
# Author:      Jordan Gilbert
#
# Created:     10/15/2015
# Updated:      07/25/2017
# Copyright:   (c) Jordan Gilbert 2017
# Latest Update: 02/27/2020  -   Maggie Hallerud   -  maggie.hallerud@aggiemail.usu.edu
# License:     This work is licensed under the Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International
#              License. To view a copy of this license, visit http://creativecommons.org/licenses/by-nc-sa/4.0/.
# --------------------------------------------------------------------------------------------------------------------------

import arcpy
from arcpy.sa import *
import os
import sys
import numpy as np
import projectxml
import uuid
import datetime
import shutil
from SupportingFunctions import  find_available_num_prefix, make_layer


def main(
    projName,
    hucID,
    hucName,
    projPath,
    ex_veg,
    hist_veg,
    seg_network,
    valley,
    lg_river,
    dredge_tailings,
    outName):
    """ Calculates riparian vegetation departure for a stream network
    :param projName: Project name for XML metadata
    :param hucID: Huc ID for XML metadata
    :param hucName: Huc name for XML metadata
    :param projPath: RCAT project folder
    :param ex_veg: Existing vegetation raster
    :param hist_veg: Historic vegetation raster
    :param seg_network: Segmented network shapefile
    :param valley: Valley bottom shapefile
    :param lg_river: Large rivers polygon shapefile (optional)
    :param dredge_tailings: Dredge tailings polygon shapefile (optional)
    :param outName: Name for output network
    return: Output network with RVD fields
    """
    # make clean temporary directory
    scratch = projPath + '/Temp'
    if os.path.exists(scratch):
        shutil.rmtree(scratch)
    os.mkdir(scratch)

    # set up arcpy environment
    arcpy.env.overwriteOutput = True
    arcpy.env.workspace = 'in_memory'
    arcpy.CheckOutExtension("spatial")

    # check inputs
    arcpy.AddMessage("Validating inputs...")
    validate_inputs(ex_veg, hist_veg, seg_network, valley, lg_river, dredge_tailings)

    # create clean outputs and intermediates folders
    arcpy.AddMessage("Building output folder structure...")
    intermediates_folder, analysis_folder, tempOut = build_output_folder(projPath, seg_network)

    # create thiessen polygons and clip to fragmented valley bottom
    arcpy.AddMessage("Creating thiessen polygons...")
    thiessen_valley, valley_buf = create_thiessen_polygons_in_valley(seg_network, valley, intermediates_folder, scratch)
    # create lookup tables for existing and historic veg scores
    # create folder structure
    arcpy.AddMessage("Creating vegetation lookup rasters...")
    veg_rasters_folder = os.path.join(intermediates_folder, "03_VegetationRasters")
    ex_veg_lookup_folder = os.path.join(veg_rasters_folder, "01_Ex_Veg")
    hist_veg_lookup_folder = os.path.join(veg_rasters_folder, "02_Hist_Veg")
    folders = [veg_rasters_folder, ex_veg_lookup_folder, hist_veg_lookup_folder]
    for f in folders:
        make_folder(f)
    # make lookup rasters
    ex_riparian, ex_native = make_veg_lookup_rasters(ex_veg, ex_veg_lookup_folder, type="ex_veg")
    hist_riparian, hist_native = make_veg_lookup_rasters(hist_veg, hist_veg_lookup_folder, type="hist_veg")
        
    # reclassify areas within dredge tailings polygons
    if dredge_tailings is not None:
        arcpy.AddMessage("Reclassifying vegetation within dredge tailings...")
        ex_riparian, ex_native = vegetation_adjustment(dredge_tailings, ex_veg, ex_riparian, ex_native, thiessen_valley, scratch, ex_veg_lookup_folder, "Ex", "DrgTailngs")

    # reclassify areas within the large river polygon
    if lg_river is not None:
        arcpy.AddMessage("Reclassifying vegetation within large river polygons...")
        ex_riparian, ex_native = vegetation_adjustment(lg_river, ex_veg, ex_riparian, ex_native, thiessen_valley, scratch, ex_veg_lookup_folder, "Ex", "LgRiver")
        hist_riparian, hist_native = vegetation_adjustment(lg_river, hist_veg, hist_riparian, hist_native, thiessen_valley, scratch, hist_veg_lookup_folder, "Hist", "LgRiver")

    # calculate overall riparian vegetation departure
    arcpy.AddMessage("Calculating overall riparian vegetation departure...")
    ex_rip_field = calc_veg_mean_per_reach(thiessen_valley, ex_riparian, "ex", "rip", tempOut)
    hist_rip_field = calc_veg_mean_per_reach(thiessen_valley, hist_riparian, "hs", "rip", tempOut)
    arcpy.AddField_management(tempOut, "RIPAR_DEP", "DOUBLE")
    arcpy.AddMessage("Updating Riparian veg field...")
    with arcpy.da.UpdateCursor(tempOut, [ex_rip_field, hist_rip_field, "RIPAR_DEP"]) as cursor:
        for counter, row in enumerate(cursor):
            if counter % 100 == 0:
                arcpy.AddMessage("\tDone {}".format(counter))
            row[2] = row[0] / row[1]
            cursor.updateRow(row)
            if row[2] > 1 and row[1] == 0.0001:
                row[2] = 1
            cursor.updateRow(row)

    # calculate native riparian vegetation departure
    ex_native_field = calc_veg_mean_per_reach(thiessen_valley, ex_native, "ex", "ntv", tempOut)
    hist_native_field = calc_veg_mean_per_reach(thiessen_valley, hist_native, "hs", "ntv", tempOut)
    arcpy.AddField_management(tempOut, "NATIV_DEP", "DOUBLE")
    arcpy.AddMessage("Updating Native veg field...")
    with arcpy.da.UpdateCursor(tempOut, [ex_native_field, hist_native_field, "NATIV_DEP"]) as cursor:
        for counter, row in enumerate(cursor):
            if counter % 100 == 0:
                arcpy.AddMessage("\tDone {}".format(counter))
            row[2] = row[0] / row[1]
            cursor.updateRow(row)
            if row[2] > 1 and row[1] == 0.0001:
                row[2] = 1
            cursor.updateRow(row)

    # calculate riparian conversions
    if not outName.endswith(".shp"):
        outName = outName+".shp"
    fcOut = os.path.join(analysis_folder, outName) # specify output path
    arcpy.AddMessage("Calculating riparian vegetation conversion types...")
    calculate_riparian_conversion(ex_veg, hist_veg, valley_buf, valley, thiessen_valley, tempOut, fcOut, intermediates_folder, scratch)

    # make layers
    arcpy.AddMessage("Making layers...")
    make_layers(fcOut, thiessen_valley, veg_rasters_folder)
    
    # write XML file
    arcpy.AddMessage("Writing XML file. NOTE: This is the final step and non-critical to the outputs")
    try:
        write_xml(projPath, projName, hucID, hucName, ex_veg, hist_veg, seg_network, lg_river, dredge_tailings, intermediates_folder, analysis_folder)
    except Exception:
        arcpy.AddMessage("Writing the XML file has failed, but RVD outputs are saved. This is a known bug in RCAT and you can proceed to the next step without problems.")


def validate_inputs(ex_veg, hist_veg, seg_network, valley, lg_river, dredge_tailings):
    # Checks if the spatial references are correct and that the inputs are what we want
    try:
        network_sr = arcpy.Describe(seg_network).spatialReference
    except:
        raise Exception("There was a problem finding the spatial reference of the stream network. "
                       + "This is commonly caused by trying to run the Table tool directly after running the project "
                       + "builder. Restarting ArcGIS fixes this problem most of the time.")
    if not network_sr.type == "Projected":
        arcpy.AddMessage("WARNING: Input stream network must have a projected coordinate system!")
        #raise Exception("Input stream network must have a projected coordinate system")
    if not arcpy.Describe(ex_veg).spatialReference.name == network_sr.name:
        #raise Exception("Input existing vegetation raster must have the same coordinate system as input network for accurate calculations.")
        arcpy.AddMessage("WARNING: Input existing vegetation raster must have the same coordinate system as the input network for accurate calculations!")
    if not arcpy.Describe(hist_veg).spatialReference.name == network_sr.name:
        #raise Exception("Input historic vegetation raster must have the same coordinate system as input network for accurate calculations.")
        arcpy.AddMessage("WARNING: Input historic vegetation raster must have the same coordinate system as the input network for accurate calculations!")
    if lg_river is not None:
        if not arcpy.Describe(lg_river).spatialReference.name == network_sr.name:
            #raise Exception("Input large river polygon must have the same coordinate system as input network for accurate calculations.")
            arcpy.AddMessage("WARNING: Input large river polygon must have the same coordinate system as the input network for accurate calculations!")
    if dredge_tailings is not None:
        if not arcpy.Describe(dredge_tailings).spatialReference.name == network_sr.name:
            #raise Exception("Input dredge tailings polygons must have the same coordinate system as input network for accurate calculations.")
            arcpy.AddMessage("WARNING: Input dredge tailings polygons must have the same coordinate system as the input network for accurate calculations!")
    # check for needed veg fields in each veg raster
    needed_fields = ["RIPARIAN", "NATIVE_RIP", "CONVERSION"]
    ex_veg_fields = [f.name for f in arcpy.ListFields(ex_veg)]
    hist_veg_fields = [f.name for f in arcpy.ListFields(hist_veg)]
    missing_fields = []
    for f in needed_fields:
        if f not in ex_veg_fields:
            missing_fields.append("Existing vegetation raster is missing required attribute " + f)
        if f not in hist_veg_fields:
            missing_fields.append("Historic vegetation raster is missing required attribute " + f)
    # return message for each missing field then raise error to stop script
    if len(missing_fields) > 0:
        i = 0
        arcpy.AddMessage("------------------------------------------------------------------")
        while i+1 <= len(missing_fields):
            arcpy.AddMessage(missing_fields[i])
            i += 1
        raise Exception("ERROR: Add required attributes (listed above) to vegetation data before running RVD.")


def build_output_folder(projPath, seg_network):
    # make master output folder if not present
    master_outputs_folder = os.path.join(projPath, "Outputs")
    make_folder(master_outputs_folder)

    # make new output folder for current run
    j = 1
    str_num = '01'
    new_output_folder = os.path.join(master_outputs_folder, "Output_" + str_num)
    while os.path.exists(new_output_folder):
        j += 1
        if j > 9:
            str_num = str(j)
        else:
            str_num = "0" + str(j)
        new_output_folder = os.path.join(master_outputs_folder, "Output_" + str_num)
    os.mkdir(new_output_folder)

    # make new intermediates folder
    intermediates_folder = os.path.join(new_output_folder, "01_Intermediates")
    os.mkdir(intermediates_folder)

    # make new analysis folder
    analysis_folder = os.path.join(new_output_folder, "02_Analyses")
    os.mkdir(analysis_folder)

    # make RVD analysis folder
    rvd_analysis_folder = os.path.join(analysis_folder, find_available_num_prefix(analysis_folder)+"_RVD")
    os.mkdir(rvd_analysis_folder)

    # copy segmented network to temporary output file for editing
    tempOut = os.path.join(rvd_analysis_folder, "tempout.shp")
    arcpy.CopyFeatures_management(seg_network, tempOut)

    return intermediates_folder, rvd_analysis_folder, tempOut


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
    # create layer from midpoints
    midpoints_lyr = "midpoints_lyr"
    arcpy.MakeFeatureLayer_management(midpoints, midpoints_lyr)

    # create thiessen polygons surrounding reach midpoints
    thiessen_folder = os.path.join(intermediates_folder, "01_MidpointsThiessen")
    make_folder(thiessen_folder)
    thiessen = thiessen_folder + "/midpoints_thiessen.shp"
    arcpy.CreateThiessenPolygons_analysis(midpoints, thiessen, "ALL")

    # buffer fragmented valley bottom
    valley_buf = scratch + "/valley_buf.shp"
    valley_lyr = 'valley_lyr'
    arcpy.MakeFeatureLayer_management(in_features=valley, out_layer=valley_lyr) #convert valley buffer to layer - JLW
    arcpy.Buffer_analysis(valley_lyr, valley_buf, "30 Meters", "FULL", "ROUND", "ALL")

    # clip thiessen polygons to buffered valley bottom
    thiessen_valley_folder = os.path.join(intermediates_folder, "02_ValleyThiessen")
    make_folder(thiessen_valley_folder)
    thiessen_clip = scratch + "/Thiessen_Valley_Clip.shp"
    arcpy.Clip_analysis(thiessen, valley_buf, thiessen_clip)

    # convert multipart features to single part
    arcpy.AddField_management(thiessen_clip, "RCH_FID", "SHORT")
    with arcpy.da.UpdateCursor(thiessen_clip, ["ORIG_FID", "RCH_FID"]) as cursor:
        for row in cursor:
            row[1] = row[0]
            cursor.updateRow(row)
    thiessen_singlepart = scratch + "/Thiessen_Valley_Singlepart.shp"
    arcpy.MultipartToSinglepart_management(thiessen_clip, thiessen_singlepart)
    thiessen_singlepart_lyr = arcpy.MakeFeatureLayer_management(in_features=thiessen_singlepart)

    # Select only polygon features that intersect network midpoints
    thiessen_select = arcpy.SelectLayerByLocation_management(thiessen_singlepart_lyr, "INTERSECT", midpoints_lyr,
                                                             selection_type="NEW_SELECTION")
    thiessen_valley = thiessen_valley_folder + "/Thiessen_Valley.shp"
    arcpy.CopyFeatures_management(thiessen_select, thiessen_valley)

    return thiessen_valley, valley_buf


def make_veg_lookup_rasters(veg, folder, type):
    if type=="ex_veg":
        prefix = "Existing"
    else:
        prefix = "Historic"
    # make riparian lookup raster and save
    riparian = Lookup(veg, "RIPARIAN")
    riparian.save(os.path.join(folder, prefix + "_Riparian.tif"))
    # make native lookup raster and save
    native = Lookup(veg, "NATIVE_RIP")
    native.save(os.path.join(folder, prefix + "_NativeRiparian.tif"))
    return riparian, native


def vegetation_adjustment(polygons, veg_raster, riparian, native, thiessen_valley, scratch, veg_folder, veg_type, polygon_type):
    # set raster environment for mask
    arcpy.env.extent = thiessen_valley
    arcpy.env.snapRaster = veg_raster
    # dissolve polygons into single feature
    polygons_dissolved = os.path.join(scratch, polygon_type+'_dissolved.shp')
    arcpy.Dissolve_management(polygons, polygons_dissolved)
    # extract raster values within polygon feature
    raster_in_polygons = ExtractByMask(veg_raster, polygons_dissolved)
    # set all values within extracted raster to 0 (i.e., not riparian or native riparian)
    cursor = arcpy.UpdateCursor(raster_in_polygons)
    for row in cursor:
        row.setValue("RIPARIAN", 0)
        row.setValue("NATIVE_RIP", 0)
        cursor.updateRow(row)
    del cursor, row
    # merge reclassified raster with original rasters
    riparian = reclassify_adjusted_veg(raster_in_polygons, riparian, "RIPARIAN", veg_type+"_Riparian_"+polygon_type, veg_folder)
    native = reclassify_adjusted_veg(raster_in_polygons, native, "NATIVE_RIP", veg_type+"_Native_"+polygon_type, veg_folder)
    return riparian, native
    

def reclassify_adjusted_veg(masked_raster, veg_lookup, field_name, out_name, folder):
    masked_raster_lookup = Lookup(masked_raster, field_name)
    masked_raster_reclass = Reclassify(masked_raster_lookup, "VALUE", "0 8; NODATA 0")
    raster_adjustment = masked_raster_reclass + veg_lookup
    adjusted_raster_output = Reclassify(raster_adjustment, "VALUE", "0 0; 1 1; 8 0; 9 0")
    adjusted_raster_output.save(os.path.join(folder, out_name + ".tif"))
    return adjusted_raster_output


def calc_veg_mean_per_reach(thiessen_valley, veg_lookup, veg_type, out_type, tempOut):

    arcpy.AddMessage("Calculating veg mean for {} {}".format(veg_type, out_type))
    # set raster environment for mask
    arcpy.env.extent = thiessen_valley
    arcpy.env.snapRaster = veg_lookup
    # calculate proportion of area with coded vegetation (riparian or native riparian) for each reach based on thiessen polygons
    # Note: since raster values are 0 and 1, "MEAN" is the same as the proportion of area for all values=1
    arcpy.AddMessage("\t Doing zonal stats...")
    veg_zs = ZonalStatisticsAsTable(thiessen_valley, "RCH_FID", veg_lookup, veg_type+"_veg_zs_"+out_type, statistics_type="MEAN")
    # add existing veg field to temp output by reach ids & calculate based on joined zonal stats
    arcpy.JoinField_management(tempOut, "FID", veg_zs, "RCH_FID", "MEAN")
    veg_field = veg_type.capitalize() + out_type.capitalize() + "_Mean"
    arcpy.AddField_management(tempOut, veg_field, "DOUBLE")
    arcpy.AddMessage("\t Updating veg field...")
    with arcpy.da.UpdateCursor(tempOut, ["MEAN", veg_field]) as cursor:
        for counter, row in enumerate(cursor):
            if counter % 100 == 0:
                arcpy.AddMessage("\t\tDone {}".format(counter))
            row[1] = row[0]
            cursor.updateRow(row)
            if row[1] == 0:
                row[1] = 0.0001
            cursor.updateRow(row)
    arcpy.DeleteField_management(tempOut, "MEAN")
    return veg_field


def calculate_riparian_conversion(ex_veg, hist_veg, valley_buf, valley, thiessen_valley, tempOut, fcOut, intermediates_folder, scratch):
    # set extent for all rasters
    arcpy.env.extent = 'MAXOF'
    arcpy.env.snapRaster = ex_veg
    # setting folder paths
    ex_veg_lookup_folder = os.path.join(intermediates_folder, "03_VegetationRasters/01_Ex_Veg")
    hist_veg_lookup_folder = os.path.join(intermediates_folder, "03_VegetationRasters/02_Hist_Veg")
    # create existing and historic rasters based on vegetation "conversion" fields
    arcpy.AddMessage('\t Creating Lookups...')
    ex_veg_conversion_lookup = Lookup(ex_veg, "CONVERSION")
    ex_veg_conversion_lookup.save(os.path.join(ex_veg_lookup_folder, "Ex_Cover.tif"))
    hist_conversion_lookup = Lookup(hist_veg, "CONVERSION")
    hist_conversion_lookup.save(os.path.join(hist_veg_lookup_folder, "Hist_Cover.tif"))
    # create change raster by substracting existing from historic
    arcpy.AddMessage('\t Creating Conversion Raster...')
    conversion_raster = hist_conversion_lookup - ex_veg_conversion_lookup
    int_conversion_raster = Int(conversion_raster)

    # get raster of pixels with historic or existing riparian
    arcpy.AddMessage('\t Creating Lookups...')
    ex_riparian_lookup = Lookup(ex_veg, "RIPARIAN")
    hist_riparian_lookup = Lookup(hist_veg, "RIPARIAN")
    arcpy.AddMessage('\t Creating Riparian Raster...')
    riparian_sum = ex_riparian_lookup + hist_riparian_lookup
    all_riparian = Reclassify(riparian_sum, "VALUE", "0 NODATA; 1 1; 2 2", "NODATA")
    all_riparian.save(os.path.join(os.path.dirname(ex_veg_lookup_folder), "All_Riparian_recl.tif"))
    riparian_conversion_raster = ExtractByMask(int_conversion_raster, all_riparian)

    arcpy.AddMessage('\t Reclassifying data...')
    # reclassify change raster to include only values pertaining to riparian conversion; all non-riparian conversion gets a NODATA value
    remap = "-480 NODATA; -460 NODATA; -450 NODATA; -435 NODATA; -400 NODATA; -80 -50; -64 NODATA; -63 NODATA; -62 NODATA; -60 -50; -50 -50; -47 NODATA; -48 NODATA; -49 NODATA; " \
            "-45 NODATA; -37 NODATA; -38 NODATA; -39 NODATA; -35 -50; -30 NODATA; -25 NODATA; -20 NODATA; -19 NODATA; -18 NODATA; -17 NODATA; -115 NODATA; 17 NODATA; 18 NODATA; 5 NODATA; " \
            "-10 NODATA; 0 0; 10 NODATA; 19 NODATA; 20 NODATA; 25 NODATA; 30 NODATA; 37 NODATA; 38 NODATA; 39 NODATA; 45 NODATA; 47 NODATA; 48 NODATA; 49 NODATA; 62 NODATA; 63 NODATA; " \
            "64 NODATA; 400 NODATA; 435 NODATA; 450 NODATA; 460 NODATA; 480 NODATA; 497 NODATA; 498 NODATA; 499 NODATA; 35 35; 50 50; 60 60; 80 80; 97 97; 98 98; 99 99"
    final_conversion_raster = Reclassify(riparian_conversion_raster, "VALUE", remap, "NODATA")
    # make list of all values in conversion raster
    valueList = []
    cursor = arcpy.SearchCursor(final_conversion_raster)
    for row in cursor:
        valueList.append(row.getValue("VALUE"))
    del cursor

    arcpy.AddMessage('\t Creating Individual Conversion Rasters...')

    # make individual rasters for each conversion value - value gets a "1", everything else is "NODATA"
    if 0 in valueList:
        conversion_0 = Reclassify(final_conversion_raster, "VALUE", "-50 NODATA; 0 1; 35 NODATA; 50 NODATA; 60 NODATA; 80 NODATA; 97 NODATA; 98 NODATA; 99 NODATA", "NODATA")
    else:
        conversion_0 = None
    if 35 in valueList:
        conversion_35 = Reclassify(final_conversion_raster, "VALUE", "-50 NODATA; 0 NODATA; 35 1; 50 NODATA; 60 NODATA; 80 NODATA; 97 NODATA; 98 NODATA; 99 NODATA", "NODATA")
    else:
        conversion_35 = None
    if 50 in valueList:
        conversion_50 = Reclassify(final_conversion_raster, "VALUE", "-50 NODATA; 0 NODATA; 35 NODATA; 50 1; 60 NODATA; 80 NODATA; 97 NODATA; 98 NODATA; 99 NODATA", "NODATA")
    else:
        conversion_50 = None
    if 60 in valueList:
        conversion_60 = Reclassify(final_conversion_raster, "VALUE", "-50 NODATA; 0 NODATA; 35 NODATA; 50 NODATA; 60 1; 80 NODATA; 97 NODATA; 98 NODATA; 99 NODATA", "NODATA")
    else:
        conversion_60 = None
    if 80 in valueList:
        conversion_80 = Reclassify(final_conversion_raster, "VALUE", "-50 NODATA; 0 NODATA; 35 NODATA; 50 NODATA; 60 NODATA; 80 1; 97 NODATA; 98 NODATA; 99 NODATA", "NODATA")
    else:
        conversion_80 = None
    if 97 in valueList:
        conversion_97 = Reclassify(final_conversion_raster, "VALUE", "-50 NODATA; 0 NODATA; 35 NODATA; 50 NODATA; 60 NODATA; 80 NODATA; 97 1; 98 NODATA; 99 NODATA", "NODATA")
    else:
        conversion_97 = None
    if 98 in valueList:
        conversion_98 = Reclassify(final_conversion_raster, "VALUE", "-50 NODATA; 0 NODATA; 35 NODATA; 50 NODATA; 60 NODATA; 80 NODATA; 97 NODATA; 98 1; 99 NODATA", "NODATA")
    else:
        conversion_98 = None
    if 99 in valueList:
        conversion_99 = Reclassify(final_conversion_raster, "VALUE", "-50 NODATA; 0 NODATA; 35 NODATA; 50 NODATA; 60 NODATA; 80 NODATA; 97 NODATA; 98 NODATA; 99 1", "NODATA")
    else:
        conversion_99 = None
    if -50 in valueList:
        conversion_min50 = Reclassify(final_conversion_raster, "VALUE", "-50 1; 0 NODATA; 35 NODATA; 50 NODATA; 60 NODATA; 80 NODATA; 97 NODATA; 98 NODATA; 99 NODATA", "NODATA")
    else:
        conversion_min50 = None

    # pull section of reclassified raster within buffered valley bottom and save
    out_conversion_raster = ExtractByMask(final_conversion_raster, valley_buf)
    out_conversion_raster.save(os.path.join(intermediates_folder, "03_VegetationRasters/Conversion_Raster.tif"))

    # calculate total pixel count for each reach based on zonal stats within thiessen polygons
    arcpy.AddMessage('\t Zonal Statistics per reach...')
    count_table = ZonalStatisticsAsTable(thiessen_valley, "RCH_FID", final_conversion_raster, "count_table", statistics_type="VARIETY")
    arcpy.JoinField_management(tempOut, "FID", count_table, "RCH_FID", "COUNT")
    # add count field for calculations and set counts of 0 to 1 to avoid division issues
    arcpy.AddField_management(tempOut, "count_calc", "SHORT")
    with arcpy.da.UpdateCursor(tempOut, ["COUNT", "count_calc"]) as cursor:
        for counter, row in enumerate(cursor):
            if counter % 100 == 0:
                arcpy.AddMessage("\t\tDone {}".format(counter))
            row[1] = row[0]
            cursor.updateRow(row)
            if row[1] == 0:
                row[1] = 1
            cursor.updateRow(row)

    arcpy.AddMessage('\t Calculating proportions...')
    # calculate count and proportion of each conversion type per reach and join to temporary output shp
    calculate_conversion_proportion(conversion_0, thiessen_valley, tempOut, valueList, 0, "noch")
    calculate_conversion_proportion(conversion_35, thiessen_valley, tempOut, valueList, 35, "decid")
    calculate_conversion_proportion(conversion_50, thiessen_valley, tempOut, valueList, 50, "grsh")
    calculate_conversion_proportion(conversion_60, thiessen_valley, tempOut, valueList, 60, "deveg")
    calculate_conversion_proportion(conversion_80, thiessen_valley, tempOut, valueList, 80, "conif")
    calculate_conversion_proportion(conversion_97, thiessen_valley, tempOut, valueList, 97, "inv")
    calculate_conversion_proportion(conversion_98, thiessen_valley, tempOut, valueList, 98, "dev")
    calculate_conversion_proportion(conversion_99, thiessen_valley, tempOut, valueList, 99, "agr")
    calculate_conversion_proportion(conversion_min50, thiessen_valley, tempOut, valueList, -50, "exp")

    arcpy.AddMessage('\t Creating arrays...')
    # create numpy arrays for proportion of each conversion type
    prop0_array = arcpy.da.FeatureClassToNumPyArray(tempOut, "prop_noch")
    array0 = np.asarray(prop0_array, np.float64)
    prop35_array = arcpy.da.FeatureClassToNumPyArray(tempOut, "prop_decid")
    array35 = np.asarray(prop35_array, np.float64)
    prop50_array = arcpy.da.FeatureClassToNumPyArray(tempOut, "prop_grsh")
    array50 = np.asarray(prop50_array, np.float64)
    prop60_array = arcpy.da.FeatureClassToNumPyArray(tempOut, "prop_deveg")
    array60 = np.asarray(prop60_array, np.float64)
    prop80_array = arcpy.da.FeatureClassToNumPyArray(tempOut, "prop_conif")
    array80 = np.asarray(prop80_array, np.float64)
    prop97_array = arcpy.da.FeatureClassToNumPyArray(tempOut, "prop_inv")
    array97 = np.asarray(prop97_array, np.float64)
    prop98_array = arcpy.da.FeatureClassToNumPyArray(tempOut, "prop_dev")
    array98 = np.asarray(prop98_array, np.float64)
    prop99_array = arcpy.da.FeatureClassToNumPyArray(tempOut, "prop_agr")
    array99 = np.asarray(prop99_array, np.float64)
    propMin50_array = arcpy.da.FeatureClassToNumPyArray(tempOut, "prop_exp")
    arrayMin50 = np.asarray(propMin50_array, np.float64)
    del prop0_array, prop50_array, prop60_array, prop80_array, prop97_array, prop98_array, prop99_array, propMin50_array # clear up memory

    # flag conversion type based on proportions of all conversions

    arcpy.AddMessage('\t Flagging Conversion types...')
    out_conv_code = np.zeros(len(array0), dtype=np.float64)
    for i in range(len(array0)):
        if array0[i] >= 0.85:  # if no change proportion is greater than or equal to 0.9
            out_conv_code[i] = 1  # no change
        else:  # if no change proportion is less than 0.9, move on to next greatest proportion
            if array35[i] > array50[i] and array35[i] > array60[i] and array35[i] > array80[i] and array35[i] > array97[i] and array35[i] > array98[i] and array35[i] > array99[i] and array35[i] > arrayMin50[i]:  # if deciduous/hardwood is next most dominant
                if array35[i] <= 0.10:
                    out_conv_code[i] = 80 # very minor conversion to deciduous/hardwood forest
                elif array35[i] <= 0.25 and array35[i] > 0.1:
                    out_conv_code[i] = 81  # minor conversion to deciduous/hardwood forest
                elif array35[i] > 0.25 and array35[i] <= 0.5:
                    out_conv_code[i] = 82  # moderate conversion to deciduous/hardwood forest
                else:
                    out_conv_code[i] = 83  # significant conversion to deciduous/hardwood forest
            elif array50[i] > array35[i] and array50[i] > array60[i] and array50[i] > array80[i] and array50[i] > array97[i] and array50[i] > array98[i] and array50[i] > array99[i] and array50[i] > arrayMin50[i]:  # if grass/shrubland is next most dominant
                if array50[i] <= 0.10:
                    out_conv_code[i] = 10 # very minor conversion to grass/shrubland
                elif array50[i] <= 0.25 and array50[i] > 0.1:
                    out_conv_code[i] = 11  # minor conversion to grass/shrubland
                elif array50[i] > 0.25 and array50[i] <= 0.5:
                    out_conv_code[i] = 12  # moderate conversion to grass/shrubland
                else:
                    out_conv_code[i] = 13  # significant conversion to grass/shrubland
            elif array60[i] > array35[i] and array60[i] > array50[i] and array60[i] > array80[i] and array60[i] > array97[i] and array60[i] > array98[i] and array60[i] > array99[i] and array60[i] > arrayMin50[i]:  # if barren is next most dominant
                if array60[i] <= 0.10:
                    out_conv_code[i] = 20 # very minor devegetation
                elif array60[i] <= 0.25 and array60[i] > 0.1:
                    out_conv_code[i] = 21  # minor devegetation
                elif array60[i] > 0.25 and array60[i] <= 0.5:
                    out_conv_code[i] = 22  # moderate devegetation
                else:
                    out_conv_code[i] = 23  # significant devegetation
            elif array80[i] > array35[i] and array80[i] > array50[i] and array80[i] > array60[i] and array80[i] > array97[i] and array80[i] > array98[i] and array80[i] > array99[i] and array80[i] > arrayMin50[i]:  # if conifer encroachment is next most dominant
                if array80[i] <= 0.10:
                    out_conv_code[i] = 30 # very minor conifer encroachment
                elif array80[i] <= 0.25 and array80[i] > 0.1:
                    out_conv_code[i] = 31  # minor conifer encroachment
                elif array80[i] > 0.25 and array80[i] <= 0.5:
                    out_conv_code[i] = 32  # moderate conifer encroachment
                else:
                    out_conv_code[i] = 33  # significant conifer encroachment
            elif array97[i] > array35[i] and array97[i] > array50[i] and array97[i] > array60[i] and array97[i] > array80[i] and array97[i] > array98[i] and array97[i] > array99[i] and array97[i] > arrayMin50[i]:  # if conversion to invasive is next most dominant
                if array97[i] <= 0.10:
                    out_conv_code[i] = 40 # very minor conversion to invasive
                elif array97[i] <= 0.25 and array97[i] > 0.1:
                    out_conv_code[i] = 41  # minor conversion to invasive
                elif array97[i] > 0.25 and array97[i] <= 0.5:
                    out_conv_code[i] = 42  # moderate conversion to invasive
                else:
                    out_conv_code[i] = 43  # significant conversion to invasive
            elif array98[i] > array35[i] and array98[i] > array50[i] and array98[i] > array60[i] and array98[i] > array80[i] and array98[i] > array97[i] and array98[i] > array99[i] and array98[i] > arrayMin50[i]:  # if urbanization is next most dominant
                if array98[i] <= 0.10:
                    out_conv_code[i] = 50 # very minor urbanization
                elif array98[i] <= 0.25 and array98[i] > 0.1:
                    out_conv_code[i] = 51  # minor urbanization
                elif array98[i] > 0.25 and array98[i] <= 0.5:
                    out_conv_code[i] = 52  # moderate urbanization
                else:
                    out_conv_code[i] = 53  # significant urbanization
            elif array99[i] > array35[i] and array99[i] > array50[i] and array99[i] > array60[i] and array99[i] > array80[i] and array99[i] > array97[i] and array99[i] > array98[i] and array99[i] > arrayMin50[i]:  # if conversion to agriculture is next most dominant
                if array99[i] <= 0.10:
                    out_conv_code[i] = 60 # very minor conversion to agriculture
                elif array99[i] <= 0.25 and array99[i] > 0.1:
                    out_conv_code[i] = 61  # minor conversion to agriculture
                elif array99[i] > 0.25 and array99[i] <= 0.5:
                    out_conv_code[i] = 62  # moderate conversion to agriculture
                else:
                    out_conv_code[i] = 63  # significant conversion to agriculture
            elif arrayMin50[i] > array35[i] and arrayMin50[i] > array50[i] and arrayMin50[i] > array60[i] and arrayMin50[i] > array80[i] and arrayMin50[i] > array97[i] and arrayMin50[i] > array98[i] and arrayMin50[i] > array99[i]:  # if riparian expansion is next most dominant
                if arrayMin50[i] <= 0.10:
                    out_conv_code[i] = 70 # very minor riparian expansion
                elif arrayMin50[i] <= 0.25 and arrayMin50[i] > 0.1:
                    out_conv_code[i] = 71  # minor riparian expansion
                elif arrayMin50[i] > 0.25 and arrayMin50[i] <= 0.5:
                    out_conv_code[i] = 72  # moderate riparian expansion
                else:
                    out_conv_code[i] = 73  # significant riparian expansion
            else:
                out_conv_code[i] = 0

    # save conversion types table
    arcpy.AddMessage('\t Saving Conversion Tables...')
    fid = np.arange(0, len(out_conv_code), 1)
    columns = np.column_stack((fid, out_conv_code))
    out_table = intermediates_folder + "/Conversion_Table.txt"
    np.savetxt(out_table, columns, delimiter=",", header="FID, conv_code", comments="")

    # not sure why these lines are needed- this is just taking a copy of the above table and deleting the previous
    conv_code_table = scratch + "/conv_code_table" 
    arcpy.CopyRows_management(out_table, conv_code_table)
    arcpy.Delete_management(out_table)

    arcpy.AddMessage('\t Updating Conversion Types...')
    # join conversion types table to temp output shp
    arcpy.JoinField_management(tempOut, "FID", conv_code_table, "FID", "conv_code")

    # specify conversion type field based on conversion code from table
    arcpy.AddField_management(tempOut, "Conv_Type", "text", "", "", 50)
    with arcpy.da.UpdateCursor(tempOut, ["conv_code", "Conv_Type", "COUNT"]) as cursor:
        for row in cursor:
            if row[0] == 1:
                row[1] = "No Change"
            elif row[0] == 10:
                row[1] = "Very Minor Change"
            elif row[0] == 11:
                row[1] = "Minor Change" #Conversion to Grass/Shrubland"
            elif row[0] == 12:
                row[1] = "Moderate Conversion to Grass/Shrubland"
            elif row[0] == 13:
                row[1] = "Significant Conversion to Grass/Shrubland"
            elif row[0] == 20:
                row[1] = "Very Minor Change"
            elif row[0] == 21:
                row[1] = "Minor Change" #Devegetation"
            elif row[0] == 22:
                row[1] = "Moderate Devegetation"
            elif row[0] == 23:
                row[1] = "Significant Devegetation"
            elif row[0] == 30:
                row[1] = "Very Minor Change"
            elif row[0] == 31:
                row[1] = "Minor Change" #Conifer Encroachment"
            elif row[0] == 32:
                row[1] = "Moderate Conifer Encroachment"
            elif row[0] == 33:
                row[1] = "Significant Conifer Encroachment"
            elif row[0] == 40:
                row[1] = "Very Minor Change"
            elif row[0] == 41:
                row[1] = "Minor Change" #Conversion to Invasive"
            elif row[0] == 42:
                row[1] = "Moderate Conversion to Invasive"
            elif row[0] == 43:
                row[1] = "Significant Conversion to Invasive"
            elif row[0] == 50:
                row[1] = "Very Minor Change"
            elif row[0] == 51:
                row[1] = "Minor Change" #Development"
            elif row[0] == 52:
                row[1] = "Moderate Development"
            elif row[0] == 53:
                row[1] = "Significant Development"
            elif row[0] == 60:
                row[1] = "Very Minor Change"
            elif row[0] == 61:
                row[1] = "Minor Change" #Conversion to Agriculture"
            elif row[0] == 62:
                row[1] = "Moderate Conversion to Agriculture"
            elif row[0] == 63:
                row[1] = "Significant Conversion to Agriculture"
            elif row[0] == 70:
                row[1] = "Very Minor Change"
            elif row[0] == 71:
                row[1] = "Minor Change" #Riparian Expansion"
            elif row[0] == 72:
                row[1] = "Moderate Riparian Expansion"
            elif row[0] == 73:
                row[1] = "Significant Riparian Expansion" 
            elif row[0] == 80:
                row[1] = "Very Minor Change"
            elif row[0] == 81:
                row[1] = "Minor Change" #Conversion to Deciduous Forest"
            elif row[0] == 82:
                row[1] = "Moderate Conversion to Deciduous Forest"
            elif row[0] == 83:
                row[1] = "Significant Conversion to Deciduous Forest"
            elif row[0] == 0:
                row[1] = "Multiple Dominant Conversion Types"
            elif row[2] == 1:
                if row[0] == 1:
                    row[1] = "No Change"
                else:
                    row[0] = 90 # minor change with small sample size
                    row[1] = "Very Minor Change" # minor change with small sample size
            cursor.updateRow(row)

    arcpy.AddMessage('\t Handling NoData...')
    # set everything with count 0 with nodata values, type as no riparian
    with arcpy.da.UpdateCursor(tempOut, ["COUNT", "RIPAR_DEP", "NATIV_DEP", "conv_code", "Conv_Type", "ExRip_Mean",
                                         "HsRip_Mean", "ExNtv_Mean", "HsNtv_Mean"]) as cursor:
        for row in cursor:
            if row[0] == 0:
                row[1] = -9999
                row[2] = -9999
                row[3] = 100
                row[4] = "No Riparian Vegetation Detected"
                row[5] = -9999
                row[6] = -9999
                row[7] = -9999
                row[8] = -9999
                cursor.updateRow(row)
    
    # if any features in temp output shp are outside of valley bottom, set all conversion fields to NoData value

    arcpy.AddMessage('\t Handling values outside of valley bottom...')

    arcpy.MakeFeatureLayer_management(tempOut, "outlyr")
    arcpy.SelectLayerByLocation_management("outlyr", "HAVE_THEIR_CENTER_IN", valley)
    arcpy.SelectLayerByLocation_management("outlyr", selection_type="SWITCH_SELECTION")
    getcount = arcpy.GetCount_management("outlyr")
    count = int(getcount.getOutput(0))
    if count != 0:
        with arcpy.da.UpdateCursor("outlyr", ["RIPAR_DEP", "NATIV_DEP", "conv_code", "Conv_Type", "ExRip_Mean", "HsRip_Mean",
                                              "ExNtv_Mean",  "HsNtv_Mean", "COUNT", "sum_noch", "sum_grsh", "sum_deveg",
                                              "sum_conif", "sum_inv", "sum_dev", "sum_agr", "prop_noch", "prop_grsh", "prop_deveg",
                                              "prop_conif", "prop_inv", "prop_dev", "prop_agr", "prop_exp",  "count_calc"]) as cursor:
            for row in cursor:
                row[0] = -9999
                row[1] = -9999
                row[2] = -9999
                row[3] = "NA"
                row[4] = -9999
                row[5] = -9999
                row[6] = -9999
                row[7] = -9999
                row[8] = -9999
                row[9] = -9999
                row[10] = -9999
                row[11] = -9999
                row[12] = -9999
                row[13] = -9999
                row[14] = -9999
                row[15] = -9999
                row[16] = -9999
                row[17] = -9999
                row[18] = -9999
                row[19] = -9999
                row[20] = -9999
                row[21] = -9999
                row[22] = -9999
                row[23] = -9999
                row[24] = -9999
                cursor.updateRow(row)

    # save to output shapefile
    arcpy.SelectLayerByAttribute_management("outlyr", "CLEAR_SELECTION")
    arcpy.CopyFeatures_management("outlyr", fcOut)
    arcpy.Delete_management(tempOut)


def calculate_conversion_proportion(conversion_raster, thiessen_valley, tempOut, valueList, value, field_suffix):
    sum_field = "sum_"+field_suffix # new sum field for conversion type
    arcpy.AddField_management(tempOut, sum_field, "DOUBLE")
    # calculate pixel count for conversion type and 
    if value in valueList:
        # calculate count of pixels with given value within each thiessen polygon
        # NOTE: sum only works here because input raster has 0/1 values, so sum is count of all "1"s
        if value == -50:
            string_val = "min50"
        else:
            string_val = str(value)
        arcpy.AddMessage('\t\t\t Zonal Statistics for {}...'.format(value))
        table = ZonalStatisticsAsTable(thiessen_valley, "RCH_FID", conversion_raster, "table_"+string_val, "", "SUM")
        # add zonal stats calculations to temporary output shp
        arcpy.JoinField_management(tempOut, "FID", table, "RCH_FID", "SUM")
        with arcpy.da.UpdateCursor(tempOut, ["SUM", sum_field]) as cursor:
            for row in cursor:
                row[1] = row[0]
                cursor.updateRow(row)
        arcpy.DeleteField_management(tempOut, "SUM") # otherwise will overlap with next field used
    # if value is not within conversion raster, all features will have a count of 0 for the value
    else:
        with arcpy.da.UpdateCursor(tempOut, sum_field) as cursor:
            for row in cursor:
                row[0] = 0
                cursor.updateRow(row)

    # calculate proportion of conversion type based on sum/count fields
    prop_field = "prop_"+field_suffix # new prop field for conversion type
    arcpy.AddField_management(tempOut, prop_field, "DOUBLE")
    arcpy.AddMessage('\t\t\t Updating {}...'.format(value))
    with arcpy.da.UpdateCursor(tempOut, ["count_calc", sum_field, prop_field]) as cursor:
        for row in cursor:
            row[2] = row[1] / row[0]
            cursor.updateRow(row)


def make_layers(fcOut, thiessen_valley, veg_rasters_folder):
    source_code_folder = os.path.dirname(os.path.abspath(__file__))
    symbology_folder = os.path.join(source_code_folder, "RCATSymbology")
    # pull symbology layers
    rvd_native_symbology = os.path.join(symbology_folder, "NativeRiparianVegetationDeparture.lyr")
    rvd_overall_symbology = os.path.join(symbology_folder, "RiparianVegetationDeparture.lyr")
    conversion_type_symbology = os.path.join(symbology_folder, "RiparianConversionType.lyr")
    riparian_corridor_symbology = os.path.join(symbology_folder, "RiparianCorridor.lyr")
    riparian_conversion_symbology = os.path.join(symbology_folder, "ConversionRaster.lyr")
    thiessen_valley_symbology = os.path.join(symbology_folder, "ClippedThiessenPolygons.lyr")
    # find filepaths
    conversion_raster = os.path.join(veg_rasters_folder, "Conversion_Raster.tif")
    riparian_corridor = os.path.join(veg_rasters_folder, "All_Riparian_recl.tif")
    # make layers
    make_layer(os.path.dirname(fcOut), fcOut, "Native Riparian Vegetation Departure", rvd_native_symbology,
               symbology_field="NATIV_DEP")
    make_layer(os.path.dirname(fcOut), fcOut, "Riparian Vegetation Departure", rvd_overall_symbology,
               symbology_field="RIPAR_DEP")
    make_layer(os.path.dirname(fcOut), fcOut, "Riparian Conversion Type", conversion_type_symbology,
               symbology_field="Conv_Type")
    make_layer(os.path.dirname(thiessen_valley), thiessen_valley, "Clipped Thiessen Polygons", thiessen_valley_symbology)
    make_layer(os.path.dirname(veg_rasters_folder), conversion_raster, "Riparian Conversion Raster", riparian_conversion_symbology, is_raster=True)
    make_layer(os.path.dirname(veg_rasters_folder), riparian_corridor, "Riparian Corridor", riparian_corridor_symbology, is_raster=True)
    
    
def write_xml(projPath, projName, hucID, hucName, ex_veg, hist_veg, seg_network, lg_river, dredge_tailings, intermediates_folder, analysis_folder):
    xmlfile = projPath + "/RVDproject.rs.xml"
    if not os.path.exists(xmlfile):
        # initiate xml file creation
        newxml = projectxml.ProjectXML(xmlfile, "RVD", projName)

        if not hucID == None:
            newxml.addMeta("HUCID", hucID, newxml.project)
        if not hucID == None:
            idlist = [int(x) for x in str(hucID)]
            if idlist[0] == 1 and idlist[1] == 7:
                newxml.addMeta("Region", "CRB", newxml.project)
        if not hucName == None:
            newxml.addMeta("Watershed", hucName, newxml.project)

        newxml.addRVDRealization("RVD Realization 1", rid="RZ1", dateCreated=datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                 productVersion="1.0.11", guid=getUUID())

        # add inputs and outputs to xml file
        newxml.addProjectInput("Raster", "Existing Vegetation", ex_veg[ex_veg.find("Inputs"):], iid="EXVEG1", guid=getUUID())
        newxml.addRVDInput(newxml.RVDrealizations[0], "Existing Vegetation", ref="EXVEG1")

        newxml.addProjectInput("Raster", "Historic Vegetation", hist_veg[hist_veg.find("Inputs"):], iid="HISTVEG1", guid=getUUID())
        newxml.addRVDInput(newxml.RVDrealizations[0], "Historic Vegetation", ref="HISTVEG1")

        newxml.addProjectInput("Vector", "Segmented Network", seg_network[seg_network.find("Inputs"):], iid="NETWORK1", guid=getUUID())
        newxml.addRVDInput(newxml.RVDrealizations[0], "Network", ref="NETWORK1")

        newxml.addProjectInput("Vector", "Valley Bottom", valley[valley.find("Inputs"):], iid="VALLEY1", guid=getUUID())
        newxml.addRVDInput(newxml.RVDrealizations[0], "Valley", ref="VALLEY1")

        if lg_river is not None:
            newxml.addProjectInput("Vector", "Large River Polygon", lg_river[lg_river.find("Inputs"):], iid="LRP1", guid=getUUID())
            newxml.addRVDInput(newxml.RVDrealizations[0], "LRP", ref="LRP1")

        if dredge_tailings is not None:
            newxml.addProjectInput("Vector", "Dredge Tailings", dredge_tailings[dredge_tailings.find("Inputs"):], iid="DREDGETAILINGS1", guid=getUUID())
            newxml.addRVDInput(newxml.RVDrealizations[0], "DredgeTailings", ref="DREDGETAILINGS1")

        newxml.addRVDInput(newxml.RVDrealizations[0], "Existing Cover", "Existing Riparian",
                           path=intermediates_folder + "/03_VegetationRasters/01_Ex_Veg/Existing_Riparian.tif", guid=getUUID())
        newxml.addRVDInput(newxml.RVDrealizationsp[0], "Existing Cover", "Existing Native Riparian",
                           path=intermediates_folder + "/03_VegetationRasters/01_Ex_Veg/Existing_NativeRiparian.tif", guid=getUUID())
        newxml.addRVDInput(newxml.RVDrealizations[0], "Historic Cover", "Historic Riparian",
                           path=intermediates_folder + "/03_VegetationRasters/02_Hist_Veg/Historic_Riparian.tif", guid=getUUID())
        newxml.addRVDInput(newxml.RVDrealizations[0], "Historic Cover", "Historic Native Riparian",
                           path=intermediates_folder + "/03_VegetationRasters/02_Hist_Veg/Historic_NativeRiparian.tif", guid=getUUID())
        newxml.addRVDInput(newxml.RVDrealizations[0], "Existing Cover", "Existing Cover",
                           path=intermediates_folder + "/03_VegetationRasters/02_Hist_Veg/Ex_Cover.tif", guid=getUUID())
        newxml.addRVDInput(newxml.RVDrealizations[0], "Historic Cover", "Historic Cover",
                           path=intermediates_folder + "/03_VegetationRasters/02_Hist_Veg/Hist_Cover.tif", guid=getUUID())
        newxml.addRVDInput(newxml.RVDrealizations[0], "Thiessen Polygons", "Thiessen Polygons",
                           path=intermediates_folder + "/02_ValleyThiessen/Thiessen_Valley_Clip.shp", guid=getUUID())

        newxml.addOutput("RVD Analysis", "Vector", "RVD", fcOut[fcOut.find("02_Analyses"):], newxml.RVDrealizations[0], guid=getUUID())
        newxml.addOutput("RVD Analysis", "Raster", "Conversion Raster",
                         intermediates_folder + "/Converstion_Raster.tif", newxml.RVDrealizations[0], guid=getUUID())

        newxml.write()

    else:
        exxml = projectxml.ExistingXML(xmlfile)

        rvdr = exxml.rz.findall("RVD")

        rname = []
        for x in range(len(rvdr)):
            name = rvdr[x].find("Name")
            rname.append(name.text)
        rnum = []
        for y in range(len(rname)):
            num = int(rname[y][-1])
            rnum.append(num)

        k = 2
        while k in rnum:
            k += 1

        exxml.addRVDRealization("RVD Realization " + str(k), rid="RZ" + str(k),
                                dateCreated=datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), productVersion="1.0.11", guid=getUUID())

        inputs = exxml.root.find("Inputs")

        raster = inputs.findall("Raster")
        rasterid = range(len(raster))
        for i in range(len(raster)):
            rasterid[i] = raster[i].get("id")
        rasterpath = range(len(raster))
        for i in range(len(raster)):
            rasterpath[i] = raster[i].find("Path").text

        for i in range(len(rasterpath)):
            if os.path.abspath(rasterpath[i]) == os.path.abspath(ex_veg[ex_veg.find("Inputs"):]):
                EV = exxml.root.findall(".//ExistingVegetation")
                for x in range(len(EV)):
                    if EV[x].attrib['ref'] == rasterid[i]:
                        r = EV[x].findall(".//Raster")
                        exrip_guid = r[0].attrib['guid']
                        excov_guid = r[1].attrib['guid']
                    else:
                        r = []
                exxml.addRVDInput(exxml.RVDrealizations[0], "Existing Vegetation", ref=str(rasterid[i]))
                if len(r) > 0:
                    exxml.addRVDInput(exxml.RVDrealizations[0], "Existing Cover", "Existing Riparian",
                                      path=intermediates_folder + "/03_VegetationRasters/01_Ex_Veg/Existing_Riparian.tif",
                                      guid=exrip_guid)
                    exxml.addRVDInput(exxml.RVDrealizations[0], "Existing Cover", "Existing Native Riparian",
                                      path=intermediates_folder + "/03_VegetationRasters/01_Ex_Veg/Existing_NativeRiparian.tif",
                                      guid=exrip_guid)
                    exxml.addRVDInput(exxml.RVDrealizations[0], "Existing Cover", "Existing Cover",
                                      path=intermediates_folder + "/03_VegetationRasters/01_Ex_Veg/Ex_Cover.tif",
                                      guid=excov_guid)
                else:
                    exxml.addRVDInput(exxml.RVDrealizations[0], "Existing Cover", "Existing Riparian",
                                      path=intermediates_folder + "/03_VegetationRasters/01_Ex_Veg/Existing_Riparian.tif")
                    exxml.addRVDInput(exxml.RVDrealizations[0], "Existing Cover", "Existing Native Riparian",
                                      path=intermediates_folder + "/03_VegetationRasters/01_Ex_Veg/Existing_NativeRiparian.tif")
                    exxml.addRVDInput(exxml.RVDrealizations[0], "Existing Cover", "Existing Cover",
                                      path=intermediates_folder + "/03_VegetationRasters/01_Ex_Veg/Ex_Cover.tif")
            elif os.path.abspath(rasterpath[i]) == os.path.abspath(hist_veg[hist_veg.find("Inputs"):]):
                HV = exxml.root.findall(".//HistoricVegetation")
                for x in range(len(HV)):
                    if HV[x].attrib['ref'] == rasterid[i]:
                        r = HV[x].findall(".//Raster")
                        histrip_guid = r[0].attrib['guid']
                        histcov_guid = r[1].attrib['guid']
                    else:
                        r = []
                exxml.addRVDInput(exxml.RVDrealizations[0], "Historic Vegetation", ref=str(rasterid[i]))
                if len(r) > 0:
                    exxml.addRVDInput(exxml.RVDrealizations[0], "Historic Cover", "Historic Riparian",
                                      path=intermediates_folder + "/03_VegetationRasters/02_Hist_Veg/Historic_Riparian.tif",
                                      guid=histrip_guid)
                    exxml.addRVDInput(exxml.RVDrealizations[0], "Historic Cover", "Historic Riparian",
                                      path=intermediates_folder + "/03_VegetationRasters/02_Hist_Veg/Historic_NativeRiparian.tif",
                                      guid=histrip_guid)
                    exxml.addRVDInput(exxml.RVDrealizations[0], "Historic Cover", "Historic Cover",
                                      path=intermediates_folder + "/03_VegetationRasters/02_Hist_Veg/Hist_Cover.tif",
                                      guid=histcov_guid)
                else:
                    exxml.addRVDInput(exxml.RVDrealizations[0], "Historic Cover", "Historic Riparian",
                                      path=intermediates_folder + "/03_VegetationRasters/02_Hist_Veg/Historic_Riparian.tif")
                    exxml.addRVDInput(exxml.RVDrealizations[0], "Historic Cover", "Historic Native Riparian",
                                      path=intermediates_folder + "/03_VegetationRasters/02_Hist_Veg/Historic_NativeRiparian.tif")
                    exxml.addRVDInput(exxml.RVDrealizations[0], "Historic Cover", "Historic Cover",
                                      path=intermediates_folder + "/03_VegetationRasters/02_Hist_Veg/Hist_Cover.tif")

        nlist = []
        for j in rasterpath:
            if os.path.abspath(ex_veg[ex_veg.find("Inputs"):]) == os.path.abspath(j):
                nlist.append("yes")
            else:
                nlist.append("no")
        if "yes" in nlist:
            pass
        else:
            exxml.addProjectInput("Raster", "Existing Vegetation", ex_veg[ex_veg.find("Inputs"):], iid="EXVEG" + str(k), guid=getUUID())
            exxml.addRVDInput(exxml.RVDrealizations[0], "Existing Vegetation", ref="EXVEG" + str(k))
            exxml.addRVDInput(exxml.RVDrealizations[0], "Existing Cover", "Existing Riparian",
                              path=intermediates_folder + "/03_VegetationRasters/01_Ex_Veg/Existing_Riparian.tif",
                              guid=getUUID())
            exxml.addRVDInput(exxml.RVDrealizations[0], "Existing Cover", "Existing Native Riparian",
                              path=intermediates_folder + "/03_VegetationRasters/01_Ex_Veg/Existing_NativeRiparian.tif",
                              guid=getUUID())
            exxml.addRVDInput(exxml.RVDrealizations[0], "Existing Cover", "Existing Cover",
                              path=intermediates_folder + "/03_VegetationRasters/01_Ex_Veg/Ex_Cover.tif",
                              guid=getUUID())
        nlist = []
        for j in rasterpath:
            if os.path.abspath(hist_veg[hist_veg.find("Inputs"):]) == os.path.abspath(j):
                nlist.append("yes")
            else:
                nlist.append("no")
        if "yes" in nlist:
            pass
        else:
            exxml.addProjectInput("Raster", "Historic Vegetation", hist_veg[hist_veg.find("Inputs"):], iid="HISTVEG" + str(k), guid=getUUID())
            exxml.addRVDInput(exxml.RVDrealizations[0], "HistoricVegetation", ref="HISTVEG" + str(k))
            exxml.addRVDInput(exxml.RVDrealizations[0], "Historic Cover", "Historic Riparian",
                              path=intermediates_folder + "/03_VegetationRasters/02_Hist_Veg/Historic_Riparian.tif",
                              guid=getUUID())
            exxml.addRVDInput(exxml.RVDrealizations[0], "Historic Cover", "Historic Native Riparian",
                              path=intermediates_folder + "/03_VegetationRasters/02_Hist_Veg/Historic_NativeRiparian.tif",
                              guid=getUUID())
            exxml.addRVDInput(exxml.RVDrealizations[0], "Historic Cover", "Historic Cover",
                              path=intermediates_folder + "/03_VegetationRasters/02_Hist_Veg//Hist_Cover.tif",
                              guid=getUUID())
        del nlist

        vector = inputs.findall("Vector")
        vectorid = range(len(vector))
        for i in range(len(vector)):
            vectorid[i] = vector[i].get("id")
        vectorpath = range(len(vector))
        for i in range(len(vector)):
            vectorpath[i] = vector[i].find("Path").text

        for i in range(len(vectorpath)):
            if os.path.abspath(vectorpath[i]) == os.path.abspath(seg_network[seg_network.find("Inputs"):]):
                DN = exxml.root.findall(".//Network")
                for x in range(len(DN)):
                    if DN[x].attrib['ref'] == vectorid[i]:
                        r = DN[x].findall(".//ThiessenPolygons")
                        thiessen_guid = r[0].attrib['guid']
                    else:
                        r = []
                exxml.addRVDInput(exxml.RVDrealizations[0], "Network", ref=str(vectorid[i]))
                if len(r) > 0:
                    exxml.addRVDInput(exxml.RVDrealizations[0], "Thiessen Polygons", "Thiessen Polygons",
                                      path=intermediates_folder + "/02_ValleyThiessen/Thiessen_Valley_Clip.shp",
                                      guid=thiessen_guid)
                else:
                    exxml.addRVDInput(exxml.RVDrealizations[0], "Thiessen Polygons", "Thiessen Polygons",
                                      path=intermediates_folder + "/02_ValleyThiessen/Thiessen_Valley_Clip.shp")
            elif os.path.abspath(vectorpath[i]) == os.path.abspath(valley[valley.find("Inputs"):]):
                exxml.addRVDInput(exxml.RVDrealizations[0], "Valley", ref=str(vectorid[i]))
            if lg_river is not None:
                if os.path.abspath(vectorpath[i]) == os.path.abspath(lg_river[lg_river.find("Inputs"):]):
                    exxml.addRVDInput(exxml.RVDrealizations[0], "LRP", ref=str(vectorid[i]))
            if dredge_tailings is not None:
                if os.path.abspath(vectorpath[i]) == os.path.abspath(dredge_tailings[dredge_tailings.find("Inputs"):]):
                    exxml.addRVDInput(exxml.RVDrealizations[0], "DredgeTailings", ref=str(vectorid[i]))

        nlist = []
        for j in vectorpath:
            if os.path.abspath(seg_network[seg_network.find("Inputs"):]) == os.path.abspath(j):
                nlist.append("yes")
            else:
                nlist.append("no")
        if "yes" in nlist:
            pass
        else:
            exxml.addProjectInput("Vector", "Segmented Network", seg_network[seg_network.find("Inputs"):], iid="NETWORK" + str(k), guid=getUUID())
            exxml.addRVDInput(exxml.RVDrealizations[0], "Network", ref="NETWORK" + str(k))
            exxml.addRVDInput(exxml.RVDrealizations[0], "Thiessen Polygons", "Thiessen Polygons",
                              path=intermediates_folder + "/02_ValleyThiessen/Thiessen_Valley_Clip.shp",
                              guid=getUUID())
        nlist = []
        for j in vectorpath:
            if os.path.abspath(valley[valley.find("Inputs"):]) == os.path.abspath(j):
                nlist.append("yes")
            else:
                nlist.append("no")
        if "yes" in nlist:
            pass
        else:
            exxml.addProjectInput("Vector", "Valley Bottom", valley[valley.find("Inputs"):], iid="VALLEY" + str(k), guid=getUUID())
            exxml.addRVDInput(exxml.RVDrealizations[0], "Valley", ref="VALLEY" + str(k))

        if lg_river is not None:
            nlist = []
            for j in vectorpath:
                if os.path.abspath(lg_river[lg_river.find("Inputs"):]) == os.path.abspath(j):
                    nlist.append("yes")
                else:
                    nlist.append("no")
            if "yes" in nlist:
                pass
            else:
                exxml.addProjectInput("Vector", "Large River Polygon", lg_river[lg_river.find("Inputs"):], iid="LRP" + str(k), guid=getUUID())
                exxml.addRVDInput(exxml.RVDrealizations[0], "LRP", ref="LRP" + str(k))

        if dredge_tailings is not None:
            nlist = []
            for j in vectorpath:
                if os.path.abspath(dredge_tailings[dredge_tailings.find("Inputs"):]) == os.path.abspath(j):
                    nlist.append("yes")
                else:
                    nlist.append("no")
            if "yes" in nlist:
                pass
            else:
                exxml.addProjectInput("Vector", "Dredge Tailings Polygon", dredge_tailings[dredge_tailings.find("Inputs"):], iid="DREDGETAILINGS" + str(k), guid=getUUID())
                exxml.addRVDInput(exxml.RVDrealizations[0], "DredgeTailings", ref="DREDGETAILINGS" + str(k))

        del nlist

        exxml.addOutput("RVD Analysis " + str(k), "Vector", "RVD Output", fcOut[fcOut.find("02_Analyses"):], exxml.RVDrealizations[0], guid=getUUID())
        exxml.addOutput("RVD Analysis " + str(k), "Raster", "Conversion Raster",
                         intermediates_folder + "/Converstion_Raster.tif",
                         exxml.RVDrealizations[0], guid=getUUID())

        exxml.write()

                              
def getUUID():
    return str(uuid.uuid4()).upper()


def make_folder(folder):
    """
    Makes folder if it doesn't exist already
    """
    if not os.path.exists(folder):
        os.mkdir(folder)
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
        sys.argv[11])
