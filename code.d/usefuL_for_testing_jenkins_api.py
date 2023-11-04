"""This is for someone else that needs to test the api. Its notes and not to be reviewed.
It was a quick copy and paste to test the installers crucial steps"""

from urllib.parse import quote
import subprocess
import shlex
import logging
import re
import requests
import urllib3

"""Copy and paste as it is
https://qct-artifactory.qualcomm.com/ui/repos/tree/General/clonezillacredentials/jenkinsfortestinginataller.txt
"""

API_KEY_SERVER = "https://qct-artifactory.qualcomm.com"
API_KEY_REPO = "/artifactory/clonezillacredentials"
PROJECT_URL = "https://jenkinsaps-sd.qualcomm.com/tbs/job/tbs-noncce-folder/job/clonezilla"
PORTAL = "clonezilla_2.1_prd/job/clonezilla_reimage"
PORTAL = "clonezilla_2.1_prd/job/clonezilla_reimage_v3"

safd="andcha/clonezilla-img-mgmt:image_info"

def get_jenkins_config(username, api_key):
    """The config file is necessary to create new jobs.
    https://support.cloudbees.com/hc/en-us/articles/
    220857567-How-to-create-a-job-using-the-REST-API-and-cURL-
    """
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    configstring = f"{PROJECT_URL}/job/{PORTAL}/config.xml"  # dont
    print("Attempting to get the jenkins config file.")
    config_file = requests.get(configstring, auth=(username, api_key), verify=False)
    if config_file.ok:
        print("SUCCESS - Config file status code %s", config_file.status_code)
    else:
        print("FAILURE - Config file status code %s", config_file.status_code)
    return config_file.content


def build_url_string(hostname, clonezilla_image, notifications, unique_id):
    """The url is used to pass the variables to jenkins so a functioning job can be created."""
    owner_user = "andcha"
    reversed_hostname = hostname[::-1]
    site = "boulder"
    location = "somelab"
    # Some labs have spaces in their names.

    url_string = f"{PROJECT_URL}/job/{PORTAL}" f"/buildWithParameters?"

    # It seems that specifying any additional options would be pointless
    # for the project this is used for as we dont want to have any manual
    # intervention.
    parameter_string = (
        f"token={JENKINS_SERVER_TOKEN}"
        f"&HOSTNAME={hostname}"
        f"&HOSTNAME_CHECK={reversed_hostname}"
        f"&IMAGE={clonezilla_image}"
        f"&BUILD_USER_ID={owner_user}"
        f"&NOTIFICATION_LIST={notifications}"
        f"&LOCATION={location}"
        f"&wipe_disk=False"
        f"&GIT_BRANCH=andcha/clonezilla-img-mgmt:image_info"
        f"&OWNER={owner_user}"
        f"&SITE={site}&"
        f"&UNIQUE_ID={unique_id}"
    )

    full_string = url_string + parameter_string
    return full_string

def post_to_jenkins(url_string, username, api_key, jenkins_config_file):
    """If we provide all the information needed this should not be the same as using
    go/tbsimaging."""

    start_imaging = requests.post(
        url_string,
        auth=(username, api_key),
        data=jenkins_config_file,
        verify=False,
    )
    if start_imaging.ok:
        print(
            "SUCCESS - Imaging should be starting. Code %s, Check go/tbsimaging for "
            "further information.",
            start_imaging.status_code,
        )
    else:
        msg = "FAILURE - Imaging failed to start, the error code is %s".\
            format(start_imaging.status_code)
        print(msg)
        raise RuntimeError(msg)

hostname='qct-8022-enbu-0'
clonezilla_image='mar20-2020.7.53.38.rel-5gc-sep_20-x9drdiflf-03092020_170737'
notifications='andcha'
unique_id="blahblah"

jenkins_config_file = get_jenkins_config(USERNAME_TO_USE_WITH_JENKINS, api_key)
url_string = build_url_string(hostname, clonezilla_image, notifications, unique_id)
post_to_jenkins(
    url_string,
    USERNAME_TO_USE_WITH_JENKINS,
    api_key,
    jenkins_config_file
)
