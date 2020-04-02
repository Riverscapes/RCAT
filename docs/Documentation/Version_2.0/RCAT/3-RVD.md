---
title: Step 2 - Riparian Vegetation Departure (RVD)
category: RCAT
---

The Riparian Vegetation Departure (RVD) tool uses vegetation landcover inputs to determine the departure of riparian vegetation between two time periods. Generally, RVD is used to compare current riparian vegetation cover (modeled using the LANDFIRE Existing Vegetation Type (EVT) layer) to historic (pre-European settlement) vegetation (modeled using the LANDFIRE Bio-physical Setting (BpS) layer). For more information on EVT and BpS layers, see LANDFIRE's [website](http://landfire.gov/vegetation.php). Alternatively, RVD could be used to compare pre- and post-restoration vegetation conditions as long as vegetation landcover data is available for both before and after the restoration. LANDFIRE EVT layers are reclassified based on imagery every two years, so this could be an option for pre- and post-restoration landcover data, or drone imagery could be collected and classified into landcover classes. Before running RVD, both vegetation layers must have the following attributes populated: `RIPARIAN`, `NATIVE_RIP`, and `CONVERSION`. See the [preparing RCAT inputs page]({{ site.baseurl }}/Documentation/RCAT/Version_2.0/1-Preprocessing) for details. The riparian departure field is required to run the [Riparian Condition Assessment (RCA) tool]({ site.baseurl }/Documentation/Version_2.0/RCAT/6-RCA).


## Parameters

![RVD_interface]({{ site.baseurl }}/assets/images/RVD_interface_2.0.PNG)


- **Project name** (optional): Project name to be used in the XML metadata file.
- **Watershed HUC ID** (optional): Watershed HUC ID to be used in the XML metadata file.
- **Watershed name** (optional): Watershed name to be used in the XML metadata file.
- **Select project folder**: Select project folder created by the RVD Project Builder.
- **Select existing vegetation raster**: Select the LANDFIRE EVT layer for the area of interest.
- **Select historic vegetation raster**: Select the LANDFIRE BPS layer for the area of interest.
- **Select segmented stream network**: Select the stream network shapefile from the inputs folder within the project folder.
- **Select valley bottom polygon**: Select the fragmented valley bottom polygon shapefile from the inputs folder within the project folder. 
- **Select large river polygon** (optional): Select the large river polygon shapefile from the inputs folder. In areas with large rivers (ie Green, Colorado, Snake, Columbia), all landcover cells within these large river polygons are coded as no data. In smaller rivers, the open water landcover class is coded as riparian. In development, we found that coding open water in large rivers as riparian skewed them to appear to be in better condition than they are. In small rivers, if open water was *not* coded as riparian, they appeared to be in worse condition than they were. The "Area" shapefile that was downloaded with NHD data can generally be used as this large river polygon.
- **Select dredge tailings polygon** (optional): Select the dredge tailings shapefile from the inputs folder. In areas with dredge tailings, existing riparian landcover is coded with a vegetation score of "0" - i.e., no riparian vegetation.
- **Name RVD output**: Specify a name to store the final polyline output, which will be found in the outputs folder within the project folder.

## RVD Outputs

### Standard Outputs

- **Native Riparian Vegetation Departure ratio** `NATIV_DEP`: This is calculated for each reach by finding the area of current existing native riparian landcover within the valley bottom of a reach, then dividing this value by the area of historic native riparian landcover within the reach's valley bottom. (equivalent to RCAT Version 1.0 `DEP_RATIO`)

![RVD_Native_Departure]({{ site.baseurl }}/assets/images/RVD_NativDep.png)

- **Riparian Vegetation Departure ratio** `RIPAR_DEP`: This is calculated for each reach by finding the area of current existing riparian landcover (including nonnative species) within valley bottom of a reach, then dividing this value by the historic riparian landcover within the reach's valley bottom.

![RVD_Riparian_Departure]({{ site.baseurl }}/assets/images/RVD_RiparDep.png)
 
- **Riparian Vegetation Conversion Type** `CONV_TYPE`: This is identified by comparing landcover within the riparian zone, with the riparian zone defined as the area within the valley bottom that is classified as riparian in either the existing *or* historic vegetation rasters. 

![RVD_Conv_Type]({{ site.baseurl }}/assets/images/RVD_Conversion.png)

### Comparison of Outputs with and without Dredge Tailings Input

- Riparian Vegetation Departure ratio without adjustment for dredge tailings

![RVDNoTailings]({{ site.baseurl }}/assets/images/RVDWithoutTailings.png)

- Riparian Vegetation Departure ratio with adjustment for dredge tailings

![RVDTailings]({{ site.baseurl }}/assets/images/RVDWithTailings.png)

### Additional RVD Output Fields

Riparian vegetation proportions for the valley bottom corresponding to each reach.

- `Ex_Rip_Mean`: Proportion of valley bottom with existing riparian cover. (equivalent to `EVT_MEAN` field from [RCAT Version 1.0]({{ site.baseurl }}/Documentation/Version_1.0/RVD)
- `Hs_Rip_Mean`: Proportion of valley bottom with historic riparian cover. (equivalent to `BPS_MEAN` field from RCAT Version 1.0){{ site.baseurl }}/Documentation/Version_1.0/RVD)
- `Ex_Ntv_Mean`: Proportion of valley bottom with existing *native* riparian cover.
- `Hs_Ntv_Mean`: Proportion of valley bottom with historic *native* riparian cover. In most cases this field is equivalent to `Hs_Rip_Mean`.

