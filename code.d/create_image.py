"""Create a clonezilla image"""

import re
import time
import shlex
import subprocess
import argparse
from datetime import datetime
import sys
from random import randint
import requests
import urllib3
import modify_jenkins_job
import create_json_file_in_repo

def get_access_token(username, password):
    """A one time expiring access token is used to pull credentials necesary
    to mount the shares storing the tbs images."""
    url = "https://qct-artifactory.qualcomm.com/artifactory/api/security/token"
    expiration_time_in_seconds = 600  # 10 Minutes if we cant
    # pxe in that time imaging will fail. Added because we have
    # to use the slow network arg as a default now.
    try:
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        requests_response = requests.post(
            url,
            verify=False,
            auth=(username, password),
            data={
                "username": username,
                "expires_in": expiration_time_in_seconds,
                "scope": 'member-of-groups:*'
            },
        )

        if requests_response.status_code != 200:
            raise Exception(f"Something wrong with {url} or authentication.")
    except Exception as my_exception:
        print(my_exception)
    return requests_response.json()

def get_token_information(all_json_data):
    """Pull the data we care about from the json
    that is returned by artifactory."""
    token = all_json_data["access_token"]
    first_ten_of_token = token[:10]
    expiration_in_seconds = str(all_json_data["expires_in"])
    token_type = all_json_data["token_type"]
    return token, first_ten_of_token, expiration_in_seconds, token_type

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

def formatted_date():
    """Make the date look as we want it."""
    date = datetime.utcnow().isoformat(sep='_', timespec='auto') \
        .replace("-", "") \
        .replace(":", "") \
        .replace(".", "")
    return date

def determine_ucm_proxy():
    """Find a UCM proxy."""
    ucm_proxy = run_a_command("/usr/local/sbin/gvquery -p ucmproxy")[0].rstrip()
    return ucm_proxy

def get_parameter_from_mdb(hostname, parameter):
    """Query mdb for a particular parameter."""
    command_to_run = f"/usr/local/bin/mdb {hostname} return {parameter}"
    raw = run_a_command(command_to_run)[0]
    cleaned_mdb = (re.search(f'{parameter}: (.*)\n', raw).group(1)).rstrip() \
        .replace(" ", "")
    if "Not present in entry." in cleaned_mdb:
        cleaned_mdb = "Fix me."
    return cleaned_mdb

def get_hw_model(hostname):
    """As these systems are already in mdb we can query the hardware model from
    there rather than using dmidecode etc."""
    hw_model = get_parameter_from_mdb(hostname, "motherboard-version")
    hw_model_new = re.sub(r'[\W_]+', '', hw_model).upper()
    return hw_model_new

def create_image_name(hostname, tbs_release, image_type):
    """The image name is made up from the release, the image type i.e. 5g, 5gc etc,
    the month of the year, the hardware model and the exact time the image was made."""

    is_ipmi_up(hostname)
    hw_model = get_hw_model(hostname)
    full_date = formatted_date()
    month_year = datetime.now().strftime('%b_%y')  #
    # Duplication of running date need to figure out something here.
    image_name = tbs_release + "-" + \
                 image_type + "-" + \
                 month_year + "-" + \
                 hw_model + "-" + \
                 full_date
    return image_name.lower()

def check_password(hostname):
    """Try and determine the hardware and return that in additon to the username and password."""
    try:
        # Catch an i9
        ipmi_username = "ADMIN"
        ipmi_password = "Qualcomm5G"
        _, _, returncode = \
            run_a_command(f'ipmitool -H ipmi-{hostname}.qualcomm.com '
                          f'-U {ipmi_username} -P {ipmi_password} fru print')
        if returncode != 0:
            raise Exception("Password didnt work.")
    except Exception:
        ipmi_username = "ADMIN"
        ipmi_password = "ADMIN"
        _, _, returncode = \
            run_a_command(f'ipmitool -H ipmi-{hostname}.qualcomm.com '
                          f'-U {ipmi_username} -P {ipmi_password} fru print')
        if returncode != 0:
            raise Exception("Password didnt work.")
    return ipmi_username, ipmi_password


def read_image_data(image_name):
    """Querying a system for the hardware type is unreliable. Sometimes
    data is in the fru times sometimes it is not. We are now going to try and assume
    that the user that is imaging is using the correct image for their hardware."""
    image_name = image_name.upper()
    if "X11" in image_name:
        hardware_type = "X11"
    elif "X9" in image_name:
        hardware_type = "X9"
    elif "SYS" in image_name:
        hardware_type = "X9"
    elif "C9X" in image_name:
        hardware_type = "I9"
    else:
        hardware_type = "X9"
    return hardware_type

