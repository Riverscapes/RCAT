---
title: Segment Network Tool
category: Supporting Tools
---

The outputs of several of the tools in this toolbox are summarized onto a stream network. We have found the most accurate nationally available stream network to be the 24k NHD (National Hydrography Dataset) provided by the USGS. Using the NHD Network Builder Tool, a subset of the complete network can be selected to represent only the portion of the network that the user is interested in (the perennial network for example).

## Pre-Processing

First, the NHD network must be downloaded. The data can be downloaded from the USGS [here](http://viewer.nationalmap.gov/basic/). Extract the file containing all NHD data to a location on your machine.

## Parameters

![SegmentNetwork_interface]({{ site.baseurl }}/assets/images/SegmentNetwork_interface_2.0.PNG)

- **Input NHD Flowline**: in the folder containing the NHD data, select the flowline feature class. This is the complete network from which the subset will be extracted.
- **Input NHD Waterbody** (optional): if you want to remove flowlines from within waterbodies (lakes, reservoirs, etc), select the Waterbody feature class from the folder containing the NHD data (See 'subset artificial paths parameter).
- **Input NHD Area** (optional): in areas with large rivers, the flowlines are coded as 'artificial paths' within these area files, which are polygons representing the large rivers. If you are subsetting the artificial path flowlines when running the tool (see next parameter), select the Area feature class from the folder containing the NHD data in order to keep these flowlines.
- **Check to subset artificial paths** (optional): if you want to keep some artificial paths, but not all of them, check this box. Many portions of the perennial network are coded as artificial paths, but if you do not check this box, and consequently keep all of them, you may end up with flowlines that you do not want to be part of the final network. For example, flowlines that cross reservoirs and stock ponds. By checking this box, the artificial paths are subset to keep all artificial paths representing rivers, while removing those that cross waterbodies larger than a size specified in the next parameter.
- **Waterbody threshold size** (optional): if subsetting the artificial paths, this is the waterbody threshold size (in square kilometers) above which the flowlines will be removed from the waterbody.
  The default value is 0.001, which is the size of a large beaver dam. Using the default value will keep the flowlines in beaver ponds and other small ponds along the network, and remove them from larger lakes and reservoirs. If you want a continuous network, either do not subset the artificial paths, or choose a very large value for the threshold size (this has the advantage of still removing artifical paths in stock ponds and other locations that aren't part of the network of interest).
- **Remove Artifical Paths** (optional): check this box if you wish to remove all artificial paths from the final network.


## Outputs

![flowline](https://bitbucket.org/jtgilbert/riparian-condition-assessment-tools/wiki/Tool_Documentation/pics/flowline.png)

Raw NHD Flowline Input for a HUC 8 Watershed

![network](https://bitbucket.org/jtgilbert/riparian-condition-assessment-tools/wiki/Tool_Documentation/pics/network.png)

Final Network Output from the NHD Network Builder