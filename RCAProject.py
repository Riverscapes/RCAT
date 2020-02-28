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


def main(projPath, ex_cov, hist_cov, network, frag_valley, lrp, dredge_tailings):
    """Create an RCA project and populate the inputs"""

    arcpy.env.overwriteOutput = True

    if not os.path.exists(projPath):
        os.mkdir(projPath)

    if os.getcwd() is not projPath:
        os.chdir(projPath)

    set_structure(projPath, lrp, dredge_tailings)

    # add the existing veg inputs to project
    inex_cov = ex_cov.split(";")
    os.chdir(projPath + "/Inputs/01_Ex_Cov/")
    i = 1
    for x in range(len(inex_cov)):
        if not os.path.exists("Ex_Cov_" + str(i)):
            os.mkdir("Ex_Cov_" + str(i))
        if not os.path.exists("Ex_Cov_" + str(i) + "/" + os.path.basename(inex_cov[x])):
            src = string.replace(inex_cov[x], "'", "")
            shutil.copytree(src, "Ex_Cov_" + str(i) + "/" + os.path.basename(inex_cov[x]))
        i += 1

    # add the historic veg inputs to project
    inhist_cov = hist_cov.split(";")
    os.chdir(projPath + "/Inputs/02_Hist_Cov/")
    i = 1
    for x in range(len(inhist_cov)):
        if not os.path.exists("Hist_Cov_" + str(i)):
            os.mkdir("Hist_Cov_" + str(i))
        if not os.path.exists("Hist_Cov_" + str(i) + "/" + os.path.basename(inhist_cov[x])):
            src = string.replace(inhist_cov[x], "'", "")
            shutil.copytree(src, "Hist_Cov_" + str(i) + "/" + os.path.basename(inhist_cov[x]))
        i += 1

    # add the network inputs to project
    innetwork = network.split(";")
    os.chdir(projPath + "/Inputs/03_Network/")
    i = 1
    for x in range(len(innetwork)):
        if not os.path.exists("Network_" + str(i)):
            os.mkdir("Network_" + str(i))
        arcpy.CopyFeatures_management(innetwork[x], "Network_" + str(i) + "/" + os.path.basename(innetwork[x]))
        i += 1

    # add the valley inputs to the project
    infragvalley = frag_valley.split(";")
    os.chdir(projPath + "/Inputs/04_Frag_Valley/")
    i = 1
    for x in range(len(infragvalley)):
        if not os.path.exists("Frag_Valley_" + str(i)):
            os.mkdir("Frag_Valley_" + str(i))
        arcpy.CopyFeatures_management(infragvalley[x], "Frag_Valley_" + str(i) + "/" + os.path.basename(infragvalley[x]))
        i += 1

    # add the large river polygons to the project
    if lrp is not None:
        inlrp = lrp.split(";")
        os.chdir(projPath + "/Inputs/05_LRP/")
        i = 1
        for x in range(len(inlrp)):
            if not os.path.exists("LRP_" + str(i)):
                os.mkdir("LRP_" + str(i))
            arcpy.CopyFeatures_management(inlrp[x], "LRP_" + str(i) + "/" + os.path.basename(inlrp[x]))
            i += 1
    else:
        pass

    # add the dredge tailings polygons to the project
    if dredge_tailings is not None:
        indredge_tailings = dredge_tailings.split(";")
        folders = glob.glob(projPath + "/Inputs/0*_DredgeTailings/")
        os.chdir(folders[0])
        i = 1
        for x in range(len(indredge_tailings)):
            if not os.path.exists("DredgeTailings_" + str(i)):
                os.mkdir("DredgeTailings_" + str(i))
            arcpy.CopyFeatures_management(indredge_tailings[x], "DredgeTailings_" + str(i) + "/" + os.path.basename(indredge_tailings[x]))
            i += 1
    else:
        pass

def set_structure(projPath, lrp, dredge_tailings):
    """Sets up the folder structure for an RVD project"""

    if not os.path.exists(projPath):
        os.mkdir(projPath)

    if os.getcwd() is not projPath:
        os.chdir(projPath)

    if not os.path.exists("Inputs"):
        os.mkdir("Inputs")
    os.chdir("Inputs")
    if not os.path.exists("01_Ex_Cov"):
        os.mkdir("01_Ex_Cov")
    if not os.path.exists("02_Hist_Cov"):
        os.mkdir("02_Hist_Cov")
    if not os.path.exists("03_Network"):
        os.mkdir("03_Network")
    if not os.path.exists("04_Frag_Valley"):
        os.mkdir("04_Frag_Valley")
    if lrp is not None:
        if not os.path.exists("05_LRP"):
            os.mkdir("05_LRP")
        if dredge_tailings is not None:
            if not os.path.exists("06_Dredge_Tailings"):
                os.mkdir("06_DredgeTailings")
    else:
        if dredge_tailings is not None:
            if not os.path.exists("06_Dredge_Tailings"):
                os.mkdir("06_Dredge_Tailings")
        else:
            pass


if __name__ == '__main__':
    main(
        sys.argv[1],
        sys.argv[2],
        sys.argv[3],
        sys.argv[4],
        sys.argv[5],
        sys.argv[6],
        sys.argv[7])
