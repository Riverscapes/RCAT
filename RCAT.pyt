import os
import arcpy
import VBETProject
import VBET
import NHDNetworkBuilder
import RVD
import RCAProject
import RCA
import BankfullChannel
import ConfiningMargins
import Promoter


class Toolbox(object):
    def __init__(self):
        """Define the toolbox (the name of the toolbox is the name of the
        .pyt file)."""
        self.label = "Riparian Area Condition Assessments 1.0"
        self.alias = "Riparian Area Condition Assessments"

        # List of tool classes associated with this toolbox
        self.tools = [VBETBuilder, VBETtool, NHDNetworkBuildertool, RVDtool, RCATBuilder, RCAtool,
                      BankfullChannelTool, ConfinementTool, Promotertool]


class VBETBuilder(object):
    def __init__(self):
        """Define the tool (tool name is the name of the class)."""
        self.label = "01-Build VBET Project"
        self.category = "02-VBET"
        self.description = "Sets up a VBET project folder and defines the inputs"
        self.canRunInBackground = False

    def getParameterInfo(self):
        """Define parameter definitions"""
        param0 = arcpy.Parameter(
            displayName="Select Project Folder",
            name="projPath",
            datatype="DEFolder",
            parameterType="Required",
            direction="Input")

        param1 = arcpy.Parameter(
            displayName="Select DEM inputs",
            name="dem",
            datatype="DERasterDataset",
            parameterType="Required",
            direction="Input",
            multiValue=True)

        param2 = arcpy.Parameter(
            displayName="Select drainage network datasets",
            name="network",
            datatype="DEFeatureClass",
            parameterType="Required",
            direction="Input",
            multiValue=True)

        param3 = arcpy.Parameter(
            displayName="Select drainage area raster datasets",
            name="drar",
            datatype="DERasterDataset",
            parameterType="Optional",
            direction="Input",
            multiValue=True)

        return [param0, param1, param2, param3]

    def isLicensed(self):
        """Set whether tool is licensed to execute."""
        return True

    def updateParameters(self, parameters):
        """Modify the values and properties of parameters before internal
        validation is performed.  This method is called whenever a parameter
        has been changed."""
        return

    def updateMessages(self, parameters):
        """Modify the messages created by internal validation for each tool
        parameter.  This method is called after internal validation."""
        return

    def execute(self, p, messages):
        """The source code of the tool."""
        reload(VBETProject)
        VBETProject.main(p[0].valueAsText,
                        p[1].valueAsText,
                        p[2].valueAsText,
                        p[3].valueAsText)
        return


