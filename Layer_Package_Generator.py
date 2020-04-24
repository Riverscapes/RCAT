# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
# Name: Layer Package Generator
# Purpose: Finds existing layers in a project, generates them if they are missing and their base exists, and then puts
# them into a layer package
#
# Author: Maggie Hallerud
# Created on: 22 April 2020
# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #


import arcpy
import os
import glob
from SupportingFunctions import *
import re


def main(output_folder, layer_package_name, clipping_network):
    """
    Generates a layer package from a RCAT project
    :param output_folder: What output folder we want to use for our layer package
    :param layer_package_name: What we want to name our layer package
    :param clipping_network: What we want to clip our network to
    :return:
    """

    arcpy.env.overwriteOutput = 'TRUE'

    if layer_package_name == "None":
	layer_package_name = None
    if clipping_network == "None":
	clipping_network = None
        
    if layer_package_name is None:
        if clipping_network is not None:
            layer_package_name = "RCATLayerPackage_Clipped"
        else:
            layer_package_name = "RCATLayerPackage"

    validate_inputs(output_folder)

    project_folder = os.path.dirname(os.path.dirname(output_folder))
    inputs_folder = find_folder(project_folder, "Inputs")
    intermediates_folder = os.path.join(output_folder, "01_Intermediates")
    analyses_folder = os.path.join(output_folder, "02_Analyses")

    trib_code_folder = os.path.dirname(os.path.abspath(__file__))
    symbology_folder = os.path.join(trib_code_folder, 'RCATSymbology')

    try:
        check_for_layers(intermediates_folder, analyses_folder, inputs_folder, symbology_folder)
    except Exception as err:
        arcpy.AddMessage(
            "Something went wrong while checking for layers. The process will package the layers that exist.")
        arcpy.AddMessage("The error message thrown was the following:")
        arcpy.AddWarning(err)

    if clipping_network is not None:
        network_clip, rvd_clip, confinement_clip, rca_clip = create_clipped_layers(output_folder, clipping_network, symbology_folder)
    
    make_layer_package(output_folder, intermediates_folder, analyses_folder,
                       inputs_folder, symbology_folder, layer_package_name, clipping_network)


def create_clipped_layers(output_folder, clipping_network, symbology_folder):
    """
    Makes clipped layers of all RCAT outputs
    param output_folder: folder where RCAT outputs will be found
    param clipping_network: network which RCAT outputs will be clipped to (e.g. the perennial)
    param symbology_folder: folder where standardized RCAT layers are found
    """
    arcpy.AddMessage("Making clipped layers.....")
    proj_path = os.path.dirname(os.path.dirname(output_folder))
    intermediates_folder = find_folder(output_folder, 'Intermediates')
    analyses_folder = find_folder(output_folder, 'Analyses')
    rvd_folder = find_folder(analyses_folder, "RVD")
    confinement_folder = find_folder(analyses_folder, "Confinement")
    rca_folder = find_folder(analyses_folder, "RCA")
    
    # find relevant files
    network = find_file(proj_path, 'Inputs/*[0-9]*_Network/Network_*[0-9]*/*.shp')
    rvd_file = find_file(rvd_folder, '*.shp')
    confinement_file = find_file(confinement_folder, '*.shp')
    rca_file = find_file(rca_folder, '*.shp')

    # clip all files
    network_clip = clip_file(network, clipping_network)
    rvd_clip = clip_file(rvd_file, clipping_network)
    if confinement_file is not None:
        confinement_clip = clip_file(confinement_file, clipping_network)
    else:
        confinement_file = None
    if rca_file is not None:
        rca_clip = clip_file(rca_file, clipping_network)
    else:
        rca_clip = None

    # make new network layer
    make_clipped_layers(os.path.dirname(network), network_clip, clipping_network, symbology_folder)

    # make new analyses layers
    make_clipped_layers(os.path.dirname(rvd_file), rvd_clip, clipping_network, symbology_folder)
    if confinement_file is not None:
        make_clipped_layers(os.path.dirname(confinement_file), confinement_clip, clipping_network, symbology_folder)
    if rca_file is not None:
        make_clipped_layers(os.path.dirname(rca_file), rca_clip, clipping_network, symbology_folder)

    return network_clip, rvd_clip, rca_clip
        

def clip_file(shapefile, clipping_network):
    """
    Clips RCAT network outputs to clipping network with standardized name
    param shapefile: RCAT output to be clipped
    param clipping_network: polyline to clip RCAT outputs to
    """
    if os.path.exists(shapefile):
        perennial_shapefile = shapefile.split('.')[0] + "_Perennial.shp"
        if os.path.exists(perennial_shapefile):
            arcpy.AddMessage('.........Using previously clipped ' + os.path.basename(perennial_shapefile))
            return perennial_shapefile
        elif shapefile.endswith('_Perennial.shp') or shapefile.endswith('_clipped.shp'):
            arcpy.AddMessage('.........Using previously clipped ' + os.path.basename(shapefile))
            return shapefile
        else:
            try:
                out_name = shapefile.split('.')[0] + "_clipped.shp"
                arcpy.Clip_analysis(shapefile, clipping_network, out_name)
                return out_name
            except Exception as err:
                arcpy.AddMessage("WARNING: Clipping failed for "+ network + ". Exception thrown was:")
                arcpy.AddMessage(err)
    else:
        arcpy.AddMessage("WARNING: Could not find " + shapefile + " to make clipped layers")


