#!/usr/bin/env python3.7

"""tbs_clonezilla

*************
Why do this ?
*************
A TBS system can take several hours to get up and running but if we have a
known good configuration we can restore that machine back in 8 minutes.
8 minutes to image the machine, the DNS adds apx. 10 and the post install
depends but I have plans to clean that too.

There's 2 components to this they can be used together or independently.

Most users will use this script via the tbs installer.
------------------------------------------------------
#. This creates a MAC file.
#. Pulls a pre created image for a TBS X11/x9/i9 production system from NFS.
#. Clonezilla then puts that image onto the pxe'd system.
#. Clonezilla runs some post install steps to mount the lvm and make that image/system unique
#. Clonezilla post install then creates a script on the newly imaged machine
#     that for example rejoins a system to the domain, wait for DNS etc.
#. The post install script will try 3 times to sync up with GV and if for some reason
#     the proxies are having issues will warn the user that some things may not be synced.


*****************
Filer dependencys
*****************

+------------+------------+-----------+
| Site       | Filer      | Notes     |
+============+============+===========+
| Boulder    | Titanic    |           |
+------------+------------+-----------+
| Hyderabad  | Cube       |           |
+------------+------------+-----------+
| Haifa      |  Pint      |           |
+------------+------------+-----------+
| Sandiego   |  Sundae    |           |
+------------+------------+-----------+
| Bangalore  |  Blrsweng1 |           |
+------------+------------+-----------+
| Bridgewater|  Vern      |           |
+------------+------------+-----------+
| Beijing    |  Citrus    |           |
+------------+------------+-----------+
| Falcon     |  Titanic   | Not tested|
|            |            | in prd.   |
+------------+------------+-----------+

*************
Testing notes
*************
Installer lives here - /opt/install/tbsinstall/lib64/python3.6/site-packages/tbsinstaller/

cd /opt/data/install/tbs_nr_fullstack_mar20/tbs_nr_fullstack_mar20-2020.6.83.5.rel

super tbspackman --fetch
https://qct-artifactory.qualcomm.com/artifactory/tbs-nr-release-bundle-internal/
fullstack/tbs_nr_fullstack_mar20-2020.6.83.5.rel.json

Can just specify one machine
super tbsinstall --clone   --server_gnb_image
mar20-2020.6.83.5.rel-5g-Jun_20-X11DPiNT-25062020_211545

"""

import re
import random
import time
import shlex
import subprocess
import argparse
from datetime import datetime, timezone
import os
import sys
import requests
import urllib3
import json
from retry import retry


static_sites = ['austin', 'bangalore', 'beijing', 'boulder',
                'boxborough', 'bridgewater', 'encapa', 'encnaa',
                'falcon', 'farnborough', 'haifa', 'hyderabad',
                'india', 'lasvegas', 'paris', 'sandiego',
                'santaclara', 'sezhyderabad', 'shanghai',
                'sanjose','owl','wolf','lion']


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


def is_fqdn(hostname: str) -> bool:
    """
    Taken from
    https://codereview.stackexchange.com/questions/235473/fqdn-validation
    https://en.m.wikipedia.org/wiki/Fully_qualified_domain_name
    """
    if not 1 < len(hostname) < 253:
        return False

    # Remove trailing dot
    if hostname[-1] == '.':
        hostname = hostname[0:-1]

    #  Split hostname into list of DNS labels
    labels = hostname.split('.')

    #  Define pattern of DNS label
    #  Can begin and end with a number or letter only
    #  Can contain hyphens, a-z, A-Z, 0-9
    #  1 - 63 chars allowed
    fqdn = re.compile(r'^[a-z0-9]([a-z-0-9-]{0,61}[a-z0-9])?$', re.IGNORECASE)

    # Check that all labels match that pattern.
    return all(fqdn.match(label) for label in labels)


def calculate_expiration_time(time_to_add_in_seconds):
    """We should not allow the mac files to stay on the pxes indefintely
    otherwise we will upset UCM."""
    seconds = int(time.time())
    expiration_time = seconds + time_to_add_in_seconds
    return expiration_time



def ucm_info(parameter="site"):
    """Find info using gvquery."""
    return run_a_command(f"/usr/local/sbin/gvquery -p {parameter}")[0].rstrip()



def get_access_token(username, password):
    """A one time expiring access token is used to pull credentials necesary
    to mount the shares storing the tbs images."""
    url = "https://qct-artifactory.qualcomm.com/artifactory/api/security/token"
    expiration_time_in_seconds = 600 # 10 Minutes if we cant
    # pxe in that time imaging will fail. Added because we have
    # to use the slow network arg as a default now.
    try:
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        r = requests.post(
            url,
            verify=False,
            auth=(username, password),
            data={
                "username": username,
                "expires_in": expiration_time_in_seconds,
                "scope": 'member-of-groups:*'
            },
        )

        if r.status_code != 200:
            raise Exception(f"Something wrong with {url} or authentication.")
    except Exception as my_exception:
        print(my_exception)
    return r.json()



def post_data(url, username, password):
    """We write the mac file and mac token file to the pxes to be consumed
    at a later point in the process. The token file for example contains
    the one time use token."""
    try:
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        r = requests.post(
            url,
            verify=False,
            auth=(username, password),
            data={
                "username": username,
                "expires_in": expiration_time_in_seconds,
                "scope": "api:*",
            },
        )

        if r.status_code != 200:
            raise Exception(f"Something wrong with {url}")
    except Exception as my_exception:
        print(my_exception)
    return r.json()



def get_token_information(all_json_data):
    """Pull the data we care about from the json
    that is returned by artifactory."""
    token = all_json_data["access_token"]
    first_ten_of_token = token[:10]
    expiration_in_seconds = str(all_json_data["expires_in"])
    token_type = all_json_data["token_type"]
    return token, first_ten_of_token, expiration_in_seconds, token_type



def build_token_file(
        email_recipients,
        hostname,
        user_name,
        owner_user_file,
        department,
        office_location,
        image,
        access_token,
        filer,
        mount_string,
        site,
        ucm_proxy,
        mac_address,
        smb_string,
        machine_executing_script,
        wipe_disk,
        date,
        filer_site,
        is_this_an_i9,
        first_ten_of_token,
        expiration_in_seconds,
        token_type,
        cifs_mount_string,
        jenkins_job_id,
        BUILD_CAUSE,
        UNIQUE_ID,
        GVTIER
        ):
    """Writing to the pxes allows us to consume configuration data without
    mounting additional shares which we may or may not have access to."""
    token_file = f"""EMAIL_RECIPIENTS={email_recipients}
HOSTNAME={hostname}
USERNAMEFORSCRIPT={user_name}
OWNER_USER={owner_user_file}
OWNER_USER_DEPARTMENT={department}
MACHINE_SCRIPT_WAS_EXECUTED_FROM={machine_executing_script}
LOCATION='{office_location}'
DATE_FOR_CLONEZILLA={date}
IMAGE={image}
KEY={access_token}
FILER={filer}
SMB_STRING={smb_string}
MOUNT={mount_string}
SITE={site}
UCM_PROXY={ucm_proxy}
MAC_ADDRESS=01{mac_address.replace(':','-')}
wipe_disk={wipe_disk}
filer_site={filer_site}
i9={is_this_an_i9}
first_10_of_token={first_ten_of_token}
expiration={expiration_in_seconds}
token_type={token_type}
cifs_mount_string={cifs_mount_string}
jenkins_job_id={jenkins_job_id},
clonezilla_method={BUILD_CAUSE},
UNIQUE_ID={UNIQUE_ID}
GV_TIER={GVTIER}
"""

    return token_file