class VBETtool(object):
    def __init__(self):
        """Define the tool (tool name is the name of the class)."""
        self.label = "2-Valley Bottom Extraction Tool"
        self.category = "02-VBET"
        self.description = "Uses a DEM and stream network to extract a valley bottom polygon"
        self.canRunInBackground = False

    def getParameterInfo(self):
        """Define parameter definitions"""
        param0 = arcpy.Parameter(
            displayName="Project Name",
            name="projName",
            datatype="GPString",
            parameterType="Optional",
            direction="Input")

        param1 = arcpy.Parameter(
            displayName="Watershed HUC ID",
            name="hucID",
            datatype="GPDouble",
            parameterType="Optional",
            direction="Input")

        param2 = arcpy.Parameter(
            displayName="Watershed Name",
            name="hucName",
            datatype="GPString",
            parameterType="Optional",
            direction="Input")

        param3 = arcpy.Parameter(
            displayName="Select Project Folder",
            name="proj_path",
            datatype="DEFolder",
            parameterType="Required",
            direction="Input")

        param4 = arcpy.Parameter(
            displayName="Input DEM",
            name="inDEM",
            datatype="DERasterDataset",
            parameterType="Required",
            direction="Input")

        param5 = arcpy.Parameter(
            displayName="Input Stream Network",
            name="inNetwork",
            datatype="DEFeatureClass",
            parameterType="Required",
            direction="Input")
        param5.filter.list = ["Polyline"]

        param6 = arcpy.Parameter(
            displayName="Input Drainage Area Raster",
            name="inDA",
            datatype="DERasterDataset",
            parameterType="Optional",
            direction="Input")

        param7 = arcpy.Parameter(
            displayName="Name Valley Bottom Output",
            name="outValleyBottom",
            datatype="GPString",
            parameterType="Required",
            direction="Input")

        param8 = arcpy.Parameter(
            displayName="High Drainage Area Threshold",
            name="high_da_thresh",
            datatype="GPDouble",
            parameterType="Required",
            direction="Input")
        param8.value = 250

        param9 = arcpy.Parameter(
            displayName="Low Drainage Area Threshold",
            name="low_da_thresh",
            datatype="GPDouble",
            parameterType="Required",
            direction="Input")
        param9.value = 25

        param10 = arcpy.Parameter(
            displayName="Large Buffer Size",
            name="lg_buf_size",
            datatype="GPDouble",
            parameterType="Required",
            direction="Input")

        param11 = arcpy.Parameter(
            displayName="Medium Buffer Size",
            name="med_buf_size",
            datatype="GPDouble",
            parameterType="Required",
            direction="Input")

        param12 = arcpy.Parameter(
            displayName="Small Buffer Size",
            name="sm_buf_size",
            datatype="GPDouble",
            parameterType="Required",
            direction="Input")

        param13 = arcpy.Parameter(
            displayName="Minimum Buffer Size",
            name="min_buf_size",
            datatype="GPDouble",
            parameterType="Required",
            direction="Input")

        param14 = arcpy.Parameter(
            displayName="Large Slope Threshold",
            name="lg_slope_thresh",
            datatype="GPDouble",
            parameterType="Required",
            direction="Input")
        param14.value = 5

        param15 = arcpy.Parameter(
            displayName="Medium Slope Threshold",
            name="med_slope_thresh",
            datatype="GPDouble",
            parameterType="Required",
            direction="Input")
        param15.value = 7

        param16 = arcpy.Parameter(
            displayName="Small Slope Threshold",
            name="sm_slope_thresh",
            datatype="GPDouble",
            parameterType="Required",
            direction="Input")
        param16.value = 12

# added in temp directory to VBET folder to avoid defining workspace
#        param17 = arcpy.Parameter(
#            displayName="Scratch Workspace",
#            name="scratchWS",
#            datatype="DEWorkspace",
#            parameterType="Required",
#            direction="Input")
#        param17.filter.list = ["Local Database"]
#        param17.value = arcpy.env.scratchWorkspace

        param17 = arcpy.Parameter(
            displayName="Aggregation Distance",
            name="ag_distance",
            datatype="GPDouble",
            parameterType="Required",
            direction="Input")
        param17.value = 100

        param18 = arcpy.Parameter(
            displayName="Minimum Polygon Area to Keep in Output",
            name="min_area",
            datatype="GPDouble",
            parameterType="Required",
            direction="Input")
        param18.value = 30000

        param19 = arcpy.Parameter(
            displayName="Minimum Hole Area to Keep in Output",
            name="min_hole",
            datatype="GPDouble",
            parameterType="Required",
            direction="Input")
        param19.value = 50000

        param20 = arcpy.Parameter(
            displayName="Validate Drainage Area Using ReachDist",
            name="check_drain_area",
            datatype="GPBoolean",
            parameterType="Optional",
            direction="Input")

        return [param0, param1, param2, param3, param4, param5, param6, param7, param8, param9, param10, param11,
                param12, param13, param14, param15, param16, param17, param18, param19, param20]

    def isLicensed(self):
        """Set whether tool is licensed to execute."""
        return True

    def updateParameters(self, parameters):
        """Modify the values and properties of parameters before internal
        validation is performed.  This method is called whenever a parameter
        has been changed."""
        return

    def updateMessages(self, parameters):
        """Modify the messages created by internal validation for each tool
        parameter.  This method is called after internal validation."""
        return

    def execute(self, p, messages):
        """The source code of the tool."""
        reload(VBET)
        VBET.main(p[0].valueAsText,
                  p[1].valueAsText,
                  p[2].valueAsText,
                  p[3].valueAsText,
                  p[4].valueAsText,
                  p[5].valueAsText,
                  p[6].valueAsText,
                  p[7].valueAsText,
                  p[8].valueAsText,
                  p[9].valueAsText,
                  p[10].valueAsText,
                  p[11].valueAsText,
                  p[12].valueAsText,
                  p[13].valueAsText,
                  p[14].valueAsText,
                  p[15].valueAsText,
                  p[16].valueAsText,
                  p[17].valueAsText,
                  p[18].valueAsText,
                  p[19].valueAsText,
                  p[20].valueAsText)
        return