def make_clipped_layers(folder, shapefile, clipping_network, symbology_folder):
    """
    Makes clipped layers for all layer in folder based on shapefile that has been clipped
    param folder: folder where old layers will be found and new clipped layers stored
    param shapefile: shapefile layers will be based off
    param symbology_folder: folder where base layers will be found
    """
    lyrs = find_layers_in_folder(folder, None)
    for lyr in lyrs[:]:
        if lyr.endswith('_clipped.lyr'):
            lyrs.remove(lyr)
    for lyr in lyrs:
        name = os.path.basename(lyr)
        symbology = os.path.join(symbology_folder, name)
        desc = arcpy.Describe(lyr)
        out_name = str(desc.nameString)
        out_file = name.split('.')[0]+'_clipped.lyr'
        if os.path.exists(os.path.join(folder, out_file)):
            arcpy.Delete_management(os.path.join(folder, out_file))
        if os.path.exists(symbology):
            try:
                make_layer(folder, shapefile, new_layer_name=out_name,
                           symbology_layer=symbology, is_raster=False, file_name=out_file)
            except Exception as err:
                arcpy.AddMessage("WARNING: Failed to make " + out_file + ". Error thrown was:")
                arcpy.AddMessage(err)
        

def validate_inputs(output_folder):
    """
    Checks that the inputs are in the form that we want them to be
    :param output_folder: What output folder we want to base our layer package off of
    :return:
    """
    if not re.match(r'Output_\d\d', os.path.basename(output_folder)):
        raise Exception("Given output folder is invalid.\n\n" +
                        'Look for a folder formatted like "Output_##", where # represents any number')


def check_for_layers(intermediates_folder, analyses_folder, inputs_folder, symbology_folder):
    """
    Checks for what layers exist, and creates them if they do not exist
    :param intermediates_folder: Where our intermediates are kept
    :param analyses_folder: Where our analyses are kept
    :param inputs_folder: Where our inputs are kept
    :param symbology_folder: Where we pull symbology from
    :return:
    """
    arcpy.AddMessage("Recreating missing layers (if possible)...")
    check_intermediates(intermediates_folder, symbology_folder)
    check_analyses(analyses_folder, symbology_folder)
    check_inputs(inputs_folder, symbology_folder)


def check_intermediates(intermediates_folder, symbology_folder):
    """
    Checks for all the intermediate layers
    :param intermediates_folder: Where our intermediates are kept
    :param symbology_folder: Where we pull symbology from
    :return:
    """
    thiessen_valley_symbology = os.path.join(symbology_folder, "ClippedThiessenPolygons.lyr")
    conversion_raster_symbology = os.path.join(symbology_folder, "RiparianConversionRaster.lyr")
    riparian_symbology = os.path.join(symbology_folder, "RiparianCorridor.lyr")
    bankfull_width_symbology = os.path.join(symbology_folder, "BankfullChannelWidthPolygons.lyr")
    valley_width_symbology = os.path.join(symbology_folder, "ValleyBottomWidthPolygons.lyr")
    connectivity_symbology = os.path.join(symbology_folder, "FloodplainConnectivityRaster.lyr")

    thiessen_valley_folder = find_folder(intermediates_folder, "ValleyThiessen")
    vegetation_rasters_folder = find_folder(intermediates_folder, "VegetationRasters")
    confinement_folder = find_folder(intermediates_folder, "Confinement")
    connectivity_folder = find_folder(intermediates_folder, "Connectivity")

    thiessen_valley_layer = os.path.join(thiessen_valley_folder, "ClippedThiessenPolygons.lyr")
    thiessen_valley_clip = os.path.join(thiessen_valley_folder, "Thiessen_Valley_Clip.shp")
    check_layer(thiessen_valley_layer, thiessen_valley_clip, thiessen_valley_symbology, is_raster=False,
                layer_name="Clipped Thiessen Polygons") 

    conversion_raster_layer = os.path.join(vegetation_rasters_folder, "RiparianConversionRaster.lyr")
    conversion_raster = os.path.join(vegetation_rasters_folder, "Conversion_Raster.tif")
    check_layer(conversion_raster_layer, conversion_raster, conversion_raster_symbology, is_raster=True,
                layer_name="Riparian Conversion Raster")

    riparian_layer = os.path.join(vegetation_rasters_folder, "RiparianCorridor.lyr")
    riparian_raster = os.path.join(vegetation_rasters_folder, "All_Riparian_recl.tif")
    check_layer(riparian_layer, riparian_raster, riparian_symbology, is_raster=True,
                layer_name="Riparian Corridor")

    bankfull_width_layer = os.path.join(confinement_folder, "BankfullChannelWidthPolygons.lyr")
    confinement_bankfull = os.path.join(confinement_folder, "Conf_Thiessen_Bankfull.shp")
    check_layer(bankfull_width_layer, confinement_bankfull, bankfull_width_symbology, is_raster=False,
                layer_name="Bankfull Channel Width Polygons")

    valley_width_layer = os.path.join(confinement_folder, "ValleyBottomWidthPolygons.lyr")
    confinement_valley = os.path.join(confinement_folder, "Conf_Thiessen_Valley.shp")
    check_layer(valley_width_layer, confinement_valley, valley_width_symbology, is_raster=False,
                layer_name="Valley Bottom Width Polygons")

    
    connectivity_layer = os.path.join(connectivity_folder, "FloodplainConnectivityRaster.lyr")
    connectivity = os.path.join(connectivity_folder, "Floodplain_Connectivity.tif")
    check_layer(connectivity_layer, connectivity, connectivity_symbology, is_raster=True,
                layer_name="Floodplain Connectivity Raster")
    

