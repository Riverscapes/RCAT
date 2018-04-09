---
title: Interpreting RCAT Outputs
---

[R-CAT: Riparian Condition Assessment Toolbox](http://rcat.riverscapes.xyz/)‎ > ‎

## Interpreting RCAT Outputs

### Valley Bottom Extraction Tool (V-BET)

The V-BET output is simply an output polygon that represents the extent of the valley bottom for associated stream networks. 

### Riparian Vegetation Departure (RVD)

The Riparian Vegetation Departure from historic condition output is a line network, that is symbolized by default departure (in percent) of existing riparian vegetation cover from modeled historic riparian vegetation cover.

![rvd_legend]({{ site.baseurl }}/assets/images/rvd_legend.PNG)

 *Figure 1 - The default symbolization for the Riparian Vegetation Departure from historic condition output*

The 'DEP_RATIO' field that is symbolized by default is not the only field in the output table, however. The following table lists and explains relevant fields in the Riparian Vegetation Departure output.

*Table 1 - Relevant Riparian Vegetation Departure output fields*

| Attribute Name | Description                              |
| -------------- | ---------------------------------------- |
| EVT_MEAN       | Represents approximate percent of existing riparian cover within the valley bottom associated with the given stream segment.  Based off of LANDFIRE EVT. |
| BPS_MEAN       | Represents approximate percent of historic riparian cover within the valley bottom associated with the given stream segment.  Based off of LANDFIRE BpS. |
| DEP_RATIO      | Equal to EVT_MEAN/BPS_MEAN.  Represents the proportion of historic riparian cover that currently exists within the valley bottom associated with the given stream segment.  The default symbolization for 'departure' is equal to 1 - DEP_RATIO. |
| CONV_CODE      | Conversion Code.  Each landcover type in both the EVT and BpS layers are given a unique value.  The EVT values are then subtracted from the BpS values, creating a 'Conversion Code' which has an associated 'Conversion Type.'  (See table 2) |
| CONV_TYPE      | Conversion Type.  For all 'Conversion Codes,' there is a corresponding conversion type, which gives a likely cause for riparian reduction or degradation.  (See table 2) |



On rare occasions, the existing vegetation layer will show an increase in riparian vegetation from the historic vegetation layer, resulting in a 'dep_ratio' of greater than one.  This causes the departure to be a negative value.  Because the accuracy of existing vegetation data is generally not high enough to determine that such increases are real, these are lumped into the 'negligible departure' output category.

The 'CONV_TYPE' field is the other field which can be meaningfully symbolized. If there has been a reduction in riparian vegetation for a given stream segment, the 'CONV_TYPE' field describes what the likely cause for the degradation is. The 'CONV_TYPE' field is the extension of the original Riparian Vegetation Departure that we refer to as Riparian Vegetation Conversion Type.

*Figure 2 - Symbolization used for the Riparian Vegetation Conversion Type output, which is the 'CONV_TYPE' field in the Riparian Vegetation Departure output*

![rvct_legend]({{ site.baseurl }}/assets/images/rvct_legend.PNG)



*Table 2 - Conversion codes and associated conversion types in the Riparian Vegetation Conversion Type.*



| Conversion Type                   | Conversion Code(s) |
| --------------------------------- | ------------------ |
| Conifer Encroachment              | 80                 |
| Conversion to Agriculture         | 99                 |
| Devegetated                       | 60                 |
| Development                       | 98                 |
| Conversion to Invasive Vegetation | 97                 |
| No Change                         | 0                  |
| Conversion to Grass/Shrubland     | 50                 |



### Riparian Condition Assessment (RCA)

The Riparian Condition Assessment output is a line network that is symbolized by a field that represents overall riparian area condition (based on Riparian Vegetation Departure, land use intensity, and floodplain fragmentation) on a continuous scale from 0 (poor) to 1 (intact) in a field called 'CONDITION'. These values are broken into four bins: poor, moderate, good and intact.

![rca_legend]({{ site.baseurl }}/assets/images/rca_legend.PNG)

*Figure 3 - Layer symbolization for the Riparian Condition Assessment output*

As with Riparian Vegetation Departure, there are other meaningful fields in the output table. In addition to the condition field, there are fields which contain information for each of the inputs into the condition model. The table below lists and describes these additional fields.

*Table 2 - Relevant Riparian Condition Assessment output fields*

| Attribute Name | Description                              |
| -------------- | ---------------------------------------- |
| RVD            | The value for riparian vegetation departure as calculated using the RVD tool. |
| LUI            | A score for land use intensity (for the floodplain associated with each stream segment) on a continuous scale from 0 to 3 where 0 is completely urbanized and 3 is completely undisturbed.  Derived from LANDFIRE EVT. |
| CONNECT        | A value from 0 to 1 that represents the proportion of the floodplain associated with each stream segment that has not been cut off by transportation infrastructure. |



### Riparian Recovery Potential

The Riparian Recovery Potential uses the Riparian Condition Assessment outputs as an input and builds upon it using another model to come up with intrinsic Riparian Recovery Potential. In other words, the output represents the ability of the riparian area associated with a reach to recover if it was simply left alone without any further management or impacts. This layer is symbolized based on the 'IRP' field, which stands for Intrinsic Recovery Potential.

![rrp_legend]({{ site.baseurl }}/assets/images/rrp_legend.PNG)



*Figure 4 - Layer symbolization for the Riparian Recovery Potential output*

In addition to the 'IRP' field, the output of Riparian Recovery Potential contains a field called 'GEO_RP,' which is a continuous output on a scale from 0 (poor geomorphic condition) to 3 (intact) that serves as a proxy for geomorphic recovery potential derived again from the LANDFIRE EVT layer. This field serves as a model input for the rule-based final Riparian Recovery Potential output.

