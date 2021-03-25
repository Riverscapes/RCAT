#-------------------------------------------------------------------------------
# Name:        Fragmenter.py
# Purpose:     Fragments the Valley Bottom by any inputs
# Author:      Tyler Hatch
#
# Created:     3/21/21
#-------------------------------------------------------------------------------

# Import modules
import arcpy
import sys
import os


def main(valley_bottom, streams, fragmenters, out_folder):

    # Set environment variables
    arcpy.env.overwriteOutput = True
    arcpy.env.workspace = out_folder

    # Copy Valley Bottom
    valley_copy = arcpy.CopyFeatures_management(valley_bottom, "Valley_Copy.shp")

    # Merge all fragmenters
    fragmenters_merge = arcpy.Merge_management(fragmenters, "All_Fragmenters.shp")

    # Convert everything to a cut polygon
    mesh = arcpy.FeatureToPolygon_management([valley_copy, fragmenters_merge], 'Polygon_Mesh.shp')

    # Clip that polygon with the orginal VB
    new_valley = arcpy.Clip_analysis(mesh, valley_copy, "Prelim_Clip.shp")

    # Add Connected field
    try:
        arcpy.management.DeleteField(new_valley, 'Connected')
    except: 
        pass
    arcpy.AddField_management(new_valley, 'Connected', 'SHORT')

    # Select all streams where network touches, set connected to 1
    valley_layer = arcpy.MakeFeatureLayer_management(new_valley, "valley_layer")
    arcpy.SelectLayerByLocation_management(valley_layer, 'intersect', streams)
    arcpy.CalculateField_management(valley_layer, "Connected", "1", "PYTHON_9.3")

    # Invert selection
    arcpy.SelectLayerByAttribute_management(valley_layer, "SWITCH_SELECTION", "")

    # Set remaining streams to zero
    arcpy.CalculateField_management(valley_layer, "Connected", "0", "PYTHON_9.3")
    arcpy.SelectLayerByAttribute_management(valley_layer, "CLEAR_SELECTION", "")
    arcpy.CopyFeatures_management(valley_layer, "PrelimFragVB.shp")
    
    # Delete Temperary Shapefiles
    for shape in [valley_copy, fragmenters_merge, mesh, new_valley]:
        try:
            arcpy.management.Delete(shape)
        except:
            pass


if __name__ == '__main__':
    main(sys.argv[1],
        sys.argv[2],
        sys.argv[3],
        sys.argv[4])