def check_analyses(analyses_folder, symbology_folder):
    """
    Checks for all the intermediate layers
    :param analyses_folder: Where our analyses are kept
    :param symbology_folder: Where we pull symbology from
    :return:
    """
    rvd_folder = find_folder(analyses_folder, "RVD")
    bankfull_folder = find_folder(analyses_folder, "BankfullChannel")
    confinement_folder = find_folder(analyses_folder, "Confinement")
    rca_folder = find_folder(analyses_folder, "RCA")

    check_analyis_layer(rvd_folder, "Riparian Vegetation Departure",
                         symbology_folder, "RiparianVegetationDeparture.lyr", "RIPAR_DEP")
    check_analysis_layer(rvd_folder, "Native Riparian Vegetation Departure",
                         symbology_folder, "NativeRiparianVegetationDeparture.lyr", "NATIV_DEP")
    check_analysis_layer(rvd_folder, "Riparian Conversion Type",
                         symbology_folder, "RiparianConversionType.lyr", "Conv_Type")

    check_analysis_layer(bankfull_folder, "Bankfull Channel Network",
                         symbology_folder, "BankfullChannelNetwork.lyr", "BUFWIDTH")
    check_analysis_layer(bankfull_folder, "Upstream Drainage Area",
                         symbology_folder, "UpstreamDrainageArea.lyr", "DRAREA")
    check_analysis_layer(bankfull_folder, "Precipitation By Reach",
                         symbology_folder, "PrecipitationByReach.lyr", "PRECIP")
    bankfull_polygon = find_shapefile_with_field(bankfull_folder, "SmoPgnFlag")
    if bankfull_polygon is not None:
        bankfull_lyr = os.path.join(bankfull_folder, "BankfullChannelPolygon.lyr")
        check_layer(bankfull_lyr, bankfull_polygon, os.path.join(symbology_folder, "BankfullChannelPolygon.lyr"),
                    is_raster=False, layer_name="Bankfull Channel Polygon")
    
    check_analysis_layer(confinement_folder, "Confinement Ratio",
                         symbology_folder, "ConfinementRatio.lyr", "CONF_RATIO")

    check_analysis_layer(rca_folder, "Riparian Condition", symbology_folder,
                         "RiparianCondition.lyr", "CONDITION")
    check_analysis_layer(rca_folder, "Land Use Intensity", symbology_folder,
                         "LandUseIntensity.lyr", "LUI")
    check_analysis_layer(rca_folder, "Floodplain Connectivity", symbology_folder,
                         "FloodplainConnectivity.lyr", "CONNECT")
    check_analysis_layer(rca_folder, "Proportion Currently Vegetated", symbology_folder,
                         "ProportionCurrentlyVegetated.lyr", "EX_VEG")
    check_analysis_layer(rca_folder, "Proportion Historically Vegetated", symbology_folder,
                         "ProportionHistoricallyVegetated.lyr", "HIST_VEG")
    check_analysis_layer(rca_folder, "Vegetation Remaining", symbology_folder,
                         "VegetationRemaining.lyr", "VEG")
                                                 

def check_analysis_layer(layer_base_folder, layer_name, symbology_folder,
                         symbology_file_name, field_name, layer_file_name=None):
    """
    Checks if an analyses layer exists. If it does not, it looks for a shape file that can create the proper symbology.
    If it finds a proper shape file, it creates the layer that was missing
    :param analyses_folder: The root of the analyses folder
    :param layer_base_folder: The folder containing the layer file
    :param layer_name: The name of the layer to create
    :param symbology_folder: The path to the symbology folder
    :param symbology_file_name: The name of the symbology layer we want to pull from
    :param field_name: The name of the field we'll be basing our symbology off of
    :param layer_file_name: The name of the layer file (if different from the layer_name without spaces)
    :return:
    """
    if layer_file_name is None:
        layer_file_name = layer_name.replace(" ", "") + ".lyr"

    layer_file = os.path.join(layer_base_folder, layer_file_name)
    if os.path.exists(layer_file):  # if the layer already exists, we don't care, we can exit the function
        return

    if field_name is not None:
        shape_file = find_shapefile_with_field(layer_base_folder, field_name)
        if shape_file is None:
            return

    layer_symbology = os.path.join(symbology_folder, symbology_file_name)

    make_layer(layer_base_folder, shape_file, layer_name, symbology_layer=layer_symbology)


def find_shapefile_with_field(folder, field_name):
    """
    Looks for a file in the given folder that has the field name we're looking for
    :param folder: The folder to look in
    :param field_name: The field name we're looking for
    :return: The file path that has the field we want
    """
    for check_file in os.listdir(folder):
        if check_file.endswith(".shp"):
            file_path = os.path.join(folder, check_file)
            file_fields = [f.name for f in arcpy.ListFields(file_path)]
            if field_name in file_fields:
                return file_path
    return None