class NHDNetworkBuildertool(object):
    def __init__(self):
        """Define the tool (tool name is the name of the class)."""
        self.label = "NHD Network Builder"
        self.category = "Misc"
        self.description = "Creates a user specified stream network using attributes from NHD hydrography data"
        self.canRunInBackground = False

    def getParameterInfo(self):
        """Define parameter definitions"""
        param0 = arcpy.Parameter(
            displayName="Input NHD Flowline",
            name="inFlowline",
            datatype="DEFeatureClass",
            parameterType="Required",
            direction="Input")
        param0.filter.list = ["Polyline"]

        param1 = arcpy.Parameter(
            displayName="Input NHD Waterbody",
            name="inWaterbody",
            datatype="DEFeatureClass",
            parameterType="Optional",
            direction="Input")
        param1.filter.list = ["Polygon"]

        param2 = arcpy.Parameter(
            displayName="Input NHD Area",
            name="inArea",
            datatype="DEFeatureClass",
            parameterType="Optional",
            direction="Input")
        param2.filter.list = ["Polygon"]

        param3 = arcpy.Parameter(
            displayName="Check to subset artifical paths",
            name="ap_fix",
            datatype="GPBoolean",
            parameterType="Optional",
            direction="Input")

        param4 = arcpy.Parameter(
            displayName="Waterbody threshold size (sq km)",
            name="subsize",
            datatype="GPDouble",
            parameterType="Optional",
            direction="Input")
        param4.value = 0.001

        param5 = arcpy.Parameter(
            displayName="Remove Artifical Paths",
            name="boolArtPath",
            datatype="GPBoolean",
            parameterType="Optional",
            direction="Input")

        param6 = arcpy.Parameter(
            displayName="Remove Canals",
            name="boolCanals",
            datatype="GPBoolean",
            parameterType="Optional",
            direction="Input")

        param7 = arcpy.Parameter(
            displayName="Remove Aqueducts",
            name="boolAqueducts",
            datatype="GPBoolean",
            parameterType="Optional",
            direction="Input")

        param8 = arcpy.Parameter(
            displayName="Remove Stormwater",
            name="boolStormwater",
            datatype="GPBoolean",
            parameterType="Optional",
            direction="Input")

        param9 = arcpy.Parameter(
            displayName="Remove Connectors",
            name="boolConnectors",
            datatype="GPBoolean",
            parameterType="Optional",
            direction="Input")

        param10 = arcpy.Parameter(
            displayName="Remove General Streams",
            name="boolStreams",
            datatype="GPBoolean",
            parameterType="Optional",
            direction="Input")

        param11 = arcpy.Parameter(
            displayName="Remove Intermittent Streams",
            name="boolIntermittent",
            datatype="GPBoolean",
            parameterType="Optional",
            direction="Input")

        param12 = arcpy.Parameter(
            displayName="Remove Perennial Streams",
            name="boolPerennial",
            datatype="GPBoolean",
            parameterType="Optional",
            direction="Input")

        param13 = arcpy.Parameter(
            displayName="Remove Ephemeral Streams",
            name="boolEphemeral",
            datatype="GPBoolean",
            parameterType="Optional",
            direction="Input")

        param14 = arcpy.Parameter(
            displayName="Output Stream Network",
            name="outNetwork",
            datatype="DEFeatureClass",
            parameterType="Required",
            direction="Output")

        param15 = arcpy.Parameter(
            displayName="Select a Projection",
            name="proj",
            datatype="GPCoordinateSystem",
            parameterType="Required",
            direction="Input")

        param16 = arcpy.Parameter(
            displayName="Scratch Workspace",
            name="scratchWS",
            datatype="DEWorkspace",
            parameterType="Required",
            direction="Input")
        param16.filter.list = ["File System"]

        return [param0, param1, param2, param3, param4, param5, param6, param7, param8, param9, param10, param11, param12, param13, param14, param15, param16]

    def isLicensed(self):
        """Set whether tool is licensed to execute."""
        return True

    def updateParameters(self, parameters):
        """Modify the values and properties of parameters before internal
        validation is performed.  This method is called whenever a parameter
        has been changed."""
        return

    def updateMessages(self, parameters):
        """Modify the messages created by internal validation for each tool
        parameter.  This method is called after internal validation."""
        return

    def execute(self, p, messages):
        """The source code of the tool."""
        reload(NHDNetworkBuilder)
        NHDNetworkBuilder.main(p[0].valueAsText,
                               p[1].valueAsText,
                               p[2].valueAsText,
                               p[3].valueAsText,
                               p[4].valueAsText,
                               p[5].valueAsText,
                               p[6].valueAsText,
                               p[7].valueAsText,
                               p[8].valueAsText,
                               p[9].valueAsText,
                               p[10].valueAsText,
                               p[11].valueAsText,
                               p[12].valueAsText,
                               p[13].valueAsText,
                               p[14].valueAsText,
                               p[15].valueAsText,
                               p[16].valueAsText)
        return


