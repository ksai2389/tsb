"Create a report of clonezilla images by querying mdb."

import subprocess
import shlex
import collections
import csv
import os

def run_a_command(cmd_to_run):
    """Run a standard linux command on a system."""
    some_command = subprocess.Popen(
        shlex.split(cmd_to_run), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout, stderr = some_command.communicate()
    stdout = stdout.decode("utf-8")
    stderr = stderr.decode("utf-8")
    returncode = some_command.returncode
    return [stdout, stderr, returncode]

def numerically_sort_dictionary(dictionary_to_sort):
    """Sort a dictionary numerically."""
    sorted_dictionary = {}
    for (key, value) in sorted(dictionary_to_sort.items(), key=lambda x: x[1], reverse=True):
        sorted_dictionary[key] = value
    return sorted_dictionary

def get_clonezilla_usage_from_mdb(duty):
    """Query mdb for clonezilla images and retrieve the occurances of a given element in a list"""
    clonezilla_images = []
    command_to_run = f"/usr/local/bin/mdb duty={duty} return clonezilla_version"
    raw = run_a_command(command_to_run)[0]
    for mdb_line in raw.splitlines():
        # Example lines
        #----------------------------------------
        #clonezilla_version: 23-09-2020-11:39:12,jun20-2020.8.61.63.
        # rel-5g-sep_20-x11dpint-18092020_051057
        #----------------------------------------
        # clonezilla_version: 23-09-2020-11:35:02,aug20-2020.8.28_gv78i9.
        # rel-5gc-Aug_20-C9X299PG300F-28082020_211742
        #----------------------------------------
        # clonezilla_version: Not present in entry.
        #----------------------------------------
        if "Not present in entry." not in mdb_line and "clonezilla_version:" \
                in mdb_line and "Exec Failed" not in mdb_line:
            clonezilla_images.append(mdb_line.split(",")[1])
    # <class 'collections.Counter'>
    #Counter({'7.6_X9DRD_enbl_c': 439, '26072019_171745-X9DRDiFLF-lte-enbl_e':
    # 422, '7.6_X9DRD_enbu_d': 210,.....})
    #This convert to dictionary
    occurrences = dict(collections.Counter(clonezilla_images))
    return numerically_sort_dictionary(occurrences)

def write_data_to_csv(output_folder, dictionary):
    """Clonezilla uses 2 headers, image and count. Write the contents of
    a dictionary to a csv and put the headers at the top."""
    headers = ["image", "count"]
    with open(os.path.join(output_folder, "images_report.csv"), 'w') as output_file:
        writer = csv.writer(output_file)
        writer.writerow(headers)
        for key, value in dictionary.items():
            writer.writerow([key, value])

def clonezilla_image_usage_report():
    """Collect the usage of clonezilla images from mdb as determined by a specific duty,
     usually tbs-server. Take the results of this information so it can be written to a filer."""
    clonezilla_image_list = get_clonezilla_usage_from_mdb('tbs-server')
    write_data_to_csv("/local/mnt/workspace/", clonezilla_image_list)

if __name__ == '__main__':
    clonezilla_image_usage_report()