def check_inputs(inputs_folder, symbology_folder):
    """
    Checks for all the intermediate layers
    :param inputs_folder: Where our inputs are kept
    :param symbology_folder: Where we pull symbology from
    :return:
    """
    network_folder = find_folder(inputs_folder, "Network")
    ex_vegetation_folder = find_folder(inputs_folder, "Existing_Vegetation")
    hist_vegetation_folder = find_folder(inputs_folder, "Historic_Vegetation")
    valley_folder = find_folder(inputs_folder, "Fragmented_Valley")
    lrp_folder = find_folder(inputs_folder, "Large_River_Polygon")
    tailings_folder = find_folder(inputs_folder, "Dredge_Tailings")
    topo_folder = find_folder(inputs_folder, "Topography")
    precip_folder = find_folder(inputs_folder, "Precipitation")

    ex_veg_native_symbology = os.path.join(symbology_folder, "ExistingVegNativeRiparian.lyr")
    ex_veg_riparian_symbology = os.path.join(symbology_folder, "ExistingVegRiparian.lyr")
    ex_veg_group_symbology = os.path.join(symbology_folder, "ExistingVegType.lyr")
    ex_veg_vegetated_symbology = os.path.join(symbology_folder, "ExistingVegetated.lyr")
    landuse_symbology = os.path.join(symbology_folder, "LandUseRaster.lyr")
    
    hist_veg_native_symbology = os.path.join(symbology_folder, "HistoricVegNativeRiparian.lyr")
    hist_veg_riparian_symbology = os.path.join(symbology_folder, "HistoricVegOverallRiparian.lyr")
    hist_veg_group_symbology = os.path.join(symbology_folder, "HistoricVegType.lyr")
    hist_veg_vegetated_symbology = os.path.join(symbology_folder, "HistoricVegetated.lyr")

    network_symbology = os.path.join(symbology_folder, "Network.lyr")
    flow_direction_symbology = os.path.join(symbology_folder, "FlowDirection.lyr")
    valley_bottom_symbology = os.path.join(symbology_folder, "FragmentedValleyBottom.lyr")
    valley_outline_symbology = os.path.join(symbology_folder, "ValleyBottomOutline.lyr")
    lrp_symbology = os.path.join(symbology_folder, "LargeRiverPolygon.lyr")
    precip_symbology = os.path.join(symbology_folder, "Precipitation.lyr")
    dredge_tailings_symbology = os.path.join(symbology_folder, "DredgeTailings.lyr")

    network_destinations = find_destinations(network_folder)
    make_input_layers(network_destinations, "Network", symbology_layer=network_symbology, is_raster=False)
    make_input_layers(network_destinations, "Flow Direction", symbology_layer=flow_direction_symbology, is_raster=False)

    ex_veg_destinations = find_destinations(ex_vegetation_folder)
    make_input_layers(ex_veg_destinations, "Existing Native Riparian Vegetation",
                      symbology_layer=ex_veg_native_symbology, is_raster=True)
    make_input_layers(ex_veg_destinations, "Existing Riparian Vegetation",
                      symbology_layer=ex_veg_riparian_symbology, is_raster=True)
    make_input_layers(ex_veg_destinations, "Existing Landcover Group",
                      symbology_layer=ex_veg_group_symbology, is_raster=True)
    make_input_layers(ex_veg_destinations, "Existing Vegetated",
                      symbology_layer=ex_veg_riparian_symbology, is_raster=True)
    make_input_layers(ex_veg_destinations, "Land Use Raster",
                      symbology_layer=landuse_symbology, is_raster=True)

    hist_veg_destinations = find_destinations(hist_vegetation_folder)
    make_input_layers(ex_veg_destinations, "Existing Native Riparian Vegetation",
                      symbology_layer=hist_veg_native_symbology, is_raster=True)
    make_input_layers(ex_veg_destinations, "Existing Riparian Vegetation",
                      symbology_layer=hist_veg_riparian_symbology, is_raster=True)
    make_input_layers(ex_veg_destinations, "Existing Vegetation Type",
                      symbology_layer=hist_veg_group_symbology, is_raster=True)
    make_input_layers(ex_veg_destinations, "Existing Vegetated",
                      symbology_layer=hist_veg_riparian_symbology, is_raster=True)

    valley_destinations = find_destinations(valley_folder)
    make_input_layers(valley_destinations, "Fragmented Valley Bottom",
                      symbology_layer=valley_bottom_symbology, is_raster=False)
    make_input_layers(valley_destinations, "Valley Bottom Outline",
                      symbology_layer=valley_outline_symbology, is_raster=False)

    if lrp_folder is not None:
        lrp_destinations = find_destinations(lrp_folder)
        make_input_layers(lrp_destinations, "Large River Polygon",
                          symbology_layer=lrp_symbology, is_raster=False)

    if tailings_folder is not None:
        tailings_destinations = find_destinations(tailings_folder)
        make_input_layers(tailings_destinations, "Dredge Tailings",
                          symbology_layer=dredge_tailings_symbology, is_raster=False)
        
    if topo_folder is not None:
        make_topo_layers(topo_folder, symbology_folder)

    if precip_folder is not None:
        precip_destinations = find_destinations(precip_folder)
        make_input_layers(precip_destinations, "Precipitation Raster",
                          symbology_layer=precip_symbology, is_raster=True)


