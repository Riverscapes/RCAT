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



**Version 1.0**

- [NHD Network Builder]({{ site.baseurl }}/Documentation/Version_1.0/NHD)
- [Valley Bottom Extraction Tool (VBET)]({{ site.baseurl }}/Documentation/Version_1.0/VBET)
- [Riparian Vegetation Departure (RVD)]({{ site.baseurl }}/Documentation/Version_1.0/RVD)
- [Riparian Condition Assessment (RCA)]({{ site.baseurl }}/Documentation/Version_1.0/RCA)


## Download

[![Riverscapes_DownloadGITHUB]({{ site.baseurl }}/assets/images/Riverscapes_DownloadGITHUB.png)](https://github.com/Riverscapes/RCAT/releases/latest)

[**Download**](https://github.com/Riverscapes/RCAT/releases/latest) the Riparian Condition Assessment Tools (RCAT) Latest Release (including VBET)

### Update History
 Update prior to GitHUB: 01/25/2017 - Version 1.0 released. The primary difference between 1.0 and previous versions is that the tools are now "project" structured. Before running the tools, the projects are prepared using the "Build Project" tools that allow you to gather all inputs and structures them before running the tools. An xml file is also produced containing some metadata.

02/14/2017 - RCAT Version 1.0.2 - Updates to RCA tool

03/06/2017 - RCAT Version 1.0.3 - Minor improvements

03/07/2017 - RCAT Version 0.2 and VBET Versions 0.2 and 1.0.2 - Minor improvements

03/08/2017 - RCAT Version 1.0.4 - fixed bug in RVD with large river polygon

03/20/2017 - RCAT and VBET Version 1.0.5 - updated xml format and matched current VBET version to current RCAT version

05/02/2017 - RCAT and VBET Versions 0.2.1 and 1.0.6 - added Bankfull Channel tool to RCAT 1.0.6. Outputs no longer include any segments not in valley bottom.

05/10/2017 - RCAT and VBET Versions 1.0.7 - retains networks segments in open water but attributes them with NoData values. RCAT 0.2.2 - same update.

06/20/2017 - RCAT and VBET Versions 1.0.8 - fixed problem with realization numbers and IDs, added Realization Promoter tool.

07/25/2017 - RCAT Version 1.0.9 - fixed bug with RVD tool.

08/03/2017 - RCAT Version 1.0.10 - When using the Realization Promoter Tool, you can now add in the edited VBET output to the VBET realization being promoted.

09/12/2017 - RCAT Versions 1.0.11 and 0.2.3 - fixed same bug that RVD tool had (fixed 1.0.9) in RCA tool.




![CC_Watermarks_Riverscapes]({{ site.baseurl }}/assets/images/CC_Watermarks_Riverscapes.png) This work is licensed under the Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International License. To view a copy of this license, visit <http://creativecommons.org/licenses/by-nc-sa/4.0/>.
