# import modules
import os
import arcpy
import shutil
import sys
import string


def main(projPath, ex_veg, hist_veg, network, valley, lrp):
    """Create an RVD project and populate the inputs"""

    arcpy.env.overwriteOutput = True

    if not os.path.exists(projPath):
        os.mkdir(projPath)

    if os.getcwd() is not projPath:
        os.chdir(projPath)

    set_structure(projPath)

    # add the existing veg inputs to project
    inex_veg = ex_veg.split(";")
    os.chdir(projPath + "/01_Inputs/01_Ex_Veg/")
    i = 1
    for x in range(len(inex_veg)):
        if not os.path.exists("Ex_Veg_" + str(i)):
            os.mkdir("Ex_Veg_" + str(i))
        if not os.path.exists("Ex_Veg_" + str(i) + "/" + os.path.basename(inex_veg[x])):
            src = string.replace(inex_veg[x], "'", "")
            shutil.copytree(src, "Ex_Veg_" + str(i) + "/" + os.path.basename(inex_veg[x]))
        i += 1

    # add the historic veg inputs to project
    inhist_veg = hist_veg.split(";")
    os.chdir(projPath + "/01_Inputs/02_Hist_Veg/")
    i = 1
    for x in range(len(inhist_veg)):
        if not os.path.exists("Hist_Veg_" + str(i)):
            os.mkdir("Hist_Veg_" + str(i))
        if not os.path.exists("Hist_Veg_" + str(i) + "/" + os.path.basename(inhist_veg[x])):
            src = string.replace(inhist_veg[x], "'", "")
            shutil.copytree(src, "Hist_Veg_" + str(i) + "/" + os.path.basename(inhist_veg[x]))
        i += 1

    # add the network inputs to project
    innetwork = network.split(";")
    os.chdir(projPath + "/01_Inputs/03_Network/")
    i = 1
    for x in range(len(innetwork)):
        if not os.path.exists("Network_" + str(i)):
            os.mkdir("Network_" + str(i))
        arcpy.Copy_management(innetwork[x], "Network_" + str(i) + "/" + os.path.basename(innetwork[x]))
        i += 1

    # add the valley inputs to the project
    invalley = valley.split(";")
    os.chdir(projPath + "/01_Inputs/04_Valley/")
    i = 1
    for x in range(len(invalley)):
        if not os.path.exists("Valley_" + str(i)):
            os.mkdir("Valley_" + str(i))
        arcpy.Copy_management(invalley[x], "Valley_" + str(i) + "/" + os.path.basename(invalley[x]))
        i += 1

    # add the large river polygons to the project
    if lrp is not None:
        inlrp = lrp.split(";")
        os.chdir(projPath + "/01_Inputs/05_LRP/")
        i = 1
        for x in range(len(inlrp)):
            if not os.path.exists("LRP_" + str(i)):
                os.mkdir("LRP_" + str(i))
            arcpy.Copy_management(inlrp[x], "LRP_" + str(i) + "/" + os.path.basename(inlrp[x]))
            i += 1
    else:
        pass


def set_structure(projPath):
    """Sets up the folder structure for an RVD project"""

    if not os.path.exists(projPath):
        os.mkdir(projPath)

    if os.getcwd() is not projPath:
        os.chdir(projPath)

    if not os.path.exists("01_Inputs"):
        os.mkdir("01_Inputs")
    if not os.path.exists("02_Analyses"):
        os.mkdir("02_Analyses")
    os.chdir("01_Inputs")
    if not os.path.exists("01_Ex_Veg"):
        os.mkdir("01_Ex_Veg")
    if not os.path.exists("02_Hist_Veg"):
        os.mkdir("02_Hist_Veg")
    if not os.path.exists("03_Network"):
        os.mkdir("03_Network")
    if not os.path.exists("04_Valley"):
        os.mkdir("04_Valley")
    if not os.path.exists("05_LRP"):
        os.mkdir("05_LRP")

if __name__ == '__main__':
    main(
        sys.argv[1],
        sys.argv[2],
        sys.argv[3],
        sys.argv[4],
        sys.argv[5],
        sys.argv[6])
