---
title: Riparian Vegetation Departure (RVD)
---

The Riparian Vegetation Departure (RVD) tool uses LANDFIRE landcover inputs to determine the departure of riparian vegetation from pre-settlement conditions. Current riparian vegetation cover is modeled using the LANDFIRE Existing Vegetation Type (EVT) layer. Historic (pre-European settlement) vegetation is modeled using the LANDFIRE Bio-physical Setting (BpS) layer. For more information on these layers see LANDFIRE's [website](http://landfire.gov/vegetation.php). In both of these layers, all native, riparian vegetation is given a value of 1, and all other vegetation is given a value of 0. The valley bottom is broken into polygons that correspond to approximately 500 meter segments of stream network, and within each polygon, the number of existing riparian cells is divided by the number of modeled historic riparian cells. The result is a ratio that represents the proportion of historic riparian vegetation that currently exists on the landscape. This value is then applied to the network. In addition, an analysis is performed that looks at types of riparian conversion and quantifies each type within each stream segment to determine possible causes of riparian degradation.

## Pre-Processing

- Prepare a network using the [NHD Network Builder]({{ site.baseurl }}/Documentation/Version_1.0/NHD)
- Dissolve and segment the network. (~500 meter segments work well.)
- Produce a valley bottom using [VBET]({{ site.baseurl }}/Documentation/Version_1.0/VBET), and manually edit to desired accuracy.
- Download the LANDFIRE EVT and BpS layers from the LANDFIRE [website](http://www.landfire.gov/) (for US Only; Equivalent vegetation layers may exist in other countries)

## Parameters

- **Existing Vegetation layer**: select the LANDFIRE EVT layer for the area of interest.
- **Historic Vegetation layer**: select the LANDFIRE BPS layer for the area of interest.
- **Input Segmented Stream Network**: select the stream network that was dissolved and segmented.
- **Input Valley Bottom Polygon**: select the valley bottom polygon that was created using VBET and manually edited.
- **Large River Polygon** (optional): In areas with large rivers (ie Green, Colorado, Snake, Columbia), all landcover cells within these large river polygons are coded as no data. In smaller rivers, the open water landcover class is coded as riparian. In development, we found that coding open water in large rivers as riparian skewed them to appear to be in better condition than they are. In small rivers, if open water was *not* coded as riparian, they appeared to be in worse condition than they were. The "Area" shapefile that was downloaded with NHD data can generally be used as this large river polygon.
- **RVD Output**: select a location and name to store the final polyline output.
- **Scratch Workspace**: Select a geodatabase as a workspace to store temporary files. The default is the Arc default geodatabase.

## Outputs

- Riparian Vegetation Departure ratio `DEP_RATIO`

![RVDoutput]({{ site.baseurl }}/assets/images/RVDoutput.png)

- Riparian Vegetation Conversion Type `CONV_TYPE`

![RCToutput]({{ site.baseurl }}/assets/images/RCToutput.png)

### Additional RCA Output Fields

`EVT_MEAN`: proportion of polygon corresponding to stream segment with existing riparian cover. `BPS_MEAN`: proportion of polygon corresponding to stream segment with historic riparian cover. `COUNT`: the number of cells within the polygon corresponding to stream segment that were historically riparian. `sum_noch`: the number of cells within the polygon corresponding to stream segment whose conversion type is 'no change.' `sum_grsh`: the number of cells within the polygon corresponding to stream segment whose conversion type is 'conversion to grass/shrubland.' `sum_deveg`: the number of cells within the polygon corresponding to stream segment whose coversion type is 'devegetate.' `sum_con`: the number of cells within the polygon corresponding to stream segment whose conversion type is 'conifer encroachment.' `sum_inv`: the number of cells within the polygon corresponding to stream segment whose conversion type is 'coversion to invasive.' `sum_dev`: the number of cells within the polygon corresponding to stream segment whose conversion type is 'developed.' `sum_ag`: the number of cells within the polygon corresponding to stream segment whose conversion type is 'conversion to agriculture.' `prop_noch`: proportion of polygon corresponding to stream segment where riparian remained riparian (`sum_noch`/`COUNT`). `prop_grsh`: proportion of polygon corresponding to stream segment in which riparian was converted to grassland or shrubland(`sum_grsh`/`COUNT`). `prop_deveg`: proportion of polygon corresponding to stream segment in which riparian was removed and no vegetation took it's place (ie remained dirt or rock) (`sum_deveg`/`COUNT`). `prop_con`: proportion of polygon corresponding to stream segment in which riparian was converted to conifer forest (`sum_con`/`COUNT`). `prop_inv`: proportion of polygon corresponding to stream segment in which riparian was converted to invasive vegetation (`sum_inv`/`COUNT`). `prop_dev`: proportion of polygon corresponding to stream segment in which riparian was converted to developed areas (`sum_dev`/`COUNT`). `prop_ag`: proportion of polygon corresponding to stream segment in which riparian was converted to agriculture (`sum_ag`/`COUNT`).

![rvd_workflow]({{ site.baseurl }}/assets/images//rvd_workflow.png)

Conceptual diagram showing how vegetation departure from historic and riparian vegetation conversion type are calculated