def build_mac_file(
        expiration_time,
        clonezilla_method_string,
        filer,
        site,
        extra_args,
        ucm_proxy,
        post_install_script,
        smb_string,
        wipe_disk,
        filer_site,
        token_file_url,
        mac_file_url,
        git_string):
    """The mac file is what the system looks to for determine what the next steps are."""
    disk_wipe_script = ""
    partition_helper_script = ""
    clonezilla_version = "clonezilla-live-2.7.1-22.tbs"
    script_location_prefix = "~/clonezilla-img-mgmt_v2.0/code.d"

    if wipe_disk is True:
        # We only want to run the wipe the disk script
        # if we are writing to the entire disk.
        disk_wipe_script = f"{script_location_prefix}/disk_wipe.sh"
        partition_helper_script = f"{script_location_prefix}/new_restore_partition_helper.sh"

    get_credentials_script = f"{script_location_prefix}/getcredentials.sh"
    fstab_helper = f"{script_location_prefix}/fstab_helper.sh"
    post_install_script = f"{script_location_prefix}/{post_install_script}"

    #if valid_site is not True:
    #    site = "sandiego" # We need the mount string to
        # look like its in SD but want to use the local PXE

    cifs_mount_string = f"mount -t cifs //{filer}.qualcomm.com{smb_string}/{filer_site}/secure.d/ " \
                 f"-o credentials=/tmp/credentials.txt,vers=3.0 /home/partimag/"

    mac_file = f"""# purge after: {expiration_time}
default Clonezilla_Live
LABEL Clonezilla_Live
MENU LABEL Clonezilla_Live
KERNEL tftp://%LOCALHOST%/pxelinux/pxelinux.cfg/corp/qso/{clonezilla_version}/vmlinuz
APPEND initrd=tftp://%LOCALHOST%/pxelinux/pxelinux.cfg/corp/qso/{clonezilla_version}/initrd.img \
boot=live username=user union=overlay config components quiet noswap edd=on nomodeset nodmraid \
locales=en_US.UTF-8 keyboard-layouts=en keyboard-layouts=en \
ocs_live_run="ocs-sr -g auto -e1 auto -e2 -r -j2 -scr -p reboot {clonezilla_method_string}" \
ocs_live_extra_param="" modprobe.blacklist=qat_c62x modprobe.blacklist=intel_qat \
ocs_prerun1="{git_string}" \
ocs_prerun2="wget {token_file_url} -P /tmp/" \
ocs_prerun3="{get_credentials_script}" \
ocs_prerun4="{disk_wipe_script}" \
ocs_prerun5="{cifs_mount_string}" \
ocs_prerun6="shred -n 200 -z -u /tmp/credentials.txt" \
ocs_prerun7="{partition_helper_script}" \
ocs_prerun8="curl -X DELETE {token_file_url} || true" \
ocs_prerun9="curl -X DELETE {mac_file_url} || true" \
ocs_postrun1="{post_install_script}" \
ocs_postrun3="{fstab_helper}" ocs_live_batch=yes net.ifnames=0 nosplash noprompt \
fetch={ucm_proxy.replace('http','tftp')}\
/pxelinux/pxelinux.cfg/corp/qso/{clonezilla_version}/filesystem.squashfs {extra_args}
IPAPPEND 2
"""
    return mac_file, cifs_mount_string



def remove_prefix(text):
    """Clean up the data related to the scripts we are using."""
    if text.startswith("/prj"):
        return text[len("/prj") :]
    return text



def is_ipmi_up(hostname):
    """Ping the ipmi to see if its functioning in DNS.
    Long term we should maybe looking at logging in."""
    try:
        _, _, returncode = run_a_command(f"ping -c1 ipmi-{hostname}")
        if returncode != 0:
            raise Exception(f"\n\nIpmi for ipmi-{hostname} doesnt seem to be online.\n\n")
    except Exception as my_exception:
        sys.exit({my_exception})


def determine_correct_filer(site, jenkins_job_id):
    """Each site tbs imaging is needed should really have its own filer
    so we are pulling from the most appropriate filer. If we dont have one
    we use the one in SD assuming its in the kit and notify to get one added."""
    site = site.lower()

    filer_dictionary = {
        "boulder": {"filer": "titanic"},
        #The below format can be used for temporary imaging using remote nearest site filer.
        #"chennai": {"remote-filer": "blrsweng1", "filer-site": "bangalore"},
        "chennai": {"filer": "vedapuri"},
        "hyderabad": {"filer": "cube"},
        "haifa": {"filer": "pint"},
        "sandiego": {"filer": "sundae"},
        "bangalore": {"filer": "blrsweng1"},
        "farnborough": {"filer": "radio"},
        "bridgewater": {"filer": "vern"},
        "beijing": {"filer": "citrus"},
        "santaclara": {"filer": "scooby"},
        "austin": {"filer": "western"}
    }
    if site in filer_dictionary:
        filerinfo=filer_dictionary[site]
        if 'filer' in filerinfo:
            (filer, filer_site) = (filerinfo['filer'], site)
        elif 'remote-filer' in filerinfo:
            (filer, filer_site) = (filerinfo['remote-filer'], filerinfo['filer-site'])
    else:
        (filer, filer_site) = ('sundae','sandiego')
        msg=f"Clonezilla image filer needed at {site}"
        send_message("tbs.cs.svr.tier3@qualcomm.com", msg, jenkins_job_id)

    return filer, filer_site



def pxe_the_system(hostname, ipmi_username, ipmi_password):
    """Contact the system and change the boot order so that it will PXE
    without intervention from a user."""

    check_ipmi_status(hostname, ipmi_username, ipmi_password, 0)
    print("About to change the boot device.")
    run_a_command(
        f"/usr/bin/ipmitool -H ipmi-{hostname} "
        f"-U {ipmi_username} -P {ipmi_password} chassis bootdev pxe"
    )
    print("About to reset the power.")
    run_a_command(
        f"/usr/bin/ipmitool -H ipmi-{hostname} "
        f"-U {ipmi_username} -P {ipmi_password} chassis power reset"
    )


