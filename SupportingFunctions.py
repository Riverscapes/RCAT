#-----------------------------------------------------------------------------#
# Name:        GIS Tools Module                                               #
# Purpose:     Support components for Riverstyles and Stream Network Toolbox  #
#               (pulled from GNAT toolbox gis_tools script)                   #
# Author:      Kelly Whitehead (kelly@southforkresearch.org)                  #
#              South Fork Research, Inc                                       #
#              Seattle, Washington                                            #
#                                                                             #
# Created:     2015-Jan-08                                                    #
# Version:     1.3                                                            #
# Modified:    2015-Aug-12                                                    #
#                                                                             #
# Copyright:   (c) Kelly Whitehead 2015                                       #
#                                                                             #
#-----------------------------------------------------------------------------#
# load dependencies
import math
import os


def make_folder(folder):
    """
    Makes folder if it doesn't exist already
    """
    if not os.path.exists(folder):
        os.mkdir(folder)
    return 


def find_available_num_prefix(folder_root):
    """
    Tells us the next number for a folder in the directory given
    :param folder_root: Where we want to look for a number
    :return: A string, containing a number
    """
    taken_nums = [fileName[0:2] for fileName in os.listdir(folder_root)]
    POSSIBLENUMS = range(1, 100)
    for i in POSSIBLENUMS:
        string_version = str(i)
        if i < 10:
            string_version = '0' + string_version
        if string_version not in taken_nums:
            return string_version
    arcpy.AddWarning("There were too many files at " + folder_root + " to have another folder that fits our naming convention")
    return "100"


def newGISDataset(workspace, inputDatasetName):
    # creates new GIS layer in workspace
    """ workspace = "LAYER", "in_memory", folder or gdb"""
    if arcpy.Exists(workspace):
        if arcpy.Describe(workspace).workspaceType == "LocalDatabase" or workspace == "in_memory":
            ext = ""
        else:
            ext = ".shp"

    if workspace == "LAYER" or workspace == "layer" or workspace == "Layer":
        inputDataset = inputDatasetName
        if arcpy.Exists(inputDataset):
            arcpy.Delete_management(inputDataset)
    else:
        inputDataset = workspace + "\\" + inputDatasetName + ext
        if arcpy.Exists(inputDataset):
            arcpy.Delete_management(inputDataset)

    return inputDataset


def resetData(inputDataset):
    if arcpy.Exists(inputDataset):
        arcpy.Delete_management(inputDataset)

    return


def resetField(inTable,FieldName,FieldType,TextLength=0):
    """clear or create new field.  FieldType = TEXT, FLOAT, DOUBLE, SHORT, LONG, etc.

    :return: str field name
    """
    
    if arcpy.Describe(inTable).dataType == "ShapeFile":
        FieldName = FieldName[:10]

    if len(arcpy.ListFields(inTable,FieldName))==1:
        if FieldType == "TEXT":
            arcpy.CalculateField_management(inTable,FieldName,"''","PYTHON")
        else:
            arcpy.CalculateField_management(inTable,FieldName,"0","PYTHON")
        #arcpy.DeleteField_management(inTable,FieldName) #lots of 999999 errors 
    
    else: #Create Field if it does not exist
        if FieldType == "TEXT":
            arcpy.AddField_management(inTable,FieldName,"TEXT",field_length=TextLength)
        else:
            arcpy.AddField_management(inTable,FieldName,FieldType)
    return str(FieldName) 
