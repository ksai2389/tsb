"""Collect imaging data from jenkins directly rather than splunk.

Usage
(venv.d) andcha@hu-andcha-lv:/local/mnt/workspace/jenkinsreport$ python3 reportv2.py -h
usage: reportv2.py [-h] --username USERNAME --password PASSWORD --job_url
                   JOB_URL [--job_name JOB_NAME] [--output OUTPUT]

optional arguments:
  -h, --help            show this help message and exit
  --username USERNAME, -u USERNAME
                        Username
  --password PASSWORD, -p PASSWORD
                        password
  --job_url JOB_URL, -j JOB_URL
                        the url used by jenkins
  --job_name JOB_NAME, -n JOB_NAME
                        The name of the job
  --output OUTPUT, -o OUTPUT
                        Output file to ...csv
(venv.d) andcha@hu-andcha-lv:/local/mnt/workspace/jenkinsreport$

Example parameters
-o /tmp/2tuesday.csv -u andcha -p somesupersecretpassword
-j https://jenkinsaps-sd.qualcomm.com/tbs/job/tbs-noncce-folder/job/
clonezilla/job/clonezilla_2.1_prd/
-n clonezilla_reimage
"""

import argparse
import os
import datetime
import jenkins
import pandas as pd


# I dont think we should need to do this on a properly configured server.
os.environ["REQUESTS_CA_BUNDLE"] = ""
os.environ["CURL_CA_BUNDLE"] = ""

pd.set_option('display.max_colwidth', None)
pd.set_option('display.max_rows', None)


def run_parser():
    """Initiate the parser"""
    parser = argparse.ArgumentParser()

    # Add long and short argument
    parser.add_argument(
        "--username", "-u", help="Username", required=True
    )
    parser.add_argument("--password", "-p", help="password", required=True)
    parser.add_argument("--job_url", "-j", help="the url used by jenkins", required=True)
    parser.add_argument("--job_name", "-n", help="The name of the job")
    parser.add_argument("--output", "-o", help="Output file to ...csv")
    parser.add_argument("--host", "-H", help="Only display the hostname")
    parser.add_argument("--owner", "-O", help="Only display machines by owner")
    parser.add_argument("--custom", "-c", help='Add a custom list of columns,'
                                               'this should be a comma separated'
                                               'list i.e -c "timestamp,HOSTNAME,BUILD_ID,IMAGE,'
                                               'wipe_disk,Started by" additional variables can'
                                               'be found under the Environment variables section'
                                               'of a completed job')
    args = parser.parse_args()
    return args

def collect_imaging_information():
    """The json returned by jenkins has all of the data we want in different places.
     Which is why I'm pulling from different keys etc."""
    args = run_parser()
    server = jenkins.Jenkins(args.job_url, username=args.username, password=args.password)
    builds = server.get_job_info(args.job_name, fetch_all_builds=True)['builds']
    list_of_builds = [item['number'] for item in builds]
    build_info = [server.get_build_env_vars(args.job_name, info)['envMap']
                  for info in list_of_builds]
    items = [server.get_build_info(args.job_name, item) for item in list_of_builds]
    timestamps = [item['timestamp'] for item in items]
    actions = [item['actions'] for item in items]
    startedby = [section['causes'][0]['shortDescription'] for x in actions for section in x if
                 'hudson.model.CauseAction' in section.values()]

    for count, item in enumerate(build_info):
        item['Started by'] = startedby[count].split()[-1]
        item['timestamp'] = datetime.datetime.fromtimestamp(timestamps[count] / 1000)

    if args.custom:
        columns = args.custom.split(",")
    else:
        columns = ['timestamp', 'HOSTNAME', 'BUILD_ID', 'IMAGE', 'wipe_disk', 'Started by']

    if args.owner:
        builds = pd.DataFrame(build_info).reindex(columns=columns + ['OWNER'])
        builds = builds[builds['OWNER'] == args.owner ]
    else:
        builds = pd.DataFrame(build_info).reindex(columns=columns)

    if args.host:
        builds = builds[builds['HOSTNAME'] == args.host]

    if args.output:
        builds.to_csv(args.output, index=False)

    print(builds.to_string(index=False))

if __name__ == "__main__":
    collect_imaging_information()
