---
title: Riparian Condition Assessment (RCA)
---

The Riparian Condition Assessment (RCA) tool models the condition of riparian areas based on three inputs: riparian vegetation departure (as modeled using the [RVD](https://bitbucket.org/jtgilbert/riparian-condition-assessment-tools/wiki/Tool_Documentation/RVD) tool), land use intensity, and floodplain connectivity. Each segment of an input network is attributed with values on continuous scales for each of these three inputs. The output (condition) of each segment is then assessed using a fuzzy inference system. The tool produces an output polyline shapefile which includes the three model inputs as attributes, as well as an output table that contains the calculated condition for each segment which can be joined to the polyline using the "FID" field.

## Pre-Processing

- Prepare a stream network using the [NHD Network Builder]({{ site.baseurl }}/Documentation/Version_1.0/NHD)
- Dissolve and segment the network. (~500 meter segments work well.)
- Produce a valley bottom using [VBET]({{ site.baseurl }}/Documentation/Version_1.0/VBET), and manually edit to desired accuracy.
- Download the LANDFIRE EVT and BpS layers from the LANDFIRE [website](http://www.landfire.gov/) (for US Only; Equivalent vegetation layers may exist in other countries)

NOTE: These pre-processing steps are the same as for the RVD tool. If the RVD tool has already been run, these same inputs can be used to run the RCA tool.

To run this tool, one of the required inputs is a valley bottom polygon that has been fragmented using a transportation infrastructure network (roads, railroads, etc.). The following process describes how to derive this input:

- Overlay a finalized road/railroad network on a copy of a final, edited valley bottom polygon.
- Begin editing the valley bottom polygon. Select the whole road/railroad network (right click on the shapefile, go to "Selection" and choose "Select All").
- Go to "Editor" > "More Editing Tools" > "Advanced Editing"
- Click on the "Split Polygons" tool and split the valley bottom using the transportation network.
- Go through the split valley and manually fix polygons that need to be enclosed. (Areas where the stream does not intersect a polygon will be considered disconnected from the floodplain. See figure below.)

![manual](({{ site.baseurl }}/assets/images/fragvalley.png)

- Add a field (type short int) to the split valley bottom feature and name it "Connected".
- Make sure you are still editing the split valley bottom.
- In "Select by Location" select the portions of the split valley bottom polygon that the stream network intersects. In the attribute table, change value of the "Connected" field to 1 for the highlighted features.
- All other features should have a value of 0. (If necessary, reverse the selection and give the now highlighted features a value of 0.)
- Export the feature as a new shapefile with a name referring to floodplain connectivity. This will be used as an input in the RCA tool.

The figure below shows a final split valley bottom, ready for use in the tool.

![fp_connectivity]({{ site.baseurl }}/assets/images/fp_connectivity.png)

## Parameters

- **Input Segmented Stream Network**: select the stream network that was dissolved and segmented.

NOTE: In the current version of the tool, if the stream network contains too many features (or segments), the tool will run out of memory and fail to run. Stream networks for watersheds can be clipped down to subwatersheds to run the tool with, and then the outputs can be merged together. For future versions, this issue will be resolved.

- **Input Fragmented Valley Bottom**: select the shapefile of the valley bottom fragmented using transportation infrastructure in the pre-processing steps.
- **Existing Vegetation Layer**: select the LANDFIRE EVT layer for the area of interest.
- **Historic Vegetation Layer**: select the LANDFIRE BPS layer for the area of interest.
- **Valley Bottom Width Threshold**: enter a width value above which streams will be considered "unconfined" and below which the streams will be considered "confined." Note: the process used to calculate valley width gives a rough, over-estimated estimate, so this value should also be over-estimated (for example the default value of 190 meters for the tool is roughly 100 meters on the ground). The value can be decreased from the default value (190) in order to include more of the network as unconfined, or increased in order to include less of the network as unconfined.
- **Large River Polygon** (optional): In areas with large rivers (ie Green, Colorado, Snake, Columbia), all landcover cells within these large river polygons are coded as no data. In smaller rivers, the open water landcover class is coded as riparian. In development, we found that coding open water in large rivers as riparian skewed them to appear to be in better condition than they are. In small rivers, if open water was *not* coded as riparian, they appeared to be in worse condition than they were. The "Area" shapefile that was downloaded with NHD data can generally be used as this large river polygon.
- **RCA Output**: Select an output location and name for the final polyline output.
- **Scratch Workspace**: Select a geodatabase as a workspace to store temporary files. The default is the Arc default geodatabase.

## Outputs

- The RCA output symbolized using the default symbology of the `CONDITION` field.

![RCAoutput](({{ site.baseurl }}/assets/images/RCAoutput.png)

Additionally the `VEG` field may be of interest, and simply represents the proportion of historic vegetation cover (riparian and non-riparian) that exists on the landscape today.

- The RCA output symbolized using the `VEG` field to show the proportion of historic vegetation cover that exists now.

![RCAveg](({{ site.baseurl }}/assets/images/RCA_veg.png)

### Additional RCA Output Fields

`RVD`: The riparian vegetation departure score (proportion of historic riparian vegetation) for the given stream segment. `LUI`: The Land Use Intensity index, on a scale from 0 (high) to 3 (low). `CONNECT`: The proportion of the polygon (floodplain) associated with stream segment that is accessible to the stream. `COND_VAL`: A value on a continuous index from 0 to 1 that represents the condition of the riparian area for unconfined streams. (a value of 0 means that the stream is confined and the value is not relevant.)

![rca_workflow](({{ site.baseurl }}/assets/images/RCA_workflow.png)

Conceptual diagram showing how riparian condition assessment is calculated