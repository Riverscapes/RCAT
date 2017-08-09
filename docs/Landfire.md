[R-CAT: Riparian Condition Assessment Tool]({{ site.url }})‎ > ‎[R-CAT Applications]({{ site.baseurl }}/R-CATApplications)‎ > [Utah Implementation]({{ site.baseurl }}/UtahImplementation)

### LANDFIRE Data Limitations

### 30 M Vegetation Data Is Sometimes Too Coarse

In the Utah application, we used vegetation data from LANDFIRE, a nationwide 30 m Landsat satellite imagery-based landcover classification. In the narrowest desert or mountain headwater riparian corridors, 30 m spatial resolution data appears to be too coarse to consistently provide sufficient detail to adequately map riparian vegetation. Fortunately, with minor modifications, all of the R-CAT models can be run with higher resolution vegetation data and in settings with narrow riparian corridors, the use of higher resolution vegetation data is warranted (see Macfarlane et al. In press). In the products derived using the 30 m data, the coarseness of the data results in these narrow riparian corridors appearing to be in worse condition than they really are. For example, in a narrow headwater stream, the LANDFIRE Bps layer will depict a band of riparian vegetation, whereas in the EVT layer, the existing band is actually too narrow to be picked up in a 30 m cell, and the cell will consequently be classified as conifer, or whatever the dominant vegetation type within the 30 m cell is (Figure 1).

![fig1.1left](/assets/images/fig1.1left.PNG)

![fig1.1right](/assets/images/fig1.1right.PNG)

