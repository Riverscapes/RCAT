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
import arcpy


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


def find_folder(folder_location, folder_name):
    """
    If the folder exists, returns it. Otherwise, raises an error
    :param folder_location: Where to look
    :param folder_name: The folder to look for
    :return: Path to folder
    """
    folders = os.listdir(folder_location)
    for folder in folders:
        if folder.endswith(folder_name):
            return os.path.join(folder_location, folder)
    return None


def make_layer(output_folder, layer_base, new_layer_name, symbology_layer=None, is_raster=False, description="Made Up Description", file_name=None, symbology_field=None):
    """
    Creates a layer and applies a symbology to it
    :param output_folder: Where we want to put the layer
    :param layer_base: What we should base the layer off of
    :param new_layer_name: What the layer should be called
    :param symbology_layer: The symbology that we will import
    :param is_raster: Tells us if it's a raster or not
    :param description: The discription to give to the layer file
    :return: The path to the new layer
    """
    new_layer = new_layer_name
    if file_name is None:
        file_name = new_layer_name.replace(' ', '')
    new_layer_save = os.path.join(output_folder, file_name.replace(' ', ''))
    
    if not new_layer_save.endswith(".lyr"):
        new_layer_save += ".lyr"

    if is_raster:
        try:
            arcpy.MakeRasterLayer_management(layer_base, new_layer)
        except arcpy.ExecuteError as err:
            if get_execute_error_code(err) == "000873":
                arcpy.AddError(err)
                arcpy.AddMessage("The error above can often be fixed by removing layers or layer packages from the Table of Contents in ArcGIS.")
                raise Exception
            else:
                raise arcpy.ExecuteError(err)

    else:
        if arcpy.Exists(new_layer):
            arcpy.Delete_management(new_layer)
        arcpy.MakeFeatureLayer_management(layer_base, new_layer)

    if symbology_layer:
        arcpy.ApplySymbologyFromLayer_management(new_layer, symbology_layer)

    if not os.path.exists(new_layer_save):
        arcpy.SaveToLayerFile_management(new_layer, new_layer_save, "RELATIVE")
        new_layer_instance = arcpy.mapping.Layer(new_layer_save)
        new_layer_instance.description = description
        new_layer_instance.save()
    return new_layer_save


def get_execute_error_code(err):
    """
    Returns the error code of the given arcpy.ExecuteError error, by looking at the string of the error
    :param err:
    :return:
    """
    return err[0][6:12]
