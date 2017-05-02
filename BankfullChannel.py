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
        min_width,
        percent_buf,
        scratch):

    arcpy.env.overwriteOutput = True
    arcpy.CheckOutExtension("spatial")

    # input checks
    networkSR = arcpy.Describe(network).spatialReference
    if networkSR.type == "Projected":
        pass
    else:
        raise Exception("Input stream network must have a projected coordinate system")

    precipSR = arcpy.Describe(precip).spatialReference
    if precipSR.type == "Projected":
        pass
    else:
        raise Exception("Input precip vector data must have a projected coordinate system")

    lfprecip = arcpy.ListFields(precip, "Inches")
    if len(lfprecip) != 1:
        raise Exception("Input precip vector must have field 'Inches'")

    network_fields = [f.name for f in arcpy.ListFields(network)]
    if "OBJECTID" in network_fields:
        raise Exception("Input stream network cannot not have field 'OBJECTID' (use shapefile)")

    # create a midpoint buffer for each network segment.  This is analysis area for zonal stats.
    midpoints = scratch + "/midoints"
    arcpy.FeatureVerticesToPoints_management(network, midpoints, "MID")
    midpoint_fields = [f.name for f in arcpy.ListFields(midpoints)]
    midpoint_fields.remove("OBJECTID")
    midpoint_fields.remove("Shape")
    midpoint_fields.remove("ORIG_FID")
    arcpy.DeleteField_management(midpoints, midpoint_fields)
    mp_buffer = scratch + "/mp_buffer"
    arcpy.Buffer_analysis(midpoints, mp_buffer, "100 Meters", "", "", "LIST", "ORIG_FID")

    # generate precip raster in cm
    lfprecip2 = arcpy.ListFields(precip, "CM")
    if lfprecip2 != 0:
        arcpy.DeleteField_management(precip, "CM")
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
    arcpy.AddMessage("Adding precipitation and drainage area values to network")
    precipandda(mp_buffer, drarea, precip_cm, network)

    # add the bankfull width and buffer width to network.
    arcpy.AddMessage("Adding bankfull width value to network")
    if percent_buf == None:
        addbufwidth(network, min_width)
    else:
        addpercentbufwidth(network, min_width, percent_buf)

    # generate the bankfull polygon
    arcpy.AddMessage("Generating bankfull polygon")
    createbankfullpolygon(network, output, scratch)

    arcpy.CheckInExtension("spatial")


def precipandda(mp_buffer, drarea, precip_cm, network):
    """pull precip and da values on to network"""

    drarea_zs = ZonalStatisticsAsTable(mp_buffer, "ORIG_FID", drarea, "da_table", statistics_type="MAXIMUM")
    arcpy.JoinField_management(network, "FID", drarea_zs, "ORIG_FID", "MAX")
    lf = arcpy.ListFields(network, "DA_sqkm")
    if len(lf) != 0:
        arcpy.DeleteField_management(network, "DA_sqkm")

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
    if len(lf) != 0:
        arcpy.DeleteField_management(network, "Precip")

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


def addpercentbufwidth(network, min_width, percent_buf):
    """add the bankfull width and buffer width to the network with a percent buffer"""

    lf = arcpy.ListFields(network, "BFWIDTH")
    if len(lf) != 0:
        arcpy.DeleteField_management(network, "BFWIDTH")
    arcpy.AddField_management(network, "BFWIDTH", "FLOAT")
    cursor = arcpy.da.UpdateCursor(network, ["DA_sqkm", "Precip", "BFWIDTH"])
    for row in cursor:
        index = 0.177*(pow(row[0],0.397)*pow(row[1],0.453))
        row[2] = index
        cursor.updateRow(row)
        if row[2] < float(min_width):
            row[2] = float(min_width)
        cursor.updateRow(row)
    del row
    del cursor

    lf2 = arcpy.ListFields(network, "BUFWIDTH")
    if len(lf2) != 0:
        arcpy.DeleteField_management(network, "BUFWIDTH")
    arcpy.AddField_management(network, "BUFWIDTH", "DOUBLE")
    cursor = arcpy.da.UpdateCursor(network, ["BFWIDTH", "BUFWIDTH"])
    for row in cursor:
        index2 = row[0]/2 + ((row[0]/2) * (float(percent_buf)/100))
        row[1] = index2
        cursor.updateRow(row)
    del row
    del cursor


def addbufwidth(network, min_width):
    """add the bankfull width and buffer width to the network without a percent buffer"""

    lf = arcpy.ListFields(network, "BFWIDTH")
    if len(lf) != 0:
        arcpy.DeleteField_management(network, "BFWIDTH")
    arcpy.AddField_management(network, "BFWIDTH", "FLOAT")
    cursor = arcpy.da.UpdateCursor(network, ["DA_sqkm", "Precip", "BFWIDTH"])
    for row in cursor:
        index = 0.177*(pow(row[0],0.397)*pow(row[1],0.453))
        row[2] = index
        cursor.updateRow(row)
        if row[2] < float(min_width):
            row[2] = float(min_width)
        cursor.updateRow(row)
    del row
    del cursor

    lf2 = arcpy.ListFields(network, "BUFWIDTH")
    if len(lf2) != 0:
        arcpy.DeleteField_management(network, "BUFWIDTH")
    arcpy.AddField_management(network, "BUFWIDTH", "DOUBLE")
    cursor = arcpy.da.UpdateCursor(network, ["BFWIDTH", "BUFWIDTH"])
    for row in cursor:
        index2 = row[0]/2
        row[1] = index2
        cursor.updateRow(row)
    del row
    del cursor


def createbankfullpolygon(network, output, scratch):
    """generate the bankfull channel polygon"""

    bankfull = scratch + "/bankfull"
    arcpy.Buffer_analysis(network, bankfull, "BUFWIDTH", "FULL", "ROUND", "ALL")

    arcpy.SmoothPolygon_cartography(bankfull, output, "PAEK", "10 METERS")


if __name__ == '__main__':

    main(sys.argv[1],
         sys.argv[2],
         sys.argv[3],
         sys.argv[4],
         sys.argv[5],
         sys.argv[6],
         sys.argv[7])
