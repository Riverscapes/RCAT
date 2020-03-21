---
title: Step 4 - Confinement Tool
category: RCAT
---

The Confinement Tool generates both the Confining Margins (intersection of the edges of the valley bottom polygon and the active channel polygon) and transfers this information to the stream network using a near-function method. This information can then be used to calculate confinement values based on  segment lengths or moving windows along the line network. 

This tool was adapted from the [Confining Margins tool](http://confinement.riverscapes.xyz/Generate-Confining-Margins.html) in the [Riverscapes Confinement Toolbox](http://confinement.riverscapes.xyz/).

## Parameters

![ConfinementTool]({{ site.baseurl }}assets/images/ConfinementTool_interface_2.0.PNG)

- **Select RVD network**: Select output network from the RVD tool.
- **Select valley bottom polygon**: Select input valley bottom polygon.
- **Select bankfull channel polygon**: Select polygon output from the Bankfull Channel tool. 
- **Select output folder for run**: Output folder for this run of RCAT, where intermediates and outputs will be saved.
- **Name confinement network output**: Name for output network including confinement fields.
- **Name confining margins output**: Name for output network of confining margins.
- **Calculate integrated width attributes?**: Default is unchecked.

## Outputs

### Raw Confinement Network

Output stream network including the raw confinement state, confinement type, and constriction in the following attributes:

- `CON_LEFT ` and `CON_RIGHT`: Binary for whether each segment is confined on the left and right of the stream.
  - 1 = section is confined on that side the stream.
  - 0 = section is not confined on that side of the stream. 

> Note: The side of the stream is relative, and does not necessarily refer to conventional definitions of river-right or river-left.

- `CON_TYPE`: Describes the type of confinement observed on each reach, based on `CON_LEFT` and `CON_RIGHT`
  - "None" = Not confined on either side of the stream. Same as "Unconfined".
  - "Right" = Confined on right side of stream.
  - "Left" = Confined on left side of the stream. 
  - "Both" = Confined on both sides of the stream. Same as "Constricted"

![ConfinementType]({{ site.baseurl }}/assets/images/ConfinementTypeOutput.png)

- `IsConfined`: Binary for whether the reach is confined or not.
  - 1 = reach is confined (i.e. `CON_TYPE` = "Right", "Left", or "Both").
  - 0 = reach is unconfined (i.e., `CON_TYPE` = "None").

![RawConfinement]({{ site.baseurl }}/assets/images/RawConfinementOutput.png)

- `IsConstrict`: Binary for whether the reach is constricted (confined on both sides) or not
  - 1 = reach is constricted (i.e. `CON_TYPE` = "Both").
  - 0 = reach is not constricted (i.e., `CON_TYPE` = "Right", "Left", or "None")

### Confining Margins

Output polyline shapefile that represents the confining margins as the intersection of the input stream channel and valley bottom polygons. The significance of this dataset is spatial, and has no meaningful attributes. 

![ConfiningMargins]({{ site.baseurl }}/assets/images/ConfiningMargins.png)