"""When creating a new clonezilla image we should add it
to the jenkins configuration of both the prd and dev jobs.
We use the tbsciaw account and the associated api key to
authenticate against. Copy the config change it and write it back."""

import subprocess
import shlex
import argparse
import requests
import urllib3

PROJECT_URL = "https://jenkinsaps-sd.qualcomm.com/tbs/job/tbs-noncce-folder/job/clonezilla"

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

def get_jenkins_config(username, api_key, portal):
    """The config file is necessary to create new jobs.
    https://support.cloudbees.com/hc/en-us/articles/
    220857567-How-to-create-a-job-using-the-REST-API-and-cURL-
    """
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    configstring = f"{PROJECT_URL}/job/{portal}/config.xml"  # dont
    print("Attempting to get the jenkins config file.")
    print(configstring)
    config_file = requests.get(configstring, auth=(username, api_key), verify=False)
    if config_file.ok:
        print(f"SUCCESS - We pulled the config file and the "
              f"status code is {config_file.status_code}")
    else:
        print(f"FAILURE - Config file status code {config_file.status_code}")
    return config_file.content

def post_to_jenkins(url_string, username, api_key, jenkins_config_file):
    """If we provide all the information needed this should not be the same as using
    go/tbsimaging."""

    communicate_with_jenkins = requests.post(
        url_string,
        auth=(username, api_key),
        data=jenkins_config_file,
        verify=False,
    )
    if communicate_with_jenkins.ok:
        print(
            f"SUCCESS - Code {communicate_with_jenkins.status_code}. "
            f"We should have added the new config to jenkins."
        )
    else:
        msg = f"FAILURE - Something went wrong - code  {communicate_with_jenkins.status_code} " \
              f"doubtful that anything was written to jenkins."
        raise RuntimeError(msg)

def modify_jenkins_xml(jenkins_config_file, new_image_name):
    """Im aware of the xml tool but these seems to work as well for this use case and is simpler"""
    jenkins_str = jenkins_config_file.decode('utf-8')
    new_jenkins_config = jenkins_str.replace(
        r"              <string>marker1</string>",
        f"              <string>{new_image_name}</string>\n"
        r"              <string>marker1</string>")
    return new_jenkins_config

def run_parser():
    """Initiate the parser """
    parser = argparse.ArgumentParser()

    # Add long and short argument
    parser.add_argument("--username", "-u", help="username", required=True)
    parser.add_argument("--api_key", "-k", help="api_key", required=True)
    parser.add_argument("--image", "-i", help="Which image should we use ? ", required=True)
    parser.add_argument("--url_to_copy_and_restore",
                        "-r", help="Which url should we copy ? ", required=True)

    # Read arguments from the command line
    args = parser.parse_args()
    if args.username:
        username = args.username
    if args.api_key:
        api_key = args.api_key
    if args.image:
        image = args.image
    if args.url_to_copy_and_restore:
        url_to_copy_and_restore = args.url_to_copy_and_restore
    return username, api_key, image, url_to_copy_and_restore

def modify_jenkins_config():
    """Mass of the work is done here."""
    # Collect the necessary information.
    username, api_key, image, url_to_copy_and_restore = run_parser()
    # Copy a give jenkins job.
    jenkins_config_file = get_jenkins_config(username, api_key, url_to_copy_and_restore)
    # Create the new jenkins configuration
    new_jenkins_config_file = modify_jenkins_xml(jenkins_config_file, image)
    post_to_jenkins(f"{PROJECT_URL}/job/{url_to_copy_and_restore}/config.xml",
                    username, api_key, new_jenkins_config_file)

if __name__ == '__main__':
    modify_jenkins_config()