Pixel counts for converesion types within the riparian zone corresponding to each reach.

- `COUNT`: Total pixel count of the riparian zone.
- `calc_count`: Equivalent to `COUNT`, except that `0` values are set to `1` to avoid errors in later calculations. 
- `sum_noch`: Pixel count of conversion type 'no change' within the riparian zone (i.e., historic and existing landcover are both riparian). 
- `sum_decid`: Pixel count of conversion type 'conversion to deciduous/hardwood forest' within the riparian zone (i.e., historic landcover is riparian and existing landcover is deciduous/hardwood forest).
- `sum_grsh`: Pixel count of conversion type 'conversion to grass/shrubland' within the riparian zone (i.e., historic landcover is riparian and existing landcover is grass/shrub). 
- `sum_deveg`: Pixel count of coversion type 'devegetated' within the riparian zone (i.e., historic landcover is riparian and existing landcover is rock/ice/sand/etc). 
- `sum_con`: Pixel count of conversion type 'conifer encroachment' within the riparian zone (i.e., historic landcover is riparian and existing landcover is conifer/mixed conifer-hardwood).
- `sum_inv`: Pixel count of conversion type 'conversion to invasive' within the riparian zone (i.e., historic landcover is riparian and existing landcover is invasive/exotic). 
- `sum_dev`: Pixel count of conversion type 'developed' within the riparian zone (i.e., historic landcover is riparian and existing landcover is developed/urban). 
- `sum_ag`: Pixel count of conversion type 'conversion to agriculture' within the riparian zone (i.e., historic landcover is riparian and existing landcover is agriculture). 
- `sum_exp`: Pixel count of conversion type 'riparian expansion' within the riparian zone (i.e., historic landcover is upland and existing landcover is riparian).

Proportion of the riparian zone corresponding to a reach occupied by each conversion type.

- `prop_noch`: Proportion of riparian zone with conversion type 'no change' (`sum_noch`/`calc_count`). 
- `prop_decid`: Proportion of riparian zone with conversion type 'conversion to deciduous/hardwood forest' (`sum_decid`/`calc_count`).
- `prop_grsh`: Proportion of riparian zone with conversion type 'conversion to grass/shrubland' (`sum_grsh`/`calc_count`). 
- `prop_deveg`: Proportion of riparian zone with conversion type 'devegetated' (`sum_deveg`/`calc_count`). 
- `prop_con`: Proportion of riparian zone with conversion type 'conifer encroachment' (`sum_con`/`calc_count`). 
- `prop_inv`: Proportion of riparian zone with conversion type 'conversion to invasive' (`sum_inv`/`calc_count`). 
- `prop_dev`: Proportion of riparian zone with conversion type 'developed' (`sum_dev`/`COUNT`). 
- `prop_ag`: Proportion of riparian zone with conversion type 'conversion to agriculture' (`sum_ag`/`calc_count`).
- `prop_exp`: Proportion of riparian zone with conversion type 'riparian expansion' (`sum_exp`/`calc_count`)
- `conv_code`: Numerical code assigning major conversion type based on conversion type `prop_**` fields. Each `conv_code` value corresponds to a `Conv_Type` value.

## RVD Workflow

1. The valley bottom is broken into thiessen polygons that correspond to segments/reaches on the stream network.
2. Within each polygon, the number of existing riparian cells, historic riparian cells, existing native riparian cells, and historic native riparian cells is calculated. 
3. The calculated cell counts from step 2 are joined to the corresponding network segments.
4. Overall riparian vegetation departure is calculated by dividing the existing riparian count by the historic riparian count for each segment or reach. The result is a ratio that represents the proportion of historic riparian vegetation that currently persists on the landscape, including invasive riparian landcover. 
5. Native riparian vegetation departure is calculated by dividing the existing native riparian count by the historic native riparian count for each segment or reach. The result is a ratio that represents the proportion of historic native riparian vegetation that persists on the landscape.
6. Riparian conversion types are identified on a cell-by-cell basis by comparing existing to historic landcover types within the riparian zone. The riparian zone is defined as any cell classified as existing *or* historic riparian landcover.
7. Dominant riparian conversion types are assigned to each stream segment by finding the conversion type that accounts for the largest area within the surrounding riparian zone. If less than 10% of a segment's riparian zone has changed, the segment is classified as "no change". If multiple conversion types account for equally large proportions of the riparian zone, then the segment is classified as "multiple dominant conversion types".

![rvd_workflow]({{ site.baseurl }}/assets/images//rvd_workflow.png)

Conceptual diagram showing how vegetation departure from historic and riparian vegetation conversion type are calculated

<div align="center">
	<a class="hollow button" href="{{ site.baseurl }}/Documentation/Version_2.0/RCAT/2-RCATProjectBuilder"><i class="fa fa-arrow-circle-left"></i> Back to Step 2 </a>
	<a class="hollow button" href="{{ site.baseurl }}/Documentation/Version_2.0/RCAT/4-BankfullChannelTool"><i class="fa fa-arrow-circle-right"></i> Continue to Step 4 </a>
</div>	