def bmc_reset(hostname, ipmi_username, ipmi_password):
    """Reset the ipmi of a station."""
    print(f"Attempting a cold reset on ipmi-{hostname}.")
    stdout, stderr, returncode = run_a_command(
        f"/usr/bin/ipmitool -H ipmi-{hostname} "
        f"-U {ipmi_username} -P {ipmi_password} mc reset cold"
    )
    print(stdout, stderr, returncode)



def check_ipmi_status(hostname, ipmi_username, ipmi_password, try_count):
    """The ipmi of a system is needed to pxe a system.
    The ipmi needs to be responsive to do that.  We will
    try and identify a system if its in this state."""

    _, stderr, _ = run_a_command(
        f"/usr/bin/ipmitool -H ipmi-{hostname} "
        f"-U {ipmi_username} -P {ipmi_password} chassis status"
    )

    if len(stderr) > 0:
        while try_count < 1:
            bmc_reset(hostname, ipmi_username, ipmi_password)
            time.sleep(90) # It takes on average a system 90 seconds
            # to come back up after a reset.
            check_ipmi_status(hostname, ipmi_username, ipmi_password, 1)
        else:
            raise RuntimeError(f"ipmi-{hostname} is "
                               f"unresponsive and needs manual intervention.")
    else:
        print(f"ipmi-{hostname} is responding, we can proceed.")



def get_machine_type(hostname):
    """System types are identified by naming conventions. MUch of this will not be
    needed now because the tbs installer is determining the image to use
    but its useful for me."""
    if re.match(r"tbs-[0-9][0-9][0-9][0-9]-5g\.", hostname):
        tbs_type = "5g machine"
    elif re.match(r"tbs-[0-9][0-9][0-9][0-9]-5gc\.", hostname):
        tbs_type = "5gc machine"
    elif re.match(r"qct-[0-9][0-9][0-9][0-9]-enbu", hostname):
        tbs_type = "lte enbu"
    elif re.match(r"qct-[0-9][0-9][0-9][0-9]-enbl", hostname):
        tbs_type = "lte enbl"
    elif re.match(r"tbs-[0-9][0-9][0-9][0-9]-sim\.", hostname):
        tbs_type = "5g sim"
    elif re.match(r"tbs-5g-plat-[0-9]*", hostname):
        tbs_type = "5g plat"
    elif re.match(r"tbs-5g-pt-[0-9]*", hostname):
        tbs_type = "5g pt"
    elif re.match(r"tbs-5gnr-mt-[0-9]*", hostname):
        tbs_type = "5g mt system"
    else:
        raise Exception(f"No image name was specified; "
                        f"unable to find default due to unrecognized naming convention "
                        f"for {hostname}")
    return tbs_type



def identify_image(tbs_type):
    """Use a dictionary to identify what image a machine should use is an image is not provided."""
    image_dictionary = {
        "5g machine": {"image": "12092019_203233-X11DPiNT-5g-jun19-2019.8.43.25.rel"},
        "5gc machine": {"image": "12092019_203305-X9DRDiFLF-5gc-jun19-2019.8.43.25.rel"},
        "lte enbu": {"image": "7.6_X9DRD_enbu_d"},
        "lte enbl": {"image": "7.6_X9DRD_enbl_c"},
        "5g sim machine/": {"image": "5gnr-sim-061419"},
    }
    return image_dictionary[tbs_type]["image"]


def build_ph_data(username):
    """Query ph to find informtaion about a given user."""
    ph_record = run_a_command("ldapsearch -LLLxH ldap://qed-ldap.qualcomm.com "
                              "-b ou=people,dc=qualcomm,dc=com cn=%s" % username)[0]

    #This code is for exempting job failures when owner information is not found in ph. Especially when dealing with users/owners who might have left Qualcomm."
    if len(ph_record) == 0:
        bailout_user = "tbsadmin"
        ph_record = run_a_command("ldapsearch -LLLxH ldap://qed-ldap.qualcomm.com "
                              "-b ou=people,dc=qualcomm,dc=com cn=%s" % bailout_user)[0]
    return ph_record


def create_ph_dictionary(some_output):
    """Convert the data gained from ph into a dictionary so we can use it at a later point."""
    ph_record_dictionary = {}
    for line in some_output.split("\n"):
        if ":" in line:
            ph_key_value = line.split(":")
            key = ph_key_value[0].lstrip()
            value = ph_key_value[1].lstrip()
            ph_record_dictionary[key] = value
    return ph_record_dictionary



def reverse_my_hostname(hostname):
    """Determine what the reversed hostname should be."""
    return hostname[::-1]



def check_reverse_hostname(calculated_reversed_hostname, provided_reversed_hostname, hostname):
    """Was the reversed name provided as expected ?"""
    if calculated_reversed_hostname != provided_reversed_hostname:
        raise Exception(f"The hostname, {hostname.upper()} "
                        f"and the reverse hostname {provided_reversed_hostname.upper()} "
                        f"are NOT as expected. Please try again.")


def check_password(hostname):
    """Try and determine the hardware and return that in additon to the username and password."""
    try:
        ipmi_username = "ADMIN"
        ipmi_password = "Qualcomm5G"
        stdout, stderr, returncode = \
                run_a_command(f'ipmitool -H ipmi-{hostname}.qualcomm.com '
                            f'-U {ipmi_username} -P {ipmi_password} fru print')
        if returncode == 0:
            print(stdout)
        elif returncode == 1:
        #"5G password didn't work. Trying 4G one."
            ipmi_username = "ADMIN"
            ipmi_password = "ADMIN"
            stdout, stderr, returncode = \
                run_a_command(f'ipmitool -H ipmi-{hostname}.qualcomm.com '
                            f'-U {ipmi_username} -P {ipmi_password} fru print')
            if returncode == 0:
                print(stdout)
            else:
                raise Exception(stderr)
        else:
            raise Exception(stderr)
    except Exception:
        #Doing a BMC reset as we ran into an error getting the required output above.
        print(f"ipmitool failed, status {stderr}. Doing a BMC cold reset once to see if that fixes the issue.")
        bmc_reset = f"ipmitool -H ipmi-{hostname}.qualcomm.com -U {ipmi_username} -P {ipmi_password} bmc reset cold"
        stdout, stderr, returncode = run_a_command(bmc_reset)
        print(stdout)
        time.sleep(60)
        stdout, stderr, returncode = \
                run_a_command(f'ipmitool -H ipmi-{hostname}.qualcomm.com '
                            f'-U {ipmi_username} -P {ipmi_password} fru print')
        if returncode == 0:
            print(stdout)
        else:
            raise Exception(f"ipmitool failed, status {stderr}")
    return ipmi_username, ipmi_password


