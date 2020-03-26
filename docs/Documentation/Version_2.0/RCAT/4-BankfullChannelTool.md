---
title: Step 3 - Bankfull Channel Polygon Tool
category: RCAT
---

The Bankfull Channel Tool generates an approximate bankfull channel, with an optional buffer. This tool is modified from the Bankfull Channel tool in the [Confinement Toolbox](http://confinement.riverscapes.xyz/) and is included as a basic tool for generating an active channel polygon used in the [Confinement Tool]({{ site.baseurl }}/Documentation/Version_2.0/5-ConfinementTool.md). 

## Parameters

![BankfullChannel_interface]({{ site.baseurl }}/assets/images/BankfullChannel_interface_2.0.PNG)

- **Segmented network**: Select input segmented network for which bankfull channels will be created.

>  Note: The tool uses the segmentation of the network. Too fine of segmentation will result in difficulty in finding the max drainage area for a section of stream, where too large of segmentation may result in overestimation of bankfull in many area.

- **Valley bottom polygon**: Select input fragmented valley bottom polygon.

> Shortcut: It may be possible to use a simple buffer polygon of the stream network, however, make sure that the 'stream' in the flow accumulation raster is within this buffer. Manual editing may be necessary at lower elevations with very large and flat valley bottoms.

- **DEM**: A DEM covering the entire watershed. It is highly recommended to use a projection system with equal cell size (i.e. UTM).
- **Drainage area raster** (optional): Drainage area raster for watershed, in square kilometers.
- **Precipitation raster**: Precipitation raster covering entire watershed, in millimeters. It is highly recommended to use a projection system with equal cell size (i.e. UTM).
- **Minimum Bankfull Width**: Minimum width of the bankfull channel, in meters. Default value is 5.
- **Percent Buffer** (optional): Percent by which to buffer the calculated bankfull width, for adjustment of the regression equation to other watersheds. Default value is 100 (i.e., buffered width is the same as calculated bankfull width).

> Note: You will want to increase this buffer for the confinement tool, which identifies confinement as any instance where the bankfull channel intersects the valley bottom polygon.

- **Output Folder**: Output folder for current RCAT run, to which outputs and intermediates will be saved to.
- **Output Name**: Name of output bankfull channel polygon.

## Output

### Bankfull Channel Fields

- `DRAREA`: Drainage area for reach, in square kilometers, calculated as the maximum value within a thiessen polygon centered on the reach's midpoint and clipped to the input valley bottom. 
- `PRECIP`: Precipitation for reach, in millimeters, calculated as the maximum value within a thiessen polygon centered on the reach's midpoint and clipped to the input valley bottom.
- `BFWIDTH`: Calculated bankfull channel width of reach, in meters, based on the equation from Beechie and Imaki 2013.
- `BUFWIDTH`: Buffered bankfull channel width of reach, calculated as `BFWIDTH * (percent_buffer / 100)` with `percent_buffer` defined in the input parameters. This is the value used to buffer the network to create the output bankfull channel polygon.

### Bankfull Channel Polygon

Bankfull polygons for each continuous section of  stream network, created by buffering each reach of the input segmented network by `BUFWIDTH`, then dissolving and smoothing the result.

![BankfullOutput]({{ site.baseurl }}/assets/images/Bankfull_output_2.0.png)

Bankfull output polygon (light blue)


------

## Summary of Method 

1. Generate thiessen polygons from the midpoints of the input segmented network, clipped to the input valley bottom extent.
2. Use Zonal Statistics to find the maximum values of precipitation and drainage area for each thiessen polygon.
3. Assign `PRECIP` and `DRAREA` values to each segment based on the zonal statistics from the corresponding thiessen polygon.
4. Calculate Bankfull Width for each segment based on the following regression:
   bf_width(m) = 0.177(DrainageArea^0.397)(Precip^0.453))
5. Calculate buffer width:
   bf_buffer(m) = bf_width + bf_width/(percent buffer/100)
6. Perform buffer on each segment based on the buffer width.
7. Buffer the input segmented network by the buffer width of each segment.
8. Generate a minimum width buffer.
9. Merge and dissolve the bankfull polygon with the minimum width buffer.
10. Apply 10m "PAEK" smoothing.

## Citation

Beechie, T. and H. Imaki. 2013. Predicting natural channel patterns based on landscape and geomorphic controls in the Columbia River basin, USA. Water Resources Research 50(1): 39-57. https://doi.org/10.1002/2013WR013629.