def make_topo_layers(topo_folder, symbology_folder):
    """
    Writes the layers
    :param topo_folder: We want to make layers for the stuff in this folder
    :return:
    """
    dem_symbology = os.path.join(symbology_folder, "DEM.lyr")
    #slope_symbology = os.path.join(symbology_folder, "Slope.lyr")
    hillshade_symbology =  os.path.join(symbology_folder, "Hillshade.lyr")
    flow_symbology = os.path.join(symbology_folder, "FlowAccumulationRaster.lyr")

    for folder in os.listdir(topo_folder):
        dem_folder_path = os.path.join(topo_folder, folder)
        for file_name in os.listdir(dem_folder_path):
            if file_name.endswith(".tif"):
                try:
                    dem_file = os.path.join(dem_folder_path, file_name)
                    if not os.path.exists(os.path.join(dem_folder_path, "DEM.lyr")) and os.path.exists(dem_file):
                        make_layer(dem_folder_path, dem_file, "DEM", dem_symbology, is_raster=True)
                except Exception as err:
                    arcpy.AddMessage("WARNING: Check layer failed for DEM. Error thrown was:")
                    arcpy.AddMessage(err)

        hillshade_folder = find_folder(dem_folder_path, "Hillshade")
        if hillshade_folder is not None:
            try:
                hillshade_file = find_file(hillshade_folder, "*.tif")
                if not os.path.exists(os.path.join(hillshade_folder, "Hillshade.lyr")) and os.path.exists(hillshade_file):
                    make_layer(hillshade_folder, hillshade_file, "Hillshade", hillshade_symbology, is_raster=True)
            except Exception as err:
                arcpy.AddMessage("WARNING: Fixing layer failed for hillshade raster. Error thrown was:")
                arcpy.AddMessage(err)

        #slope_folder = find_folder(dem_folder_path, "Slope")
        #if slope_folder is not None:
        #    try:
        #        slope_file = find_file(slope_folder, "*.tif")
        #        if not os.path.exists(os.path.join(slope_folder, "Slope.lyr")) and os.path.exists(slope_file):
        #            make_layer(slope_folder, slope_file, "Slope", slope_symbology, is_raster=True)
        #    except Exception as err:
        #        arcpy.AddMessage("WARNING: Fixing layer failed for slope raster. Error thrown was:")
        #        arcpy.AddMessage(err)

        flow_folder = find_folder(dem_folder_path, "Flow")
        if flow_folder is not None:
            try:
                flow_file = find_file(flow_folder, "*.tif")
                if not os.path.exists(os.path.join(flow_folder, "FlowAccumulationRaster.lyr")) and os.path.exists(flow_file):
                    make_layer(flow_folder, flow_file, "Flow Accumulation Raster", flow_symbology, is_raster=True)
            except Exception as err:
                arcpy.AddMessage("WARNING: Fixing layer failed for flow accumulation raster. Error thrown was:")
                arcpy.AddMessage(err)
        


def find_destinations(root_folder):
    """
    Finds all the .shp and .tif files in a directory, and returns an array with the paths to them
    :param root_folder: The root folder where we want to find shape files
    :return:
    """
    destinations = []
    for root, dirs, files in os.walk(root_folder):
        for check_file in files:
            if check_file.endswith(".shp") or check_file.endswith('.tif'):
                destinations.append(os.path.join(root, check_file))
    return destinations


def make_input_layers(destinations, layer_name, is_raster, symbology_layer=None, file_name=None, check_field=None):
    """
    Makes the layers for everything in the folder
    :param destinations: A list of paths to our inputs
    :param layer_name: The name of the layer
    :param is_raster: Whether or not it's a raster
    :param symbology_layer: The base for the symbology
    :param file_name: The name for the file (if it's different from the layerName)
    :param check_field: The name of the field that the symbology is based on
    :return:
    """
    if file_name is None:
        file_name = layer_name
    for destination in destinations:
        skip_loop = False
        dest_dir_name = os.path.dirname(destination)

        if file_name is None:
            file_name = layer_name.replace(" ", "")
        new_layer_save = os.path.join(dest_dir_name, file_name.replace(' ', ''))
        if not new_layer_save.endswith(".lyr"):
            new_layer_save += ".lyr"
        if os.path.exists(new_layer_save):
            skip_loop = True
        if check_field:
            fields = [f.name for f in arcpy.ListFields(destination)]
            if check_field not in fields:
                # Skip the loop if the base doesn't support
                skip_loop = True

        if not skip_loop:
            make_layer(dest_dir_name, destination, layer_name,
                       symbology_layer=symbology_layer, is_raster=is_raster, file_name=file_name)


def make_layer_package(output_folder, intermediates_folder, analyses_folder,
                       inputs_folder, symbology_folder, layer_package_name, clipping_network):
    """
    Makes a layer package for the project
    :param output_folder: Folder to output the layer package to
    :param intermediates_folder: Folder containing intermediates layers
    :param analyses_folder: Folder containing analyses layers
    :param inputs_folder: Folder containing inputs layers
    :param symbology_folder: Folder containing symbology layers
    :param layer_package_name: Name for the layer package output
    :param clipping_network: Network to clip the layer package with
    :return:
    """
    if layer_package_name == "" or layer_package_name is None:
        layer_package_name = "LayerPackage"
    if not layer_package_name.endswith(".lpk"):
        layer_package_name += ".lpk"

    arcpy.AddMessage("Assembling Layer Package...")
    empty_group_layer = os.path.join(symbology_folder, "EmptyGroupLayer.lyr")

    mxd = arcpy.mapping.MapDocument("CURRENT")
    mxd.relativePaths = False
    df = arcpy.mapping.ListDataFrames(mxd)[0]
    for lyr in arcpy.mapping.ListLayers(mxd, "", df):
        arcpy.mapping.RemoveLayer(df, lyr)

    analyses_layer = get_analyses_layer(analyses_folder, empty_group_layer, df, mxd, clipping_network)
    inputs_layer = get_inputs_layer(empty_group_layer, inputs_folder, df, mxd, clipping_network)
    intermediates_layer = get_intermediates_layers(empty_group_layer, intermediates_folder, analyses_folder, df, mxd, clipping_network)
    output_layer = group_layers(empty_group_layer, "Output", [intermediates_layer, analyses_layer], df, mxd)
    output_layer = group_layers(empty_group_layer, layer_package_name[:-4],
                                [inputs_layer, output_layer], df, mxd, remove_layer=False)

    layer_package = os.path.join(output_folder, layer_package_name)
    arcpy.AddMessage("Saving Layer Package...")
    arcpy.PackageLayer_management(output_layer, layer_package)


