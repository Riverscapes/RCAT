# -------------------------------------------------------------------------------
# Name:        RCAT Project Builder
# Purpose:     Gathers and structures the inputs for an RCAT project
#              
# Author:      Jordan Gilbert
#
# Created:     09/25/2015
# Latest Update: 03/20/2017
# Copyright:   (c) Jordan Gilbert 2017
# Licence:     This work is licensed under the Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International
#              License. To view a copy of this license, visit http://creativecommons.org/licenses/by-nc-sa/4.0/.
# -------------------------------------------------------------------------------

# import modules
import os
import glob
import arcpy
import shutil
import sys
import string
from SupportingFunctions import make_folder, find_available_num_prefix


def main(projPath, network, ex_cov, hist_cov, frag_valley, lrp, dredge_tailings, dem, precip):
    """Creates an RCA project folder and populates the inputs
    :param projPath: Project folder where RCAT inputs and outputs will be stored
    :param network: Segmented stream network shapefile
    :param ex_cov: Folder holding existing landcover raster
    :param hist_cov: Folder holding historic landcover raster
    :param frag_valley: Fragmented valley bottom shapefile
    :param lrp: Large river polygons shapefile
    :param dredge_tailings: Dredge tailing polygons shapefile
    :param dem: Elevation raster (in m)
    :param precip: Precipitation raster (in mm)
    return: RCAT project structure
    """
    # clean up inputs
    if lrp == "None":
        lrp = None
    if dredge_tailings == "None":
        dredge_tailings = None
    if dem == "None":
        dem = None
    if precip == "None":
        precip = None

    # set environment parameters
    arcpy.env.overwriteOutput = True

    # set up main project folder
    make_folder(projPath)
    if os.getcwd() is not projPath:
        os.chdir(projPath)
    set_structure(projPath, lrp, dredge_tailings, dem, precip)

    # add the network inputs to project
    innetwork = network.split(";")
    os.chdir(projPath + "/Inputs/01_Network/")
    i = 1
    for x in range(len(innetwork)):
        make_folder("Network_" + str(i))
        arcpy.CopyFeatures_management(innetwork[x], "Network_" + str(i) + "/" + os.path.basename(innetwork[x]))
        i += 1
        
    # add the existing veg inputs to project
    inex_cov = ex_cov.split(";")
    os.chdir(projPath + "/Inputs/02_Existing_Vegetation/")
    i = 1
    for x in range(len(inex_cov)):
        if not os.path.exists("Ex_Veg_" + str(i)):
            src = string.replace(inex_cov[x], "'", "")
            shutil.copytree(src, "Ex_Veg_" + str(i))
        i += 1

    # add the historic veg inputs to project
    inhist_cov = hist_cov.split(";")
    os.chdir(projPath + "/Inputs/03_Historic_Vegetation/")
    i = 1
    for x in range(len(inhist_cov)):
        if not os.path.exists("Hist_Veg_" + str(i)):
            src = string.replace(inhist_cov[x], "'", "")
            shutil.copytree(src, "Hist_Veg_" + str(i))
        i += 1


    # add the valley inputs to the project
    infragvalley = frag_valley.split(";")
    os.chdir(projPath + "/Inputs/04_Fragmented_Valley/")
    i = 1
    for x in range(len(infragvalley)):
        make_folder("Frag_Valley_" + str(i))
        arcpy.CopyFeatures_management(infragvalley[x], "Frag_Valley_" + str(i) + "/" + os.path.basename(infragvalley[x]))
        i += 1

    # add the large river polygons to the project
    if lrp is not None:
        inlrp = lrp.split(";")
        folders = glob.glob(projPath + "/Inputs/05_Large_River_Polygon/")
        os.chdir(folders[-1])
        i = 1
        for x in range(len(inlrp)):
            make_folder("LRP_" + str(i))
            arcpy.CopyFeatures_management(inlrp[x], "LRP_" + str(i) + "/" + os.path.basename(inlrp[x]))
            i += 1
    else:
        pass

    # add the dredge tailings polygons to the project
    if dredge_tailings is not None:
        indredge_tailings = dredge_tailings.split(";")
        folders = glob.glob(projPath + "/Inputs/0*_Dredge_Tailings/")
        os.chdir(folders[-1])
        i = 1
        for x in range(len(indredge_tailings)):
            make_folder("DredgeTailings_" + str(i))
            arcpy.CopyFeatures_management(indredge_tailings[x], "DredgeTailings_" + str(i) + "/" + os.path.basename(indredge_tailings[x]))
            i += 1
    else:
        pass

    # add the dem raster to the project
    if dem is not None:
        indems = dem.split(";")
        folders = glob.glob(projPath + "/Inputs/0*_Topography/")
        os.chdir(folders[-1])
        i = 1
        for x in range(len(indems)):
            make_folder("DEM_" + str(i))
            arcpy.CopyRaster_management(indems[x], os.path.join(os.getcwd(), "DEM_"+str(i), os.path.basename(indems[x])))
            i += 1
    else:
        pass

    # add the precip raster to the project
    if precip is not None:
        inprecips = precip.split(";")
        folders = glob.glob(projPath + "/Inputs/0*_Precipitation/")
        os.chdir(folders[-1])
        i = 1
        for x in range(len(inprecips)):
            make_folder("Precip_" + str(i))
            arcpy.CopyRaster_management(inprecips[x], os.path.join(os.getcwd(), "Precip_"+str(i), os.path.basename(inprecips[x])))
            i += 1
    else:
        pass


def set_structure(projPath, lrp, dredge_tailings, dem, precip):
    """Sets up the folder structure for an RVD project"""

    make_folder(projPath)

    if os.getcwd() is not projPath:
        os.chdir(projPath)

    inputs = os.path.join(projPath, "Inputs")
    make_folder(inputs)
    os.chdir(inputs)
    
    make_folder("01_Network")
    make_folder("02_Existing_Vegetation")
    make_folder("03_Historic_Vegetation")
    make_folder("04_Fragmented_Valley")
    if lrp is not None:
        make_folder(find_available_num_prefix(inputs) + "_Large_River_Polygon")
    if dredge_tailings is not None:
        make_folder(find_available_num_prefix(inputs) + "_Dredge_Tailings")
    if dem is not None:
        make_folder(find_available_num_prefix(inputs) + "_Topography")
    if precip is not None:
        make_folder(find_available_num_prefix(inputs) + "_Precipitation")


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
        sys.argv[9])