def read_image_data(hostname, ipmi_username, ipmi_password, image_name):
    """Querying a system for the hardware type is unreliable. Sometimes
    data is in the fru times sometimes it is not. We are now going to try and assume
    that the user that is imaging is using the correct image for their hardware."""
    image_name = image_name.upper()
    if "X11" in image_name or "X12" in image_name:
        image_type = "X11"
    elif "X9" in image_name:
        image_type = "X9"
    elif "SYS" in image_name:
        image_type = "X11"
    elif "C9X" in image_name:
        image_type = "I9"
    elif "SUPER" in image_name:
        image_type = "X10"
    elif "X8DTL" in image_name:
        image_type = "X8"
    else:
        image_type = "NOT-X8-9-10-11-I9"
    command_to_run = f"/cm/config/duty/tbs-server/sm/sum -u {ipmi_username} -p {ipmi_password} -i ipmi-{hostname} -c GetDmiInfo"
    sumout,  _, returncode = run_a_command(command_to_run)
    if returncode == 0:
        sum = sumout.upper()
        for line in sum.split("\n"):
            if "BBPD" in line:
                sum_hw = line.strip().split()[3].strip('"')
        if "X11" in sum_hw or "X12" in sum_hw:
            hw_model = "X11"
        elif "X9" in sum_hw:
            hw_model = "X9"
        elif "C9X" in sum_hw:
            hw_model = "I9"
        elif "X10" in sum_hw:
            hw_model = "X10"
    elif returncode == 153:
                print(f"{hostname} doesn't support sum tool to query its hardware model.")
    else:
        hw_model = "HW_UNKNOWN"
    print(f"Hardware model of {hostname} is {hw_model}")
    print(f"Image selected is for {image_type}")
    if image_type == hw_model:
            print(f"{hostname} hardware type is {hw_model} & selected image {image_name} is compatible. Proceeding further.")
    elif "HW_UNKNOWN" in hw_model:
            print(f"Sum tool couldn't retrieve the hardware data for {hostname}. Proceeding with user selected image.")
    elif "NOT-X8-9-10-11-I9" in image_type:
            print(f"Proceeding with imaging with user selected image as the {image_type} didn't match latest hw_models.")
            text_for_email = f"We need to add a new image_type in read_image_data module. Please refer {jenkins_job_id} for more information."
            send_message("tbs.cs.svr.tier3@qualcomm.com", f"Missing {hw_model} in read_image_data module", text_for_email)
    else:
            status=f"{hostname} hardware type is {hw_model} & selected image {image_name} is not compatible with it."
            override_mismatched_image=os.environ.get("OVERRIDE_MISMATCHED_IMAGE",False)
            if override_mismatched_image:
                print(f"{status} Continuing due to OVERRIDE_MISMATCHED_IMAGE={override_mismatched_image}")
            else:
                raise Exception(f"{status} Stopping the execution now. Please select right image name.")

    return image_type


def get_mac_address_from_ipmi(hostname, ipmi_username, ipmi_password, i9):
    """The way a mac address is determined depends on the hardware. i9's have one method,
    X11/X9 something else. Ideally I'd like to query the system directly but its not reliable
    at this time which leaves us no option except to assume the user pics the correct image
    for their hardware."""
    try:
        if i9:
            print("This image type is for i9's so we're assuming the system be "
                  "installed is an i9 and thus we must use the i9 commands.")
            raw_mac_address, _, returncode = \
                run_a_command(f'ipmitool -H ipmi-{hostname}.qualcomm.com '
                              f'-U {ipmi_username} -P {ipmi_password} raw 0x30 0x9F')
            if returncode != 0:
                raise Exception("Mac address determination failed.")
            mac_address = raw_mac_address.replace(' ', '-')[4:21:].upper()
        else:
            raw_mac_address, _, returncode = \
                run_a_command(f'ipmitool -H ipmi-{hostname}.qualcomm.com '
                              f'-U {ipmi_username} -P {ipmi_password} raw 0x30 0x21')
            if returncode != 0:
                raise Exception("Mac address determination failed.")

            mac_address = raw_mac_address.replace(' ', '-')[13:].upper()
    except Exception as my_exception:
        print(my_exception)

    return str(mac_address.strip())


def gv_tier(hostname):
    "Determine whether a system is in pvw tier or not."
    try:
        tier = get_parameter_from_mdb(hostname,'gv_tier')
    except AttributeError:
        tier="prd"
        print(f"No mdb entry for {hostname}, defaulting to {tier} tier")

    return tier

def get_parameter_from_mdb(hostname, parameter):
    """Query mdb for a particular parameter."""
    command_to_run = f"/usr/local/bin/mdb {hostname} return {parameter}"
    raw = run_a_command(command_to_run)[0]
    if parameter in raw and "Not present in entry." not in raw:
        cleaned_mdb = (re.search(f'{parameter}: (.*)\n', raw).group(1)).rstrip()\
                            .replace(" ", "")
    elif "Not present in entry." in raw or "No matches to your query." in raw:
        cleaned_mdb = "Fix me."
    return cleaned_mdb


def get_ucm_proxy_from_mdb(site):
    """Get the ucm proxy from the site and pick a random site."""
    list_of_proxies = []
    command_to_run = f"/usr/local/bin/mdb project=GlobalPXE site_local={site} return name"
    raw = run_a_command(command_to_run)[0].splitlines()
    for line in raw:
        if "name:" in line:
            proxy = line.split("name: ")[1]
            if not any(value in proxy for value in ("dmz", "krizak", "k8snode1", "sd", "uefi")):
                list_of_proxies.append(proxy)
    return random.choice(["http://" + s for s in list_of_proxies])



def send_message(recipient, subject, body):
    """Send an email using the systems mail client."""
    try:
        process = subprocess.Popen(['mail', '-s', subject, recipient],
                                   stdin=subprocess.PIPE)
    except Exception as error:
        print(error)
    process.communicate(str.encode(body))



def notifcation_string(additional_notifications):
    """Remove duplicate names for the email notifcations"""
    addition_notifications = additional_notifications.split(",")
    default_notifications = ["tbs.notify.clonezilla.restore@qti.qualcomm.com"]
    for item in addition_notifications:
        default_notifications.append(item)
        my_list = list(dict.fromkeys(default_notifications))
    str1 = ","
    notification_list = str1.join(my_list).rstrip(',')
    return notification_list