def get_analyses_layer(analyses_folder, empty_group_layer, df, mxd, clipping_network):
    """
    Returns the layers we want for the 'RCAT Outputs' section
    :param analyses_folder: folder holding capacity, conservation restoration, and validation outputs
    :param empty_group_layer: empty group layer
    :param df: data frame where layer package is being built
    :param mxd: ArcMap document where layer package is being built
    :param clipping_network: The network RCAT outputs will be clipped
    :return:
    """
    rvd_folder = find_folder(analyses_folder, "RVD")
    bankfull_folder = find_folder(analyses_folder, "BankfullChannel")
    confinement_folder = find_folder(analyses_folder, "Confinement")
    rca_folder = find_folder(analyses_folder, "RCA")
    
    if clipping_network is None:
        condition_lyr = find_file(rca_folder, "RiparianCondition.lyr")
    else:
        condition_lyr = find_file(rca_folder, "RiparianCondition_clipped.lyr")

    rvd_layers = find_layers_in_folder(rvd_folder, clipping_network)
    bankfull_polygon = find_file(bankfull_folder, "BankfullChannelPolygon.lyr")
    bankfull_network = find_file(bankfull_folder, "BankfullChannelNetwork.lyr")
    bankfull_layers = [bankfull_polygon, bankfull_network]
    confinement_layers = find_layers_in_folder(confinement_folder, clipping_network)

    rvd_layer = group_layers(empty_group_layer, "Riparian Vegetation Departure", rvd_layers, df, mxd)
    bankfull_layer = group_layers(empty_group_layer, "Bankfull Channel", bankfull_layers, df, mxd)
    confinement_layer = group_layers(empty_group_layer, "Confinement", confinement_layers, df, mxd)
    rca_layer = group_layers(empty_group_layer, "Riparian Condition Assessment", [condition_lyr], df, mxd)
    
    output_layer = group_layers(empty_group_layer, "Riparian Condition Assessment Tool - RCAT",
                                [bankfull_layer, confinement_layer, rvd_layer, rca_layer], df, mxd)

    return output_layer


def get_inputs_layer(empty_group_layer, inputs_folder, df, mxd, clipping_network):
    """
    Gets all the input layers, groups them properly, returns the layer
    :param empty_group_layer: The base to build the group layer with
    :param inputs_folder: Path to the inputs folder
    :param df: The dataframe we're working with
    :param mxd: The map document we're working with
    :param clipping_network: The network to clip the layer with
    :return: layer for inputs
    """
    network_folder = find_folder(inputs_folder, "Network")
    ex_veg_folder = find_folder(inputs_folder, "Existing_Vegetation")
    hist_veg_folder = find_folder(inputs_folder, "Historic_Vegetation")
    valley_folder = find_folder(inputs_folder, "Fragmented_Valley")
    lrp_folder = find_folder(inputs_folder, "Large_River_Polygon")
    tailings_folder = find_folder(inputs_folder, "Dredge_Tailings")
    topo_folder = find_folder(inputs_folder, "Topography")
    precip_folder = find_folder(inputs_folder, "Precipitation")

    ex_veg_native_lyrs = find_veg_layers(ex_veg_folder, "ExistingNativeRiparianVegetation.lyr")
    ex_veg_riparian_lyrs = find_veg_layers(ex_veg_folder, "ExistingRiparianVegetation.lyr")
    ex_veg_type_lyrs = find_veg_layers(ex_veg_folder, "ExistingVegetationType.lyr")
    ex_veg_vegetated_lyrs = find_veg_layers(ex_veg_folder, "ExistingVegetated.lyr")
    ex_veg_layers = ex_veg_vegetated_lyrs + ex_veg_riparian_lyrs + ex_veg_native_lyrs + ex_veg_type_lyrs
    ex_veg_layer = group_layers(empty_group_layer, "Existing Vegetation", ex_veg_layers, df, mxd)
    
    hist_veg_native_lyrs = find_veg_layers(hist_veg_folder, "HistoricNativeRiparianVegetation.lyr")
    hist_veg_riparian_lyrs = find_veg_layers(hist_veg_folder, "HistoricRiparianVegetation.lyr")
    hist_veg_type_lyrs = find_veg_layers(hist_veg_folder, "HistoricVegetationType.lyr")
    hist_veg_vegetated_lyrs = find_veg_layers(hist_veg_folder, "HistoricVegetated.lyr")
    hist_veg_layers = hist_veg_vegetated_lyrs + hist_veg_riparian_lyrs + hist_veg_native_lyrs + hist_veg_type_lyrs
    hist_veg_layer = group_layers(empty_group_layer, "Historic Vegetation", hist_veg_layers, df, mxd)

    veg_layer = group_layers(empty_group_layer, "Vegetation", [hist_veg_layer, ex_veg_layer], df, mxd)

    network_layers = find_instance_layers(network_folder, clipping_network)
    network_layer = group_layers(empty_group_layer, "Network", network_layers, df, mxd)

    valley_layers = find_instance_layers(valley_folder, None)
    valley_layer = group_layers(empty_group_layer, "Fragmented Valley Bottom", valley_layers, df, mxd)

    lrp_layers = find_instance_layers(lrp_folder, None)
    lrp_layer = group_layers(empty_group_layer, "Large River Polygon", lrp_layers, df, mxd)

    tailings_layers = find_instance_layers(tailings_folder, None)
    tailings_layer = group_layers(empty_group_layer, "Dredge Tailings", tailings_layers, df, mxd)

    # TODO: Make this work if more than one landuse instance
    landuse_layers = find_veg_layers(ex_veg_folder, "LandUseRaster.lyr")
    landuse_layer = group_layers(empty_group_layer, "Land Use", landuse_layers, df, mxd)
    
    dem_layers = find_instance_layers(topo_folder, None)
    hillshade_layers = find_dem_derivative(topo_folder, "Hillshade")
    #slope_layers = find_dem_derivative(topo_folder, "Slope")
    flow_layers = find_dem_derivative(topo_folder, "Flow")
    topo_layer = group_layers(empty_group_layer, "Topography",
                              hillshade_layers + dem_layers + flow_layers, df, mxd)

    precip_layers = find_instance_layers(precip_folder, None)
    precip_layer = group_layers(empty_group_layer, "Precipitation", precip_layers, df, mxd)

    return group_layers(empty_group_layer, "Inputs",
                        [topo_layer, precip_layer, landuse_layer, veg_layer, valley_layer, tailings_layer, lrp_layer, network_layer], df, mxd)


