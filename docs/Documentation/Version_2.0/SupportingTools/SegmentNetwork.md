---
title: Segment Network Tool
category: Supporting Tools
---

For RCAT to run properly, the input stream network must be segmented into reaches of a specified interval. The Segment Network Tool segments an NHD network for input into the [RCAT Project Builder]({{ site.baseurl }}/Documentation/Version_2.0/RCAT/2-RCATProjectBuilder).

## Pre-Processing

The downloaded NHD network should be run through the [NHD Network Builder]({{ site.baseurl }}/Documentation/Version_2.0/SupportingTools/NHD) before being input into the Segment Network Tool.

## Parameters

![SegmentNetwork_interface]({{ site.baseurl }}/assets/images/SegmentNetwork_interface_2.0.PNG)

- **Select input stream network**: Select the network to segment (this should be a cleaned up NHD network).
- **Select output file path**: Specify a file path and name for the output segmented network.
- **Segmentation interval (in meters)**: Specify the segmentation interval. Segments of the output file will mostly be this length. The default is 300 meters.
- **Minimum segment length (in meters)**: Specify the minimum segment length. Segments smaller than this length will be merged with adjacent segments. The default is 50 meters.
