---
title: Step 7 - Layer Package Generator
category: RCAT
---

The Layer Package Generator tool is an optional final step in the RCAT toolbox. Each of the RCAT tools creates layer files for relevant inputs, intermediates, and outputs, which allow the user to review and investigate the model results. Layer files are difficult to share or transfer because the rely on an absolute file path to a data source, which breaks when the layer is moved from its original location. Layer packages resolve this issue by including the data source with the layer. 

The Layer Package Generator gathers and organizes all layers from the RCAT model (and generates new layers if not found) into a layer package for easy transfer of model results.

## Running the Layer Package Generator
Completing the following steps before running the Layer Package Generator tool will ensure that the tool runs as desired.

**Clean up the project folder**
The Layer Package Generator relies on a consistent folder structure to find layer files and source data. As of the latest release (RCAT V2.0.2) the tool is not able to accept multiple versions of any input or output. Examples of this include: 

- Multiple networks, existing/historic vegetation rasters, valley bottoms, etc.
- Multiple iterations of RVD, Bankfull, Confinement, or RCA.

Before running the Layer Package Generator, you must select one version to include in the layer package and temporarily remove all other folders and files from the project folder. 

**Clear the table of contents**
Remove all files from the table of contents before running the tool. The tool may throw an error if the table of contents is not clear. 

### Inputs

![LPG_interface]({{ site.baseurl }}/assets/images/LPG_interface_2.0.PNG)

- **Output Folder** : RCAT automatically creates output folders, labeled “Output_01”, “Output_02”, etc. Layer Packages are meant to contain the outputs of only one run of RCAT. Choose which set of outputs you want to base your layer package off.
- **Layer Package Name** : Any set of characters is acceptable as input for the layer package name. If you choose to not give the tool a name for the layer package, it will default to “RCATLayerPackage.lpk” or "RCATLayerPackage_Clipped.lpk".
- **Clipping Network** (optional): Network to which all outputs will be clipped. If no clipping network is input, the layer package will include the entire network on which the model was run. Examples of possible clipping networks include a sub-watershed or the perennial network (if the model was run on a full network).

### Outputs

As you run the tool, you may see the layers being rapidly grouped in the Table of Contents, with the map changing accordingly. This is normal. Arcpy requires the layers to be added to the Table of Contents before they can be grouped, which leads to this odd-looking behavior. 

After the tool is run, there should be a layer package file in the selected output folder. This file can be emailed or uploaded without breaking any links between the symbology and data sources.

--------------------------------
<div align="center">
	<a class="hollow button" href="{{ site.baseurl }}/Documentation/Version_2.0/RCAT/6-RCA"><i class="fa fa-arrow-circle-left"></i> Back to Step 6 </a>
</div>	
