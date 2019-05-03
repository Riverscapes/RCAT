
# user defined arguments
pf_path = r'C:\etal\Shared\Projects\USA\California\SierraNevada\BRAT\wrk_Data\00_CodeTest\VBET\Batch'
run_folder = 'BatchRun_01'
overwrite_run = False

#  import required modules and extensions
import os
from VBETProject import main as vbproj


def main(overwrite = overwrite_run):
    # change directory to the parent folder path
    os.chdir(pf_path)
    # list all folders in parent folder path - note this is not recursive
    dir_list = filter(lambda x: os.path.isdir(x), os.listdir('.'))
    # remove folders in the list that start with '00_' since these aren't our huc8 folders
    for dir in dir_list[:]:
        if dir.startswith('00_'):
            dir_list.remove(dir)

    # run vbet project script for each huc8 folder
    for dir in dir_list:

        # create VBET folder if it doesn't exist
        if not os.path.exists(os.path.join(pf_path, dir, 'VBET')):
            os.mkdir(os.path.join(pf_path, dir, 'VBET'))

        # set run folder path
        projPath = os.path.join(pf_path, dir, 'VBET', run_folder)

        # check if run folder already exists
        if not os.path.exists(projPath) or overwrite is True:

            # set script parameters
            dem = os.path.join(pf_path, dir, 'DEM\\NED_DEM_10m.tif')
            network = os.path.join(pf_path, dir, 'NHD', 'NHD_24k_300mReaches.shp')
            drar = None

            # if required inputs exist run the vbet project script
            # otherwise print warning message and skip to next directory in list
            if all([os.path.exists(dem), os.path.exists(network)]):
                print "Running VBET project for " + dir
                vbproj(projPath, dem, network, drar)
            else:
                print "WARNING: Script cannot be run.  Not all inputs exist for " + dir
                pass

        else:
            print 'VBET project already exists.  Skipping ' + dir
            pass


if __name__ == '__main__':
    main()
