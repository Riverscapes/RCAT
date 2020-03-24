#----------------------------------------------------------------------------#
# Title: LANDFIRE RCAT Fields                                                #
# Purpose: Adds "CONVERSION" field to LANDFIRE EVT & BPS rasters for input   #
#            into RVD tool, adds "LU_CODE" to LANDFIRE EVT for input into    #
#            RCA tool, and adds "VEGETATED" field to EVT & BPS for input RCA #
# Note: This tool was developed based on the field names and categories we   #
#            commonly encounter in the 2014 LANDFIRE data. Given that these  #
#            categories will change with new LANDFIRE data, it is HIGHLY     #
#            recommended that you manually go through these fields after     #
#            running the tool and double check that everything makes sense!  #
#            If you do notice any categories missing, please add them into   #
#            the code so they aren't missed in future runs!                  #
#                                                                            #
# Author: Maggie Hallerud maggie.hallerud@aggiemail.usu.edu                  #
# Date: 27 Feb 2020                                                          #
#----------------------------------------------------------------------------#


# load dependencies
import arcpy
import os


def main(ex_veg, hist_veg):
    # set up environment
    arcpy.env.workspace = 'in_memory'
    arcpy.env.overwriteOutput = True
    
    # add "CONVERSION" field to both rasters
    add_conversion_field(ex_veg, hist_veg)
    # add "LU_CODE" field to existing vegetation raster
    add_lui_field(ex_veg)
    # add "VEGETATED" field to both raster
    add_vegetated_field(ex_veg, hist_veg)


def add_conversion_field(ex_veg, hist_veg):
    # add "CONVERSION" field to existing vegetation raster
    ex_field = arcpy.ListFields(ex_veg, "CONVERSION")
    if len(ex_field) is not 1:
        arcpy.AddField_management(ex_veg, "CONVERSION", "DOUBLE")

    with arcpy.da.UpdateCursor(ex_veg, ["EVT_PHYS", "EVT_GP_N", "CONVERSION"]) as cursor:
        for row in cursor:
            if row[0] == "Open Water":
                row[2] = 500
            elif row[0] == "Non-vegetated":
                row[2] = 40
            elif row[0] == "Snow-Ice":
                row[2] = 40
            elif row[0] == "Developed":
                row[2] = 2
            elif row[0] == "Developed-Low Intensity":
                row[2] = 2
            elif row[0] == "Developed-Medium Intensity":
                row[2] = 2
            elif row[0] == "Developed-High Intensity":
                row[2] = 2
            elif row[0] == "Developed-Roads":
                row[2] = 2
            elif row[0] == "Barren":
                row[2] = 40
            elif row[0] == "Quarries-Strip Mines-Gravel Pits":
                row[2] = 2
            elif row[0] == "Agricultural":
                row[2] = 1
            elif row[0] == "Grassland":
                row[2] = 50
            elif row[0] == "Hardwood":
                row[2] = 100
            elif row[0] == "Shrubland":
                row[2] = 50
            elif row[0] == "Conifer-Hardwood":
                row[2] = 20
            elif row[0] == "Conifer":
                row[2] = 20
            elif row[0] == "Riparian":
                row[2] = 100
            elif row[0] == "Sparsely Vegetated":
                row[2] = 40
            elif row[0] == "Exotic Tree-Shrub":
                row[2] = 3
            elif row[0] == "Exotic Herbaceous":
                row[2] = 3
            elif row[1] == "708": # introduced woody wetland vegetation
                row[2] = 3
            elif row[1] == "707": # introduced upland vegetation- treed
                row[2] = 3
            elif row[1] == "706": # introduced upland vegetation - shrub
                row[2] = 3
            elif row[1] == "703": # introduced perennial grassland and forbland 
                row[2] = 3
            else:
                row[2] = -9999 #NoData value
            cursor.updateRow(row)

    # add "CONVERSION" field to historic vegetation raster
    hist_field = arcpy.ListFields(hist_veg, "CONVERSION")
    if len(hist_field) is not 1:
        arcpy.AddField_management(hist_veg, "CONVERSION", "DOUBLE")

    with arcpy.da.UpdateCursor(hist_veg, ["GROUPVEG", "CONVERSION"]) as cursor:
        for row in cursor:
            if row[0] == "Riparian":
                row[1] = 100
            elif row[0] == "Open Water":
                row[1] = 500
            elif row[0] == "Perennial Ice/Snow":
                row[1] = 40
            elif row[0] == "Barren-Rock/Sand/Clay":
                row[1] = 40
            elif row[0] == "Sparse":
                row[1] = 40
            elif row[0] == "Hardwood":
                row[1] = 100
            elif row[0] == "Conifer":
                row[1] = 20
            elif row[0] == "Shrubland":
                row[1] = 50
            elif row[0] == "Hardwood-Conifer" or row[0] == "Conifer-Hardwood":
                row[1] = 20
            elif row[0] == "Grassland":
                row[1] = 50
            else:
                row[1] = -9999 #NoData value
            cursor.updateRow(row)