class RVDtool(object):
    def __init__(self):
        """Define the tool (tool name is the name of the class)."""
        self.label = "2-Riparian Vegetation Departure"
        self.category = "01-RCAT"
        self.description = "Models current departure from historic riparian vegetation cover"
        self.canRunInBackground = False

    def getParameterInfo(self):
        """Define parameter definitions"""
        param0 = arcpy.Parameter(
            displayName="Project Name",
            name="projName",
            datatype="GPString",
            parameterType="Optional",
            direction="Input")

        param1 = arcpy.Parameter(
            displayName="Watershed HUC ID",
            name="hucID",
            datatype="GPDouble",
            parameterType="Optional",
            direction="Input")

        param2 = arcpy.Parameter(
            displayName="Watershed Name",
            name="hucName",
            datatype="GPString",
            parameterType="Optional",
            direction="Input")

        param3 = arcpy.Parameter(
            displayName="Select Project Folder",
            name="projPath",
            datatype="DEFolder",
            parameterType="Required",
            direction="Input")

        param4 = arcpy.Parameter(
            displayName="Existing Vegetation Raster",
            name="evt",
            datatype="DERasterDataset",
            parameterType="Required",
            direction="Input")

        param5 = arcpy.Parameter(
            displayName="Historic Vegetation Raster",
            name="bps",
            datatype="DERasterDataset",
            parameterType="Required",
            direction="Input")

        param6 = arcpy.Parameter(
            displayName="Input Segmented Stream Network",
            name="network",
            datatype="DEFeatureClass",
            parameterType="Required",
            direction="Input")
        param6.filter.list = ["Polyline"]

        param7 = arcpy.Parameter(
            displayName="Input Valley Bottom Polygon",
            name="valley",
            datatype="DEFeatureClass",
            parameterType="Required",
            direction="Input")
        param7.filter.list = ["Polygon"]

        param8 = arcpy.Parameter(
            displayName="Large River Polygon",
            name="lg_river",
            datatype="DEFeatureClass",
            parameterType="Optional",
            direction="Input")
        param8.filter.list = ["Polygon"]

        param9 = arcpy.Parameter(
            displayName="Dredge Tailings Polygon",
            name="dredge_tailings",
            datatype="DEFeatureClass",
            parameterType="Optional",
            direction="Input")
        param9.filter.list = ["Polygon"]

        param10 = arcpy.Parameter(
            displayName="Name RVD Output",
            name="outName",
            datatype="GPString",
            parameterType="Required",
            direction="Input")
        # param10.symbology = os.path.join(os.path.dirname(__file__), "RVD_ratio.lyr")

