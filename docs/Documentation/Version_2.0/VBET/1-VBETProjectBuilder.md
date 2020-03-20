---
title: Valley Bottom Extraction Tool (VBET) Project Builder
category: VBET
---

A valley bottom is a low lying area of a valley comprised of both the stream channel and contemporary floodplain. This area also represents the maximum possible extent of riparian areas of the streams associated with the valley bottom. VBET uses a minimum of two input datasets, a Digital Elevation Model (DEM) and a stream network to create a polygon representing the valley bottom. This valley bottom polygon is then used as an extent for the riparian condition analyses in this toolbox.

## Pre-Processing

Stream network preparation: a stream network for the area of interest must first be prepared. See [NHD Network Builder Tool]({{ site.baseurl }}/Documentation/Version_2.0/SupportingTools/NHD).
DEM preparation: A DEM should be downloaded and clipped to the extent of the analysis area (ie match the extent of the stream network). The DEM should have a projected coordinate system that matches the selected coordinate system for the stream network.
Drainage area raster: optionally, a flow accumulation raster can be derived, and converted to a drainage area raster (units of square kilometers) to be used in the VBET tool. If this is not done beforehand, it will be performed automatically upon running the tool.

## Parameters

![VBETProjectInterface]({{ site.baseurl }}/assets/images/VBETProject_interface_2.0.PNG)

- **Select project folder**: Project folder where all inputs and outputs will be stored for the VBET project. 
- **Select DEM raster(s)**: Input DEM raster.
- **Select drainage network shapefile(s)**: Input stream network shapefile.
- **Select drainage area raster(s)** (optional): Input drainage area raster. If not provided, a drainage area raster will be calculated later. 