def get_mac_address_from_ipmi(hostname, image):
    """The way a mac address is determined depends on the hardware. i9's have one method,
    X11/X9 something else. Ideally I'd like to query the system directly but its not reliable
    at this time which leaves us no option except to assume the user pics the correct image
    for their hardware."""
    try:
        hardware_type = read_image_data(image)
        ipmi_username, ipmi_password = check_password(hostname)

        if "I9" in hardware_type:
            print("This image type is for i9's so we're assuming the system be "
                  "installed is an i9 and thus we must use the i9 commands.")
            raw_mac_address, _, returncode = \
                run_a_command(f'ipmitool -H ipmi-{hostname}.qualcomm.com '
                              f'-U {ipmi_username} -P {ipmi_password} raw 0x30 0x9F')
            if returncode != 0:
                raise Exception("Mac address determination failed.")
            mac_address = raw_mac_address.replace(' ', '-')[4:21:].upper()
            i_9 = True
        else:
            raw_mac_address, _, returncode = \
                run_a_command(f'ipmitool -H ipmi-{hostname}.qualcomm.com '
                              f'-U {ipmi_username} -P {ipmi_password} raw 0x30 0x21')
            if returncode != 0:
                raise Exception("Mac address determination failed.")

            mac_address = raw_mac_address.replace(' ', '-')[13:].upper()
            i_9 = False
    except Exception as my_exception:
        print(my_exception)
    return str(mac_address.strip()), i_9, ipmi_username, ipmi_password

def is_ipmi_up(hostname):
    """Ping the ipmi to see if its functioning in DNS.
    Long term we should maybe looking at logging in."""
    try:
        _, _, returncode = run_a_command(f"ping -c1 ipmi-{hostname}")
        if returncode != 0:
            raise Exception(f"Ipmi for ipmi-{hostname} doesnt seem to be online.")
    except Exception as my_exception:
        sys.exit({my_exception})

def collect_arguments():
    """Collect the arguments need to create and image."""
    parser = argparse.ArgumentParser()
    # Add long and short argument
    parser.add_argument("--token_username", "-U",
                        help="The username we use to request a 1 time token from artifactory")
    parser.add_argument("--password", "-P")
    parser.add_argument("--tbs_release", "-R", help="release name")
    parser.add_argument("--image_type", "-I", help="image type")
    parser.add_argument("--hostname", "-H", help="The hostname of the golden system.")
    parser.add_argument("--build_user", "-B", help="The user that initiated the job")
    parser.add_argument("--filer", "-F", help="The filer we need to save data to.")
    parser.add_argument("--smb_string", "-S",
                        help="The path that smb will use.", default="/tbs/clonezilla/boulder/")
    parser.add_argument("--ocs_args", "-O",
                        help="OCS args allow us to override the default options for image "
                             "creation.")
    parser.add_argument("--notification_list", "-N",
                        help="Not fully functional yet", default="andcha, jmeagher")
    parser.add_argument("--manual_mac_address", "-M",
                        help="Not fully functional yet pecify a manual mac address")
    parser.add_argument("--api_key", "-A", help="Api key")
    parser.add_argument("--artifactory_repo", "-Q",
                        help="qct artifactory repo like tbs-nr-release-bundle-eng-local/fullstack")
    parser.add_argument("--tbs_release_type", "-T", help="i.e. tbs_nr_fullstack ")



    # Read arguments from the command line
    args = parser.parse_args()
    token_username = args.token_username
    token_password = args.password
    golden_machine = args.hostname
    tbs_release = args.tbs_release
    image_type = args.image_type
    build_user = args.build_user
    filer = args.filer
    smb_string = args.smb_string
    ocs_args = args.ocs_args
    manual_mac_address = args.manual_mac_address
    notification_list = args.notification_list
    api_key = args.api_key


    artifactory_repo = args.artifactory_repo
    tbs_release_type = args.tbs_release_type

    return token_username, token_password, golden_machine, tbs_release, image_type, build_user, \
           filer, smb_string, ocs_args, notification_list, manual_mac_address, api_key, \
           artifactory_repo, tbs_release_type

def get_station_id(hostname):
    """Determine the station id from the machines hostname."""
    try:
        station_id = int("-".join(hostname.split("-", 2)[1:2]))
        return station_id
    except ValueError:
        return randint(1000000,9999999)

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

def remove_prefix(text):
    """Clean up the data related to the scripts we are using."""
    if text.startswith("/prj"):
        return text[len("/prj") :]
    return text


def listtostring(list_to_convert):
    """Convert a list to a string."""
    str1 = " "
    return str1.join(list_to_convert)