#        param11 = arcpy.Parameter(
#            displayName="Scratch Workspace",
#            name="scratch",
#            datatype="DEWorkspace",
#            parameterType="Required",
#            direction = "Input")
#        param11.filter.list = ["Local Database"]
#        param11.value = arcpy.env.scratchWorkspace

        return [param0, param1, param2, param3, param4, param5, param6, param7, param8, param9, param10]

    def isLicensed(self):
        """Set whether tool is licensed to execute."""
        return True

    def updateParameters(self, parameters):
        """Modify the values and properties of parameters before internal
        validation is performed.  This method is called whenever a parameter
        has been changed."""
        return

    def updateMessages(self, parameters):
        """Modify the messages created by internal validation for each tool
        parameter.  This method is called after internal validation."""
        return

    def execute(self, p, messages):
        """The source code of the tool."""
        reload(RVD)
        RVD.main(p[0].valueAsText,
                  p[1].valueAsText,
                  p[2].valueAsText,
                  p[3].valueAsText,
                  p[4].valueAsText,
                  p[5].valueAsText,
                  p[6].valueAsText,
                  p[7].valueAsText,
                  p[8].valueAsText,
                  p[9].valueAsText,
                  p[10].valueAsText)
        return


class RCATBuilder(object):
    def __init__(self):
        """Define the tool (tool name is the name of the class)."""
        self.label = "1-Build RCAT Project"
        self.category = "01-RCAT"
        self.description = "Sets up an RCAT project folder and defines the inputs"
        self.canRunInBackground = False

    def getParameterInfo(self):
        """Define parameter definitions"""
        param0 = arcpy.Parameter(
            displayName="Select Project Folder",
            name="projPath",
            datatype="DEFolder",
            parameterType="Required",
            direction="Input")

        param1 = arcpy.Parameter(
            displayName="Select drainage network datasets",
            name="network",
            datatype="DEFeatureClass",
            parameterType="Required",
            direction="Input",
            multiValue=True)

        param2 = arcpy.Parameter(
            displayName="Select existing cover folder",
            name="ex_cov",
            datatype="DEFolder",
            parameterType="Required",
            direction="Input",
            multiValue=True)

        param3 = arcpy.Parameter(
            displayName="Select historic cover folder",
            name="hist_cov",
            datatype="DEFolder",
            parameterType="Required",
            direction="Input",
            multiValue=True)

        param4 = arcpy.Parameter(
            displayName="Select fragmented valley bottom datasets",
            name="frag_valley",
            datatype="DEFeatureClass",
            parameterType="Required",
            direction="Input",
            multiValue=True)

        param5 = arcpy.Parameter(
            displayName="Select large river polygons",
            name="lrp",
            datatype="DEFeatureClass",
            parameterType="Optional",
            direction="Input",
            multiValue=True)

        param6 = arcpy.Parameter(
            displayName="Select dredge tailings polygons",
            name="dredge_tailings",
            datatype="DEFeatureClass",
            parameterType="Optional",
            direction="Input",
            multiValue=True)

        param7 = arcpy.Parameter(
            displayName="Select DEM",
            name="dem",
            datatype="DERasterDataset",
            parameterType="Optional",
            direction="Input",
            multiValue=True)

        param8 = arcpy.Parameter(
            displayName="Select precipitation raster",
            name="dredge_tailings",
            datatype="DERasterDataset",
            parameterType="Optional",
            direction="Input",
            multiValue=True)

        return [param0, param1, param2, param3, param4, param5, param6, param7, param8]

    def isLicensed(self):
        """Set whether tool is licensed to execute."""
        return True

    def updateParameters(self, parameters):
        """Modify the values and properties of parameters before internal
        validation is performed.  This method is called whenever a parameter
        has been changed."""
        return

    def updateMessages(self, parameters):
        """Modify the messages created by internal validation for each tool
        parameter.  This method is called after internal validation."""
        return

    def execute(self, p, messages):
        """The source code of the tool."""
        reload(RCAProject)
        RCAProject.main(p[0].valueAsText,
                        p[1].valueAsText,
                        p[2].valueAsText,
                        p[3].valueAsText,
                        p[4].valueAsText,
                        p[5].valueAsText,
                        p[6].valueAsText,
						p[7].valueAsText,
						p[8].valueAsText)
        return


