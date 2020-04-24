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
#arcpy.CheckOutExtension("3D")
arcpy.env.overwriteOutput=True

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
    arcpy.env.workspace = projPath
    
    # set up main project folder
    arcpy.AddMessage("Setting up folder structure....")
    make_folder(projPath)
    lrp_folder, dredge_folder, dem_folder, precip_folder = set_structure(projPath, lrp, dredge_tailings, dem, precip)

    arcpy.AddMessage("Copying inputs to project folder....")
    # add the network inputs to project
    network_folder = os.path.join(projPath, "Inputs", "01_Network")
    network_destinations = copy_multi_inputs_to_project(network, network_folder, "Network_")
        
    # add the existing veg inputs to project
    ex_veg_folder = os.path.join(projPath, "Inputs", "02_Existing_Vegetation")
    ex_veg_destinations = copy_multi_inputs_to_project(ex_cov, ex_veg_folder, "Ex_Veg_", is_raster=True)

    # add the historic veg inputs to project
    hist_veg_folder = os.path.join(projPath, "Inputs", "03_Historic_Vegetation")
    hist_veg_destinations = copy_multi_inputs_to_project(hist_cov, hist_veg_folder, "Hist_Veg_", is_raster=True)

    # add the valley inputs to the project
    frag_valley_folder = os.path.join(projPath, "Inputs", "04_Fragmented_Valley")
    valley_destinations = copy_multi_inputs_to_project(frag_valley, frag_valley_folder, "Frag_Valley_")

    # add the large river polygons to the project
    if lrp is not None:
        lrp_destinations = copy_multi_inputs_to_project(lrp, lrp_folder, "LRP_")
    else:
        lrp_destinations = None

    # add the dredge tailings polygons to the project
    if dredge_tailings is not None:
        dredge_destinations = copy_multi_inputs_to_project(dredge_tailings, dredge_folder, "DredgeTailings_")
    else:
        dredge_destinations = None

    # add the dem raster to the project
    if dem is not None:
        dem_destinations = copy_multi_inputs_to_project(dem, dem_folder, "DEM_", is_raster=True)
    else:
        dem_destinations = None

    # add the precip raster to the project
    if precip is not None:
        precip_destinations = copy_multi_inputs_to_project(precip, precip_folder, "Precip_", is_raster=True)
    else:
        precip_destinations = None

    # make all layers
    arcpy.AddMessage("Making layers....")
    make_layers(network_destinations, ex_veg_destinations, hist_veg_destinations, valley_destinations,
                lrp_destinations, dredge_destinations, dem_destinations, precip_destinations)


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
        lrp_folder = find_available_num_prefix(inputs) + "_Large_River_Polygon"
        make_folder(lrp_folder)
    else:
        lrp_folder = None
    if dredge_tailings is not None:
        dredge_folder = find_available_num_prefix(inputs) + "_Dredge_Tailings"
        make_folder(dredge_folder)
    else:
        dredge_folder = None
    if dem is not None:
        dem_folder = find_available_num_prefix(inputs) + "_Topography"
        make_folder(dem_folder)
    else:
        dem_folder = None
    if precip is not None:
        precip_folder = find_available_num_prefix(inputs) + "_Precipitation"
        make_folder(precip_folder)
    else:
        precip_folder=None
        
    return lrp_folder, dredge_folder, dem_folder, precip_folder


def copy_multi_inputs_to_project(inputs, folder, sub_folder_name, is_raster=False):
    """Copies multiple inputs to proper folder structure
    :param inputs: Input files to be copied into project structure
    :param sub_folder_name: Folder in inputs folder to copy files into
    :name: Name of sub-directories in folder
    :is_raster: True if raster
    :return: List of copied file destinations"""
    make_folder(folder)
    split_inputs = inputs.split(";")
    i = 1
    destinations = []
    for input_path in split_inputs:
        str_i = str(i)
        if i <10:
            str_i = '0'+str_i
        new_sub_folder = os.path.join(folder, sub_folder_name + str_i)
        make_folder(new_sub_folder)
        name = os.path.basename(input_path)
        if len(name.split('.')[0]) > 13:
            name = name.split('.')[0][0:12] + '.tif'
        destination_path = os.path.join(new_sub_folder, name)
        if is_raster:
            arcpy.CopyRaster_management(input_path, destination_path)
        else:
            arcpy.CopyFeatures_management(input_path, destination_path)
        i += 1
        destinations.append(destination_path)
    return destinations


