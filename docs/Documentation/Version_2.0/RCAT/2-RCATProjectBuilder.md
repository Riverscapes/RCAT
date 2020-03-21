---
title: Step 1 - RCAT Project Builder
category: RCAT
---

The RCAT Project Builder tool builds a folder structure that organizes the input data in a standardized manner and provides the structure necessary for running subsequent RCAT tools.

NOTE: See the [preprocessing steps]({{ site.baseurl }}/Documentation/Version_1.0/Preprocessing) before running this tool.

## Parameters

![RCATProjectBuilder]({{ site.baseurl }}/assets/images/RCATProjectBuilder1_2.0.PNG)

![RCATProjectBuilder2({{ site.baseurl }}/assets/images/RCATProjectBuilder2_2.0.PNG)

- **Select project folder**: Select newly created folder to store all RCA inputs, intermediates, and outputs in.
- **Select drainage network datasets**: Select pre-processed segmented network shapefile(s) you want to use in this RCA run.
- **Select existing cover folder**: Select folder holding LANDFIRE existing vegetation data for the area of interest.
- **Select historic cover folder**: Select folder holding LANDFIRE historic vegetation data for the area of interest.
- **Select fragmented valley bottom datasets**: Select pre-processed valley bottom shapefile(s) you want to use in this RCA run.
- **Select large river polygons** (optional): Select large river shapefile(s) you want to use in this RCA run. 
- **Select dredge tailings polygons** (optional): Select dredge tailings shapefile(s) you want to use in this RCA run. 
- **Select DEM** (optional): Select DEM if you want to run the Bankfull Channel tool (required for the Confinement and RCA tools).
- **Select precipitation raster** (optional): Select precipitation raster if you want to run the Bankfull Channel tool (required for the Confinement and RCA tools).

NOTE: See the [RVD page]({{ site.baseurl }}/Documentation/Version_2.0/RCAT/RVD) for figures showing how including dredge tailings affects vegetation values.

