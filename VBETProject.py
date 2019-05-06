# -------------------------------------------------------------------------------
# Name:        V-BET Project Builder
# Purpose:     Gathers and structures the inputs for a V-BET project
#              the valley bottom
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
import sys
import arcpy
from arcpy.sa import *
arcpy.CheckOutExtension('Spatial')


def main(projPath, dem, network, drar):
    """Create an RVD project and populate the inputs"""

    arcpy.env.overwriteOutput = True

    if not os.path.exists(projPath):
        os.mkdir(projPath)

    if os.getcwd() is not projPath:
        os.chdir(projPath)

    set_structure(projPath)

    # add the dem inputs to project
    indem = dem.split(";")
    i = 1
    for x in range(len(indem)):
        demDir = os.path.join(projPath, '01_Inputs', '01_Topo', 'DEM_' + str(i))
        if not os.path.exists(os.path.join(demDir)):
            os.mkdir(os.path.join(demDir))
        outdem = os.path.join(demDir, os.path.basename(indem[x]))
        arcpy.CopyRaster_management(indem[x], outdem)
        i += 1

    # add the network inputs to project
    innetwork = network.split(";")
    i = 1
    for x in range(len(innetwork)):
        networkDir = os.path.join(projPath, '01_Inputs', '02_Network', 'Network_' + str(i))
        if not os.path.exists(networkDir):
            os.mkdir(networkDir)
        outnetwork = os.path.join(networkDir, os.path.basename(innetwork[x]))
        arcpy.Copy_management(innetwork[x], outnetwork)
        i += 1

    # add the drainage area raster input if it exists
    if drar is not None:
        indrar = drar.split(";")
        i = 1
        demDir = os.path.join(projPath, '01_Inputs', '01_Topo', 'DEM_' + str(i))
        for x in range(len(indrar)):
            flowDir = os.path.join(demDir, 'Flow')
            if not os.path.exists(flowDir):
                os.mkdir(flowDir)
            outdrar = os.path.join(flowDir, os.path.basename(indrar[x]))
            arcpy.CopyRaster_management(indrar[x], outdrar)
            i += 1


def set_structure(projPath):
    """Sets up the folder structure for an VBET project"""

    if not os.path.exists(projPath):
        os.mkdir(projPath)

    if os.getcwd() is not projPath:
        os.chdir(projPath)

    if not os.path.exists("01_Inputs"):
        os.mkdir("01_Inputs")
    if not os.path.exists("02_Analyses"):
        os.mkdir("02_Analyses")
    os.chdir("01_Inputs")
    if not os.path.exists("01_Topo"):
        os.mkdir("01_Topo")
    if not os.path.exists("02_Network"):
        os.mkdir("02_Network")
    os.chdir(projPath)

if __name__ == '__main__':
    main(
        sys.argv[1],
        sys.argv[2],
        sys.argv[3],
        sys.argv[4])
