#!/bin/bash

# Andrew Chandler
# Mon Jul 30 15:07:45 MDT 2018
# This script is part of the post install of the clonezilla script.
# It will ...
#

# DOWN_PRIVATE_IPS - Take down private IP interfaces
# UP_PRIVATE_IPS - Bring back up private IP interfaces
# COMBINE_NICS  - configure IP addresses for combined stations
# CHECK_FORWARD - DNS Breaks if dns is broken, wait until the fwd lookup works.
# CHECK_REVERSE - DNS Breaks if dns is broken, wait until the reverse lookup works.
# CLEAN_HOSTFILE - Clean the hostfile
# CLEANUP_GV_HOSTNAME - Clean up up GV hostname file
# CLEAN_UP_NETWORK - Clean up whats in the networking config
# CREATE_CRONFILE - Create another script that GV uses to perform additional postinstall tasks
# CREATE_IPMI_CRON - Create another script that GV uses to perform additional postinstall tasks
# CREATE_UDEV_RULE - Make sure that the correct interfaces come up correctly named
# DO_THE_BUSINESS - Install UAAA etc etc.
# FIND_NETWORKING_INFO - Identify the ip address etc etc
# FIX_INTERFACES_CENTOS6 - Fix networking relating to Centos 6
# FIX_INTERFACES_CENTOS7 - Fux networking relating to Centos 7
# FIX_PERMS -
# FIX_POSTFIX - Update the hostname with postfix.
# FIX_UAAA_ISSUES
# IDENTIFY_OS - Find out what OS we're imaging.
# KILL_AUTOFS - Kill autofs - this was though tto speed up shutdown.
# MOUNT_THE_DISK - Mount the restored disk
# PATCH_THE_BOX - Make sure Ubuntu desktops are patched after imaging.
# REMOVE_CHEF - Remove the Chef directory.
# REMOVE_DHCP_LEASES - Remove the exitsing DHCP lease information
# REMOVE_PERSISTENT_RULES - Remove Persistent Rules
# REMOVE_SSH_KEYS - We need new SSH keys to stay secure.
# SET_HOSTNAME - Set the hostname of the new machine
# SETUP_MOTD - Use the MOTD as a way to show progress.
# SETUPUSER - echo into GV the user
# SETUPLOCATION - echo into GV the location
# UBUNTU_NETWORK - Desktops use static ips set the static IP.
# UUIDGEN - Network Manager and GV hostid use a unique identifier. Create a new one.

# The above list is created by running
#andcha@plunger-lnx:/prj/share/andchafortesting/clonezilla.d$ grep \(\) postinstallscript.sh| sed 's/()\ {//g'| sort

# Log info can be seen in
#           /var/log/gv/cron.1_per_boot

# There should only be 1 file in the directory that looks like
# a MAC file.

cd /tmp

for i in `ls`; do
if [[ "$i" =~ ^([a-fA-F0-9]{2}-){5}[a-fA-F0-9]{2}$ ]] ; then
   TBS_TOKEN=$i
   break
fi
done

source $TBS_TOKEN

SLASH=/root/slash.d
VARD=/root/var.d
VOLUME_GROUP=vg00
HOSTNAMEFILE=$SLASH/etc/HOSTNAME

CHEF_DIR=$SLASH/etc/chef


SET_HOSTNAME () {
hostname=$HOSTNAME
#export $HOSTNAME
}

MAKE_VG_ACTIVE () {
vgchange -a y $VOLUME_GROUP
}

MOUNT_THE_DISK () {
mkdir $SLASH && mount /dev/mapper/vg00-slashvol $SLASH
mkdir $VARD && mount /dev/mapper/vg00-varvol $VARD
}

IDENTIFY_OS () {
grep 'Red Hat Enterprise Linux release 8' $SLASH/etc/release
if [[ $? -eq 0 ]] ;then
   OS=R8
fi


grep 'CentOS Linux release 7' $SLASH/etc/release
if [[ $? -eq 0 ]] ;then
   OS=C7
fi
#/S
grep 'CentOS Linux release 6' $SLASH/etc/release
if [[ $? -eq 0 ]] ;then
   OS=C6
fi

grep 'Ubuntu' $SLASH/etc/release
if [[ $? -eq 0 ]] ;then
   OS=Ubuntu
fi
}

COPY_TMP_FILE () {
cp /tmp/$TBS_TOKEN /$SLASH/etc/my_data
}

CLEAN_UP_NETWORK () {
## Cleanup the network
# Put an if in here.
sed -i '/HOSTNAME/d' $SLASH/etc/sysconfig/network
echo "HOSTNAME=$HOSTNAME" >> $SLASH/etc/sysconfig/network
# Remove any reference to the machine that was used for the golden image.
ls $SLASH/etc/sysconfig/network-scripts/ifcfg* | xargs sed -i 's/qct-8022-enbu-0/'"$HOSTNAME"'/g'
ls $SLASH/etc/sysconfig/network-scripts/ifcfg* | xargs sed -i 's/qct-8545-enbl-2/'"$HOSTNAME"'/g'
}

SETUP_MOTD () {
echo -e "\n\n\n\n Cron not finished yet....\n\n\n\n" > $SLASH/etc/banner
echo -e "\n\n\n\n Cron not finished yet....\n\n\n\n" > $SLASH/etc/motd
}

REMOVE_CHEF () {
if [[ -d $CHEF_DIR ]]; then
   rm -rf $CHEF_DIR
fi
}

FIX_INTERFACES_CENTOS6 () {
if [[ $OS == C6 ]]; then
for INTERFACE_FOR_MAC in `ifconfig -a| awk '/eth/ {print $1}'`; do
MACADDRESS=$(ifconfig $INTERFACE_FOR_MAC | awk '/HWaddr/ {mac=$NF; next} { print mac}'|head -n1)
echo -e "#HWADDR=$MACADDRESS" >> $SLASH/etc/sysconfig/network-scripts/ifcfg-$INTERFACE_FOR_MAC
done
fi
}

FIX_INTERFACES_CENTOS7 () {
if [[ $OS == C7 ]] || [[ $OS == R8 ]]  ; then
INTERFACE_FOR_MAC=`ip route| awk '/default/ {print $5}'`
MACADDRESS=$(ifconfig $INTERFACE_FOR_MAC | awk '/ether/ { print $2}'|head -n1)

for QUALNETINTERFACEFILE in `grep -l HWADD $SLASH/etc/sysconfig/network-scripts/ifcfg-*`; do
sed -i '/^HWADDR/d' $QUALNETINTERFACEFILE ;
sed -i '/^UUID/d' $QUALNETINTERFACEFILE ;
sed -i '/^HOSTNAME/d' $QUALNETINTERFACEFILE ;

sed -i '/^DHCP_HOSTNAME/d' $QUALNETINTERFACEFILE ;
sed -i '/^HOSTNAME/d' $QUALNETINTERFACEFILE ;

echo -e "HWADDR=$MACADDRESS" >> $QUALNETINTERFACEFILE ;
echo -e "DHCP_HOSTNAME="$HOSTNAME"" >> $QUALNETINTERFACEFILE ;
echo -e "HOSTNAME="$HOSTNAME"" >> $QUALNETINTERFACEFILE ;
#echo -e "UUID=$MACADDRESS" >> $QUALNETINTERFACEFILE ;
done

fi
}

CLONEZILLA_DATE () {
CLONEZILLA_VERSION_FILE=/$VARD/adm/gv/ext/clonezilla-version

(
cat <<'CREATE_VERSION_FILE'
#!/bin/bash
PATH=/usr/local/bin:/usr/bin:/bin:/usr/local/sbin:/usr/sbin:/sbin
DATE_FOR_CLONEZILLA=/var/opt/clonezilla-date
paste -sd, $DATE_FOR_CLONEZILLA

CREATE_VERSION_FILE
) > $CLONEZILLA_VERSION_FILE

chmod +x $CLONEZILLA_VERSION_FILE
}


REMOVE_REJOIN_CRON () {
UAAA_CRON_FILE=$VARD/adm/gv/cron.d/rc.1_per_boot
grep 'duty rejoin uaaa' $UAAA_CRON_FILE
RC=$?

if [[ $RC -eq 0 ]]; then
   sed -i '/duty rejoin uaaa/d' $UAAA_CRON_FILE
fi
}

SETUPSITE () {
echo $SITE > $VARD/adm/gv/site
}

CP_DELETE_LIST () {
cp /root/nfs/tbs_clonezilla_sysscripts/files_to_remove.txt $VARD/opt/
}

_SETUP_NOTIFY_LIST () {
echo $EMAIL_RECIPIENTS > $VARD/opt/email
}

_SETUP_CLONEZILLA () {
echo $DATE_FOR_CLONEZILLA > $VARD/opt/clonezilla-date
echo $IMAGE >> $VARD/opt/clonezilla-date
/bin/cp -rf /home/partimag/$IMAGE/who_made_image.txt $VARD/opt/
}

_CLEAN_OUT_UCM_PROXY () {
echo > $VARD/adm/gv/ucmproxy
}

SETUPUSER () {
echo $OWNER_USER > $VARD/adm/gv/user
}

CREATE_CELL_EXT () {
CELL_FILE=/$VARD/adm/gv/ext/cell
(
cat <<'CREATE_CELL_FILE'
#!/bin/bash
PATH=/usr/local/bin:/usr/bin:/bin:/usr/local/sbin:/usr/sbin:/sbin

# Andrew Chandler
# Part of clonezilla script
# Wed Jan 30 11:00:15 MST 2019

# Background info can be found here
# http://qwiki.qualcomm.com/it-ucm/GV_Proxy_Configuration#Changing_the_cell_of_a_GVBP_host

# Setting the afs cell is important for best performance.
# Currently many TBS systems have the wrong afs cell set and this
# means that when the select_gvproxy script runs it won't
# necessarily pick the best gvproxy. This script will fix that.

SITE=`cat /var/adm/gv/site`

# Functions
_CALCULATE_CELL () {
if [[ $SITE == "sandiego" ]] || [[ $SITE == "sanjose" ]] ; then
   CELL=qualcomm.com
elif [[ $SITE == "beijing" ]] ; then
   CELL=shanghai.qualcomm.com
elif [[ $SITE == "nuernberg" ]] ; then
   CELL=amsterdam.qualcomm.com
else
   CELL=$SITE.qualcomm.com
fi
}

# Run functions
_CALCULATE_CELL ;

echo $CELL

CREATE_CELL_FILE
) > $CELL_FILE
}