class ConfinementTool(object):
    def __init__(self):
        """Define the tool (tool name is the name of the class)."""
        self.label = "4-Confinement Tool"
        self.category = "01-RCAT"
        self.description = "Determine the Confining Margins using the stream network, bankfull channel polygon, and valley bottom polygon."
        self.canRunInBackground = False

    def getParameterInfo(self):
        """Define parameter definitions"""
        param0 = arcpy.Parameter(
            displayName="Stream network from RVD",
            name="network",
            datatype="DEFeatureClass",
            parameterType="Required",
            direction="Input")

        param1 = arcpy.Parameter(
            displayName="Valley bottom polygon",
            name="valley_bottom",
            datatype="DEFeatureClass",
            parameterType="Required",
            direction="Input")

        param2 = arcpy.Parameter(
            displayName="Bankfull channel polygon",
            name="bankfull_channel",
            datatype="DEFeatureClass",
            parameterType="Required",
            direction="Input")

        param3 = arcpy.Parameter(
            displayName="Output folder",
            name="output_folder",
            datatype="DEFolder",
            parameterType="Required",
            direction="Input")

        param4 = arcpy.Parameter(
            displayName="Raw confinement output name",
            name="output_raw_confinement",
            datatype="GPString",
            parameterType="Required",
            direction="Input")

        param5 = arcpy.Parameter(
            displayName="Confining margins output name",
            name="output_confining_margins",
            datatype="GPString",
            parameterType="Required",
            direction="Input")

        param6 = arcpy.Parameter(
            displayName="Calculate integrated width attributes?",
            name="integrate_width_attributes",
            datatype="GPBoolean",
            parameterType="Required",
            direction="Input")
        param6.value = "False"

        return [param0, param1, param2, param3, param4, param5, param6]

    def isLicensed(self):
        """Set whether tool is licensed to execute."""
        return True

    def updateParameters(self, parameters):
        """Modify the values and properties of parameters before internal
        validation is performed.  This method is called whenever a parameter
        has been changed."""
        return

    def updateMessages(self, parameters):
        """Modify the messages created by internal validation for each tool
        parameter.  This method is called after internal validation."""
        return

    def execute(self, p, messages):
        """The source code of the tool."""
        reload(ConfiningMargins)
        ConfiningMargins.main(p[0].valueAsText,
                  p[1].valueAsText,
                  p[2].valueAsText,
                  p[3].valueAsText,
                  p[4].valueAsText,
                  p[5].valueAsText,
                  p[6].valueAsText)
        return


