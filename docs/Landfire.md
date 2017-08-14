---
title: LANDFIRE Data Limitations
---

[![RCAT_Banner_Web](assets/images/RCAT_Banner_Web.png)]({{ site.url }})


[R-CAT: Riparian Condition Assessment Tool]({{ site.url }})‎ > ‎[R-CAT Applications]({{ site.baseurl }}/R-CATApplications)‎ > [Utah Implementation]({{ site.baseurl }}/UtahImplementation)

### LANDFIRE Data Limitations

### 30 M Vegetation Data Is Sometimes Too Coarse

In the Utah application, we used vegetation data from LANDFIRE, a nationwide 30 m Landsat satellite imagery-based landcover classification. In the narrowest desert or mountain headwater riparian corridors, 30 m spatial resolution data appears to be too coarse to consistently provide sufficient detail to adequately map riparian vegetation. Fortunately, with minor modifications, all of the R-CAT models can be run with higher resolution vegetation data and in settings with narrow riparian corridors, the use of higher resolution vegetation data is warranted (see Macfarlane et al. In press). In the products derived using the 30 m data, the coarseness of the data results in these narrow riparian corridors appearing to be in worse condition than they really are. For example, in a narrow headwater stream, the LANDFIRE Bps layer will depict a band of riparian vegetation, whereas in the EVT layer, the existing band is actually too narrow to be picked up in a 30 m cell, and the cell will consequently be classified as conifer, or whatever the dominant vegetation type within the 30 m cell is (Figure 1).

![fig1.1left](/assets/images/fig1.1left.PNG)

![fig1.1right](/assets/images/fig1.1right.PNG)

Figure 1 - Green depicts the modeled historic riparian vegetation from BpS, and pink depicts the current riparian vegetation based on Landsat 
classification. The right panel demonstrates an area where a thin riparian band is modelled in the LANDFIRE BpS, but is not significantly
wide to be picked up in the EVT, resulting in an underestimation of condition.

### Invasive Riparian Vegetation Is Underestimated In The LANDFIRE EVT Layer

Within the Colorado Plateau, many riparian areas have been completely overtaken by invasive tamarisk. The LANDFIRE EVT layer picks up some of this invasive vegetation on tributary streams within the region (e.g. Dirty Devil, San Rafael), but does not capture it well in the mainstem Colorado and Green Rivers. Consequently, the modeled riparian condition of these two rivers is overestimated. 

### Incision and Entrenchment Are Not Considered in the Riparian Condition Assessment

The Riparian Condition Assessment (RCA) tool assesses riparian condition based on the departure of current riparian vegetation cover from historic, floodplain fragmentation due to transportation infrastructure and land use intensity within the surrounding valley bottom, all indicative of floodplain condition. Nevertheless, the model does not provide a measure of channel incision or entrenchment which are important indicators for floodplain health. Such information could only be generated using high resolution topographic data (1 m LiDAR data), which is not yet available statewide in Utah.

### Grazing Pressure Is Not Considered in the Riparian Condition Assessment

Grazing pressure can have a large impact on riparian zones. Spatial data depicting grazing is lacking, and is difficult to model or estimate using the land cover classification data that R-CAT utilizes. For future versions of the tool, we intend to work on modelling both grazing pressure and eventually incision. Areas where grazing pressure and/or incision are present are generally modeled to be in better condition than they actually are in the RCA output.

### References

- Macfarlane, W.W., C.M. McGinty, B.G. Laub and S.J. Gifford. 2016. High resolution riparian vegetation mapping to prioritize conservation and restoration in a degraded desert river. Restoration Ecology