# ----------------------------------------------------------------------------------------------------------------------
# Name: Bankfull Channel
# Purpose: Creates a polygon representing the bankfull channel of a network. The equation/regression used to
#          derive the polygon was developed for the Interior Columbia River Basin by T. Beechie and H. Imaki.
# Author: Jordan Gilbert
# Created: 05/2015
# Updated: 04/2017
# License:
# ----------------------------------------------------------------------------------------------------------------------

import arcpy
from arcpy.sa import *
import sys


def main(
        network,
        drarea,
        precip,
        output,
        min_buf,
        percent_buf,
        scratch):

    arcpy.env.overwriteOutput = True
    arcpy.CheckOutExtension("spatial")

    # create a midpoint buffer for each network segment.  This is analysis area for zonal stats.
    midpoints = scratch + "/midoints"
    arcpy.FeatureVerticesToPoints_management(network, midpoints, "MID")
    midpoint_fields = [f.name for f in arcpy.ListFields(midpoints)]
    midpoint_fields.remove("OBJECTID")
    midpoint_fields.remove("Shape")
    midpoint_fields.remove("ORIG_FID")
    arcpy.Delete_management(midpoint_fields)
    mp_buffer = scratch + "/mp_buffer"
    arcpy.Buffer_analysis(midpoints, mp_buffer, "100 Meters", "", "", "NONE")

    # generate precip raster in cm
    arcpy.AddField_management(precip, "CM", "DOUBLE")
    cursor = arcpy.da.UpdateCursor(precip, ["Inches", "CM"])
    for row in cursor:
        row[1] = row[0]*2.54
        cursor.updateRow(row)
    del row
    del cursor

    precip_cm = scratch + "/precip_cm"
    arcpy.PolygonToRaster_conversion(precip, "CM", precip_cm, "", "", 30)

    # pull precip and da values on to the network
    precipandda(mp_buffer, drarea, precip_cm, network)

    # add the bankfull width and buffer width to network.
    if percent_buf == None:
        addbufwidth(network)
    else:
        addpercentbufwidth(network, percent_buf)

    # generate the bankfull polygon
    createbankfullpolygon(network, min_buf, output, scratch)

    arcpy.CheckInExtension("spatial")


def precipandda(mp_buffer, drarea, precip_cm, network):
    """pull precip and da values on to network"""

    drarea_zs = ZonalStatisticsAsTable(mp_buffer, "ORIG_FID", drarea, "drarea_table", statistics_type="MAXIMUM")
    arcpy.JoinField_management(network, "FID", drarea_zs, "ORIG_FID", "MAX")
    lf = arcpy.ListFields(network, "DA_sqkm")
    if len(lf) is 1:
        arcpy.DeleteField_management(network, "DA_sqkm")
    else:
        pass

    arcpy.AddField_management(network, "DA_sqkm", "DOUBLE")
    cursor = arcpy.da.UpdateCursor(network, ["MAX", "DA_sqkm"])
    for row in cursor:
        row[1] = row[0]
        cursor.updateRow(row)
        if row[1] < 0.1:
            row[1] = 0.1
        cursor.updateRow(row)
    del row
    del cursor
    arcpy.DeleteField_management(network, "MAX")

    precip_zs = ZonalStatisticsAsTable(mp_buffer, "ORIG_FID", precip_cm, "precip_table", statistics_type="MEAN")
    arcpy.JoinField_management(network, "FID", precip_zs, "ORIG_FID", "MEAN")
    lf = arcpy.ListFields(network, "Precip")
    if len(lf) is 1:
        arcpy.DeleteField_management(network, "Precip")
    else:
        pass

    arcpy.AddField_management(network, "Precip", "DOUBLE")
    cursor = arcpy.da.UpdateCursor(network, ["MEAN", "Precip"])
    for row in cursor:
        row[1] = row[0]
        cursor.updateRow(row)
        if row[1] < 1:
            row[1] = 1
        cursor.updateRow(row)
    del row
    del cursor
    arcpy.DeleteField_management(network, "MEAN")


def addpercentbufwidth(network, percent_buf):
    """add the bankfull width and buffer width to the network with a percent buffer"""

    arcpy.AddField_management(network, "BFWIDTH", "FLOAT")
    cursor = arcpy.da.UpdateCursor(network, ["DA_sqkm", "Precip", "BFWIDTH"])
    for row in cursor:
        index = 0.177*(pow(row[0],0.397)*pow(row[1],0.453))
        row[2] = index
        cursor.updateRow(row)
    del row
    del cursor

    arcpy.AddField_management(network, "BUFWIDTH", "DOUBLE")
    cursor = arcpy.da.UpdateCursor(network, ["BFWIDTH", "BUFWIDTH"])
    for row in cursor:
        index2 = row[0]/2 + ((row[0]/2) * (percent_buf/100))
        row[1] = index2
        cursor.updateRow(row)
    del row
    del cursor


def addbufwidth(network):
    """add the bankfull width and buffer width to the network without a percent buffer"""

    arcpy.AddField_management(network, "BFWIDTH", "FLOAT")
    cursor = arcpy.da.UpdateCursor(network, ["DA_sqkm", "Precip", "BFWIDTH"])
    for row in cursor:
        index = 0.177*(pow(row[0],0.397)*pow(row[1],0.453))
        row[2] = index
        cursor.updateRow(row)
    del row
    del cursor

    arcpy.AddField_management(network, "BUFWIDTH", "DOUBLE")
    cursor = arcpy.da.UpdateCursor(network, ["BFWIDTH", "BUFWIDTH"])
    for row in cursor:
        index2 = row[0]/2
        row[1] = index2
        cursor.updateRow(row)
    del row
    del cursor


def createbankfullpolygon(network, min_buf, output, scratch):
    """generate the bankfull channel polygon"""

    bankfull = scratch + "/bankfull"
    min_buffer = scratch + "/min_buffer"
    arcpy.Buffer_analysis(network, bankfull, "BUFWIDTH", "FULL", "ROUND", "ALL")
    arcpy.Buffer_analysis(network, min_buffer, min_buf, "FULL", "ROUND", "ALL")

    bankfull_merge = scratch + "/bankfull_merge"
    arcpy.Merge_management([bankfull, min_buffer], bankfull_merge)
    bankfull_dissolve = scratch + "/bankfull_dissolve"
    arcpy.Dissolve_management(bankfull_merge, bankfull_dissolve)

    arcpy.SmoothPolygon_cartography(bankfull_dissolve, output, "PAEK", "10 METERS")


if __name__ == '__main__':
    main(
        sys.argv[1],
        sys.argv[2],
        sys.argv[3],
        sys.argv[4],
        sys.argv[5],
        sys.argv[6],
        sys.argv[7])