class RCAtool(object):
    def __init__(self):
        """Define the tool (tool name is the name of the class)."""
        self.label = "5-Riparian Condition Assessment"
        self.category = "01-RCAT"
        self.description = "Models riparian area condition based on riparian departure, land use intensity, and floodplain accessibility"
        self.canRunInBackground = False

    def getParameterInfo(self):
        """Define parameter definitions"""
        param0 = arcpy.Parameter(
            displayName="Project Name",
            name="projName",
            datatype="GPString",
            parameterType="Optional",
            direction="Input")

        param1 = arcpy.Parameter(
            displayName="Watershed HUC ID",
            name="hucID",
            datatype="GPDouble",
            parameterType="Optional",
            direction="Input")

        param2 = arcpy.Parameter(
            displayName="Watershed HUC Name",
            name="hucName",
            datatype="GPString",
            parameterType="Optional",
            direction="Input")

        param3 = arcpy.Parameter(
            displayName="Select Output Folder for Run",
            name="projPath",
            datatype="DEFolder",
            parameterType="Required",
            direction="Input")

        param4 = arcpy.Parameter(
            displayName="Existing Cover Raster",
            name="evt",
            datatype="DERasterDataset",
            parameterType="Required",
            direction="Input")

        param5 = arcpy.Parameter(
            displayName="Historic Cover Raster",
            name="bps",
            datatype="DERasterDataset",
            parameterType="Required",
            direction="Input")

        param6 = arcpy.Parameter(
            displayName="Input Stream Network from Riparian Vegetation Departure",
            name="seg_network",
            datatype="DEFeatureClass",
            parameterType="Required",
            direction="Input")
        param6.filter.list = ["Polyline"]

        param7 = arcpy.Parameter(
            displayName="Input Fragmented Valley Bottom",
            name="frag_valley",
            datatype="DEFeatureClass",
            parameterType="Required",
            direction="Input")
        param7.filter.list = ["Polygon"]

        param8 = arcpy.Parameter(
            displayName="Large River Polygon",
            name="lg_river",
            datatype="DEFeatureClass",
            parameterType="Optional",
            direction="Input")
        param8.filter.list = ["Polygon"]

        param9 = arcpy.Parameter(
            displayName="Dredge Tailings Polygon",
            name="mines",
            datatype="DEFeatureClass",
            parameterType="Optional",
            direction="Input")
        param9.filter.list = ["Polygon"]

        param10 = arcpy.Parameter(
            displayName="Valley Bottom Width Threshold",
            name="width_thresh",
            datatype="GPDouble",
            parameterType="Required",
            direction="Input")
        param10.value = 120

        param11 = arcpy.Parameter(
            displayName="Name RCA Output",
            name="output",
            datatype="GPString",
            parameterType="Required",
            direction="Input")

#        param11 = arcpy.Parameter(
#            displayName="Scratch Workspace",
#            name="scratch",
#            datatype="DEWorkspace",
#            parameterType="Required",
#            direction = "Input")
#        param11.filter.list = ["Local Database"]
#        param11.value = arcpy.env.scratchWorkspace

        return [param0, param1, param2, param3, param4, param5, param6, param7, param8, param9, param10, param11]

    def isLicensed(self):
        """Set whether tool is licensed to execute."""
        return True

    def updateParameters(self, parameters):
        """Modify the values and properties of parameters before internal
        validation is performed.  This method is called whenever a parameter
        has been changed."""
        return

    def updateMessages(self, parameters):
        """Modify the messages created by internal validation for each tool
        parameter.  This method is called after internal validation."""
        return

    def execute(self, p, messages):
        """The source code of the tool."""
        reload(RCA)
        RCA.main(p[0].valueAsText,
                  p[1].valueAsText,
                  p[2].valueAsText,
                  p[3].valueAsText,
                  p[4].valueAsText,
                  p[5].valueAsText,
                  p[6].valueAsText,
                  p[7].valueAsText,
                  p[8].valueAsText,
                  p[9].valueAsText,
                  p[10].valueAsText,
                  p[11].valueAsText)
        return