def email_body(hostname, site, filer, image, mac_address, machine_executing_script,
               wipe_disk, mac_file_url, pxe_requested, git_branch, date, mac_file,
               jenkins_job_id, filer_site):
    """The email body is used for both informational purposes and debugging.
    The information here is useful for both."""
    if wipe_disk == True:
        wipe_disk = "Wipe disk"
    else:
        wipe_disk = "Restore Partitions"

    email_text = f"Do not reply to this message to get support, it is filtered by most.\n\n" \
                 f"Please use your usual support channel.\n\n" \
                 f"Hostname of the machine to be imaged: {hostname} \n" \
                 f"\nMachine the script was run from: {machine_executing_script} \n" \
                 f"TIME: {date} \n" \
                 f"CALCULATED SITE: {site} \n" \
                 f"Filer site: {filer_site} \n" \
                 f"\nCALCULATED FILER: {filer} \n" \
                 f"IMAGE: {image} \n" \
                 f"METHOD: {wipe_disk} \n" \
                 f"TRIGGER METHOD: {os.environ['BUILD_CAUSE']} \n" \
                 f"DID WE REQUEST PXE: {pxe_requested} \n" \
                 f"MAC ADDRESS: {mac_address} \n" \
                 f"GIT BRANCH: {git_branch} \n" \
                 f"IPMI_ADDRESS: https://ipmi-{hostname} \n" \
                 f"MAC_FILE_URL: {mac_file_url} \n" \
                 f"Jenkins Job {jenkins_job_id}console \n" \
                 f"Debugging help can be found at https://go/tbs_image_triage" \
                 f"\n\n{mac_file}"
    return email_text



def get_site_list():
    """Get the list of valid sites for TBS servers"""

    # This takes a few seconds to execute, and it doesn't handle new sites
    # so if there is a faster/better alternative, this should be replaced
    cmd = "/usr/local/bin/mdb duty=tbs-server return site" + \
          " | /pkg/sysadmin/bin/mdbrotate | sort -u"

    queried_site_list = set()
    attempts = 0
    while len(queried_site_list) < 1 and attempts < 10:

        if attempts > 0:
            # Not our first time thru, so wait a sec
            time.sleep(1)

        # Normally, shell=True is a security risk, but in this case,
        # we're not executing a cmd with any user args, so it should be fine
        # This is a workaround from having to define multiple subprocesses
        # for using pipes

        query_result_str = subprocess.check_output(cmd, shell=True).decode()
        queried_site_list = set(query_result_str.splitlines())
        queried_site_list.discard("Not present in entry.")

        attempts = 1 + attempts

    return queried_site_list.union(set(static_sites))


def get_station_id(hostname):
    """Determine the station id from the machines hostname."""
    try:
        station_id = int("-".join(hostname.split("-", 2)[1:2]))
    except ValueError:
        station_id = random.randint(1, 100)
    return station_id



def hex_integer(station_id):
    """The station id is used to generate a string that looks like a mac file.
    Converting to hex means that any check ucm have in place to check for a
    valid mac address will pass."""
    #hex of station_id might look like 0x3e8 or
    # 0x270f
    hex_id = hex(station_id)[-4:].replace("x", "0")
    return hex_id



def hex_for_token_file(hostname):
    """TBS leverages UCM's pxe servers and their rest apis to write a file that contains
    varibles used by clonezilla and the mac file that is used to pxe.
    https://qwiki.qualcomm.com/it-ucm/Univac_REST_API_Quick-Start
    To stay in line with their naming convention we are now hexing the station ID and writing to
    the api with a new unique mac address for example
    a system 8022 with a mac of 0C-C4-7A-6D-24-D4
    becomes 1F-54-7A-6D-24-D4.
    Note non of the first 4 characters I tested appear to have been handed out to
    vendors so we should not clash.
    In addition we delete the mac file as soon as we've used it so it should really
    not be around any longer than a few minutes.
    """
    station_id = get_station_id(hostname)
    string_to_substitute = hex_integer(station_id)
    with_dashes = '-'.join(string_to_substitute[i:i+2]
                           for i in range(0, len(string_to_substitute), 2))
    return with_dashes.upper()



def new_mac_for_token_file(string1, string2):
    """Replace the first 4 characters of a string with another."""
    new_string = string1[0:4]+string2[4:]
    return new_string



def get_department_number(ph_dictionary):
    """In at least one scenario the departmentnumber key is not consistent,
    we should try and catch that."""
    try:
        department = ph_dictionary['departmentNumber'].split(' ')[0]
    except KeyError:
        # If the standard key is not used lets try departmentnumber instead.
        department = ph_dictionary['departmentnumber'].split(' ')[0]
    return department



def get_branch_project(branch):
    """Clone a specific branch from either tbs' main or from a users fork."""
    git_prj = "tbs/clonezilla-img-mgmt"
    git_branch_string = ""
    if ":" in branch:
        git_prj = branch.split(":")[0]
        git_branch = branch.split(":")[1]
        git_branch_string = "git checkout " + git_branch
    git_string = f"GIT_SSL_NO_VERIFY=1 git clone https://github.qualcomm.com/{git_prj} clonezilla-img-mgmt_v2.0" \
             f" && cd clonezilla-img-mgmt_v2.0/code.d; {git_branch_string}"
    return git_string

@retry(ConnectionResetError, tries=3, delay=30)
def get_bluecat_access_token(username, password):
    """An access token is needed to connect to Bluecat REST API"""
    url = "https://gateway.qualcomm.com/rest_login"
    data = {"username": username, "password": password}
    headers = {'Content-type': 'application/json', 'Accept': 'text/plain'}
    print("We are trying to get a bluecat token")
    try:
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        d = requests.post(url, json=data, headers=headers, verify=False)
        if d.status_code != 200:
            raise Exception(f"""\
                Something wrong with {url} or authentication.")
                response = {json.dumps(d.json(), indent=4, default=vars)}
                data = {json.dumps(data, indent=4, default=vars)}
                """)
        d_out = d.json()
        bluecat_token = d_out["access_token"]
        print(bluecat_token)
    except Exception as my_exception:
        print(my_exception)
    return bluecat_token

@retry(ConnectionResetError, tries=3, delay=30)
def get_ip_from_bluecat_using_mac_address(bluecat_token, mac_address):
    url = "https://gateway.qualcomm.com/query/hostinfo_from_mac"
    print("Using the above token we will get ip_address with mac")
    try:
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        headers = {'Content-type': 'application/json', "auth": f"Basic {bluecat_token}"}
        data = {"mac": mac_address}
        ip_mac = requests.post(url, headers=headers, json=data, verify=False)
        if ip_mac.status_code == 200:
            print(ip_mac.json())
            ip_mac_out = ip_mac.json()
            if "error" in ip_mac_out:
                bluecat_ip = "IP_NOT_ASSIGNED to the MAC Address as of now. No need to delete any lease"
            else:
                bluecat_ip = ip_mac_out["address"]
                print(f'{bluecat_ip} is the ip fetched from bluecat for {mac_address}')
        elif ip_mac.status_code == 500:
            bluecat_ip = "Lease already deleted"
            print(f'{bluecat_ip} for {mac_address}')
        else:
            raise Exception(f"""\
Something wrong with {url} or ip_from_bluecat_using_mac_address query.
response = {json.dumps(ip_mac.json(), indent=4, default=vars)}
data = {json.dumps(data, indent=4, default=vars)}
""")
    except Exception as my_exception:
        print(my_exception)
    return bluecat_ip