def build_mac_file(
        image_name,
        token_file_url,
        notification_list,
        nfs_mount_string,
        cifs_mount_string,
        build_user,
        ocs_live_run_args):
    """The mac file is what the system looks to for determine what the next steps are."""
    expiration_time = calculate_expiration_time(600)
    clonezilla_version = "clonezilla-live-20190420-disco-amd64"
    script_location_prefix = "~/nfs/tbs_clonezilla_sysscripts"
    get_credentials_script = f"{script_location_prefix}/getcredentials.sh"

    if ocs_live_run_args is None:
        ocs_live_run_args = f"-q2 -j2 -z1p -i 4096 -fsck-y -senc -p reboot " \
                            f"savedisk {image_name} sda"
    else:
        ocs_arg_list = ocs_live_run_args.split()
        ocs_live_run_args = listtostring(ocs_arg_list[:-1]) + " " \
                            + image_name + " " + str(ocs_arg_list[-1])

    mac_file = f"""# purge after: {expiration_time}
default Clonezilla_Live
LABEL Clonezilla_Live
MENU LABEL Clonezilla_Live
KERNEL tftp://%LOCALHOST%/pxelinux/pxelinux.cfg/corp/qso/{clonezilla_version}/vmlinuz
APPEND initrd=tftp://%LOCALHOST%/pxelinux/pxelinux.cfg/corp/qso/{clonezilla_version}/initrd.img \
boot=live username=user union=overlay config components quiet noswap edd=on nomodeset odmraid \
locales=en_US.UTF-8 keyboard-layouts=en keyboard-layouts=en \
ocs_live_run="/usr/sbin/ocs-sr {ocs_live_run_args}" \
ocs_live_extra_param="" modprobe.blacklist=qat_c62x modprobe.blacklist=intel_qat \
ocs_prerun1="sudo service ssh start" \
ocs_prerun2="{nfs_mount_string}" \
ocs_prerun3="wget {token_file_url} -P /tmp/" \
ocs_prerun4="{get_credentials_script}" \
ocs_prerun5="{cifs_mount_string}" \
ocs_prerun6="shred -n 200 -z -u /tmp/credentials.txt" \
ocs_prerun7="if test -d /home/partimag/{image_name} ; then reboot; fi" \
ocs_prerun8="/root/nfs/tbs_clonezilla_sysscripts/dns_helper.sh" \
ocs_live_batch=yes net.ifnames=0 nosplash noprompt \
fetch=tftp://%LOCALHOST%/pxelinux/pxelinux.cfg/corp/qso/{clonezilla_version}/filesystem.squashfs
IPAPPEND 2
"""
    return mac_file

def build_token_file(access_token):
    """Writing to the pxes allows us to consume configuration data without
    mounting additional shares which we may or may not have access to."""
    expiration_time = calculate_expiration_time(600)
    token_file = f"""# purge after: {expiration_time}
KEY={access_token}
"""
    return token_file

def calculate_expiration_time(time_to_add_in_seconds):
    """We should not allow the mac files to stay on the pxes indefintely
    otherwise we will upset UCM."""
    seconds = int(time.time())
    expiration_time = seconds + time_to_add_in_seconds
    return expiration_time

def build_urls(hostname, mac_address):
    """We post the mac and token file to these urls"""
    ucm_proxy = determine_ucm_proxy()
    token_mac = new_mac_for_token_file(hex_for_token_file(hostname), mac_address)
    token_file_url = f"{ucm_proxy}/univac/api/mac_file/{token_mac}"
    mac_file_url = f"{ucm_proxy}/univac/api/mac_file/01-{mac_address}"
    return token_file_url, mac_file_url

def build_mnt_strings(filer, smb_string):
    """Site should always be set to Boulder for now, and we're only getting one very
    small file so in the short term we should be fine.Long term I would like to include
    the credentials script but theres some other dependencies I want to tidy away first."""
    mount_string = "/prj/tbs/clonezilla"
    site = "boulder"

    # Hardcoded for now for reason above.
    nfs_mount_string = f"mkdir ~/nfs && mount -t nfs titanic.qualcomm.com:{mount_string}/{site} nfs"

    if filer is None:
        smb_string = remove_prefix(mount_string)
        cifs_mount_string = f"mount -t cifs //titanic.qualcomm.com{smb_string}/{site}/secure.d/ " \
                            f"-o credentials=/tmp/credentials.txt,vers=3.0 /home/partimag/"
    elif "titanic" not in filer:
        cifs_mount_string = f"mount -t cifs //{filer}.qualcomm.com/{smb_string} /home/partimag/"

    return nfs_mount_string, cifs_mount_string

