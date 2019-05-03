#  import required modules and extensions
import os
import sys
import shutil

pf_path = r'C:\etal\Shared\Projects\USA\California\SierraNevada\BRAT\wrk_Data'

def main():
    # change directory to the parent folder path
    os.chdir(pf_path)
    # list all folders in parent folder path - note this is not recursive
    dir_list = filter(lambda x: os.path.isdir(x), os.listdir('.'))
    # remove folders in the list that start with '00_' since these aren't our huc8 folders
    for dir in dir_list[:]:
        if dir.startswith('00_'):
            dir_list.remove(dir)

    # run network builder function for each huc8 folder
    for dir in dir_list:
        output_dir = os.path.join(pf_path, dir, 'VBET\\BatchRun_01')
        #output_dir = os.path.join(pf_path, dir, 'VBET\\BatchRun_01\\Temp')
        #output_dir = os.path.join(pf_path, dir, 'VBET\\BatchRun_01\\02_Analyses\\Output_1')
        #output_dir = os.path.join(pf_path, dir, 'VBET\\BatchRun_01\\01_Inputs\\01_Topo\\DEM_1\\Flow')
        #if os.path.exists(output_dir):
        if os.path.exists(output_dir):
            print output_dir
            ## Try to remove tree; if failed show an error using try...except on screen
            try:
                tmp_dir = os.path.join(pf_path, dir, 'VBET\\BatchRun_01')
                # flow_dir = os.path.join(pf_path, dir, 'VBET\\BatchRun_01\\01_Inputs\\01_Topo\\DEM_1\\Flow')
                # buff_dir = os.path.join(pf_path, dir, 'VBET\\BatchRun_01\\01_Inputs\\02_Network\\Network_1\\Buffers_1')
                shutil.rmtree(tmp_dir)
            except OSError as e:
                print ("Error: %s - %s." % (e.filename, e.strerror))



if __name__ == '__main__':
    main()