@retry(ConnectionResetError, tries=3, delay=30)
def delete_ip_lease(bluecat_ip, bluecat_token):
    url = "https://gateway.qualcomm.com/lease/delete"
    print("We are trying to delete DHCP lease now.")
    try:
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        headers = {'Content-type': 'application/json', "auth": f"Basic {bluecat_token}"}
        data = {"ip": bluecat_ip}
        del_ip = requests.post(url, headers=headers, json=data, verify=False)
        if del_ip.status_code != 200:
            raise Exception(f"""\
                Something wrong with {bluecat_token} or {bluecat_ip} deletion")
                response = {json.dumps(del_ip.json(), indent=4, default=vars)}
                data = {json.dumps(data, indent=4, default=vars)}
                """)
    except Exception as my_exception:
        print(my_exception)
    print(del_ip.json())

@retry(ConnectionResetError, tries=3, delay=30)
def query_networkid_from_ip(bluecat_ip, bluecat_token):
    url = "https://gateway.qualcomm.com/query/hostinfo_all_from_ip"
    try:
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        headers = {'Content-type': 'application/json', "auth": f"Basic {bluecat_token}"}
        data = {"ip": bluecat_ip}
        net_ip = requests.post(url, headers=headers, json=data, verify=False)
        if net_ip.status_code == 200:
            net_ip_out = net_ip.json()
            bluecat_netid = net_ip_out["network"].strip().split("/")[0]
            print(bluecat_netid)
        else:
            raise Exception(f"""\
                Something went wrong while querying {bluecat_ip} using {bluecat_token}")
                response = {json.dumps(net_ip.json(), indent=4, default=vars)}
                data = {json.dumps(data, indent=4, default=vars)}
                """)
    except Exception as my_exception:
        print(my_exception)
    return bluecat_netid

@retry(ConnectionResetError, tries=3, delay=30)
def query_current_pxe(bluecat_netid, bluecat_token):
    url = "https://gateway.qualcomm.com/options/query_pxe"
    try:
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        headers = {'Content-type': 'application/json', "auth": f"Basic {bluecat_token}"}
        data = {"subnet": bluecat_netid}
        pxe_id = requests.post(url, headers=headers, json=data, verify=False)
        if pxe_id.status_code == 200:
            pxe_out = pxe_id.json()
            bluecat_pxe_list = dict();
            bluecat_pxe_list['tftp'] = pxe_out["success"].split(":")[1].split(",")[0].split(" ")[3]
            bluecat_pxe_list['next'] = pxe_out["success"].split(":")[1].split("),")[1].split(" ")[3]
            print(f"Bluecat defined IPs for PXE are {bluecat_pxe_list}")
        else:
            raise Exception(f"""\
                Something wrong with {bluecat_token} or {bluecat_ip} deletion")
                response = {json.dumps(pxe_id.json(), indent=4, default=vars)}
                data = {json.dumps(data, indent=4, default=vars)}
                """)
    except Exception as my_exception:
        print(my_exception)
    return bluecat_pxe_list

def get_ucm_pxe_ip_from_mdb(site):
    """Get the ucm proxy from the site and pick a random site."""
    pxes = []
    command_to_run = f"/usr/local/sbin/mdb project=globalpxe site={site} return ip_address"
    raw = run_a_command(command_to_run)[0].splitlines()
    for line in raw:
        if "ip_address:" in line:
            pxe = line.split("ip_address: ")[1]
            if "," in pxe:
                pxe = pxe.split(",")
            pxes.append(pxe)
            if any(isinstance(i, list) for i in pxes):
                list_of_ucm_pxes = []
                for element in pxes:
                    if type(element) is list:
                        # Check if type is list than iterate through the sublist
                        for item in element:
                            list_of_ucm_pxes.append(item)
                    else:
                        list_of_ucm_pxes.append(element)
            else:
                list_of_ucm_pxes = pxes
    print(f"UCM imaging servers are {list_of_ucm_pxes}")
    return list_of_ucm_pxes

def validate_tftp(bluecat_netid, bluecat_pxe_list, list_of_ucm_pxes, site):
    """Compare UCM PXE data with bluecat TFTP / NEXT IPs and if both are same, then we dont have to do anything"""
    tft = bluecat_pxe_list["tftp"]
    nxt = bluecat_pxe_list["next"]
    if (tft == nxt) and (tft in list_of_ucm_pxes):
        update_pxe = "TFTP/PXE_UPDATE_NOT_REQUIRED"
    else:
        print(f"TFTP needs to be updated for {bluecat_netid} in {site}")
        update_pxe = "NEED_TO_UPDATE_TFTP/PXE"
    print(update_pxe)
    return update_pxe

@retry(ConnectionResetError, tries=3, delay=30)
def update_tftp_pxe(list_of_ucm_pxes, bluecat_netid, bluecat_token):
    """We will use the UCM defined imaging global PXE server for the site and update the same in bluecat_netid"""
    url = "https://gateway.qualcomm.com/options/update_pxe"
    site_ucm_pxe = list_of_ucm_pxes[0]
    try:
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        headers = {'Content-type': 'application/json', "auth": f"Basic {bluecat_token}"}
        data = {"subnet": bluecat_netid, "pxe": site_ucm_pxe}
        pxe_update = requests.post(url, headers=headers, json=data, verify=False)
        pxe_out = pxe_update.json()
        print(pxe_out)
    except Exception as my_exception:
        print(my_exception)
    return pxe_out

def get_nac_api_client_details(username, artifactory_access_token):
    artifactory_server = "qct-artifactory.qualcomm.com"
    artifactory_repo = "icevmcredentials"
    nac_api_client_file = "nac-api-tbs-client-details.txt"
    url = f"https://{artifactory_server}:443/artifactory/{artifactory_repo}/{nac_api_client_file}"
    try:
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        r = requests.get(
            url,
            verify=False,
            allow_redirects=True,
            auth=(username, artifactory_access_token)
        )
        if r.status_code != 200:
            raise Exception(f"Something wrong with {url} or authentication.")
    except Exception as my_exception:
        print(my_exception)
    open(nac_api_client_file, 'wb').write(r.content)
    read_nac_file_contents = open(nac_api_client_file, 'r')
    nac_file_contents = read_nac_file_contents.read()
    read_nac_file_contents.close()
    os.remove(nac_api_client_file)
    for line in nac_file_contents.split("\n"):
        if "client_id" in line:
            nac_api_client_id = line.strip().split('=')[1]
        elif "client_secret" in line:
            nac_api_client_secret = line.strip().split('=')[1]
    return nac_api_client_id, nac_api_client_secret