def jenkins_job_modifications(username, api_key, image, url_to_copy_and_restore):
    """Modify the jenkins job so that new images are automatically added to the dropdown."""

    PROJECT_URL = "https://jenkinsaps-sd.qualcomm.com/tbs/job/tbs-noncce-folder/job/clonezilla"

    # Copy a give jenkins job.
    jenkins_config_file = modify_jenkins_job.get_jenkins_config(username, api_key,
                                                                url_to_copy_and_restore)
    # Create the new jenkins configuration
    new_jenkins_config_file = modify_jenkins_job.modify_jenkins_xml(jenkins_config_file, image)
    modify_jenkins_job.post_to_jenkins(f"{PROJECT_URL}/job/{url_to_copy_and_restore}/config.xml",
                                       username, api_key, new_jenkins_config_file)


def upload_release_data(username, password, image_name, hostname, tbs_release_type,
                        artifactory_repo):
    """Upload json to artifactory to be used by the tbs installer."""
    #/prj/tbs/clonezilla/boulder/tbs_clonezilla_sysscripts/create_json_file_in_repo.py
    # -n r16sep20-2020.11.57.17.rel-5gc-dec_20-x9drdiflf-13122020_143859
    # -r tbs-nr-release-bundle-eng-local/fullstack
    # -H tbs-1063-5gc -T tbs_nr_fullstack

    clonezilla_image_dictionary = {}

    api_key = create_json_file_in_repo.get_data_from_rest(
        "https://qct-artifactory.qualcomm.com/artifactory/api/security/apiKey",
        username,
        password,
        "apiKey",
        )

    clonezilla_image_dictionary, release_value, json_name = create_json_file_in_repo.modify_names(
        clonezilla_image_dictionary, image_name, hostname, tbs_release_type)

    # Needs clean up
    release_value = release_value.rsplit("-", 1)[0]
    release_value_json_file = json_name

    status_code = create_json_file_in_repo.download_file(
        f"https://qct-artifactory.qualcomm.com/artifactory/"
        f"{artifactory_repo}/"
        f"{release_value_json_file}",
        api_key,
        f"{release_value_json_file}",
    )

    if status_code != 200:

        create_json_file_in_repo.post_to_artifactory(
            f"https://qct-artifactory.qualcomm.com/artifactory/"
            f"{artifactory_repo}/{release_value_json_file}",
            username,
            api_key,
            clonezilla_image_dictionary,
        )

    else:
        clonezilla_image_dictionary = create_json_file_in_repo.read_current_json(
            f"{release_value_json_file}")

        clonezilla_image_dictionary, release_value, json_name = \
            create_json_file_in_repo.modify_names(clonezilla_image_dictionary,
                                                  image_name, hostname, tbs_release_type)

        create_json_file_in_repo.post_to_artifactory(
            f"https://qct-artifactory.qualcomm.com/artifactory/"
            f"{artifactory_repo}/{release_value_json_file}",
            username,
            api_key,
            clonezilla_image_dictionary,
        )

    print(f"https://qct-artifactory.qualcomm.com/artifactory/{artifactory_repo}"
          f"/{release_value_json_file}")
    print(clonezilla_image_dictionary)


def create_image():
    """Do the work here."""

    token_username, token_password, hostname, tbs_release, image_type, \
    build_user, filer, smb_string, ocs_args, notification_list, manual_mac_address, \
    api_key, artifactory_repo, tbs_release_type = collect_arguments()

    print(f"\n\n\nWe used {hostname} to make our golden image from.\n\n\n")

    image_name = create_image_name(hostname, tbs_release, image_type)

    mac_address, _, ipmi_username, ipmi_password = \
        get_mac_address_from_ipmi(hostname, image_name)

    if manual_mac_address is not None:
        mac_address = manual_mac_address

    all_json_data = get_access_token(token_username, token_password)
    (access_token, _, _, _) = get_token_information(all_json_data)
    token_file_url, mac_file_url = build_urls(hostname, mac_address)
    nfs_mount_string, cifs_mount_string = build_mnt_strings(filer, smb_string)
    mac_file = build_mac_file(image_name, token_file_url, notification_list,
                              nfs_mount_string, cifs_mount_string, build_user, ocs_args)
    token_file = build_token_file(access_token)

    requests.put(mac_file_url, data=mac_file)
    requests.put(token_file_url, data=token_file)

    print(mac_file_url)
    print(mac_file)
    print("\n\n")
    print(token_file_url)
    print(token_file)

    pxe_the_system(hostname, ipmi_username, ipmi_password)

    #"""
    # Modify the jenkins jobs
    jenkins_job_modifications(token_username, api_key, image_name,
                              "clonezilla_2.1_prd/job/clonezilla_reimage")
    jenkins_job_modifications(token_username, api_key, image_name,
                              "clonezilla_2.1_dev/job/clonezilla_reimage")
                                #"""

    # Upload data to artifactory
    upload_release_data(token_username,
                        token_password,
                        image_name,
                        hostname,
                        tbs_release_type,
                        artifactory_repo, )

    print(f"{build_user} created an image, {image_name}")
    print(notification_list, "Coming soon.")

create_image()
