#-------------------------------------------------------------------------------
# Name:        NHD Network Builder
# Purpose:     Creates a subset of an NHD flowline network based on
#              a set of selected attributes
# Author:      Jordan Gilbert
#
# Created:     25/09/2015
# Copyright:   (c) Jordan Gilbert 2015
# Licence:     <your licence>
#-------------------------------------------------------------------------------

#import modules
import arcpy
import sys


def main(
    inFlowline,
    inWaterbody,
    inArea,
    ap_fix,
    subsize,
    boolArtPath,
    boolCanal,
    boolAqueduct,
    boolStormwater,
    boolConnector,
    boolStream,
    boolIntermittent,
    boolPerennial,
    boolEphemeral,
    outFC,
    projection,
    scratch = arcpy.env.scratchWorkspace):

    arcpy.env.overwriteOutput = True

    pFlowline = scratch + "/pFlowline.shp"
    pWaterbody = scratch + "/pWaterbody.shp"
    pArea = scratch + "/pArea.shp"
    arcpy.Project_management(inFlowline, pFlowline, projection)
    if inWaterbody is not None:
        arcpy.Project_management(inWaterbody, pWaterbody, projection)
    else:
        pass
    if inArea is not None:
        arcpy.Project_management(inArea, pArea, projection)
    else:
        pass

    arcpy.AddMessage("Splitting the flowline into components")
    #extract canals
    canal = scratch + "/canal.shp"
    aqueduct = scratch + "/aqueduct.shp"
    stormwater = scratch + "/stormwater.shp"
    arcpy.Select_analysis(pFlowline, canal, '"FCode" = 33600')
    arcpy.Select_analysis(pFlowline, aqueduct, '"FCode" = 33601')
    arcpy.Select_analysis(pFlowline, stormwater, '"FCode" = 33603')

    #extract streams
    streams = scratch + "/streams.shp"
    intermittent = scratch + "/intermittent.shp"
    perennial = scratch + "/perennial.shp"
    ephemeral = scratch + "/ephemeral.shp"
    arcpy.Select_analysis(pFlowline, streams, '"FCode" = 46000')
    arcpy.Select_analysis(pFlowline, intermittent, '"FCode" = 46003')
    arcpy.Select_analysis(pFlowline, perennial, '"FCode" = 46006')
    arcpy.Select_analysis(pFlowline, ephemeral, '"FCode" = 46007')

    #extract connectors
    connector = scratch + "/connector.shp"
    final_connector = scratch + "/final_connector.shp"
    arcpy.Select_analysis(pFlowline, connector, '"FCode" = 33400')
    arcpy.MakeFeatureLayer_management(connector, "connector_lyr")
    arcpy.SelectLayerByLocation_management("connector_lyr", "INTERSECT", perennial)
    arcpy.CopyFeatures_management("connector_lyr", final_connector)

    #artificial path selection
    if str(ap_fix) == "true":

        arcpy.AddMessage("Subsetting the artificial paths")
        #subset waterbodies to specified threshold
        lg_waterbodies = scratch + "/lg_waterbodies.shp"
        where_clause = '"AreaSqKm" > {0}'.format(subsize)
        arcpy.Select_analysis(pWaterbody, lg_waterbodies, where_clause)

        #extract artificial path from flowline
        art_path = scratch + "/art_path.shp"
        arcpy.Select_analysis(pFlowline, art_path, '"FCode" = 55800')

        #remove undesired portions of artificial path network
        art_path_ftl = scratch + "/art_path_ftl.shp"
        final_art_path = scratch + "/final_art_path.shp"
        arcpy.FeatureToLine_management([lg_waterbodies, art_path], art_path_ftl)

        permCursor = arcpy.da.UpdateCursor(art_path_ftl, ["PERMANENT_", "PERMANENT1"])
        for row in permCursor:
            row[0] = row[1]
            permCursor.updateRow(row)
        del permCursor
        del row

        fdateCursor = arcpy.da.UpdateCursor(art_path_ftl, ["FDATE", "FDATE_1"])
        for row in fdateCursor:
            row[0] = row[1]
            fdateCursor.updateRow(row)
        del fdateCursor
        del row

        resCursor = arcpy.da.UpdateCursor(art_path_ftl, ["RESOLUTION", "RESOLUTI_1"])
        for row in resCursor:
            row[0] = row[1]
            resCursor.updateRow(row)
        del resCursor
        del row

        idCursor = arcpy.da.UpdateCursor(art_path_ftl, ["GNIS_ID", "GNIS_ID_1"])
        for row in idCursor:
            row[0] = row[1]
            idCursor.updateRow(row)
        del idCursor
        del row

        nameCursor = arcpy.da.UpdateCursor(art_path_ftl, ["GNIS_NAME", "GNIS_NAM_1"])
        for row in nameCursor:
            row[0] = row[1]
            nameCursor.updateRow(row)
        del nameCursor
        del row

        reachCursor = arcpy.da.UpdateCursor(art_path_ftl, ["REACHCODE", "REACHCOD_1"])
        for row in reachCursor:
            row[0] = row[1]
            reachCursor.updateRow(row)
        del reachCursor
        del row

        ftypeCursor = arcpy.da.UpdateCursor(art_path_ftl, ["FTYPE", "FTYPE_1"])
        for row in ftypeCursor:
            row[0] = row[1]
            ftypeCursor.updateRow(row)
        del ftypeCursor
        del row

        fcodeCursor = arcpy.da.UpdateCursor(art_path_ftl, ["FCODE", "FCODE_1"])
        for row in fcodeCursor:
            row[0] = row[1]
            fcodeCursor.updateRow(row)
        del fcodeCursor
        del row

        arcpy.DeleteField_management(art_path_ftl, ["FID_lg_wat", "FID_art_pa", "PERMANENT1", "FDATE_1", "RESOLUTI_1", "GNIS_ID_1", "GNIS_NAM_1", "REACHCOD_1", "FTYPE_1", "FCODE_1", "SHAPE_LE_1"])

        arcpy.MakeFeatureLayer_management(art_path_ftl, "art_path_ftl_lyr")
        arcpy.SelectLayerByLocation_management("art_path_ftl_lyr", "WITHIN", lg_waterbodies)
        arcpy.DeleteFeatures_management("art_path_ftl_lyr")

        arcpy.SelectLayerByLocation_management("art_path_ftl_lyr", "INTERSECT", pArea, "", "NEW_SELECTION")
        arcpy.SelectLayerByAttribute_management("art_path_ftl_lyr", "REMOVE_FROM_SELECTION", "\"GNIS_NAME\" = ''")
        arcpy.SelectLayerByLocation_management("art_path_ftl_lyr", "WITHIN_A_DISTANCE", perennial, "10 Meters", "ADD_TO_SELECTION")
        arcpy.CopyFeatures_management("art_path_ftl_lyr", final_art_path)

    else:
        final_art_path = scratch + "/final_art_path.shp"
        arcpy.Select_analysis(pFlowline, final_art_path, '"FCode" = 55800')

    #merge extractions to reform complete NHD network
    arcpy.AddMessage("Re-merging flowline components into network")
    complete_NHD = scratch + "/complete_NHD.shp"
    arcpy.Merge_management([final_art_path, canal, aqueduct, stormwater, final_connector, streams, intermittent, perennial, ephemeral], complete_NHD)



    #make the complete NHD network a layer for modifying
    arcpy.AddMessage("Subsetting the network to specifications")

    NHD_subset = scratch + "/NHD_subset.shp"
    arcpy.CopyFeatures_management(complete_NHD, NHD_subset)

    arcpy.MakeFeatureLayer_management(NHD_subset, "NHD_lyr")

    #subset as specified in the parameters
    if str(boolArtPath) == "true":
        arcpy.SelectLayerByAttribute_management("NHD_lyr", "NEW_SELECTION", '"FCode" = 55800')
        arcpy.DeleteFeatures_management("NHD_lyr")

    if str(boolCanal) == "true":
        arcpy.SelectLayerByAttribute_management("NHD_lyr", "NEW_SELECTION", '"FCode" = 33600')
        arcpy.DeleteFeatures_management("NHD_lyr")

    if str(boolAqueduct) == "true":
        arcpy.SelectLayerByAttribute_management("NHD_lyr", "NEW_SELECTION", '"FCode" = 33601')
        arcpy.DeleteFeatures_management("NHD_lyr")

    if str(boolStormwater) == "true":
        arcpy.SelectLayerByAttribute_management("NHD_lyr", "NEW_SELECTION", '"FCode" = 33603')
        arcpy.DeleteFeatures_management("NHD_lyr")

    if str(boolConnector) == "true":
        arcpy.SelectLayerByAttribute_management("NHD_lyr", "NEW_SELECTION", '"FCode" = 33400')
        arcpy.DeleteFeatures_management("NHD_lyr")

    if str(boolStream) == "true":
        arcpy.SelectLayerByAttribute_management("NHD_lyr", "NEW_SELECTION", '"FCode" = 46000')
        arcpy.DeleteFeatures_management("NHD_lyr")

    if str(boolIntermittent) == "true":
        arcpy.SelectLayerByAttribute_management("NHD_lyr", "NEW_SELECTION", '"FCode" = 46003')
        arcpy.DeleteFeatures_management("NHD_lyr")

    if str(boolPerennial) == "true":
        arcpy.SelectLayerByAttribute_management("NHD_lyr", "NEW_SELECTION", '"FCode" = 46006')
        arcpy.DeleteFeatures_management("NHD_lyr")

    if str(boolEphemeral) == "true":
        arcpy.SelectLayerByAttribute_management("NHD_lyr", "NEW_SELECTION", '"FCode" = 46007')
        arcpy.DeleteFeatures_management("NHD_lyr")

    arcpy.CopyFeatures_management("NHD_lyr", outFC)

    # deleting temporary files
    arcpy.Delete_management(scratch + "/aqueduct.shp")
    arcpy.Delete_management(scratch + "/art_path.shp")
    arcpy.Delete_management(scratch + "/art_path_ftl.shp")
    arcpy.Delete_management(scratch + "/canal.shp")
    arcpy.Delete_management(scratch + "/complete_NHD.shp")
    arcpy.Delete_management(scratch + "/connector.shp")
    arcpy.Delete_management(scratch + "/ephemeral.shp")
    arcpy.Delete_management(scratch + "/final_art_path.shp")
    arcpy.Delete_management(scratch + "/intermittent.shp")
    arcpy.Delete_management(scratch + "/lg_waterbodies.shp")
    arcpy.Delete_management(scratch + "/NHD_subset.shp")
    arcpy.Delete_management(scratch + "/pArea.shp")
    arcpy.Delete_management(scratch + "/perennial.shp")
    arcpy.Delete_management(scratch + "/pFlowline.shp")
    arcpy.Delete_management(scratch + "/pWaterbody.shp")
    arcpy.Delete_management(scratch + "/stormwater.shp")
    arcpy.Delete_management(scratch + "/streams.shp")
    arcpy.Delete_management(scratch + "/final_connector.shp")

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
        sys.argv[16])