def add_lui_field(ex_veg):
    luDict = {
        "Agricultural-Aquaculture": 0.66,
        "Agricultural-Bush fruit and berries": 0.66,
        "Agricultural-Close Grown Crop": 0.66,
        "Agricultural-Fallow/Idle Cropland": 0.33,
        "Agricultural-Orchard": 0.66,
        "Agricultural-Pasture and Hayland": 0.33,
        "Agricultural-Row Crop": 0.66,
        "Agricultural-Row Crop-Close Grown Crop": 0.66,
        "Agricultural-Vineyard": 0.66,
        "Agricultural-Wheat": 0.66,
        "Developed-High Intensity": 1.0,
        "Developed-Medium Intensity": 1.0,
        "Developed-Low Intensity": 1.0,
        "Developed-Roads": 1.0,
        "Developed-Upland Deciduous Forest": 1.0,
        "Developed-Upland Evergreen Forest": 1.0,
        "Developed-Upland Herbaceous": 1.0,
        "Developed-Upland Mixed Forest": 1.0,
        "Developed-Upland Shrubland": 1.0,
        "Managed Tree Plantation - Northern and Central Hardwood and Conifer Plantation Group": 0.66,
        "Managed Tree Plantation - Southeast Conifer and Hardwood Plantation Group": 0.66,
        "Quarries-Strip Mines-Gravel Pits": 1.0
    }
    
    fields = arcpy.ListFields(ex_veg)
    if "LU_CODE" not in fields:
        arcpy.AddField_management(ex_veg, "LU_CODE", "DOUBLE")
    if "LUI_Class" not in fields:
        arcpy.AddField_management(ex_veg, "LUI_Class", "TEXT", 10)
    with arcpy.da.UpdateCursor(ex_veg, ["EVT_GP_N", "LU_CODE", "LUI_Class"]) as cursor:
        for row in cursor:
            keyName = row[0]
            if keyName in luDict:
                row[1] = luDict[keyName]
            else:
                row[1] = 0.0
            if row[1] >= 1.0:
                row[2] = 'High'
            elif row[1] <= 0.0:
                row[2] = 'VeryLow'
            elif row[1] <= 0.33:
                row[2] = 'Low'
            else:
                row[2] = 'Moderate'
            cursor.updateRow(row)


def add_vegetated_field(ex_veg, hist_veg):
    # add "VEGETATED" field to existing vegetation raster
    ex_field = arcpy.ListFields(ex_veg, "VEGETATED")
    if len(ex_field) is not 1:
        arcpy.AddField_management(ex_veg, "VEGETATED", "SHORT")

    with arcpy.da.UpdateCursor(ex_veg, ["EVT_PHYS", "VEGETATED"]) as cursor:
        for row in cursor:
            if row[0] == "Open Water":
                row[1] = 0
            elif row[0] == "Non-vegetated":
                row[1] = 0
            elif row[0] == "Snow-Ice":
                row[1] = 0
            elif row[0] == "Developed-Low Intensity":
                row[1] = 0
            elif row[0] == "Developed-Medium Intensity":
                row[1] = 0
            elif row[0] == "Developed-High Intensity":
                row[1] = 0
            elif row[0] == "Developed-Roads":
                row[1] = 0
            elif row[0] == "Barren":
                row[1] = 0
            elif row[0] == "Quarries-Strip Mines-Gravel Pits":
                row[1] = 0
            elif row[0] == "Quarries-Strip Mines-Gravel Pits-Well and Wind Pads":
                row[1] = 0
            elif row[0] == "Agricultural":
                row[1] = 0
            elif row[0] == "Exotic Herbaceous":
                row[1] = 0
            elif row[0] == "Exotic Tree-Shrub":
                row[0] = 0
            else:
                row[1] = 1
            cursor.updateRow(row)

    # add "VEGETATED" field to historic vegetation raster
    hist_field = arcpy.ListFields(hist_veg, "VEGETATED")
    if len(hist_field) is not 1:
        arcpy.AddField_management(hist_veg, "VEGETATED", "SHORT")

    with arcpy.da.UpdateCursor(hist_veg, ["GROUPVEG", "VEGETATED"]) as cursor:
        for row in cursor:
            if row[0] == "Open Water":
                row[1] = 0
            elif row[0] == "Perrennial Ice/Snow":
                row[1] = 0
            elif row[0] == "Barren-Rock/Sand/Clay":
                row[1] = 0
            elif row[0] == "Sparse":
                row[1] = 0
            else:
                row[1] = 1
            cursor.updateRow(row)

    
if __name__  == "__main__":
    main()