CLEAN_PROXIES () {
echo > $VARD/adm/gv/gvproxy/proxyhost
}

SETUPLOCATION () {
echo $LOCATION > $VARD/adm/gv/office_location
}

REMOVE_DHCP_LEASES () {
# Remove dhcp leases
if [ "$(ls -A $VARD/lib/dhclient)" ] ;then
  rm -rf $VARD/lib/dhclient/*
fi
}

REMOVE_STATION_CONFIG () {
if [ -f $SLASH/opt/tbs/etc/station_config.json ] ;then
  rm -rf $SLASH/opt/tbs/etc/station_config.json
fi
}

REMOVE_SYSCON_PATTERN () {
if [[ $hostname = *"5g" ]] ;then
   sed -i '/^kernel\.core_pattern \?=/d' $SLASH/etc/sysctl.conf
fi
}

CLEAN_UP_ROOT_ACCOUNT (){
   cat /dev/null > $SLASH/root/.bash_history
   history -cw
}

BLANK_OUT_LOGS () {
   find $VARD/log -type f -exec sh -c '>{}' \;
}

REMOVE_SSH_KEYS () {
  rm -f $SLASH/etc/ssh/ssh_host_*key*
  rm -f $SLASH/etc/ssh/ssh_known_hosts /etc/ssh/known_hosts
}

UBUNTU_NETWORK () {
FIRSTMAC=$(ifconfig eth0 | awk '/ether/ { print $2 }')
NEWNETWORKFILE=etc/network/interfaces

if [[ -f $SLASH/$NEWNETWORKFILE ]] ;then
   rm -rf $SLASH/$NEWNETWORKFILE ;

(
cat <<'UDEV_RULE'
SUBSYSTEM=="net", ACTION=="add", DRIVERS=="?*", ATTR{address}=="FIRSTMAC", ATTR{type}=="1", KERNEL=="eno*", NAME="eno1"
UDEV_RULE
) > $SLASH/etc/udev/rules.d/70-persistent-net.rules
sed -i "s/FIRSTMAC/${FIRSTMAC}/g" $SLASH/etc/udev/rules.d/70-persistent-net.rules

(
cat <<'UBUNTU_NETWORKFILE'
# This file describes the network interfaces available on your system
# and how to activate them. For more information, see interfaces(5).

source /etc/network/interfaces.d/*

# The loopback network interface
auto lo
iface lo inet loopback

# The primary network interface
# This is an autoconfigured IPv6 interface

# The following lines created by gv-me
auto eno1
iface eno1 inet static
      address IPADDRESS
      netmask SUBNETMASK
      gateway GATEWAY
      metric 1
      hwaddress FIRSTMAC
      dns-nameservers 129.46.8.10 129.46.12.10 192.35.156.19 129.46.50.7
      dns-search qualcomm.com
UBUNTU_NETWORKFILE
) > $SLASH/$NEWNETWORKFILE

sed -i "s/FIRSTMAC/${FIRSTMAC}/g" $SLASH/$NEWNETWORKFILE
sed -i "s/IPADDRESS/$IPADDRESS/g" $SLASH/$NEWNETWORKFILE
sed -i "s/SUBNETMASK/$SUBNETMASK/g" $SLASH/$NEWNETWORKFILE
sed -i "s/GATEWAY/$GATEWAY/g" $SLASH/$NEWNETWORKFILE
# Figure out away to change this with SFF

fi
}

TOUCH_REBOOTFILE () {
REBOOTFILE=$VARD/rebootme
touch $REBOOTFILE
}

FIX_POSTFIX () {
POSTFIXMAINFILE=$SLASH/etc/postfix/main.cf
if [[ -f $POSTFIXMAINFILE ]]; then
   sed -i '/^myhostname/d' $POSTFIXMAINFILE ;
   sed -i '/^mydestination/d' $POSTFIXMAINFILE ;
   echo "myhostname = $HOSTNAME" >> $POSTFIXMAINFILE ;
   echo "mydestination = $HOSTNAME, localhost, $myhostname, $HOSTNAME.qualcomm.com, localhost.qualcomm.com, localhost" >> $POSTFIXMAINFILE
fi
}

REMOVE_PERSISTENT_RULES () {
# put an if in here.
rm -rf $SLASH/etc/udev/rules.d/70-persistent-net.rules
}

CREATE_UDEV_RULE () {
FIRSTMAC=$(ifconfig eth0 | awk '/ether/ { print $2 }')
NEWUDEVFILE=/$SLASH/etc/udev/rules.d/70-persistent-net.rules

if [[ -f /$SLASH/etc/udev/rules.d/70-persistent-net.rules ]] ;then

(
cat <<'UDEVRULE'
SUBSYSTEM=="net", ACTION=="add", DRIVERS=="?*", ATTR{address}=="FIRSTMAC", ATTR{type}=="1", KERNEL=="eth*", NAME="INTERFACE"
UDEVRULE
) > $NEWUDEVFILE

if [[ $HOSTNAME = *"enbu"* ]] ;then
INTERFACE=eth2
   else
INTERFACE=eth4
fi

sed -i "s/INTERFACE/$INTERFACE/g" $NEWUDEVFILE
sed -i "s/FIRSTMAC/${FIRSTMAC}/g" $NEWUDEVFILE

fi

}

CLEAN_HOSTFILE () {
## Cleanup hosts
# Put an if in here.
sed -i '/^[0-9]/d' $SLASH/etc/hosts
# put an if in here. \
}

CLEAN_UP_GV_HOSTNAME () {
## Cleanup the hostname
# Put an if in here.
#sed -i '/^qct/d' $VARD/adm/gv/hostname
echo $HOSTNAME > $VARD/adm/gv/hostname

if [[ $OS == C7 ]] || [[ $OS == R8 ]] ;then
   HOSTNAMEFILE=$SLASH/etc/hostname
   rm $SLASH/etc/HOSTNAME
fi

echo $HOSTNAME > $HOSTNAMEFILE
}



CREATE_IPMI_CRONFILE () {
IPMI_CRONFILE=/$VARD/adm/gv/cron/boot.d/I12_IPMI_CRONFILE
(
cat <<'IPMI_TOOL_SCRIPT'
#!/bin/bash

if [[ $EUID -ne 0 ]]; then
   echo "This script must be run as root. Rerun using..."
   echo " sudo $0"
   exit 1
fi

set -xe
ipmihost="ipmi-$(hostname -s)"

/cm/config/duty/tbs-server/sm/ipmicfg -hostname "${ipmihost}"

/cm/config/duty/tbs-server/sm/ipmicfg -dhcp on

echo "Sleeping 60 seconds to let the DHCP lease take effect"
sleep 60

/usr/bin/ipmitool lan print | grep -i "address"

/bin/ping -c 3 -w 20 "${ipmihost}"

set +x +e

cat <<_END

Done.  To verify, launch https://$ipmihost from Chrome, IE or Edge. It will
complain about bad SSL certificates; use the prompts to bypass those errors.
(Firefox won't allow you to bypass these errors, so don't use Firefox for this.)

The serial console may also be enabled.  From any other TBS server, try connecting
to it using the below command. Once connected, hit <Enter> and confirm responsiveness;
then hit "~." to disconnect.

ipmitool -H "${ipmihost}" -U ADMIN -P ADMIN -I lanplus sol activate

_END
reboot
IPMI_TOOL_SCRIPT
) > $IPMI_CRONFILE
}

CREATE_CRONFILE_PROXY_FIX () {
CRONFILE2=/$VARD/adm/gv/cron/boot.d/I10_PROXY_FIX
(
cat <<'PROXY_FIX'
#/bin/bash

# Wed Jul 24 12:14:37 PDT 2019
# https://jira-scrum.qualcomm.com/jira/browse/TBSSERVER-993

PATH=/usr/local/bin:/usr/bin:/bin:/usr/local/sbin:/usr/sbin:/sbin
gv_version=`gvquery -p gv_version`

cacheproxyhost=/var/adm/gv/cache/proxyhost
proxyhost=/var/adm/gv/gvproxy/proxyhost

perllist=(
"/pkg/perl/5.10/.lib.i386_linux26/5.10.0/i686-linux/auto/IO/IO.so"
"/pkg/perl/5.10/lib/5.10.0/i686-linux/auto/Socket/Socket.so"
"/pkg/perl/5.10/lib/5.10.0/i686-linux/auto/Sys/Syslog/Syslog.so"
"/pkg/perl/5.10/lib/5.10.0/i686-linux/auto/Data/Dumper/Dumper.so"
)

if [ $gv_version == "GVBP2.6" ]; then
   for i in "${perllist[@]}" ; do
   count=`strings $i| wc -l`
      if [ $count -eq 0 ] ; then
         rm -f $cacheproxyhost ;
         rm -f $proxyhost ;
         rm -rf /pkg/perl/5.10/ ;
         run_setups -f proxies ;
         gvproxy ;
         break ;
      fi
   done
fi
PROXY_FIX
) > $CRONFILE2

chmod ugo+rx $CRONFILE2
}


##############################################################################################################
## The script below does most of the work
##############################################################################################################

CREATE_CRONFILE () {
CRONFILE=/$VARD/I11_CLONEZILLA
(
cat <<'FINISHINSTALL'
#!/bin/bash

# Andrew Chandler
# Mon Jul  9 15:06:03 MDT 2018
# Installed as part of CLONEZILLA SCRIPT

PATH=/usr/local/sbin:/usr/local/bin:/sbin:/bin:/usr/sbin:/usr/bin
set -x

source /etc/my_data

password_characters=10

_generate_password () {
  # Generate a onetime password using a combination of
  # !@#$%^\&\*\(\)_A-Z-a-z-0-9 and the length of password_characters
  # and then update the root password with this. This will mean that there will be no need to try
  # older passwords because the root password will be either the one generated here or when gv
  # updates the one currently assigned to the root word.
  echo "ID=$UNIQUE_ID,HOSTNAME=$HOSTNAME,STAGE=START,FUNC=POSTINSTALL,METHOD=$clonezilla_method" >&2
  password=`< /dev/urandom tr -dc !@#$%^\&\*\(\)_A-Z-a-z-0-9 | head -c${1:-$password_characters}`
  echo $password | passwd root --stdin >/dev/null
  echo "ID=$UNIQUE_ID,HOSTNAME=$HOSTNAME,STAGE=STOP,FUNC=${FUNCNAME[0]},METHOD=$clonezilla_method" >&2
}

_password_email () {
  # Send an email to the email recipient list
  echo "ID=$UNIQUE_ID,HOSTNAME=$HOSTNAME,STAGE=START,FUNC=${FUNCNAME[0]},METHOD=$clonezilla_method" >&2
  EMAIL_RECIPIENTS=`cat /var/opt/email`
  #default_interface=`ip route| grep default| awk -F'dev '  '{ print $2}' | head -n1`
  #qualnet_ip=`ip add show $default_interface| grep 'inet\ [0-9]'| awk -F' ' '{ print $2}'\
  #| awk -F'/' '{print $1}'`
  FIND_NETWORKING_INFO
  echo -e "Imaging has started the post install phase.\
  If you need to login to this machine before imaging has completed for debugging please run \
  \n\n\n\tssh root@$IP\n\n\nwith the password \n\n\n\t$password\n\n\n \
  If ssh doesnt work the password will also work on the ipmi assuming that is functional.\n\n\n\
  This new one time password will only be valid until GV has run; once GV has run the root password \
  can be found in the lockbox.\n\n\n
  Thanks" \
  | mail -s "Clonezilla - Post install and one time password $HOSTNAME - `date`" $EMAIL_RECIPIENTS
  echo "ID=$UNIQUE_ID,HOSTNAME=$HOSTNAME,STAGE=STOP,FUNC=${FUNCNAME[0]},METHOD=$clonezilla_method" >&2
}

_add_gv_tier_duty () {
  if [[ $GV_TIER != "prd" ]] ; then
    duty add gv.tier.${GV_TIER}
  fi
}

echo "ID=$UNIQUE_ID,HOSTNAME=$HOSTNAME,STAGE=START,FUNC=POSTINSTALL,METHOD=$clonezilla_method" >&2
PTR_RESTART=0
FWD_RESTART=0
MAIL_PTR_RESTART=0
MAIL_FWD_RESTART=0
MAILED_CHECK=""
BCTOOLS_RUN_CNT=0

EMAIL_RECIPIENTS=`cat /var/opt/email`

USERNAME_FOR_EMAIL=`cat /var/adm/gv/user`
THE_RECIPIENTS=$EMAIL_RECIPIENTS

_START_MAIL () {
echo "ID=$UNIQUE_ID,HOSTNAME=$HOSTNAME,STAGE=START,FUNC=${FUNCNAME[0]},METHOD=$clonezilla_method" >&2
echo "This might take a while most likely waiting for DNS to resolve." | mail -s "Clonezilla - Post_install start on $HOSTNAME - `date`" $THE_RECIPIENTS
echo "ID=$UNIQUE_ID,HOSTNAME=$HOSTNAME,STAGE=STOP,FUNC=${FUNCNAME[0]},METHOD=$clonezilla_method" >&2
}

_RESTART_MAIL () {
echo "ID=$UNIQUE_ID,HOSTNAME=$HOSTNAME,STAGE=START,FUNC=${FUNCNAME[0]},METHOD=$clonezilla_method" >&2
date | mail -s "Clonezilla - Post_install restart - `date`" $THE_RECIPIENTS
echo "ID=$UNIQUE_ID,HOSTNAME=$HOSTNAME,STAGE=STOP,FUNC=${FUNCNAME[0]},METHOD=$clonezilla_method" >&2
}

RUN_BCTOOLS_QUERY() {
   if [[ $BCTOOLS_RUN_CNT -le 2 ]]; then
      bctoolscache=/var/tmp/bctools_output
      echo "Trying to fix PTR record issues by submitting a request to http://bctools.qualcomm.com/bcdhcp"
      curl 'http://bctools.qualcomm.com/bcdhcp/' -X POST -H 'Content-Type: application/x-www-form-urlencoded' --data "hname=$HOSTNAME.qualcomm.com&submit=Submit+Request" > $bctoolscache
      if [[ "`cat $bctoolscache | grep "EXECUTING"`" ]]; then
         BCTOOLS_OUT=$(grep -Pzo "RAW*(\n|.)*EXECUTING" $bctoolscache)
         BC_TOOLS_RAN=YES
      else
         BCTOOLS_OUT=FAILED
      fi
      BCTOOLS_RUN_CNT=$(( BCTOOLS_RUN_CNT+1 ))
      echo "Postinstall ran RUN_BCTOOLS_QUERY on $HOSTNAME. Output for the same is \n $BCTOOLS_OUT \n " \
      | mail -s "$HOSTNAME ran RUN_BCTOOLS_QUERY as part of fixing automatic DNS record issues." sgudaval > /dev/null 2>&1
   else
      MAIL_DNS_ISSUES PTR
   fi
   echo $BCTOOLS_OUT
}


MAIL_DNS_ISSUES () {
   if [[ "$MAILED_CHECK" == YES ]]; then
      echo "MAIL_DNS_ISSUES already ran once. Hence ignoring this run."
      return
   else
      RECORD=$1
      echo "$HOSTNAME ran into DNS $RECORD issues while running postinstall script and BCTOOLS failed fixing it. IP acquired by NIC $default_iface is $IP. \
      Please follow steps mentioned @ https://confluence.qualcomm.com/confluence/display/TBS/Clonezilla+imaging+stuck+at+DNS+waiting+to+work" \
      | mail -s "$HOSTNAME ran into DNS $RECORD record issues." $THE_RECIPIENTS > /dev/null 2>&1
   fi
   MAILED_CHECK=YES
}

FIND_NETWORKING_INFO () {
echo "ID=$UNIQUE_ID,HOSTNAME=$HOSTNAME,STAGE=START,FUNC=${FUNCNAME[0]},METHOD=$clonezilla_method" >&2
INTERFACE=`ip route| awk '/default/ { print $5}'| uniq`

grep 'CentOS Linux release 7' /etc/release
if [[ $? -eq 0 ]] ;then
   OS=C7
fi

grep 'Red Hat Enterprise Linux release 8' /etc/release
if [[ $? -eq 0 ]] ;then
   OS=R8
fi


if [[ $OS == C7 ]] || [[ $OS == R8 ]] ;then
   default_iface=$(awk '$2 == 00000000 { print $1 }' /proc/net/route| uniq)
   IP=`ip addr show dev "$default_iface" | awk '$1 ~ /^inet/ { sub("/.*", "", $2); print $2 }'| head -n1`
else
   IP="$(ifconfig | grep -A 1 $INTERFACE | tail -1 | cut -d ':' -f 2 | cut -d ' ' -f 1)"
fi
echo "ID=$UNIQUE_ID,HOSTNAME=$HOSTNAME,STAGE=STOP,FUNC=${FUNCNAME[0]},METHOD=$clonezilla_method" >&2
}

SET_HOSTNAME () {
echo "ID=$UNIQUE_ID,HOSTNAME=$HOSTNAME,STAGE=START,FUNC=${FUNCNAME[0]},METHOD=$clonezilla_method" >&2
   hostnamectl set-hostname $HOSTNAME
echo "ID=$UNIQUE_ID,HOSTNAME=$HOSTNAME,STAGE=STOP,FUNC=${FUNCNAME[0]},METHOD=$clonezilla_method" >&2
}

_REDO_UCM_PROXIES () {
echo "ID=$UNIQUE_ID,HOSTNAME=$HOSTNAME,STAGE=START,FUNC=${FUNCNAME[0]},METHOD=$clonezilla_method" >&2
gvquery -p ucmproxy
echo "ID=$UNIQUE_ID,HOSTNAME=$HOSTNAME,STAGE=STOP,FUNC=${FUNCNAME[0]},METHOD=$clonezilla_method" >&2
}

TOUCH_REBOOTFILE () {
echo "ID=$UNIQUE_ID,HOSTNAME=$HOSTNAME,STAGE=START,FUNC=${FUNCNAME[0]},METHOD=$clonezilla_method" >&2
REBOOTFILE=/var/rebootme
touch $REBOOTFILE
echo "ID=$UNIQUE_ID,HOSTNAME=$HOSTNAME,STAGE=STOP,FUNC=${FUNCNAME[0]},METHOD=$clonezilla_method" >&2
}

CHECK_FOR_ROUTE () {
echo "ID=$UNIQUE_ID,HOSTNAME=$HOSTNAME,STAGE=START,FUNC=${FUNCNAME[0]},METHOD=$clonezilla_method" >&2
if [[ $(ip route | wc -l) -lt 1 ]] ; then
   reboot
else
   echo "We have a route"
fi
echo "ID=$UNIQUE_ID,HOSTNAME=$HOSTNAME,STAGE=STOP,FUNC=${FUNCNAME[0]},METHOD=$clonezilla_method" >&2
}

SHOULD_I_REBOOT () {
echo "ID=$UNIQUE_ID,HOSTNAME=$HOSTNAME,STAGE=START,FUNC=${FUNCNAME[0]},METHOD=$clonezilla_method" >&2
REBOOTFILE=/var/rebootme
if [[ -f $REBOOTFILE ]] ; then
   rm $REBOOTFILE
   reboot
fi
echo "ID=$UNIQUE_ID,HOSTNAME=$HOSTNAME,STAGE=STOP,FUNC=${FUNCNAME[0]},METHOD=$clonezilla_method" >&2
}


SET_TIME_ZONE () {
echo "ID=$UNIQUE_ID,HOSTNAME=$HOSTNAME,STAGE=START,FUNC=${FUNCNAME[0]},METHOD=$clonezilla_method" >&2
echo $site_zone
site_zone=""
case `cat /var/adm/gv/site| tr '[:upper:]' '[:lower:]'` in
    austin)
         site_zone='/usr/share/zoneinfo/US/Central'
        ;;
    bangalore)
        site_zone='/usr/share/zoneinfo/Asia/Kolkata'
        ;;
   beijing)
        site_zone='/usr/share/zoneinfo/Asia/Shanghai'
        ;;
   boulder)
        site_zone='/usr/share/zoneinfo/US/Mountain'
        ;;
   boxborough)
        site_zone='/usr/share/zoneinfo/US/Eastern'
        ;;
   bridgewater)
       site_zone='/usr/share/zoneinfo/US/Eastern'
       ;;
   farnborough)
       site_zone='/usr/share/zoneinfo/Europe/London'
       ;;
   haifa)
       site_zone='/usr/share/zoneinfo/Asia/Tel_Aviv'
       ;;
   hyderabad)
       site_zone='/usr/share/zoneinfo/Asia/Kolkata'
       ;;
   nuernberg)
       site_zone='/usr/share/zoneinfo/Europe/Berlin'
       ;;
   sandiego)
       site_zone='/usr/share/zoneinfo/US/Pacific'
       ;;
   sanjose)
       site_zone='/usr/share/zoneinfo/US/Pacific'
       ;;
   santaclara)
       site_zone='/usr/share/zoneinfo/US/Pacific'
       ;;
   shanghai)
       site_zone='/usr/share/zoneinfo/Asia/Shanghai'
       ;;
    *) site_zone=""
       ;;
esac
if [ ! -z "$site_zone" ]; then
    ln -nsf $site_zone /etc/localtime
fi
echo $site_zone
echo "ID=$UNIQUE_ID,HOSTNAME=$HOSTNAME,STAGE=STOP,FUNC=${FUNCNAME[0]},METHOD=$clonezilla_method" >&2
}

_FIX_TIME() {
echo "ID=$UNIQUE_ID,HOSTNAME=$HOSTNAME,STAGE=START,FUNC=${FUNCNAME[0]},METHOD=$clonezilla_method" >&2
date ;
timedatectl set-ntp yes;
date
echo "ID=$UNIQUE_ID,HOSTNAME=$HOSTNAME,STAGE=STOP,FUNC=${FUNCNAME[0]},METHOD=$clonezilla_method" >&2
}

_FIX_TIME_NTP() {
echo "ID=$UNIQUE_ID,HOSTNAME=$HOSTNAME,STAGE=START,FUNC=${FUNCNAME[0]},METHOD=$clonezilla_method" >&2
date ;
run_setups -f ntp
date
echo "ID=$UNIQUE_ID,HOSTNAME=$HOSTNAME,STAGE=STOP,FUNC=${FUNCNAME[0]},METHOD=$clonezilla_method" >&2
}


# Pinched from Mike Waltz script.
RESET_HOSTID ( ) {
echo "ID=$UNIQUE_ID,HOSTNAME=$HOSTNAME,STAGE=START,FUNC=${FUNCNAME[0]},METHOD=$clonezilla_method" >&2
  #Our hostid file
  hostidfile="/var/adm/gv/hostid"

  #Backup original hostid file
  if [ -f "$hostidfile" ]
  then
    cp "$hostidfile" "$hostidfile.orig"
  fi

  #UUID
  uuidgen="/usr/bin/uuidgen"
  if [ -x "$uuidgen" ]
  then
    $uuidgen
  else
    echo "00000000-0000-4000-y000-000000000000" \
      | perl -pe '
        s/0/(0..9,"a".."f")[rand(16)]/ge ;
        s/y/(8, 9, "a", "b")[rand(4)]/ge ;'
  fi > "$hostidfile"
echo "ID=$UNIQUE_ID,HOSTNAME=$HOSTNAME,STAGE=STOP,FUNC=${FUNCNAME[0]},METHOD=$clonezilla_method" >&2
}

KILL_AUTOFS () {
echo "ID=$UNIQUE_ID,HOSTNAME=$HOSTNAME,STAGE=START,FUNC=${FUNCNAME[0]},METHOD=$clonezilla_method" >&2
if [[ $OS != C7 ]] || [[ $OS != R8 ]];then
   service autofs stop
fi
echo "ID=$UNIQUE_ID,HOSTNAME=$HOSTNAME,STAGE=STOP,FUNC=${FUNCNAME[0]},METHOD=$clonezilla_method" >&2
}

DISABLE_CHRONYD_PRE_RHEL8 () {
echo "ID=$UNIQUE_ID,HOSTNAME=$HOSTNAME,STAGE=START,FUNC=${FUNCNAME[0]},METHOD=$clonezilla_method" >&2
if [[ $OS =~ C[67] ]]; then
   systemctl disable chronyd.service
fi
echo "ID=$UNIQUE_ID,HOSTNAME=$HOSTNAME,STAGE=STOP,FUNC=${FUNCNAME[0]},METHOD=$clonezilla_method" >&2
}

UUIDGEN () {
echo "ID=$UNIQUE_ID,HOSTNAME=$HOSTNAME,STAGE=START,FUNC=${FUNCNAME[0]},METHOD=$clonezilla_method" >&2
for QUALNETINTERFACEFILE in `grep -l UUID $SLASH/etc/sysconfig/network-scripts/ifcfg-*`; do
DEVICE=`awk -F\= '/DEVICE/ { print $2}' $QUALNETINTERFACE`
UUIDGEN=uuidgen $QUALNETINTERFACE
sed -i '/^UUID/d' $QUALNETINTERFACEFILE ;
echo -e "$UUIDGEN=$MACADDRESS" >> $QUALNETINTERFACEFILE ;
done
echo "ID=$UNIQUE_ID,HOSTNAME=$HOSTNAME,STAGE=STOP,FUNC=${FUNCNAME[0]},METHOD=$clonezilla_method" >&2
}

RESTART_LTE_CONFIG () {
echo "ID=$UNIQUE_ID,HOSTNAME=$HOSTNAME,STAGE=START,FUNC=${FUNCNAME[0]},METHOD=$clonezilla_method" >&2
systemctl list-units | grep tbs-lte-nic-config.service
RC=$?
if [[ $RC -eq 0 ]] ; then
   systemctl restart systemctl tbs-lte-nic-config.service
fi
echo "ID=$UNIQUE_ID,HOSTNAME=$HOSTNAME,STAGE=STOP,FUNC=${FUNCNAME[0]},METHOD=$clonezilla_method" >&2
}

_REDO_THE_INTERFACES () {
echo "ID=$UNIQUE_ID,HOSTNAME=$HOSTNAME,STAGE=START,FUNC=${FUNCNAME[0]},METHOD=$clonezilla_method" >&2
systemctl stop network.service ;
udevadm control --reload-rules ;
udevadm trigger --action=add ;
systemctl start network.service ;
echo "ID=$UNIQUE_ID,HOSTNAME=$HOSTNAME,STAGE=STOP,FUNC=${FUNCNAME[0]},METHOD=$clonezilla_method" >&2
}



FIX_UAAA_ISSUES () {
echo "ID=$UNIQUE_ID,HOSTNAME=$HOSTNAME,STAGE=START,FUNC=${FUNCNAME[0]},METHOD=$clonezilla_method" >&2
#if [[ $OS != C* ]] ;then
 #  if [[ $HOSTNAME = *"-lnx"* ]] ;then
      sed -i '/^uaaa$/d' /var/adm/gv/duties
  # fi
  # if [[ -f /var/lib/apt/lists/lock ]] ;then
  #    rm -rf /var/lib/apt/lists/lock
  # fi
#fi
echo "ID=$UNIQUE_ID,HOSTNAME=$HOSTNAME,STAGE=STOP,FUNC=${FUNCNAME[0]},METHOD=$clonezilla_method" >&2
}

CHECK_REVERSE (){
echo "ID=$UNIQUE_ID,HOSTNAME=$HOSTNAME,STAGE=START,FUNC=${FUNCNAME[0]},METHOD=$clonezilla_method" >&2
run_setups -f cron
/var/adm/gv/cron/1_per_day.d/labops_scripts.sh
touch /tmp/dnsstarted
if [[ -z "$IP" ]]; then
   FIND_NETWORKING_INFO
fi
#DNS_LOG=/var/log/dns_log.log
#touch $DNS_LOG
#exec 1>$DNS_LOG
#exec 2>&1

#Check the reverse dns
until [[ $(dig +short -x $IP ) == "$HOSTNAME.qualcomm.com." ]] ;do
   sleep 30;
   CHECK_FOR_ROUTE
   date '+%Y-%m-%d_%H:%M:%S' ;
   PTR_RESTART=$(( PTR_RESTART+1 ))
   MAIL_PTR_RESTART=$(( MAIL_PTR_RESTART+1 ))
   echo $HOSTNAME
   SETUP_MOTD_DNS
   if [[ PTR_RESTART -gt 5 ]] ;then
      #service network restart ;
      echo "Still looking at the PTR."
      FIND_NETWORKING_INFO ;
      PTR_RESTART=0
   fi
   if [[ MAIL_PTR_RESTART -gt 90 ]]; then
      RUN_BCTOOLS_QUERY
      if [[ "$BCTOOLS_OUT" == FAILED ]]; then
         echo "BCTOOLS FAILED. Sleeping for 10mins before we can retry bctools or bail out"
         sleep 600
         RUN_BCTOOLS_QUERY
      fi
      MAIL_PTR_RESTART=0
   fi
done
echo "ID=$UNIQUE_ID,HOSTNAME=$HOSTNAME,STAGE=STOP,FUNC=${FUNCNAME[0]},METHOD=$clonezilla_method" >&2
}

CHECK_FORWARD () {
#Check the forward lookup/dns

#DNS_LOG=/var/log/dns_log.log
#exec 1>$DNS_LOG
#exec 2>&1
echo "ID=$UNIQUE_ID,HOSTNAME=$HOSTNAME,STAGE=START,FUNC=${FUNCNAME[0]},METHOD=$clonezilla_method" >&2

until [[ $(dig +short $HOSTNAME.qualcomm.com ) == "$IP" ]] ;do
   sleep 30;
   date '+%Y-%m-%d_%H:%M:%S' ;
   FWD_RESTART=$(( FWD_RESTART+1 ))
   MAIL_FWD_RESTART=$(( MAIL_FWD_RESTART+1 ))
   echo $HOSTNAME
   SETUP_MOTD_DNS
   if [[ FWD_RESTART -gt 5 ]] ;then
      #service network restart ;
      echo "Still looking at the FWD."
      FIND_NETWORKING_INFO ;
      FWD_RESTART=0
   fi
   if [[ MAIL_FWD_RESTART -gt 60 ]]; then
      MAIL_DNS_ISSUES FWD
      MAIL_FWD_RESTART=0
   fi
done
echo "ID=$UNIQUE_ID,HOSTNAME=$HOSTNAME,STAGE=STOP,FUNC=${FUNCNAME[0]},METHOD=$clonezilla_method" >&2
}

DNS_GV_MESS () {
echo "ID=$UNIQUE_ID,HOSTNAME=$HOSTNAME,STAGE=START,FUNC=${FUNCNAME[0]},METHOD=$clonezilla_method" >&2
HOST_FILE=/etc/hosts

#example
#10.243.79.56    qct-8022-enbu-0.qualcomm.com qct-8022-enbu-0

(
cat <<EOF
# Generated by clonezilla as a way to limit dns' impact
#

$IP      $HOSTNAME.qualcomm.com $HOSTNAME
EOF
) > $HOST_FILE
}

CHECK_FILE_AGE () {

FILE=/tmp/dnsstarted
LIMIT_IN_MINUTES=60
AGE=0
DNS_COMPLAIN_ADDRESS=dnsadmin,tbs.clonezilla.support,labops.tbs, pdlm.test.tx
DNS_COMPLAIN_SENDER=andcha
DNS_WATCHERS=andcha
SITE=`cat /var/adm/gv/site`

VQIPDATABASE=/usr/local/etc/common/subnets/networks.qip
RAWSITE="Unable to find in this instance."

if [[ -s $VQIPDATABASE ]] && [[ -r $VQIPDATABASE ]]; then
   #This address the fact that eth0 is not the default interface when machines are being setup.
   DEFAULTINTERFACE=`ip route| grep default| awk -F'dev '  '{ print $2}'| head -n1`
   IPADDRESSETH0=`ip add show $DEFAULTINTERFACE| grep 'inet\ [0-9]'| awk -F' ' '{ print $2}'`
   SUBNET=`ipcalc -n $IPADDRESSETH0| awk -F= '{ print $2}'`
   #RAWSITE is converted to lower to get around the inconsistency of the subnet naming
   RAWSITE=`grep $SUBNET $VQIPDATABASE | awk '{ print tolower($0) }'`
fi

until [[ $AGE -ge $LIMIT_IN_MINUTES ]] ;do
AGE=$(((`/bin/date +%s` - `/usr/bin/stat -c "%Y" $FILE`) /60 ))
echo "Still going ...."
sleep 45
done

#Do something
/var/adm/gv/cron/1_per_hour.d/dns_for_splunk

echo -e "@watchers=$DNS_WATCHERS\n\nThis is an automated message.\n\n\n\
DNSTEAM, DNS for $HOSTNAME has taken $LIMIT_IN_MINUTES minutes so far and is yet to \
resolve.\n\nThe system is in $SITE\n\nThe current IP is $IP\n\nThe network interface info is as \n\n\n$(ip add show $INTERFACE)\n\n\n\

\n\n\nThe subnet info is as so:

$RAWSITE
\n\n\n

Please take a look and fix.\n\nThanks" | mail -S from=$DNS_COMPLAIN_SENDER -s \
"DNS is slow $HOSTNAME - PDLM for tracking only" $DNS_COMPLAIN_ADDRESS
return 1
echo -e "DNS is slow for `hostname -f`" | logger
}

DO_THE_BUSINESS () {
SETUP_MOTD
FILE=/tmp/dnsstarted

if [ -f $FILE ]; then
   rm -rf $FILE
fi

#Once we've passed the checks do the work
echo -e "------------------------- Do the business ..."
SITE=`gvquery -p site`
echo $SITE
#service vasd stop;
##Andcha Monday
#killall /opt/quest/sbin/.vasd ;
#yum remove vasclnt -y && echo > /var/adm/gv/gvproxy/proxyhost && sed -i '/uaaa/d' /var/adm/gv/duties && run_setups -f proxies
#sed -i '/uaaa/d' /var/adm/gv/duties ;
#yum remove vasclnt -y ;
#duty add uaaa ;
service vasd stop ;  killall /opt/quest/sbin/.vasd ; sed -i '/uaaa/d' /var/adm/gv/duties  ; yum remove vasclnt -y ; unlink /var/log/uaaa_install; sed -i '/^uaaa/d' /var/adm/gv/duties ;duty add uaaa
echo "ID=$UNIQUE_ID,HOSTNAME=$HOSTNAME,STAGE=STOP,FUNC=${FUNCNAME[0]},METHOD=$clonezilla_method" >&2
}

FIX_PERMS () {
echo "ID=$UNIQUE_ID,HOSTNAME=$HOSTNAME,STAGE=START,FUNC=${FUNCNAME[0]},METHOD=$clonezilla_method" >&2
chattr -i /var/adm/gv/cron/boot.d/I12_CLONEZILLA
rm -rf /var/adm/gv/cron/boot.d/I12_CLONEZILLA
echo "ID=$UNIQUE_ID,HOSTNAME=$HOSTNAME,STAGE=STOP,FUNC=${FUNCNAME[0]},METHOD=$clonezilla_method" >&2
}

SETUP_MOTD () {
echo "ID=$UNIQUE_ID,HOSTNAME=$HOSTNAME,STAGE=START,FUNC=${FUNCNAME[0]},METHOD=$clonezilla_method" >&2
echo -e "\n\n\n\n Cron not finished yet....\n\n\n\n" > /etc/banner
echo -e "\n\n\n\n Cron not finished yet....\n\n\n\n" > /etc/motd
echo "ID=$UNIQUE_ID,HOSTNAME=$HOSTNAME,STAGE=STOP,FUNC=${FUNCNAME[0]},METHOD=$clonezilla_method" >&2
}

SETUP_MOTD_DNS () {
echo "ID=$UNIQUE_ID,HOSTNAME=$HOSTNAME,STAGE=START,FUNC=${FUNCNAME[0]},METHOD=$clonezilla_method" >&2
echo -e "\n\n\n\n DNS waiting to work ....\n\n\n\n" > /etc/banner
echo -e "\n\n\n\n DNS waiting to work ....\n\n\n\n" > /etc/motd
echo "ID=$UNIQUE_ID,HOSTNAME=$HOSTNAME,STAGE=STOP,FUNC=${FUNCNAME[0]},METHOD=$clonezilla_method" >&2
}

PATCH_THE_BOX () {
echo "ID=$UNIQUE_ID,HOSTNAME=$HOSTNAME,STAGE=START,FUNC=${FUNCNAME[0]},METHOD=$clonezilla_method" >&2
OS=`lsb_release -i -s`
#Patch ubuntu boxes
if [[ $OS == Ubuntu ]] ;then
   apt-get update ;
   apt-get -o Dpkg::Options::="--force-confdef" -o Dpkg::Options::="--force-confold" dist-upgrade -y --force-yes;
fi
echo "ID=$UNIQUE_ID,HOSTNAME=$HOSTNAME,STAGE=STOP,FUNC=${FUNCNAME[0]},METHOD=$clonezilla_method" >&2
}

RUN_DRACUT () {
echo "ID=$UNIQUE_ID,HOSTNAME=$HOSTNAME,STAGE=START,FUNC=${FUNCNAME[0]},METHOD=$clonezilla_method" >&2
   dracut -f -v
echo "ID=$UNIQUE_ID,HOSTNAME=$HOSTNAME,STAGE=STOP,FUNC=${FUNCNAME[0]},METHOD=$clonezilla_method" >&2
}

SEND_MDB_EMAIL () {
echo "ID=$UNIQUE_ID,HOSTNAME=$HOSTNAME,STAGE=START,FUNC=${FUNCNAME[0]},METHOD=$clonezilla_method" >&2
mdb `hostname`| mail -s "Clonezilla - `date`" $THE_RECIPIENTS
echo "ID=$UNIQUE_ID,HOSTNAME=$HOSTNAME,STAGE=STOP,FUNC=${FUNCNAME[0]},METHOD=$clonezilla_method" >&2
}

LOG_IMAGING_DURATION () {
echo "ID=$UNIQUE_ID,HOSTNAME=$HOSTNAME,STAGE=START,FUNC=${FUNCNAME[0]},METHOD=$clonezilla_method" >&2
    log_temp_dir="$( mktemp -d )"
    chmod a+rx "${log_temp_dir}"
    GIT_SSL_NO_VERIFY=1 git clone https://github.qualcomm.com/tbs/clonezilla-img-mgmt.git ${log_temp_dir}
    runuser -l tbsadmin -c "${log_temp_dir}/code.d/clonezilla_imaging_log.py --gv-proxy '${proxy_selection_time},${start_proxy},${end_proxy}'"
    [[ -n "${log_temp_dir}" ]] && rm -rf ${log_temp_dir}
echo "ID=$UNIQUE_ID,HOSTNAME=$HOSTNAME,STAGE=STOP,FUNC=${FUNCNAME[0]},METHOD=$clonezilla_method" >&2
}

SEND_THE_USER_AN_EMAIL () {
echo "ID=$UNIQUE_ID,HOSTNAME=$HOSTNAME,STAGE=START,FUNC=${FUNCNAME[0]},METHOD=$clonezilla_method" >&2
mdb `hostname`| mail -s "Clonezilla - `hostname` - Rebooting your machine after a successful reimage of `hostname` - `date`" $THE_RECIPIENTS
echo "ID=$UNIQUE_ID,HOSTNAME=$HOSTNAME,STAGE=STOP,FUNC=${FUNCNAME[0]},METHOD=$clonezilla_method" >&2
}

CRON_RUN_BUT_NOT_GV () {
echo "ID=$UNIQUE_ID,HOSTNAME=$HOSTNAME,STAGE=START,FUNC=${FUNCNAME[0]},METHOD=$clonezilla_method" >&2
echo -e "\n\n\n\n\n Cron has run but GV has not run this may effect the machine in some way...\n\n\n\n" > /etc/motd
echo -e "\n\n\n\n\n Cron has run but GV has not run this may effect the machine in some way...\n\n\n\n" > /etc/banner
echo "ID=$UNIQUE_ID,HOSTNAME=$HOSTNAME,STAGE=STOP,FUNC=${FUNCNAME[0]},METHOD=$clonezilla_method" >&2
}

TRY_RUN_SETUPS () {
echo "ID=$UNIQUE_ID,HOSTNAME=$HOSTNAME,STAGE=START,FUNC=${FUNCNAME[0]},METHOD=$clonezilla_method" >&2
SETUPS_COUNT=0
until [ $SETUPS_COUNT -ge 3 ] ; do
   run_setups -f -a && break
   SETUPS_COUNT=$[SETUPS_COUNT+1]
   sleep 60 ;
   done
echo "ID=$UNIQUE_ID,HOSTNAME=$HOSTNAME,STAGE=STOP,FUNC=${FUNCNAME[0]},METHOD=$clonezilla_method" >&2
}

MAKE_CACHE () {
echo "ID=$UNIQUE_ID,HOSTNAME=$HOSTNAME,STAGE=START,FUNC=${FUNCNAME[0]},METHOD=$clonezilla_method" >&2
echo -n $HOSTNAME | egrep -iq -e "5g$"
RC=$?
if [[ $RC -eq 0 ]] ; then
   /usr/bin/yum makecache; /usr/bin/eagerupdate tbs-nr-deps-gnb
fi

echo -n $HOSTNAME | egrep -iq -e "5gc$"
RC=$?
if [[ $RC -eq 0 ]] ; then
   /usr/bin/yum makecache; /usr/bin/eagerupdate tbs-nr-deps-5gc
fi

# AJC 6/19 if [[ -d /cm/config/duty/tbs-lte.prod ]]; then
if [[ `gvquery -p duties | grep tbs-lte.prod` ]]; then
   /usr/bin/yum makecache;
   /cm/config/duty/tbs-lte.prod/scripts/eagerupdate
fi
echo "ID=$UNIQUE_ID,HOSTNAME=$HOSTNAME,STAGE=STOP,FUNC=${FUNCNAME[0]},METHOD=$clonezilla_method" >&2
}


IPMI_FIX (){
echo "ID=$UNIQUE_ID,HOSTNAME=$HOSTNAME,STAGE=START,FUNC=${FUNCNAME[0]},METHOD=$clonezilla_method" >&2
ipmihost="ipmi-$(hostname -s)"

/cm/config/duty/tbs-server/sm/ipmicfg -hostname "${ipmihost}"

/cm/config/duty/tbs-server/sm/ipmicfg -dhcp on

echo "Sleeping 60 seconds to let the DHCP lease take effect"
sleep 60

/usr/bin/ipmitool lan print | grep -i "address"

/bin/ping -c 3 -w 20 "${ipmihost}"
echo "ID=$UNIQUE_ID,HOSTNAME=$HOSTNAME,STAGE=STOP,FUNC=${FUNCNAME[0]},METHOD=$clonezilla_method" >&2
}

_REDO_PROXIES () {
echo "ID=$UNIQUE_ID,HOSTNAME=$HOSTNAME,STAGE=START,FUNC=${FUNCNAME[0]},METHOD=$clonezilla_method" >&2
start_proxy="$( gvquery -p proxyhost )"
proxy_selection_time="$( { \time -f "%e" /usr/local/sbin/run_setups -f proxies ; } |& tail -1 )"
end_proxy="$( gvquery -p proxyhost )"
/usr/local/sbin/run_setups -f repo
echo "ID=$UNIQUE_ID,HOSTNAME=$HOSTNAME,STAGE=STOP,FUNC=${FUNCNAME[0]},METHOD=$clonezilla_method" >&2
}

ADD_GNB_DUTY () {
echo "ID=$UNIQUE_ID,HOSTNAME=$HOSTNAME,STAGE=START,FUNC=${FUNCNAME[0]},METHOD=$clonezilla_method" >&2
echo -n $HOSTNAME | egrep -iq -e "5g$"
RC=$?
if [[ $RC -eq 0 ]] ; then
   duty add tbs-5g.gnb
fi

echo -n $HOSTNAME | egrep -iq -e "5gc$"
RC=$?
if [[ $RC -eq 0 ]] ; then
   duty add tbs-5g.5gc
fi
echo "ID=$UNIQUE_ID,HOSTNAME=$HOSTNAME,STAGE=STOP,FUNC=${FUNCNAME[0]},METHOD=$clonezilla_method" >&2
}

_REMOVE_STATION_CFG () {
echo "ID=$UNIQUE_ID,HOSTNAME=$HOSTNAME,STAGE=START,FUNC=${FUNCNAME[0]},METHOD=$clonezilla_method" >&2
FILE=/opt/tbs/etc/station_config.json

if [[ -f $FILE ]];then
   rm -rf $FILE
fi
echo "ID=$UNIQUE_ID,HOSTNAME=$HOSTNAME,STAGE=STOP,FUNC=${FUNCNAME[0]},METHOD=$clonezilla_method" >&2
}

_STOP_SERVICE (){
echo "ID=$UNIQUE_ID,HOSTNAME=$HOSTNAME,STAGE=START,FUNC=${FUNCNAME[0]},METHOD=$clonezilla_method" >&2
SERVICE_TO_STOP=station-cfg-backup.service
# Is the service installed

systemctl -at service| grep $SERVICE_TO_START > /dev/null 2>&1
RC=$?
#If the service is installed
if [[ $RC -eq 0 ]]; then
   systemctl stop $SERVICE_TO_STOP > /dev/null 2>&1
   systemctl disable $SERVICE_TO_STOP > /dev/null 2>&1
fi
echo "ID=$UNIQUE_ID,HOSTNAME=$HOSTNAME,STAGE=STOP,FUNC=${FUNCNAME[0]},METHOD=$clonezilla_method" >&2
}

_FIX_PERMS_ON_STATION_CFG () {
echo "ID=$UNIQUE_ID,HOSTNAME=$HOSTNAME,STAGE=START,FUNC=${FUNCNAME[0]},METHOD=$clonezilla_method" >&2
STATION_CONFIG_DIR=/opt/tbs/etc/
if [ -d "$STATION_CONFIG_DIR" ] ;then
   # Do not identify tbsadmin user by name because UAAA might not have configured it yet.
   # Rather identify it by its numerical id.
   # 1395 0 bbuhlig@tbs-server-dev-03 ../code.d % getent passwd tbsadmin
   # tbsadmin:VAS:413243:200:TBS Admin:/usr2/tbsadmin:/bin/zsh
   # 1396 0 bbuhlig@tbs-server-dev-03 ../code.d % getent passwd tbsadmin | awk -F: '{print $3}'
   # 413243
   # 1397 0 bbuhlig@tbs-server-dev-03 ../code.d % touch /tmp/testing
   # 1408 0 bbuhlig@tbs-server-dev-03 ../code.d % ls -la /tmp/testing
   # -rw-r--r-- 1 bbuhlig tbsall 0 Dec 12 19:26 /tmp/testing
   # 1409 0 bbuhlig@tbs-server-dev-03 ../code.d % sudo chown 413243 /tmp/testing
   # Enter password for bbuhlig (QUALPASS):
   # 1410 0 bbuhlig@tbs-server-dev-03 ../code.d % ls -la /tmp/testing
   # -rw-r--r-- 1 tbsadmin tbsall 0 Dec 12 19:26 /tmp/testing
   # 1411 0 bbuhlig@tbs-server-dev-03 ../code.d %

   chown -R 413243 "$STATION_CONFIG_DIR"
   chmod -R 775 "$STATION_CONFIG_DIR"
fi
echo "ID=$UNIQUE_ID,HOSTNAME=$HOSTNAME,STAGE=STOP,FUNC=${FUNCNAME[0]},METHOD=$clonezilla_method" >&2
}

_START_SERVICE (){
echo "ID=$UNIQUE_ID,HOSTNAME=$HOSTNAME,STAGE=START,FUNC=${FUNCNAME[0]},METHOD=$clonezilla_method" >&2
SERVICE_TO_START=station-cfg-backup.service
# Is the service installed
systemctl -at service| grep $SERVICE_TO_START > /dev/null 2>&1
RC=$?
#If the service is installed
if [[ $RC -ne 0 ]]; then
   systemctl enable $SERVICE_TO_START > /dev/null 2>&1
fi
echo "ID=$UNIQUE_ID,HOSTNAME=$HOSTNAME,STAGE=STOP,FUNC=${FUNCNAME[0]},METHOD=$clonezilla_method" >&2
}

_FIX_JOURNAL () {
echo "ID=$UNIQUE_ID,HOSTNAME=$HOSTNAME,STAGE=START,FUNC=${FUNCNAME[0]},METHOD=$clonezilla_method" >&2
if [ -d /var/log/journal/ ] ;then
   rm -rf /var/log/journal/
fi
echo "ID=$UNIQUE_ID,HOSTNAME=$HOSTNAME,STAGE=STOP,FUNC=${FUNCNAME[0]},METHOD=$clonezilla_method" >&2
}

_DELETE_LIST_FILES (){
echo "ID=$UNIQUE_ID,HOSTNAME=$HOSTNAME,STAGE=START,FUNC=${FUNCNAME[0]},METHOD=$clonezilla_method" >&2
while read -r file; do find $file -exec rm -rf '{}' \;  2> /dev/null; done < /var/opt/files_to_remove.txt
echo "ID=$UNIQUE_ID,HOSTNAME=$HOSTNAME,STAGE=STOP,FUNC=${FUNCNAME[0]},METHOD=$clonezilla_method" >&2
}

_FIX_HOST_FILE(){
echo "ID=$UNIQUE_ID,HOSTNAME=$HOSTNAME,STAGE=START,FUNC=${FUNCNAME[0]},METHOD=$clonezilla_method" >&2
default_interface=`ip route| grep default| awk -F'dev '  '{ print $2}' | head -n1`
qualnet_ip=`ip add show $default_interface| grep 'inet\ [0-9]'| awk -F' ' '{ print $2}'| awk -F'/' '{print $1}'`

# Most machines in NA have 2 correct hostnames in their host file. When UAAA fails we have 3 or more.
# We do see more hostnames in the file in the ap atleast 3 but again this solution will work.
if [ $(getent hosts `hostname -f`|awk -F' ' '{print NF; exit}') -gt 3 ]; then
   # Comment out the qualnet ip on a system
   sed -i "s/^$qualnet_ip/###/" /etc/hosts;
   # and force gv to query DNS again.
   run_setups -f hosts;
fi
echo "ID=$UNIQUE_ID,HOSTNAME=$HOSTNAME,STAGE=STOP,FUNC=${FUNCNAME[0]},METHOD=$clonezilla_method" >&2
}

_restore_from_clonezilla(){
restore_script=/opt/install/tbsinstall/bin/tbsrestore_user_data
echo "ID=$UNIQUE_ID,HOSTNAME=$HOSTNAME,STAGE=START,FUNC=${FUNCNAME[0]},METHOD=$clonezilla_method" >&2

if [[ -f $restore_script ]];then
   logger -t clonezilla "in restore block"
   systemctl stop tbs-prodinfra.service
   systemctl stop tbs-http.service
   $restore_script --remote --json
else
   logger -t clonezilla "missing $restore_script"
fi
echo "ID=$UNIQUE_ID,HOSTNAME=$HOSTNAME,STAGE=STOP,FUNC=${FUNCNAME[0]},METHOD=$clonezilla_method" >&2
}

_restore_from_clonezilla_post_rejoin(){
restore_script=/opt/install/tbsinstall/bin/tbsrestore_user_data
echo "ID=$UNIQUE_ID,HOSTNAME=$HOSTNAME,STAGE=START,FUNC=${FUNCNAME[0]},METHOD=$clonezilla_method" >&2

if [[ -f $restore_script ]];then
   logger -t clonezilla "${FUNCNAME[0]} in restore block"
   $restore_script --commands
else
   logger -t clonezilla "${FUNCNAME[0]} missing $restore_script"
fi
echo "ID=$UNIQUE_ID,HOSTNAME=$HOSTNAME,STAGE=STOP,FUNC=${FUNCNAME[0]},METHOD=$clonezilla_method" >&2
}

WAIT_FOR_TBSADMIN() {
echo "ID=$UNIQUE_ID,HOSTNAME=$HOSTNAME,STAGE=START,FUNC=${FUNCNAME[0]},METHOD=$clonezilla_method" >&2
while [ $(getent passwd tbsadmin| wc -l) -lt 1 ]; do sleep 10; logger "${FUNCNAME[0]} tbsadmin is not yet available"; done
echo "ID=$UNIQUE_ID,HOSTNAME=$HOSTNAME,STAGE=STOP,FUNC=${FUNCNAME[0]},METHOD=$clonezilla_method" >&2
}

FIX_HTTP_FILE(){
echo "ID=$UNIQUE_ID,HOSTNAME=$HOSTNAME,STAGE=START,FUNC=${FUNCNAME[0]},METHOD=$clonezilla_method" >&2
config_file=/etc/httpd/conf.d/tbs-httpd-05-nr.conf

if [[ -f $config_file ]];then
   sed -i /"^OIDCRedirectURI/c\OIDCRedirectURI http://$(hostname -f)/secure/redirect_uri" $config_file
   sed -i /"^RewriteCond %{HTTP_HOST}/c\RewriteCond %{HTTP_HOST} \"^$(hostname)$\"" $config_file
   sed -i /"^RewriteRule \"(.*)\"/c\RewriteRule \"(.*)\" \"http://$(hostname -f)\$1\" [R]" $config_file
fi
echo "ID=$UNIQUE_ID,HOSTNAME=$HOSTNAME,STAGE=STOP,FUNC=${FUNCNAME[0]},METHOD=$clonezilla_method" >&2
}

FIX_UAAA_WITH_START(){
echo "ID=$UNIQUE_ID,HOSTNAME=$HOSTNAME,STAGE=START,FUNC=${FUNCNAME[0]},METHOD=$clonezilla_method" >&2
duty start uaaa
duty rejoin uaaa
echo "ID=$UNIQUE_ID,HOSTNAME=$HOSTNAME,STAGE=STOP,FUNC=${FUNCNAME[0]},METHOD=$clonezilla_method" >&2
}

UPDATE_STATION_CFG(){
echo "ID=$UNIQUE_ID,HOSTNAME=$HOSTNAME,STAGE=START,FUNC=${FUNCNAME[0]},METHOD=$clonezilla_method" >&2
sleep 30
/usr/bin/stationcfg update_station -f /opt/tbs/etc/station_config.json
chown tbsadmin:tbsall /opt/tbs/etc/station_config.json
touch /opt/data/nr/splunk/tbsinstaller/events.txt
chown tbsadmin:tbsall /opt/data/nr/splunk/tbsinstaller/events.txt
/usr/bin/stationcfg update_deps
echo "ID=$UNIQUE_ID,HOSTNAME=$HOSTNAME,STAGE=STOP,FUNC=${FUNCNAME[0]},METHOD=$clonezilla_method" >&2
}

FORCE_HOSTFILE_UPDATE(){
run_setups -f hosts
}

UPDATE_CHASSIS(){
echo "ID=$UNIQUE_ID,HOSTNAME=$HOSTNAME,STAGE=START,FUNC=${FUNCNAME[0]},METHOD=$clonezilla_method" >&2
/usr/bin/stationcfg update_chassis
echo "ID=$UNIQUE_ID,HOSTNAME=$HOSTNAME,STAGE=STOP,FUNC=${FUNCNAME[0]},METHOD=$clonezilla_method" >&2
}

_UPDATE_DNS(){
echo "ID=$UNIQUE_ID,HOSTNAME=$HOSTNAME,STAGE=START,FUNC=${FUNCNAME[0]},METHOD=$clonezilla_method" >&2
run_setups -f resolv.conf
echo "ID=$UNIQUE_ID,HOSTNAME=$HOSTNAME,STAGE=STOP,FUNC=${FUNCNAME[0]},METHOD=$clonezilla_method" >&2
}

_INSTALL_BIOS_AUDIT(){
echo "ID=$UNIQUE_ID,HOSTNAME=$HOSTNAME,STAGE=START,FUNC=${FUNCNAME[0]},METHOD=$clonezilla_method" >&2
yum install -y tbs-bios-audit-check
echo "ID=$UNIQUE_ID,HOSTNAME=$HOSTNAME,STAGE=STOP,FUNC=${FUNCNAME[0]},METHOD=$clonezilla_method" >&2
}

FIX_LOG_INSTALLER_LOG_FILE() {
echo "ID=$UNIQUE_ID,HOSTNAME=$HOSTNAME,STAGE=START,FUNC=${FUNCNAME[0]},METHOD=$clonezilla_method" >&2
log_file=/opt/data/nr/log/stationinfra/log.dlf
station_infra_dir=/opt/data/nr/log/stationinfra



if [ -d $station_infra_dir ]; then
   echo "$station_infra_dir exists."
   if [ ! -f $log_file ]; then
     echo "$log_file not there creating $log_file."
     touch $log_file
   fi
   if [ -f $log_file ]; then
     chmod 666 $log_file
     chown tbsadmin:tbsall $log_file
   fi
fi
echo "$UNIQUE_ID,stop,${FUNCNAME[0]}" >&2
echo "ID=$UNIQUE_ID,HOSTNAME=$HOSTNAME,STAGE=STOP,FUNC=${FUNCNAME[0]},METHOD=$clonezilla_method" >&2
}

DATA_APPS_VM_POSTINSTALL () {
echo "ID=$UNIQUE_ID,HOSTNAME=$HOSTNAME,STAGE=START,FUNC=${FUNCNAME[0]},METHOD=$clonezilla_method" >&2
echo "$UNIQUE_ID,start,${FUNCNAME[0]}" >&2
   if [[ -f /opt/tbs/nr/vm/tbs-nr-5gc-vm-imaging-postinstall ]]; then
      echo "Executing postinstall script for Data Apps VM"
      /opt/tbs/nr/vm/tbs-nr-5gc-vm-imaging-postinstall
   fi
echo "ID=$UNIQUE_ID,HOSTNAME=$HOSTNAME,STAGE=STOP,FUNC=${FUNCNAME[0]},METHOD=$clonezilla_method" >&2
}

ICE_VM_POSTINSTALL () {
echo "ID=$UNIQUE_ID,HOSTNAME=$HOSTNAME,STAGE=START,FUNC=${FUNCNAME[0]},METHOD=$clonezilla_method" >&2
echo "$UNIQUE_ID,start,${FUNCNAME[0]}" >&2
   if [[ -f /opt/tbs/nr/vm/tbs-nr-ice-vm-imaging-postinstall ]]; then
      echo "Executing postinstall script for ICE VM"
      /opt/tbs/nr/vm/tbs-nr-ice-vm-imaging-postinstall
   fi
echo "ID=$UNIQUE_ID,HOSTNAME=$HOSTNAME,STAGE=STOP,FUNC=${FUNCNAME[0]},METHOD=$clonezilla_method" >&2
}

REMOVE_CLONEZILLA_SERVICE () {
echo "ID=$UNIQUE_ID,HOSTNAME=$HOSTNAME,STAGE=START,FUNC=${FUNCNAME[0]},METHOD=$clonezilla_method" >&2
clonezilla_service="/etc/systemd/system/clonezilla.service"
clonezilla_timer="/etc/systemd/system/clonezilla.timer"
clonezilla_script="/var/I11_CLONEZILLA"
clonezilla_cron="/var/adm/gv/cron/boot.d/I10_call_clonezilla"


   if [[ -f $clonezilla_service ]]; then
      systemctl disable clonezilla.service
      chattr -i $clonezilla_service
      chattr -i $clonezilla_timer
      chattr -i $clonezilla_script
      chattr -i $clonezilla_cron
      rm $clonezilla_service
      rm $clonezilla_timer
      rm $clonezilla_script
      rm $clonezilla_cron
   fi
echo "ID=$UNIQUE_ID,HOSTNAME=$HOSTNAME,STAGE=STOP,FUNC=${FUNCNAME[0]},METHOD=$clonezilla_method" >&2
}

DOWN_PRIVATE_IPS () {
echo "ID=$UNIQUE_ID,HOSTNAME=$HOSTNAME,STAGE=START,FUNC=${FUNCNAME[0]},METHOD=$clonezilla_method" >&2
if [[ $hostname = *"5g" ]] ;then
   ifconfig ehs0 down
   ifconfig ehs1 down
   ifconfig els1 down
fi
echo "ID=$UNIQUE_ID,HOSTNAME=$HOSTNAME,STAGE=STOP,FUNC=${FUNCNAME[0]},METHOD=$clonezilla_method" >&2
}

UP_PRIVATE_IPS () {
echo "ID=$UNIQUE_ID,HOSTNAME=$HOSTNAME,STAGE=START,FUNC=${FUNCNAME[0]},METHOD=$clonezilla_method" >&2
if [[ $hostname = *"5g" ]] ;then
   ifconfig ehs0 up
   ifconfig ehs1 up
   ifconfig els1 up
fi
echo "ID=$UNIQUE_ID,HOSTNAME=$HOSTNAME,STAGE=STOP,FUNC=${FUNCNAME[0]},METHOD=$clonezilla_method" >&2
}

COMBINE_NICS () {
echo "ID=$UNIQUE_ID,HOSTNAME=$HOSTNAME,STAGE=START,FUNC=${FUNCNAME[0]},METHOD=$clonezilla_method" >&2
if [[ $hostname = *"5g" ]] ;then
   /usr/bin/station_combine_nics
fi
echo "ID=$UNIQUE_ID,HOSTNAME=$HOSTNAME,STAGE=STOP,FUNC=${FUNCNAME[0]},METHOD=$clonezilla_method" >&2
}

MODIFY_NM_LINE () {
FILE="/etc/sysconfig/network-scripts/ifcfg-eno1"
if [[ $(gvquery -p os_dist) == "rhel8"* && -f "$FILE" ]]; then
	sed -i '/^NM_CONTROLLED/d' $FILE ;
	echo 'NM_CONTROLLED="yes"' >> $FILE
elif [[ $(gvquery -p os_dist) != "rhel8"* && -f "$FILE" ]]; then
	sed -i '/^NM_CONTROLLED/d' $FILE ;
	echo 'NM_CONTROLLED="no"' >> $FILE
fi
}

MODIFY_ICE_BRIDGE () {
FILE="/etc/sysconfig/network-scripts/ifcfg-eno1"
sed -i '/^TYPE/d' $FILE
sed -i '/^NAME/d' $FILE
sed -i '/^DELAY/d' $FILE
sed -i '/^STP/d' $FILE
if [[ -f /etc/sysconfig/network-scripts/ifcfg-eno1-nic ]]; then
	sed -i 's/device/DEVICE/' $FILE
	echo "TYPE=Bridge" >> $FILE
	echo "NAME=eno1" >> $FILE
	echo "DELAY=0" >> $FILE
	echo "STP=no" >> $FILE
fi
}

DOWN_PRIVATE_IPS
_REMOVE_STATION_CFG
#_FIX_JOURNAL
RESTART_LTE_CONFIG
_STOP_SERVICE
SHOULD_I_REBOOT
FIND_NETWORKING_INFO
_generate_password
_password_email
CHECK_REVERSE
CHECK_FORWARD
_UPDATE_DNS
_REDO_PROXIES
SET_TIME_ZONE
_FIX_TIME_NTP
SET_HOSTNAME
#RESTART_LTE_CONFIG
_REDO_THE_INTERFACES
RESET_HOSTID
_REDO_UCM_PROXIES
_add_gv_tier_duty
KILL_AUTOFS
DISABLE_CHRONYD_PRE_RHEL8
CHECK_FILE_AGE &
MAKE_CACHE
_restore_from_clonezilla
MODIFY_NM_LINE
MODIFY_ICE_BRIDGE
#CHECK_REVERSE
#CHECK_FORWARD
#FIX_UAAA_ISSUES
DO_THE_BUSINESS
DNS_GV_MESS
#UUIDGEN
CRON_RUN_BUT_NOT_GV
TRY_RUN_SETUPS
_FIX_PERMS_ON_STATION_CFG
FIX_PERMS
#PATCH_THE_BOX
#shutdown -h now
swapoff -a
RUN_DRACUT
#SEND_MDB_EMAIL
ADD_GNB_DUTY
_START_SERVICE
_FIX_HOST_FILE
_DELETE_LIST_FILES
FIX_HTTP_FILE
FIX_UAAA_WITH_START
WAIT_FOR_TBSADMIN
_restore_from_clonezilla_post_rejoin
#_INSTALL_BIOS_AUDIT
IPMI_FIX
UPDATE_STATION_CFG
UPDATE_CHASSIS
FIX_LOG_INSTALLER_LOG_FILE
COMBINE_NICS
UP_PRIVATE_IPS
DATA_APPS_VM_POSTINSTALL
ICE_VM_POSTINSTALL
FORCE_HOSTFILE_UPDATE
LOG_IMAGING_DURATION
SEND_THE_USER_AN_EMAIL
journalctl -u clonezilla >> /var/log/syslog
REMOVE_CLONEZILLA_SERVICE
echo "ID=$UNIQUE_ID,HOSTNAME=$HOSTNAME,STAGE=STOP,FUNC=POSTINSTALL,METHOD=$clonezilla_method" >&2
echo "ID=$UNIQUE_ID,HOSTNAME=$HOSTNAME,STAGE=STOP,FUNC=IMAGING,METHOD=$clonezilla_method" >&2
sleep 15
reboot
FINISHINSTALL
) > $CRONFILE

##############################################################################################################
## The script above does most of the work
##############################################################################################################

chmod ugo+rx $CRONFILE
chattr +i $CRONFILE
}

CREATE_RICKS_CRON () {
tbs_installer_updater=/$VARD/adm/gv/cron/boot.d/I13_tbs_installer_updater
(
cat <<'FINISHINSTALL_tbs_installer_updater'
#!/bin/bash

# Andrew Chandler
# Tue Feb 18 10:13:27 MST 2020
# Installed as part of CLONEZILLA SCRIPT
# https://review-tbs.qualcomm.com/#/c/102737/7/rpm/ext/clonezilla_restart.sh
PATH=/usr/sbin:/usr/bin:/bin:/usr/local/sbin:

duties=`gvquery -p duties`

if [[ $duties == *"5g"* ]]; then

sleep 90;
while [ $(getent passwd tbsadmin| wc -l) -lt 1 ]; do sleep 1; logger "Waiting for vas as part of tbs installer update"; done

logger "Running tbs_installer_updater"

if [[ -f "/opt/clonezilla_restart.sh" ]] ;then
   logger "Remove restart - tbs_installer_updater"
   rm -rf /opt/clonezilla_restart.sh
fi

if [[ -d "/opt/data/install/reboot" ]] ;then
   logger "Cd into directory - tbs_installer_updater"
   cd /opt/data/install/reboot
   logger "Running super - tbs_installer_updater"
   super tbsinstall --phases bundle,pre --meta_force
   super tbsinstall --phases manifest,post
fi

fi

if [[ -f "/var/adm/gv/cron/boot.d/I13_tbs_installer_updater" ]] ;then
   logger "I13_tbs_installer_updater cron removed."
   chattr -i /var/adm/gv/cron/boot.d/I13_tbs_installer_updater
fi

run_setups -f cron

FINISHINSTALL_tbs_installer_updater
) > $tbs_installer_updater

chmod ugo+rx $tbs_installer_updater
chattr +i $tbs_installer_updater
}

_clonezilla_service_create () {
clonezilla_service=/$SLASH/etc/systemd/system/clonezilla.service
(
cat <<'create_clonezilla_service_file'
[Unit]
Description="Clonezilla install"
Wants=clonezilla.timer
Requires=network.target
After=network.target

[Service]
Type=oneshot
ExecStart=/var/I11_CLONEZILLA
KillMode=process

[Install]
WantedBy=multi-user.target

create_clonezilla_service_file
) > $clonezilla_service

chmod ugo+rx $clonezilla_service
chattr +i $clonezilla_service
}


_clonezilla_timer_create () {
clonezilla_timer=/$SLASH/etc/systemd/system/clonezilla.timer
(
cat <<'create_clonezilla_timer_file'
[Unit]
Description=Logs some system statistics to the systemd journal
Requires=clonezilla.service

[Timer]
Unit=clonezilla.service
OnBootSec=30

[Install]
WantedBy=timers.target


create_clonezilla_timer_file
) > $clonezilla_timer

chmod ugo+rx $clonezilla_timer
chattr +i $clonezilla_timer
}

_copy_clonezilla_log() {
clonezilla_log=/root/var.d/log/clonezilla.d
if [ -d "$clonezilla_log" ]; then rm -Rf $clonezilla_log; fi
mkdir $clonezilla_log
cp -ar /var/log/* $clonezilla_log
}

_clonezilla_cron () {
clonezilla_service_cron=/$VARD/adm/gv/cron/boot.d/I10_call_clonezilla
(
cat <<'create_clonezilla_service_file'
#!/bin/bash

systemctl daemon-reload
systemctl enable clonezilla.service
systemctl start clonezilla.service

create_clonezilla_service_file
) > $clonezilla_service_cron

chmod ugo+rx $clonezilla_service_cron
chattr +i $clonezilla_service_cron
}



#MAKE_VG_ACTIVE

#DOWN_PRIVATE_IPS
MOUNT_THE_DISK
IDENTIFY_OS
SET_HOSTNAME
REMOVE_REJOIN_CRON
CLEAN_UP_NETWORK
FIX_INTERFACES_CENTOS6
FIX_INTERFACES_CENTOS7
REMOVE_CHEF
REMOVE_SSH_KEYS
REMOVE_DHCP_LEASES
REMOVE_STATION_CONFIG
REMOVE_SYSCON_PATTERN
BLANK_OUT_LOGS
REMOVE_PERSISTENT_RULES
TOUCH_REBOOTFILE
CREATE_CELL_EXT
FIX_POSTFIX
CLONEZILLA_DATE
SETUPSITE
CP_DELETE_LIST
_SETUP_NOTIFY_LIST
_SETUP_CLONEZILLA
_CLEAN_OUT_UCM_PROXY
CLEAN_PROXIES
SETUPUSER
SETUPLOCATION
CREATE_UDEV_RULE
UBUNTU_NETWORK
CLEAN_HOSTFILE
CLEAN_UP_GV_HOSTNAME
SETUP_MOTD
CLEAN_UP_ROOT_ACCOUNT
#CREATE_IPMI_CRONFILE
CREATE_CRONFILE
#CREATE_RICKS_CRON
CREATE_CRONFILE_PROXY_FIX
#DATA_APPS_VM_POSTINSTALL
_clonezilla_service_create
_clonezilla_timer_create
_clonezilla_cron
_copy_clonezilla_log
#UP_PRIVATE_IPS
COPY_TMP_FILE