def get_nac_api_access_token(c_id, c_sec):
    url = "https://login.microsoftonline.com/98e9ba89-e1a1-4e38-9007-8bdabc25de1d/oauth2/v2.0/token"
    nac_form = {
        'grant_type': (None, 'client_credentials'),
        'client_id': (None, c_id),
        'client_secret': (None, c_sec),
        'scope': (None, 'api://e2b4c231-1f84-4c7d-913e-5139c19d6557/.default'),
    }
    try:
        r = requests.post(
            url,
            verify=False,
            files=nac_form
        )
        if r.status_code != 200:
            raise Exception(f"Something wrong with {url} or authentication.")
    except Exception as my_exception:
        print(my_exception)
    nac_api_out = r.json()
    nac_auth_access_token = nac_api_out["access_token"]
    return nac_auth_access_token

def query_mac_in_elmo(nac_api_token, mac_address):
    mac_address = mac_address.replace("-", ":")
    url=f"https://nac.qualcomm.com/api/elmo/lab_machine/{mac_address}"
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {nac_api_token}',
    }
    try:
        r = requests.get(
            url,
            verify=False,
            headers=headers,
        )
        if (r.status_code == 200) or (r.status_code == 404):
            pass
        else:
            raise Exception(f"Something wrong with {url} or authentication.")
    except Exception as my_exception:
        print(my_exception)
    if r.status_code == 404:
        elmodata = "NOT_FOUND_IN_ELMO"
    else:
        elmodata = r.json()
        elmodata = json.dumps(elmodata[0])
        elmodata = json.loads(elmodata)
        elmodata = elmodata["accessLevelDescription"]
    return elmodata


