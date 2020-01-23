# ----------------------------------------------------------------------------------------------------------------------
# Name: Bankfull Channel
# Purpose: Creates a polygon representing the bankfull channel of a network. The equation/regression used to
#          derive the polygon was developed for the Interior Columbia River Basin by T. Beechie and H. Imaki.
# Author: Jordan Gilbert
# Created: 05/2015
# Updated: 01/2020 - Maggie Hallerud
# License:
# ----------------------------------------------------------------------------------------------------------------------

import arcpy
from arcpy.sa import *
import sys
import os
import shutil


def main(network, drarea, precip, valleybottom, out_dir, MinBankfullWidth, dblPercentBuffer, temp_dir, deleteTemp):

    arcpy.env.overwriteOutput = True
    arcpy.CheckOutExtension('Spatial')

    # clean and make new temp_dir
    if os.path.exists(temp_dir):
        shutil.rmtree(temp_dir)
    os.mkdir(temp_dir)

    # make output directory
    if not os.path.exists(out_dir):
        os.mkdir(out_dir)

    #create thiessen polygons from segmented stream network
    midpoints = os.path.join(temp_dir, "midpoints.shp")
    arcpy.FeatureVerticesToPoints_management(network, midpoints, "MID")
    arcpy.AddMessage("Creating thiessen polygons")
    thiessen = os.path.join(temp_dir, "thiessen.shp")
    arcpy.CreateThiessenPolygons_analysis(midpoints, thiessen)

    # clip thiessen polygons to buffered valley bottom
    thiessen_clip = os.path.join(temp_dir, "thiessen_clip.shp")
    valley_buffer = os.path.join(temp_dir, "valley_buffer.shp")
    arcpy.Buffer_analysis(valleybottom, valley_buffer, "15 Meters", "FULL", "ROUND", "ALL")
    arcpy.Clip_analysis(thiessen, valley_buffer, thiessen_clip)

    # calculate precip and drarea values for each thiessen polygon
    arcpy.AddMessage("Adding drainage area values to thiessen polygons")
    add_raster_values(thiessen_clip, drarea, "drarea", temp_dir)
    arcpy.AddMessage("Adding precipitation values to thiessen polygons")
    add_raster_values(thiessen_clip, precip, "precip", temp_dir)
    
    # dissolve network 
    arcpy.AddMessage("Applying precip and drainage area data to line network")
    dissolved_network = os.path.join(temp_dir, "dissolved_network.shp")
    arcpy.Dissolve_management(network, dissolved_network)

    # intersect dissolved network with thiessen polygons
    intersect = os.path.join(out_dir, "network_buffer_values.shp")
    arcpy.Intersect_analysis([dissolved_network, thiessen_clip], intersect, "", "", "LINE")

    # calculate buffer width
    arcpy.AddMessage("Calculating bankfull buffer width")
    calculate_buffer_width(intersect, MinBankfullWidth, dblPercentBuffer)

    # create final bankfull polygon
    create_bankfull_polygon(network, intersect, MinBankfullWidth, out_dir, temp_dir)

    # delete temporary files
    if deleteTemp == "True":
        arcpy.AddMessage("Deleting temporary directory")
        try:
            shutil.rmtree(temp_dir)
        except Exception as err:
            arcpy.AddMessage("Could not delete temp_dir, but final outputs are saved")


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
    tbl_out = os.path.join(temp_dir, "zonal_table_" + field_type + ".dbf")
    tbl_zs = ZonalStatisticsAsTable(thiessen_clip, "FID", raster, tbl_out, "DATA", "MAXIMUM")

    # join thiessen clip to zonal statas table and calculate raster value for each thiessen polygon    
    arcpy.JoinField_management(thiessen_clip, "FID", tbl_zs, "FID_", "MAX")
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
    arcpy.JoinField_management(thiessen_clip, "Input_FID", filled_missing_thiessen, "Input_FID")
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
                print "Could not delete unnecessary field " + f + " from thiessen_clip.shp"
                print "Error thrown was"
                print err


def calculate_buffer_width(intersect, MinBankfullWidth, dblPercentBuffer):
    arcpy.AddField_management(intersect, "BFWIDTH", "FLOAT")
    with arcpy.da.UpdateCursor(intersect, ["DRAREA", "PRECIP", "BFWIDTH"])as cursor:
        for row in cursor:
            # if row[0] == ' ' or row[1] == ' ':
                precip_cm = row[1]/10
                drarea = row[0]
                row[2] = 0.177*(pow(drarea,0.397))*(pow(precip_cm,0.453))
                if row[2] < float(MinBankfullWidth):
                    row[2] = float(MinBankfullWidth)
            #else:
                #   row[2] = ' '
                cursor.updateRow(row)

    # adjust buffer width based on percent buffer
    arcpy.AddField_management(intersect, "BUFWIDTH", "DOUBLE")
    with arcpy.da.UpdateCursor(intersect, ["BFWIDTH", "BUFWIDTH"]) as cursor:
        for row in cursor:
            row[1] = row[0]/2 + ((row[0]/2) * (float(dblPercentBuffer)/100))
            cursor.updateRow(row)


def create_bankfull_polygon(network, intersect, MinBankfullWidth, out_dir, temp_dir):
    # buffer network by bufwidth field to create bankfull polygon
    arcpy.AddMessage("Buffering network")
    bankfull = os.path.join(temp_dir, "bankfull.shp")
    arcpy.Buffer_analysis(intersect, bankfull, "BUFWIDTH", "FULL", "ROUND", "ALL")

    # merge buffer with min buffer
    bankfull_min_buffer = os.path.join(temp_dir, "min_buffer.shp")
    bankfull_merge = os.path.join(temp_dir, "bankfull_merge.shp")
    bankfull_dissolve = os.path.join(temp_dir, "bankfull_dissolve.shp")
    arcpy.Buffer_analysis(network, bankfull_min_buffer, str(MinBankfullWidth), "FULL", "ROUND", "ALL")
    arcpy.Merge_management([bankfull, bankfull_min_buffer], bankfull_merge)

    # dissolve polygon buffers
    arcpy.Dissolve_management(bankfull_merge, bankfull_dissolve)

    #smooth for final bankfull polygon
    arcpy.AddMessage("Smoothing final bankfull polygon")
    output = os.path.join(out_dir, "final_bankfull_channel.shp")
    arcpy.SmoothPolygon_cartography(bankfull_dissolve, output, "PAEK", "10 METERS") # TODO: Expose parameter?
    
    # Todo: add params as fields to shp.

    
if __name__ == '__main__':

    main(sys.argv[1],
         sys.argv[2],
         sys.argv[3],
         sys.argv[4],
         sys.argv[5],
         sys.argv[6],
         sys.argv[7])
