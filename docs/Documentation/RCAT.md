---
title: Riparian Condition Assessment Toolbox (RCAT)
---
## Introduction

The Riparian Condition Assessment Toolbox is an ArcGIS python toolbox created to remotely assess the condition of riparian and floodplain areas over fairly large spatial scales (e.g. HUC8 watersheds) using relatively coarse, nationally avialable datasets as inputs.

## Dependencies

- ArcPy Python module (included with ArcGIS installation)
- "Spatial Analyst" extension in ArcMap
- [scikit-fuzzy](https://pypi.python.org/pypi/scikit-fuzzy) Python module (RCA Tool only)
- In order for the scikit-fuzzy module to work properly, this [fix](https://github.com/scikit-fuzzy/scikit-fuzzy/commit/1c62c00fd218d47d7b15be021d6b65045ade958e) is required.


## Tool Documentation

### Version 2.0

For documentation on the major changes implemented, see [RCAT Version 2.0](({{ site.baseurl }}/Documentation/Version_2.0/Version2).


**RCAT** (Riparian Condition Assessment Toolbox)
- [RCAT Project Builder]({{ site.baseurl }}/Documentation/Version_2.0/RCAT/2-RCATProjectBuilder)
- [Riparian Vegetation Departure]({{ site.baseurl }}/Documentation/Version_2.0/RCAT/3-RVD)
- [Bankfull Channel]({{ site.baseurl }}/Documentation/Version_2.0/RCAT/4-BankfullChannelTool)
- [Confinement Tool]({{ site.baseurl }}/Documentation/Version_2.0/RCAT/5-ConfinementTool)
- [Riparian Condition Assessment]({{ site.baseurl }}/Documentation/Version_2.0/RCAT/6-RCA)

**VBET** (Valley Bottom Extraction Toolbox)
- [VBET Project Builder]({{ site.baseurl }}/Documentation/Version_2.0/VBET/1-VBETProjectBuilder)
- [Valley Bottom Extraction Tool]({{ site.baseurl }}/Documentation/Version_2.0/VBET/2-VBET)

**Supporting Tools**
- [NHD Network Builder]({{ site.baseurl }}/Documentation/Version_2.0/SupportingTools/NHD)
- [Segment Network Tool]({{ site.baseurl }}/Documentation/Version_2.0/SupportingTools/SegmentNetwork)
- [Add LANDFIRE Fields Tool]({{ site.baseurl }}/Documentation/Version_2.0/SupportingTools/AddLandfireFields)
- [Realization Promoter Tool]({{ site.baseurl }}/Documentation/Version_2.0/SupportingTools/RealizationPromoter)


### Version 1.0

- [NHD Network Builder]({{ site.baseurl }}/Documentation/Version_1.0/NHD)
- [Bankfull Channel Tool]({{site.baseurl }}/Documentation/Version_1.0/BankfullChannelTool)
- [Valley Bottom Extraction Tool (VBET)]({{ site.baseurl }}/Documentation/Version_1.0/VBET)
- [Riparian Vegetation Departure (RVD)]({{ site.baseurl }}/Documentation/Version_1.0/RVD)
- [Riparian Condition Assessment (RCA)]({{ site.baseurl }}/Documentation/Version_1.0/RCA)


## Download

[![Riverscapes_DownloadGITHUB]({{ site.baseurl }}/assets/images/Riverscapes_DownloadGITHUB.png)](https://github.com/Riverscapes/RCAT/releases/latest)

[**Download**](https://github.com/Riverscapes/RCAT/releases/latest) the Riparian Condition Assessment Tools (RCAT) Latest Release (including VBET)

### Update History

**04/11/2020 - RCAT Version 2.0.0** - Added bankfull channel and confinement tools for more accurate confinement metrics, added flexibility in vegetation input, added flexibility for vegetation classifications, added dredge tailings handling, added separate native riparian vegetation departure and overall riparian departure fields, improved riparian conversion metrics, added riparian conversion fields for riparian expansion and conversion to deciduous forest, increased linearity between RCAT tools, improved RCAT project folder structure, improved valley bottom delineation, added batch scripts for VBET, improved toolbox structure, added supporting tools for classifying LANDFIRE vegetation and segmenting the network, and increased stability of tools by fixing many minor bugs. Details on these changes can be found on the [RCAT Version 2.0 page]({{ site.baseurl }}/Documentation/Version_2.0/). 

**09/12/2017 - RCAT Versions 1.0.11 and 0.2.3** - fixed same bug that RVD tool had (fixed 1.0.9) in RCA tool.

**08/03/2017 - RCAT Version 1.0.10** - When using the Realization Promoter Tool, you can now add in the edited VBET output to the VBET realization being promoted.

**07/25/2017 - RCAT Version 1.0.9** - fixed bug with RVD tool.

**06/20/2017 - RCAT and VBET Versions 1.0.8** - fixed problem with realization numbers and IDs, added Realization Promoter tool.

**05/10/2017 - RCAT and VBET Versions 1.0.7** - retains networks segments in open water but attributes them with NoData values. RCAT 0.2.2 - same update.

**05/02/2017 - RCAT and VBET Versions 0.2.1 and 1.0.6** - added Bankfull Channel tool to RCAT 1.0.6. Outputs no longer include any segments not in valley bottom.

**03/20/2017 - RCAT and VBET Version 1.0.5** - updated xml format and matched current VBET version to current RCAT version

**03/08/2017 - RCAT Version 1.0.4** - fixed bug in RVD with large river polygon

**03/07/2017 - RCAT Version 0.2 and VBET Versions 0.2 and 1.0.2** - Minor improvements

**03/06/2017 - RCAT Version 1.0.3** - Minor improvements

**02/14/2017 - RCAT Version 1.0.2** - Updates to RCA tool

 **Updates prior to GitHub: 01/25/2017** - Version 1.0 released. The primary difference between 1.0 and previous versions is that the tools are now "project" structured. Before running the tools, the projects are prepared using the "Build Project" tools that allow you to gather all inputs and structures them before running the tools. An xml file is also produced containing some metadata.


![CC_Watermarks_Riverscapes]({{ site.baseurl }}/assets/images/CC_Watermarks_Riverscapes.png) This work is licensed under the Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International License. To view a copy of this license, visit <http://creativecommons.org/licenses/by-nc-sa/4.0/>.