def reimage_a_system():
    """The scripts ulitizes the create above here functions."""
    try:

        date = datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%dT%H:%M:%S.%f%z")
        machine_executing_script = os.uname()[1]
        # Initiate the parser
        parser = argparse.ArgumentParser()

        # Add long and short argument
        parser.add_argument("--username", "-u", help="set username")
        parser.add_argument("--password", "-p", help="set password")
        parser.add_argument("--image", "-i", help="Which image should we use ? ")
        parser.add_argument("--owner_user_file", "-o", help="set owner", default='morduno')
        parser.add_argument("--hostname", "-H", help="set hostname", default="qct-8022-enbu-0",
                            required=True)
        parser.add_argument("--jenkins_job_id", "-j", help="jenkins job id for debugging")
        parser.add_argument("--additional_notifications", "-N", help="Additional notifications")
        parser.add_argument("--site", "-s", help="set site")
        parser.add_argument("--reverse_hostname", "-r", help="reverse the hostname",
                            default="0-ubne-2208-tcq", required=True)
        parser.add_argument("--mac_address", "-m", help="mac address", default="")
        parser.add_argument("--wipe_disk", "-w", help="wipe disk", default=True)
        parser.add_argument("--office_location", "-l",
                            help="Which lab does this machine live in ? ")
        parser.add_argument("--test_mac_file", "-t", help="What would the mac file look like, "
                                                          "useful for debugging.", default=False)
        parser.add_argument("--extra_args", "-x", help="Extra arguments passed to the kernel",
                            default='TFTPOPTS="-b 15000"') # We have to
        # assume that the network is slow everywhere because we cant test it from the installer.

        parser.add_argument("--pxe", "-pxe", help="request a machine to pxe.", default=True)
        parser.add_argument("--git_branch", "-g",
                            help="Which git branch should we use ?", default="main")

        # Read arguments from the command line
        args = parser.parse_args()

        if args.username:
            username = args.username

        if args.password:
            password = args.password

        if args.hostname:
            hostname = args.hostname

        fqdn = hostname + ".qualcomm.com"

        if not is_fqdn(fqdn):
            raise Exception(f"\n\n{fqdn} doesn't look like a valid hostname.\n\n")


        is_ipmi_up(fqdn)
        ipmi_username, ipmi_password = check_password(hostname)

        if args.hostname:
            provided_reversed_hostname = args.reverse_hostname

        if args.jenkins_job_id:
            jenkins_job_id = args.jenkins_job_id

        if args.pxe:
            pxe_requested = args.pxe

        if args.extra_args:
            extra_args = args.extra_args

        if args.additional_notifications:
            additional_notifications = args.additional_notifications
        else:
            additional_notifications = ""

        email_notifications = notifcation_string(additional_notifications)


        if args.owner_user_file:
            owner_user_file = args.owner_user_file
        else:
            owner_user_file = get_parameter_from_mdb(hostname, "user")

        if args.wipe_disk:
            wipe_disk = args.wipe_disk

        # If we dont specify a lab we assume that the machine is correct.
        if args.office_location:
            office_location = args.office_location
        else:
            office_location = get_parameter_from_mdb(hostname, "office_location")

        if args.test_mac_file:
            test_mac_file = args.test_mac_file
        else:
            test_mac_file = False

        if args.git_branch:
            git_branch = args.git_branch

        git_string = get_branch_project(git_branch)

        calculated_reversed_hostname = reverse_my_hostname(hostname)
        check_reverse_hostname(calculated_reversed_hostname, provided_reversed_hostname, hostname)


        if args.image: # This allows TBS to specify an image
            image = args.image
        else:
            tbs_type = get_machine_type(fqdn)
            image = identify_image(tbs_type)

        # Dont proceed if the filer doesnt have the correct image.
        if image not in os.listdir(os.path.join('/prj/tbs/clonezilla',
                                                ucm_info("site"), 'secure.d')):
            raise ValueError(f"It looks like {image} is missing from"
                             f" {os.path.join('/prj/tbs/clonezilla', ucm_info('site'), 'secure.d')}'."
                             f" It may still be available in the archive.d directory.")

        try:
           image_type = read_image_data(hostname, ipmi_username, ipmi_password, image)
        except Exception as my_exception:
           print(my_exception)

        is_this_an_i9 = "I9" in image_type

        if args.mac_address:
            mac_address = args.mac_address
        else:
            mac_address = get_mac_address_from_ipmi(hostname, ipmi_username, ipmi_password, is_this_an_i9)

        # Query mdb for some information.
        ph_record_output = build_ph_data(owner_user_file)
        ph_dictionary = create_ph_dictionary(ph_record_output)
        department = get_department_number(ph_dictionary)
        all_json_data = get_access_token(username, password)

        (
            access_token,
            first_ten_of_token,
            expiration_in_seconds,
            token_type,
        ) = get_token_information(all_json_data)

        # Query go/elmo to see if the MAC / device is onboarded to QNAC.
        # If not then raise exception and halt imaging.
        (nac_client_id, nac_client_sec) = get_nac_api_client_details(username, access_token)
        nac_api_token = get_nac_api_access_token(nac_client_id, nac_client_sec)
        elmoupdate = query_mac_in_elmo(nac_api_token, mac_address)
        if "Full Access" in elmoupdate:
            print(f"Found that station is onboarded to go/elmo with \"{elmoupdate}\". Proceeding further with imaging.")
        else:
            raise ValueError(f"MAC address {mac_address} for station in QNAC shows \"{elmoupdate}\". \
            Please onboard in go/elmo and wait for an hour before proceeding with reimaging.")

        print(all_json_data, "\n\n\n\n")
        # The site determines the proxies and the correct filer to use.
        if args.site:
            site = args.site
            site = site.lower() # make sites lowercase so that dictionary matches.

            # Verify that the site passed is valid
            site_list = get_site_list()
            if site not in site_list:
                raise ValueError(f'{site} is not a valid site')
        else:
            site_from_ph = ph_dictionary['l'].lower().replace(" ", "")
            # if string is empty
            site = site_from_ph
            site = site.lower()

        ucm_proxy = get_ucm_proxy_from_mdb(site)
        print(ucm_proxy)

        mac_file_url = f"{ucm_proxy}/univac/api/mac_file/01-{mac_address}"
        print(mac_file_url)
        token_mac = new_mac_for_token_file(hex_for_token_file(hostname), mac_address)
        print(token_mac, "token_mac")
        token_file_url = f"{ucm_proxy}/univac/api/mac_file/{token_mac}"

        print(token_file_url)
        mount_string = "/prj/tbs/clonezilla"
        smb_string = remove_prefix(mount_string)
        post_install_script = "postinstallscript.sh"

        if wipe_disk is True:
            disk_or_partition = "sda"
            clonezilla_method = "restoredisk"
        elif "rhel" in image or "el8" in image:
            # The plan moving forward to to append rhel to the name of
            # rhel images that will need this change.
            disk_or_partition = "sda1 sda3 sda4 sda5"
            clonezilla_method = "-k restoreparts"
        else:
            disk_or_partition = "sda1 sda3"
            clonezilla_method = "-k restoreparts"

        # Are we going to wipe the disk or preserve the partitions ?
        clonezilla_method_string = f"{clonezilla_method} {image} {disk_or_partition}"
        print(clonezilla_method_string)

        mac_file_expiration_time = calculate_expiration_time(600)
        # How long should the mac file sit on the pxes.
        filer, filer_site = determine_correct_filer(site, jenkins_job_id)

        print(f"filer={filer}, filer_site={filer_site}\n\n\n")

        mac_file, cifs_mount_string = build_mac_file(
            mac_file_expiration_time,
            clonezilla_method_string,
            filer,
            site,
            extra_args,
            ucm_proxy,
            post_install_script,
            smb_string,
            wipe_disk,
            filer_site,
            token_file_url,
            mac_file_url,
            git_string
        )

        token_file = build_token_file(
            email_notifications,
            hostname,
            username,
            owner_user_file,
            department,
            office_location,
            image,
            access_token,
            filer,
            mount_string,
            site,
            ucm_proxy,
            mac_address,
            smb_string,
            machine_executing_script,
            wipe_disk,
            date,
            filer_site,
            is_this_an_i9,
            first_ten_of_token,
            expiration_in_seconds,
            token_type,
            cifs_mount_string,
            jenkins_job_id,
            os.environ.get('BUILD_CAUSE'),
            os.environ.get('UNIQUE_ID'),
            gv_tier(hostname)
        )

        if test_mac_file is False:
            requests.put(mac_file_url, data=mac_file)
            requests.put(token_file_url, data=token_file)
            print("Executing bluecat functions to delete IP lease")
            bluecat_token = get_bluecat_access_token(username, password)
            bluecat_ip = get_ip_from_bluecat_using_mac_address(bluecat_token, mac_address)
            if ("deleted" in bluecat_ip) or ("IP_NOT_ASSIGNED" in bluecat_ip):
                print(bluecat_ip)
                command_to_run = f"/usr/bin/host ipmi-{hostname}"
                ipmi_ip = run_a_command(command_to_run)[0].split()[3]
                print(f"ipmi-{hostname} current IP is {ipmi_ip}.")
                bluecat_netid = query_networkid_from_ip(ipmi_ip, bluecat_token)
                print(f"SubnetID for {ipmi_ip} is {bluecat_netid}. Proceeding with TFTP validation for this subnet.")
                bluecat_get_pxe = query_current_pxe(bluecat_netid, bluecat_token)
                list_of_ucm_pxes = get_ucm_pxe_ip_from_mdb(site)
                query_pxe = validate_tftp(bluecat_netid, bluecat_get_pxe, list_of_ucm_pxes, site)
                if query_pxe == "NEED_TO_UPDATE_TFTP/PXE":
                    update_tftp_pxe(list_of_ucm_pxes, bluecat_netid, bluecat_token)
                    print("TFTP updation requires atleast 30 seconds to replicate in the subnet level. Hence sleeping for 30 seconds for the rest of the execution.")
                    time.sleep(30)
            else:
                print("Executing bluecat functions to query PXE IP and update if needed")
                bluecat_netid = query_networkid_from_ip(bluecat_ip, bluecat_token)
                bluecat_get_pxe = query_current_pxe(bluecat_netid, bluecat_token)
                list_of_ucm_pxes = get_ucm_pxe_ip_from_mdb(site)
                query_pxe = validate_tftp(bluecat_netid, bluecat_get_pxe, list_of_ucm_pxes, site)
                if query_pxe == "NEED_TO_UPDATE_TFTP/PXE":
                    update_tftp_pxe(list_of_ucm_pxes, bluecat_netid, bluecat_token)
                    print("TFTP updation requires atleast 30 seconds to replicate in the subnet level. Hence sleeping for 30 seconds for the rest of the execution.")
                    time.sleep(30)
                delete_ip_lease(bluecat_ip, bluecat_token)
            pxe_the_system(hostname, ipmi_username, ipmi_password)

        email_body_text = email_body(fqdn, site, filer, image, mac_address,
                                     machine_executing_script,
                                     wipe_disk, mac_file_url, pxe_requested,
                                     git_branch, date, mac_file, jenkins_job_id,
                                     filer_site)

        send_message(f"{email_notifications}", f"Clonezilla - {fqdn}", email_body_text)

        print(mac_file_url)
        print(mac_file)
        print(token_file)

    except Exception as my_exception:
        sys.exit({my_exception})


if __name__ == '__main__':
    reimage_a_system()