def make_layers(network_destinations, ex_veg_destinations, hist_veg_destinations, valley_destinations,
                lrp_destinations, dredge_destinations, dem_destinations, precip_destinations):
    """Makes layers for all input files"""
    source_code_folder = os.path.dirname(os.path.abspath(__file__))
    symbology_folder = os.path.join(source_code_folder, "RCATSymbology")

    # grab all symbology
    network_symbology = os.path.join(symbology_folder, "Network.lyr")
    flow_direction_symbology = os.path.join(symbology_folder, "FlowDirection.lyr")
    ex_veg_native_symbology = os.path.join(symbology_folder, "ExistingVegNativeRiparian.lyr")
    ex_veg_riparian_symbology = os.path.join(symbology_folder, "ExistingVegRiparian.lyr")
    ex_veg_type_symbology = os.path.join(symbology_folder, "ExistingVegType.lyr")
    ex_vegetated_symbology = os.path.join(symbology_folder, "ExistingVegetated.lyr")
    hist_veg_native_symbology = os.path.join(symbology_folder, "HistoricVegNativeRiparian.lyr")
    hist_veg_riparian_symbology = os.path.join(symbology_folder, "HistoricVegRiparian.lyr")
    hist_veg_type_symbology = os.path.join(symbology_folder, "HistoricVegType.lyr")
    hist_vegetated_symbology = os.path.join(symbology_folder, "HistoricVegetated.lyr")
    landuse_symbology = os.path.join(symbology_folder, "LandUseRaster.lyr")
    frag_valley_symbology = os.path.join(symbology_folder, "FragmentedValleyBottom.lyr")
    valley_outline_symbology = os.path.join(symbology_folder, "ValleyBottomOutline.lyr")
    lrp_symbology = os.path.join(symbology_folder, "LargeRiverPolygon.lyr")
    dredge_tailings_symbology = os.path.join(symbology_folder, "DredgeTailings.lyr")
    dem_symbology = os.path.join(symbology_folder, "DEM.lyr")
    hillshade_symbology = os.path.join(symbology_folder, "Hillshade.lyr")
    precip_symbology =  os.path.join(symbology_folder, "Precipitation.lyr")

    # make layers for all input destinations
    for network in network_destinations:
        make_layer(os.path.dirname(network), network, "Network", network_symbology)
        make_layer(os.path.dirname(network), network, "Flow Direction", flow_direction_symbology)
    for ex_veg in ex_veg_destinations:
        make_layer(os.path.dirname(ex_veg), ex_veg, "Existing Native Riparian Vegetation", ex_veg_native_symbology, is_raster=True, symbology_field="NATIVE_RIP")
        make_layer(os.path.dirname(ex_veg), ex_veg, "Existing Riparian Vegetation", ex_veg_riparian_symbology, is_raster=True, symbology_field="RIPARIAN")
        make_layer(os.path.dirname(ex_veg), ex_veg, "Existing Vegetation Type", ex_veg_type_symbology, is_raster=True, symbology_field="CONVERSION")
        make_layer(os.path.dirname(ex_veg), ex_veg, "Existing Vegetated", ex_vegetated_symbology, is_raster=True, symbology_field="VEGETATED")
        make_layer(os.path.dirname(ex_veg), ex_veg, "Land Use Raster", landuse_symbology, is_raster=True, symbology_field="LU_CODE")
    for hist_veg in hist_veg_destinations:
        make_layer(os.path.dirname(hist_veg), hist_veg, "Historic Native Riparian Vegetation", hist_veg_native_symbology, is_raster=True, symbology_field="NATIVE_RIP")
        make_layer(os.path.dirname(hist_veg), hist_veg, "Historic Riparian Vegetation", hist_veg_riparian_symbology, is_raster=True, symbology_field="RIPARIAN")
        make_layer(os.path.dirname(hist_veg), hist_veg, "Historic Vegetation Type", hist_veg_type_symbology, is_raster=True, symbology_field="CONVERSION")
        make_layer(os.path.dirname(hist_veg), hist_veg, "Historic Vegetated", hist_vegetated_symbology, is_raster=True, symbology_field="VEGETATED")
    for valley in valley_destinations:
        make_layer(os.path.dirname(valley), valley, "Fragmented Valley Bottom", frag_valley_symbology)
        make_layer(os.path.dirname(valley), valley, "Valley Bottom Outline", valley_outline_symbology)
    if lrp_destinations is not None:
        for lrp in lrp_destinations:
            make_layer(os.path.dirname(lrp), lrp, "Large River Polygon", lrp_symbology)
    if dredge_destinations is not None:
        for dredge in dredge_destinations:
            make_layer(os.path.dirname(dredge), dredge, "Dredge Tailings", dredge_tailings_symbology)
    if dem_destinations is not None:
        for dem in dem_destinations:
            make_layer(os.path.dirname(dem), dem, "DEM", dem_symbology, is_raster=True)
            #hillshade_folder = os.path.join(os.path.dirname(dem), "Hillshade")
            #make_folder(hillshade_folder)
            #hillshade_file = os.path.join(hillshade_folder, "Hillshade.tif")
            #try:
            #    arcpy.HillShade_3d(dem, hillshade_file)
            #    make_layer(hillshade_folder, hillshade_file, "Hillshade", hillshade_symbology, is_raster=True)
            #except arcpy.ExecuteError as err:
            #    if get_execute_error_code(err) == "000859":
            #        arcpy.AddWarning("Warning: Unable to create hillshade layer. Consider modifying your DEM input if you need a hillshade.")
            #    else:
            #        raise arcpy.ExecuteError(err)
    if precip_destinations is not None:
        for precip in precip_destinations:
            make_layer(os.path.dirname(precip), precip, "Precipitation Raster", precip_symbology, is_raster=True)

        
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
