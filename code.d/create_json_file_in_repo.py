#!/usr/bin/env python3.6

"""When clonezilla images are created we should upload the information
to artifactory so it is in a format that the tbsinstaller can use."""

# TBSSERVER-1306
# Write a json file to artifactory that can be
# consumed by the tbsinstaller

import subprocess
import shlex
from argparse import ArgumentParser
import json
import os
import re
import requests
import urllib3

def run_a_command(cmd_to_run):
    """Run a standard linux command on a system."""
    some_command = subprocess.Popen(
        shlex.split(cmd_to_run), stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )
    stdout, stderr = some_command.communicate()
    stdout = stdout.decode("utf-8")
    stderr = stderr.decode("utf-8")
    returncode = some_command.returncode
    return [stdout, stderr, returncode]

def get_data_from_rest(rest_interface, username, password, keyvalue):
    """Query a rest interface to get a key.
    In the usage for clonezilla is to get tbsclonezillas api key"""
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    r = requests.get(rest_interface, auth=(username, password), verify=False)
    data = json.loads(r.content)
    return data.get(keyvalue)

def download_file(url_to_download, api_key, save_file_as):
    """Download some information from artifactory. """
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    resp = requests.get(
        url_to_download, headers={"X-JFrog-Art-Api": api_key}, verify=False
    )
    if resp.status_code == requests.codes.ok:
        open(save_file_as, "wb").write(resp.content)
    return resp.status_code


def modify_names(dictionary_name, new_image_name, hostname, tbs_release_type):
    """Depending on the hardware or release type, modify
    the dictionary, the keys and the json file name."""
    hw_type = get_hardware_from_mdb(hostname)
    print(hw_type)
    release_value = "-".join(new_image_name.split("-", 2)[:2]).replace(".rel", "")
    print(release_value)
    new_image_name = new_image_name.lower()
    print(new_image_name)
    if ".rel" in new_image_name:
        json_name = tbs_release_type + "_" + release_value + ".rel.json"
        print(json_name)
    else:
        json_name = tbs_release_type + "_" + release_value + ".json"

    if "-5g-" in new_image_name:
        release_value = release_value + "-gnb"
    if "-5gc-" in new_image_name:
        release_value = release_value + f"-5gc-{hw_type}"
    dictionary_name[release_value] = new_image_name
    return dictionary_name, release_value, json_name

def get_hardware_from_mdb(hostname):
    """Try and determine the hardware used by a machine based on information
    we have in mdb which itself is gathered from dmidecode."""
    command_to_run = f"/usr/local/bin/mdb {hostname} return motherboard-version"
    hw_model_raw = run_a_command(command_to_run)[0]
    hw_model_clean = (re.search('motherboard-version: (.*)\n', hw_model_raw).group(1))
    if "X9" in hw_model_clean:
        hw_model = "X9"
    elif "X11" in hw_model_clean:
        hw_model = "X11"
    elif "C9X299" in hw_model_clean:
        hw_model = "i9"
    else:
        hw_model = hw_model_clean
    return hw_model

def post_to_artifactory(url_to_upload_to, username, api_key, data):
    """Put our json/dictionary into artifactory"""
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    requests.put(
        url_to_upload_to, auth=(username, api_key), verify=False, data=json.dumps(data)
    )

def read_current_json(json_file):
    """If we already have some json in artifactory
    read that in as a python dictionary """
    with open(json_file, "r") as f:
        clonezilla_images = json.load(f)
    return clonezilla_images


def write_to_json(dictionary_name,):
    """Temporarily write the json file to a system so we can upload"""
    with open("/tmp/somefile.json", "w") as outfile:
        json.dump(dictionary_name, outfile, indent=4, sort_keys=True)

def upload_json_to_artifactory():
    """This function pulls in all the other functions to upload the
    correctly formatted json to artifactory."""
    username = os.getenv('tbsclonezilla_un')
    password = os.getenv('tbsclonezilla_pw')

    clonezilla_image_dictionary = {}
    parser = ArgumentParser()
    parser.add_argument(
        "-n", "--newimage", dest="new_image_name", help="new image name", metavar="FILE"
    )
    parser.add_argument(
        "-r", "--repo", dest="artifactory_repo", help="artifactory_repo", metavar="FILE"
    )
    parser.add_argument(
        "-H", "--hostname", dest="hostname_of_machine_being_imaged", help="hostname", metavar="FILE"
    )
    parser.add_argument(
        "-T", "--tbs_release_type", dest="tbs_release_type",
        help="fullstack for example", metavar="FILE"
    )

    args = parser.parse_args()
    new_image_name = args.new_image_name
    artifactory_repo = args.artifactory_repo
    hostname = args.hostname_of_machine_being_imaged
    tbs_release_type = args.tbs_release_type

    api_key = get_data_from_rest(
        "https://qct-artifactory.qualcomm.com/artifactory/api/security/apiKey",
        username,
        password,
        "apiKey",
    )

    clonezilla_image_dictionary, release_value, json_name = modify_names(
        clonezilla_image_dictionary, new_image_name, hostname, tbs_release_type)

    release_value = release_value.rsplit("-", 1)[0]
    release_value_json_file = json_name

    status_code = download_file(
        f"https://qct-artifactory.qualcomm.com/artifactory/"
        f"{artifactory_repo}/"
        f"{release_value_json_file}",
        api_key,
        f"{release_value_json_file}",
    )

    if status_code != 200:

        post_to_artifactory(
            f"https://qct-artifactory.qualcomm.com/artifactory/"
            f"{artifactory_repo}/{release_value_json_file}",
            username,
            api_key,
            clonezilla_image_dictionary,
        )

    else:
        clonezilla_image_dictionary = read_current_json(f"{release_value_json_file}")

        clonezilla_image_dictionary, release_value, json_name = modify_names(
            clonezilla_image_dictionary, new_image_name, hostname, tbs_release_type)

        post_to_artifactory(
            f"https://qct-artifactory.qualcomm.com/artifactory/{artifactory_repo}/"
            f"{release_value_json_file}",
            username,
            api_key,
            clonezilla_image_dictionary,
        )

    print(f"https://qct-artifactory.qualcomm.com/artifactory/{artifactory_repo}/"
          f"{release_value_json_file}")
    print("\n\n", clonezilla_image_dictionary, "\n\n")

if __name__ == "__main__":
    upload_json_to_artifactory()