def get_intermediates_layers(empty_group_layer, intermediates_folder, analyses_folder, df, mxd, clipping_network):
    """
    Returns a group layer with all of the intermediates
    :param empty_group_layer: The base to build the group layer with
    :param intermediates_folder: Path to the intermediates folder
    :param df: The dataframe we're working with
    :param mxd: The map document we're working with
    :param clipping_network: The network to clip the layer with
    :return: Layer for intermediates
    """
    intermediate_layers = []

    thiessen_valley_folder = find_folder(intermediates_folder, "ValleyThiessen")
    find_and_group_layers(intermediate_layers, intermediates_folder,
                          "ValleyThiessen", "Thiessen Polygons",
                          empty_group_layer, df, mxd, None)
    
    rca_folder = find_folder(analyses_folder, "RCA")
    if rca_folder is not None:
        if clipping_network is None:
            lui_lyr = find_file(rca_folder, "LandUseIntensity.lyr")
            connect_lyr = find_file(rca_folder, "FloodplainConnectivity.lyr")
            ex_veg_lyr = find_file(rca_folder, "ProportionCurrentlyVegetated.lyr")
            hist_veg_lyr = find_file(rca_folder, "ProportionHistoricallyVegetated.lyr")
            vegetated_lyr = find_file(rca_folder, "VegetationRemaining.lyr")
        else:
            lui_lyr = find_file(rca_folder, "LandUseIntensity_clipped.lyr")
            connect_lyr = find_file(rca_folder, "FloodplainConnectivity_clipped.lyr")
            ex_veg_lyr = find_file(rca_folder, "ProportionCurrentlyVegetated_clipped.lyr")
            hist_veg_lyr = find_file(rca_folder, "ProportionHistoricallyVegetated_clipped.lyr")
            vegetated_lyr = find_file(rca_folder, "VegetationRemaining_clipped.lyr")
    else:
        lui_lyr = None
        connect_lyr = None
        ex_veg_lyr = None
        hist_veg_lyr = None
        vegetated_lyr = None

    find_and_group_layers(intermediate_layers, intermediates_folder,
                          "VegetationRasters", "RVD Intermediates",
                          empty_group_layer, df, mxd, None)

    bankfull_folder = find_folder(analyses_folder, "BankfullChannel")
    if bankfull_folder is not None:
        drainage_area = find_file(bankfull_folder, "UpstreamDrainageArea.lyr")
        precip = find_file(bankfull_folder, "PrecipitationByReach.lyr")
        bankfull_layer = group_layers(empty_group_layer, "Bankfull Channel Intermediates", [drainage_area, precip], df, mxd)
        intermediate_layers.append(bankfull_layer)

    find_and_group_layers(intermediate_layers, intermediates_folder,
                          "Confinement", "Confinement Intermediates",
                          empty_group_layer, df, mxd, None)

    rca_intermediates_folder = find_folder(intermediates_folder, "Connectivity")
    if rca_intermediates_folder is not None:
        rca_intermediates = find_layers_in_folder(rca_intermediates_folder, clipping_network)
        rca_intermediates.append(connect_lyr)
        veg_layer = group_layers(empty_group_layer, "Vegetated", [hist_veg_lyr, ex_veg_lyr, vegetated_lyr], df, mxd)
        connect_layer = group_layers(empty_group_layer, "Connectivity", rca_intermediates, df, mxd)
        lui_layer = group_layers(empty_group_layer, "Land Use", [lui_lyr], df, mxd)
        rca_layer = group_layers(empty_group_layer, "RCA Intermediates", [veg_layer, connect_layer, lui_layer], df, mxd)
        intermediate_layers.append(rca_layer)

    return group_layers(empty_group_layer, "Intermediates", intermediate_layers, df, mxd)


