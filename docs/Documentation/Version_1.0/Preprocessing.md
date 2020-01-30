---
title: Pre-Processing Inputs
---

The Riparian Condition Assessment and Riparian Vegetation Departure tools require the following preparation of input files:

- Prepare a stream network using the [NHD Network Builder]({{ site.baseurl }}/Documentation/Version_1.0/NHD)
- Dissolve and segment the network. (~500 meter segments work well.)
- Produce a valley bottom using [VBET]({{ site.baseurl }}/Documentation/Version_1.0/VBET), and manually edit to desired accuracy.
- Download the LANDFIRE EVT and BpS layers from the LANDFIRE [website](http://www.landfire.gov/) (for US Only; Equivalent vegetation layers may exist in other countries)
- If you want to account for dredge tailing impacts, download mine-related spatial data from the [USGS Mineral Resources website](https://mrdata.usgs.gov/usmin/) for the state of interest. For efficiency, this shapefile should be clipped to the watershed boundary. This shapefile will represent all mining activity in your watershed, so you will want to select the features representing dredge tailings and export these to a new shapefile. 

One of the required inputs is a valley bottom polygon that has been fragmented using a transportation infrastructure network (roads, railroads, etc.). The following process describes how to derive this input from the VBET output:

- Overlay a finalized road/railroad network on a copy of a final, edited valley bottom polygon.
- Begin editing the valley bottom polygon. Select the whole road/railroad network (right click on the shapefile, go to "Selection" and choose "Select All").
- Go to "Editor" > "More Editing Tools" > "Advanced Editing"
- Click on the "Split Polygons" tool and split the valley bottom using the transportation network.
- Go through the split valley and manually fix polygons that need to be enclosed. (Areas where the stream does not intersect a polygon will be considered disconnected from the floodplain. See figure below.)

![manual]({{ site.baseurl }}/assets/images/fragvalley.png)

- Add a field (type short int) to the split valley bottom feature and name it "Connected".
- Make sure you are still editing the split valley bottom.
- In "Select by Location" select the portions of the split valley bottom polygon that the stream network intersects. In the attribute table, change value of the "Connected" field to 1 for the highlighted features.
- All other features should have a value of 0. (If necessary, reverse the selection and give the now highlighted features a value of 0.)
- Export the feature as a new shapefile with a name referring to floodplain connectivity. This will be used as an input in the RCA tool.

The figure below shows a final split valley bottom, ready for use in the tool.

![fp_connectivity]({{ site.baseurl }}/assets/images/fp_connectivity.png)
