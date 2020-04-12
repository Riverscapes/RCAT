---
title: Version 2.0
---

Substantial changes were made to RCAT in early 2020 to improve accuracy, flexibility, stability, and usability of the RCAT toolbox. The fundamental riparian vegetation departure and riparian condition assessment outputs are comparable between RCAT versions, though version 2 outputs host significant methodology changes and are more accurate than version 1 outputs. Major changes in RCAT Version 2.0 are listed below. Detailed workflows can be found in the individual tool documentation. 

[![Riverscapes_DownloadGITHUB](assets/images/Riverscapes_DownloadGITHUB.png)](https://github.com/Riverscapes/RCAT/releases/latest)

To start the RCAT Version 2.0 tutorial, click the links below:

Step 1. [Pre-processing RCAT inputs.]({{ site.baseurl }}/Documentation/Version_2.0/RCAT/1-Preprocessing) 

Step 2. [RCAT Project Builder]({{ site.baseurl }}/Documentation/Version_2.0/RCAT/2-RCATProjectBuilder)

Step 3. [Riparian Vegetation Departure]({{ site.baseurl }}/Documentation/Version_2.0/RCAT/3-RVD)

Step 4. [Bankfull Channel Tool]({{ site.baseurl }}/Documentation/Version_2.0/RCAT/4-BankfullChannelTool)

Step 5. [Confinement Tool]({{ site.baseurl }}/Documentation/Verson_2.0/RCAT/5-ConfinementTool)

Step 6. [Riparian Condition Assessment]({{ site.baseurl }}/Documentation/Version_2.0/RCAT/6-RCA)

> NOTE: RCAT Version 2.0 was developed using ArcMap 10.6.1 and tested on ArcMap 10.6.1 and ArcMap 10.7.1.

## Added flexibility in vegetation input classifications

In RCAT Version 1.0, riparian vegetation, vegetation groups, and land use fields were hard-coded into the RVD and RCA tools. This prevented flexibility in these codings between watersheds and also limited RCAT to accepting LANDFIRE vegetation data. Hard-coding these fields also opened RCAT up to the possibility of being antiquated or missing updated fields and vegetation types included in newer LANDFIRE releases.

In RCAT Version 2.0, none of the required vegetation fields are hard-coded into the main toolbox. Instead, all required vegetation fields must be user-specified manually prior to running RCAT. For users using LANDFIRE data, the new [Add LANDFIRE Fields tool]({{ site.baseurl }}/Documentation/Version_2.0/SupportingTools/AddLandfireFields) in the Supporting Tools category of the toolbox will add these fields. However, we *highly encourage* that you double check the fields added by this tool to make sure the classifications represent the realities in your study area and that no landcover types were missed. 

This change will allow more accurate classifications across study areas and project objectives, as well as enable RCAT to accept any vegetation dataset that has the required attribute fields added and populated as described in the preprocessing steps.

## Added dredge tailings handling

In RCAT Version 2.0, dredge tailing polygons are accepted as an input for both the RVD and RCA tools. Areas with dredge tailings are handled equivalent to how large rivers are handled in both tools- vegetation within these polygons is reclassified as non-riparian and connectivity is reclassified as disconnected. 

This change should greatly improve accuracy of riparian condition outputs, especially in areas where dredging activity is not represented in the vegetation and/or topographic data.

## Separate native riparian vegetation departure and overall riparian vegetation departure fields

In RCAT Version 1.0, the riparian vegetation departure ratio was based only on native riparian vegetation, while the riparian condition assessment considered both native riparian and overall riparian vegetation departures. 

In RCAT Version 2.0, both a native riparian vegetation departure ratio and an overall riparian vegetation departure ratio are calculated. This change should reduce confusion and will help display two different metrics of riparian condition, especially in areas where any riparian vegetation presence indicates that underlying stream geomorphology is less disrupted than areas with no riparian vegetation present.

## Improved confinement metrics

In RCAT Version 1.0, confinement was calculated based on valley bottom width alone. Valley bottom width was calculated by converting thiessen polygons to a circle with equivalent area and using the diameter of this circle as the valley bottom width. Then, an arbitrary valley bottom width threshold was set by the user to categorize confined and unconfined reaches. 

In RCAT Version 2.0, confinement metrics are calculate by comparing valley bottom width to bankfull channel width. For this worflow to be effective, bankfull channel and confinement tools were added to the RCAT toolbox. Valley bottom and bankfull channel widths are now calculated by dividing these polygons to match up with the segmented network, then taking the polygon area divided by the stream segment length (which is equivalent to the polygon length at the axis along the stream). The ratio between these two widths is then taken. A user-specified threshold still must be set in RCA to separate confined and unconfined metrics, but now this threshold will be consistent across watersheds since it pertains to a bankfull channel:valley bottom ratio rather than a raw width. 

These changes improve the accuracy of confinement and make confinement values and thresholds consistent across study areas.

## Improved riparian conversion calculations

In RCAT Version 1.0, riparian conversions were based only on areas historically classified as riparian. In RCAT Version 2.0, conversion classifications are based on any areas classified historically *or* currently as riparian. This change enables riparian expansion to also be calculated.

## Added riparian conversion fields

In RCAT Version 2.0, the riparian conversion fields include the following changes:
- Added "Significant riparian expansion" and "Moderate riparian expansion" categories
- Added "Significant conversion to deciduous forest" and "Moderate conversion to deciduous forest" categories
- Merged all minor change conversion types (maximum conversion type of 10-25%) into a "Minor Change" category
- Created a "Very Minor Change" category for all conversion where the maximum conversion type <10%
- Added a "No Riparian Vegetation Detected" category when there is no riparian vegetation detected along a reach. In these cases, all vegetation values (including RVD ratios) are set to a NoData value.

These changes increase the accuracy of riparian conversion outputs and acknowledge points of ambiguity, including when data is scarce for a reach.

## VBET Improvements

Fixed bugs in VBET and improved accuracy to minimize the need for manual editing. Added batch scripts for VBET in the supporting tools folder.

## Improved toolbox linearity and project structure

In RCAT Version 1.0, separate project folder structures were created for RCA and RVD, and the calculations for riparian vegetation departure were run in both RCA and RVD. 

In RCAT Version 2.0, all RCAT inputs and outputs are stored in the same project folder, and RCA uses the outputs from RVD instead of re-calculating these fields. RCA also uses the thiessen polygon intermediates created by RVD instead of recreating these thiessen polygons. The RCAT toolbox interface has been improved to reflect these workflow changes (see below). The RCAT project folder structure has also been improved to better organize inputs, intermediates, and outputs (see below for example).

These changes will greatly increase the efficiency and project tracking of RCAT projects. 

[RCAT_toolbox_2.0]({{ site.baseurl }}/assets/images/RCAT_tbx_2.0.PNG)

RCAT Version 2.0 toolbox interface

[RCAT_project_folder_example]({{ site.baseurl }}/assets/images/RCAT_project_example.PNG)

RCAT Version 2.0 project structure

## Increased stability

Many bugs were fixed in this version, which has greatly increased the stability and reliability of the RCAT toolbox.

