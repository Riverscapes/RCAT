# -------------------------------------------------------------------------------
# Name:        RCAT Realization Promoter
# Purpose:     Promotes a selected realization within any RCAT project
#
# Author:      Jordan Gilbert
#
# Created:     06/2017
# Latest Update: 08/03/2017
# Copyright:   (c) Jordan Gilbert 2017
# Licence:     This work is licensed under the Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International
#              License. To view a copy of this license, visit http://creativecommons.org/licenses/by-nc-sa/4.0/.
# -------------------------------------------------------------------------------

import xml.etree.ElementTree as ET
import xml.dom.minidom as minidom
import string
import sys
import uuid


def main(projPath, type, realization, vbetOut):
    """promote a selected realization within a project"""

    filepath = projPath + "/project.rs.xml"
    tree = ET.parse(filepath)
    root = tree.getroot()
    rz = root.find("Realizations")

    # get list of realization elements
    if type == "VBET":
        rzs = rz.findall("VBET")
    elif type == "RVD":
        rzs = rz.findall("RVD")
    elif type == "RCA":
        rzs = rz.findall("RCA")

    # check for realizations already promoted
    promids = []
    for x in range(len(rzs)):
        if rzs[x].get("promoted") == "True":
            promids.append(int(x+1))

    if len(promids) != 0:
        for x in range(len(rzs)):
            if int(rzs[x].find("Name").text[-1]) in promids:
                rzs[x].set("promoted", "False")

    # 'promote' the selected realization
    for x in range(len(rzs)):
        rzseq = rzs[x]
        rzname = rzseq.find("Name")
        rznum = rzname.text[-1]

        if int(rznum) == int(realization):
            rzs[x].set("promoted", "True")

            # if promoting a vbet project, add in the edited output to the promoted realization
            if vbetOut is not None:
                analysesNode = rzs[x].find("Analyses")
                if analysesNode is None:
                    analysesNode = ET.SubElement(rzs[x], "Analyses")
                analysisNode = analysesNode.find("Analysis")
                if analysisNode is None:
                    analysisNode = ET.SubElement(analysesNode, "Analysis")
                outputsNode = analysisNode.find("Outputs")
                if outputsNode is None:
                    outputsNode = ET.SubElement(analysisNode, "Outputs")

                vectorNode = ET.SubElement(outputsNode, "Vector")
                vectorNode.set("guid", str(uuid.uuid4()).upper())
                nameNode = ET.SubElement(vectorNode, "Name")
                nameNode.text = "Edited Valley Bottom"
                pathNode = ET.SubElement(vectorNode, "Path")
                pathNode.text = str(vbetOut[vbetOut.find("02_Analyses"):])

    # rewrite the output xml
    rough_string = ET.tostring(root, encoding='utf-8', method='xml')
    reparsed = minidom.parseString(rough_string)
    pretty = reparsed.toprettyxml(indent="\t")
    while string.find(pretty, "\n\t\n") > 0:
        pretty = string.replace(pretty, "\n\t\t\t\t\t\t\t\t\n", "\n")
        pretty = string.replace(pretty, "\n\t\t\t\t\t\t\t\n", "\n")
        pretty = string.replace(pretty, "\n\t\t\t\t\t\t\n", "\n")
        pretty = string.replace(pretty, "\n\t\t\t\t\t\n", "\n")
        pretty = string.replace(pretty, "\n\t\t\t\t\n", "\n")
        pretty = string.replace(pretty, "\n\t\t\t\n", "\n")
        pretty = string.replace(pretty, "\n\t\t\n", "\n")
        pretty = string.replace(pretty, "\n\t\n", "\n")
        pretty = string.replace(pretty, "\n\n", "\n")
        pretty = string.replace(pretty, "\n\n\n", "\n")
        pretty = string.replace(pretty, "\\", "/")
    f = open(filepath, "wb")
    f.write(pretty)
    f.close()

    return

if __name__ == '__main__':
    main(
        sys.argv[1],
        sys.argv[2],
        sys.argv[3],
        sys.argv[4])