class BankfullChannelTool(object):
    def __init__(self):
        """Define the tool (tool name is the name of the class)."""
        self.label = "3-Bankfull Channel"
        self.category = "01-RCAT"
        self.description = "Generates a polygon representing the bankfull channel"
        self.canRunInBackground = False

    def getParameterInfo(self):
        """Define parameter definitions"""
        param0 = arcpy.Parameter(
            displayName="Segmented network",
            name="network",
            datatype="DEFeatureClass",
            parameterType="Required",
            direction="Input")

        param1 = arcpy.Parameter(
            displayName="Valley bottom polygon",
            name="valleybottom",
            datatype="DEFeatureClass",
            parameterType="Required",
            direction="Input")

        param2 = arcpy.Parameter(
            displayName="DEM",
            name="dem",
            datatype="DERasterDataset",
            parameterType="Required",
            direction="Input")

        param3 = arcpy.Parameter(
            displayName="Drainage area (in square kilometers)",
            name="drarea",
            datatype="DERasterDataset",
            parameterType="Optional",
            direction="Input")

        param4 = arcpy.Parameter(
            displayName="Precipitation raster (in mm)",
            name="precip",
            datatype="DERasterDataset",
            parameterType="Required",
            direction="Input")

        param5 = arcpy.Parameter(
            displayName="Minimum Bankfull Width",
            name="MinBankfullWidth",
            datatype="GPString",
            parameterType="Required",
            direction="Input")
        param5.value = 5

        param6 = arcpy.Parameter(
            displayName="Percent Buffer",
            name="dblPercentBuffer",
            datatype="GPDouble",
            parameterType="Optional",
            direction="Input")
        param6.value = 100

        param7 = arcpy.Parameter(
            displayName="Output Folder",
            name="output_folder",
            datatype="DEFolder",
            parameterType="Required",
            direction="Input")
		
        param8 = arcpy.Parameter(
            displayName="Output name",
            name="out_name",
            datatype="GPString",
            parameterType="Required",
            direction="Input")

        return [param0, param1, param2, param3, param4, param5, param6, param7, param8]

    def isLicensed(self):
        """Set whether tool is licensed to execute."""
        return True

    def updateParameters(self, parameters):
        """Modify the values and properties of parameters before internal
        validation is performed.  This method is called whenever a parameter
        has been changed."""
        return

    def updateMessages(self, parameters):
        """Modify the messages created by internal validation for each tool
        parameter.  This method is called after internal validation."""
        return

    def execute(self, p, messages):
        """The source code of the tool."""
        reload(BankfullChannel)
        BankfullChannel.main(p[0].valueAsText,
                             p[1].valueAsText,
                             p[2].valueAsText,
                             p[3].valueAsText,
                             p[4].valueAsText,
                             p[5].valueAsText,
                             p[6].valueAsText,
                             p[7].valueAsText,
							 p[8].valueAsText)
        return


class Promotertool(object):
    def __init__(self):
        """Define the tool (tool name is the name of the class)."""
        self.label = "Realization Promoter"
        self.category = "Misc"
        self.description = "Promotes a selected realization within a RCAT project"
        self.canRunInBackground = False

    def getParameterInfo(self):
        """Define parameter definitions"""
        param0 = arcpy.Parameter(
            displayName="Select Project Folder",
            name="projPath",
            datatype="DEFolder",
            parameterType="Required",
            direction="Input")

        param1 = arcpy.Parameter(
            displayName="Select Project Type",
            name="type",
            datatype="GPString",
            parameterType="Required",
            direction="Input")
        param1.filter.type = "ValueList"
        param1.filter.list = ["VBET", "RVD", "RCA"]

        param2 = arcpy.Parameter(
            displayName="Enter Realization Number",
            name="realization",
            datatype="GPDouble",
            parameterType="Required",
            direction="Input")

        param3 = arcpy.Parameter(
            displayName="Edited VBET Output",
            name="vbetOut",
            datatype="DEFeatureClass",
            parameterType="Optional",
            direction="Input")
        param3.filter.list = ["Polygon"]

        return [param0, param1, param2, param3]

    def isLicensed(self):
        """Set whether tool is licensed to execute."""
        return True

    def updateParameters(self, parameters):
        """Modify the values and properties of parameters before internal
        validation is performed.  This method is called whenever a parameter
        has been changed."""

        if parameters[1].value == "VBET":
            parameters[3].enabled = True
        else:
            parameters[3].enabled = False

        return

    def updateMessages(self, parameters):
        """Modify the messages created by internal validation for each tool
        parameter.  This method is called after internal validation."""
        return

    def execute(self, p, messages):
        """The source code of the tool."""
        reload(Promoter)
        Promoter.main(p[0].valueAsText,
                      p[1].valueAsText,
                      p[2].valueAsText,
                      p[3].valueAsText)
        return
