[R-CAT: Riparian Condition Assessment Tool]({{ site.url }})‎ > ‎[R-CAT Applications]({{ site.baseurl }}/R-CATApplications)‎ >

### Utah Implementation

### The Need for Statewide Riparian Mapping, Condition Assessment and Recovery Potential Products

- Riparian areas provide critical habitat for the majority of Utah's wildlife. 
- Effective and efficient wildlife management requires accurate and comprehensive riparian zone mapping and assessment.
- Riparian habitat extent and condition can be used to strategically prioritize conservation and restoration projects.
- Riparian recovery potential maps can help prioritize restoration sites and can help develop realistic restoration goals.

#### Closing the Riparian Data Gap

Until now, for most of Utah, adequate riparian habitat maps describing extent, condition and recovery potential were lacking. In 2013, in an effort to close this data gap, the Bureau of Land Management (BLM) in conjunction with Utah State University's Department of Watershed Sciences began a project to delineate riparian areas throughout the Colorado Plateau Ecoregion that includes the eastern half of Utah. In 2014, a project supported by the Utah Endangered Species Mitigation Fund (ESMF) extended this riparian area mapping effort to include the western half of Utah's perennial stream and river network. In 2015, the Utah Division of Wildlife Resources (UDWR) Pittman-Robertson Wildlife Restoration Act (PR) funds was used to further refine and extend riparian condition assessment and recovery potential products statewide.



### 2013-2014 BLM Funded Riparian Mapping Project

The BLM funded study resulted in delineation of all valley bottoms for the Colorado Plateau Ecoregion (Figure 1 and Figure 2).

![fig1right]({{ site.baseurl }}/assets/images/fig1right.png)

*Figure 1 - The study area for the Bureau of Land Management project was the the entire Colorado Plateau Ecoregion.*

![fig2](/assets/images/fig2.png)

*Figure 2 - Example of spatially variable valley bottom delineation for the Colorado Plateau Ecoregion. The valley bottom sets the template for maximum riparian extent.*

The project also resulted in the initial development of the Riparian Vegetation Departure index (RVD). RVD is a ratio that is similar to the ‘observed’ to ‘expected’ (‘O/E’) type metrics used in environmental condition assessments. RVD characterizes riparian vegetation condition for a given stream reach as the ratio of existing vegetation to an estimation of pre-European settlement vegetation coverage (Figure 3). To numerically calculate condition, native riparian vegetation is coded as ‘1’ and invasive and upland classes are coded as ‘0’ in both the existing, and pre-European settlement vegetation rasters and condition is calculated as the ratio of current to historic native riparian coverage for a given reach.

To support reach-level assessments, we bound the lateral extent of our analysis by generating analysis polygons within the valley bottom. Analysis polygons are generated in three steps. First, each valley bottom unit is split into a series of Thiessen polygons, with centroids located at the midpoint of each stream segment (Figure 3). Second, the valley bottom is buffered by the pixel resolution of the vegetation data (i.e., 30-m vegetation data is buffered by 30 m) to ensure that the relevant vegetation data is completely contained within the valley bottom in headwater reaches (Figure 3). Finally, we clip the Thiessen polygon layer to the buffered valley bottom. The resulting polygons become the analysis features for which the RVD tool calculations are summarized (Figure 3).

Within each polygon, the mean of the values (i.e. the 1s and 0s) is calculated for both the existing and historic vegetation layers, resulting in values that represent the proportion of each polygon with native riparian cover (Figure 3). The final processing step is to apply the RVD calculation from the analysis polygons to reach segments and divide the historic proportion by the existing proportion (Figure 3). Low values (closer to 0) signify large departures from historic riparian coverage whereas high values (i.e., approaching or exceeding 1.0) denote that riparian communities are relatively intact (or even increasing). To facilitate output display we symbolize each reach based on departure from historic cover, defined as the calculated ratio subtracted from one, which results in a percent departure. We categorize ‘negligible departure’ as less than 10%, ‘minor departure’ 10% to 33%, ‘significant departure’ 33% to 66% and ‘large departure’ > 66%. The quality of this ratio depends both on the accuracy of the vegetation coverage datasets, and the appropriateness of the spatial scale (i.e., reach) at which calculations are made, relative to input data resolution.

In the Utah statewide application RVD used LANDFIRE Existing Vegetation Type (EVT) data and Biophysical Settings (BpS) data to estimate riparian vegetation change since Euro-American settlement at a reach level (500 m segments). The BpS layer spatially explicitly models what vegetation communities would likely occur in a specific location based on physical conditions (e.g. soils, elevation, aspect, moisture, and natural fire regime). We used the BpS layer to represent the reference (pre-settlement) vegetation condition and the EVT layer was used to represent the current (2012) vegetation condition (Figure 3). The vegetation condition assessment treats the valley bottom as the maximum probable riparian extent and contrasts existing riparian vegetation to predicted historic vegetation to estimate a score that represents the current proportion of historic native riparian vegetation cover still existing today (Figure 4).

![RVD_fig_for-web](/assets/images/RVD_fig_for-web.PNG)

*Figure 3 - A conceptual diagram of the riparian vegetation departure index showing how mid points of the drainage network (1) are used to generate Thiessen polygons (2) and how these polygons are buffered by the resolution of the vegetation data to ensure that vegetation data is completely contained within the valley bottom in headwater reaches (3). Riparian vegetation departure is calculated using the ratio of existing area of native riparian vegetation (4) to historic area of native riparian vegetation (5) and the output is a segmented drainage network containing riparian departure from historic condition scores (6).*

![fig3](/assets/images.fig3.png)