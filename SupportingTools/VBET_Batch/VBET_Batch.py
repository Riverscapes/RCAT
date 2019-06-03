
# user defined argument
pf_path = r'C:\etal\Shared\Projects\USA\California\SierraNevada\BRAT\wrk_Data\00_CodeTest\VBET\Batch'
width_csv_path = r"C:\etal\Shared\Projects\USA\California\SierraNevada\BRAT\wrk_Data\00_Projectwide\ModelParameters\TNC_BRAT_VBET_WidthParameters.csv"
da_csv_path = r"C:\etal\Shared\Projects\USA\California\SierraNevada\BRAT\wrk_Data\00_Projectwide\ModelParameters\TNC_BRAT_UpstreamDA.csv"

proj_name = "TNC_BRAT"
run_folder = 'BatchRun_01'
out_name = "Provisional_ValleyBottom_Unedited.shp"
overwrite_run = False

#  import required modules and extensions
import os
import csv
import arcpy
import glob
from collections import defaultdict
from VBET import main as vbet


def find_file(proj_path, file_pattern):

    search_path = os.path.join(proj_path, file_pattern)
    if len(glob.glob(search_path)) > 0:
        file_path = glob.glob(search_path)[0]
    else:
        file_path = None

    return file_path


def main():

    # read in csv of width parameters and convert to python dictionary
    widthDict = defaultdict(dict)
    if width_csv_path is not None:
        with open(width_csv_path, "rb") as infile:
            reader = csv.reader(infile)
            headers = next(reader)[1:]
            for row in reader:
                widthDict[row[0]] = {key: int(value) for key, value in zip(headers, row[1:])}

    # read in csv of width parameters and convert to python dictionary
    daDict = defaultdict(dict)
    if da_csv_path is not None:
        with open(da_csv_path, "r") as infile:
            reader = csv.DictReader(infile)
            for row in reader:
                daDict[row['HUC8Dir']][row['StreamName']] = float(row['US_DA_sqkm'])

    # change directory to the parent folder path
    os.chdir(pf_path)
    # list all folders in parent folder path - note this is not recursive
    dir_list = filter(lambda x: os.path.isdir(x), os.listdir('.'))
    # remove folders in the list that start with '00_' since these aren't our huc8 folders
    for dir in dir_list[:]:
        if dir.startswith('00_'):
            dir_list.remove(dir)

    # run vbet for each huc8 folder
    for dir in dir_list:

        try:
            # if valley bottom output doesn't exist, run the huc8
            projPath = os.path.join(pf_path, dir, 'VBET', run_folder)
            vbPath = os.path.join(projPath, "02_Analyses/Output_1", out_name)

            if not os.path.exists(vbPath) or overwrite_run is True:
                print "Running VBET for " + dir
                if dir in daDict:
                    sub_daDict = {k: v for k, v in daDict.iteritems() if dir in k}
                else:
                    sub_daDict = None

                # set parameters
                projName = proj_name
                hucID = dir.split('_')[1]
                hucName = dir.split('_')[0]

                DEM = find_file(projPath, '01_Inputs/01_Topo/DEM_1/*.tif')
                fcNetwork = find_file(projPath, '01_Inputs/02_Network/Network_1/*.shp')
                FlowAcc = find_file(projPath, '01_Inputs/01_Topo/DEM_1/Flow/*.tif')

                outName = out_name
                high_da_thresh = 250 # Default: 250
                low_da_thresh = 25 # Default: 25
                if dir in widthDict:
                    lg_buf_size = widthDict[dir]['LargeBuffer']
                    med_buf_size = widthDict[dir]['MedBuffer']
                    sm_buf_size = widthDict[dir]['SmallBuffer']
                    min_buf_size = widthDict[dir]['MinBuffer']
                else:
                    lg_buf_size = 200
                    med_buf_size = 100
                    sm_buf_size = 25
                    min_buf_size = 8
                lg_slope_thresh = 5 # Default: 5
                med_slope_thresh = 7 # Default: 7
                sm_slope_thresh = 12 # Default: 12
                ag_distance = 100 # Default: 100
                min_area = 0 # Default: 30000
                min_hole = 50000 # Default: 50000
                check_drain_area = True
                # run main vbet script
                vbet(projName, hucID, hucName, projPath, DEM, fcNetwork, FlowAcc, outName, high_da_thresh, low_da_thresh, lg_buf_size, med_buf_size, sm_buf_size, min_buf_size, lg_slope_thresh, med_slope_thresh, sm_slope_thresh, ag_distance, min_area, min_hole, check_drain_area, sub_daDict)
                arcpy.ResetEnvironments()
                print "\n"
                pass
        except arcpy.ExecuteError:
            arcpy.ResetEnvironments()
            print arcpy.GetMessages(2)
            print "\n"
            continue
        except Exception as e:
            arcpy.ResetEnvironments()
            print e.args[0]
            print "\n"
            continue


if __name__ == '__main__':
    main()