def find_and_group_layers(layers_list, folder_base, folder_name,
                          group_layer_name, empty_group_layer, df, mxd, clipping_network):
    """
    Looks for the folder that matches what we're looking for, then groups them together. Adds that grouped layer to the
    list of grouped layers that it was given
    :param layers_list: The list of layers that we will add our grouped layer to
    :param folder_base: Path to the folder that contains the folder we want
    :param folder_name: The name of the folder to look in
    :param group_layer_name: What we want to name the group layer
    :param empty_group_layer: The base to build the group layer with
    :param df: The dataframe we're working with
    :param mxd: The map document we're working with
    :param clipping_network: The network to clip the layer with
    :return:
    """
    folder_path = find_folder(folder_base, folder_name)
    if folder_path:
        layers = find_layers_in_folder(folder_path, clipping_network)

        layers_list.append(group_layers(empty_group_layer, group_layer_name, layers, df, mxd))


def find_veg_layers(root_folder, layer_name):
    """ Finds all layers with layer name in root folder 
    :param root_folder: The path to the folder where layers will be searched for
    :param layer_name: The basename of the layer being searched for (e.g., 'ExistingRiparianVegetation.lyr')
    :return: List of layers found"""
    layers = []
    for instance_folder in os.listdir(root_folder):
        instance_folder = os.path.join(root_folder, instance_folder)
        for dir in os.listdir(instance_folder):
            folder = os.path.join(instance_folder, dir)
            lyr = find_file(folder, layer_name)   
            if lyr is not None:
                layers.append(lyr)
    return layers

                
def find_instance_layers(root_folder, clipping_network):
    """
    Finds every layer when buried beneath an additional layer of folders (ie, in DEM_1, DEM_2, DEM_3, etc)
    :param root_folder: The path to the folder root
    :param clipping_network: The network to clip the layer with
    :return: A list of layers
    """
    if root_folder is None:
        return []

    layers = []
    for instance_folder in os.listdir(root_folder):
        instance_folder_path = os.path.join(root_folder, instance_folder)
        layers += find_layers_in_folder(instance_folder_path, clipping_network)
    return layers


def find_dem_derivative(root_folder, dir_name, clipping_network=None):
    """
    Designed to look specifically for flow, slope, and hillshade layers
    :param root_folder: Where we look
    :param dir_name: The directory we're looking for
    :return:
    """
    layers = []
    for instance_folder in os.listdir(root_folder):
        instance_folder_path = os.path.join(os.path.join(root_folder, instance_folder), dir_name)
        if os.path.exists(instance_folder_path):
            layers += find_layers_in_folder(instance_folder_path, clipping_network)
    return layers


def find_layers_in_folder(folder_root, clipping_network):
    """
    Returns a list of all layers in a folder
    :param folder_root: Where we want to look
    :param clipping_network: The network to clip the layer with
    :return:
    """
    layers = []
    if folder_root is None:
        return layers
    for instance_file in os.listdir(folder_root):
        if clipping_network is not None:
            if instance_file.endswith("_clipped.lyr"):
                layers.append(os.path.join(folder_root, instance_file))
            elif os.path.basename(instance_file) == "BankfullChannelPolygon.lyr":
                layers.append(os.path.join(folder_root, instance_file))
        elif instance_file.endswith(".lyr"):
            layers.append(os.path.join(folder_root, instance_file))
    return layers


def group_layers(group_layer, group_name, layers, df, mxd, remove_layer=True):
    """
    Groups a bunch of layers together
    :param group_layer: The empty group layer we'll add stuff to
    :param group_name: The name of the group layer
    :param layers: The list of layers we want to put together
    :param df:
    :param mxd:
    :param remove_layer: Tells us if we should remove the layer from the map display
    :return: The layer that we put our layers in
    """
    if layers == [] or layers is None:
        return None

    layers = [x for x in layers if x is not None]  # remove none type from the layers

    group_layer = arcpy.mapping.Layer(group_layer)
    group_layer.name = group_name
    group_layer.description = "Made Up Description"
    arcpy.mapping.AddLayer(df, group_layer, "BOTTOM")
    group_layer = arcpy.mapping.ListLayers(mxd, group_name, df)[0]

    for layer in layers:
        if isinstance(layer, arcpy.mapping.Layer):
            layer_instance = layer
        else:
            layer_instance = arcpy.mapping.Layer(layer)

        arcpy.mapping.AddLayerToGroup(df, group_layer, layer_instance)
    
    if remove_layer:
        arcpy.mapping.RemoveLayer(df, group_layer)

    return group_layer


def check_layer(layer_path, base_path, symbology_layer=None, is_raster=False, layer_name=None):
    """
    If the base exists, but the layer does not, makes the layer
    :param layer_path: The layer we want to check for
    :param base_path: The file that the layer is based off of
    :param symbology_layer: The symbology to apply to the new layer (if necessary)
    :param is_raster: If the new layer is a raster
    :param layer_name: The name of the layer to check
    :return:
    """
    if not os.path.exists(layer_path) and os.path.exists(base_path):
        output_folder = os.path.dirname(layer_path)
        if layer_name is None:
            layer_name = os.path.basename(layer_path)
        make_layer(output_folder, base_path, layer_name, symbology_layer, is_raster=is_raster)


def find_file(proj_path, file_pattern):
    """
    Finds and returns a specific file
    :param proj_path: The path to the project folder
    :param file_pattern: A string representing the pattern to follow to get to the file
    :return: The filepath retrieved
    """

    search_path = os.path.join(proj_path, file_pattern)
    if len(glob.glob(search_path)) > 0:
        file_path = glob.glob(search_path)[-1]
    else:
        file_path = None

    return file_path


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
            if err[0][6:12] == "000873":
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


if __name__ == "__main__":
    main(
        sys.argv[1],
        sys.argv[2],
        sys.argv[3])
