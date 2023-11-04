#!/bin/bash

# Andrew Chandler
# https://jira-scrum.qualcomm.com/jira/browse/TBSSERVER-1301
# Fri Feb 21 14:11:05 MST 2020

PATH=/usr/local/bin:/usr/local/sbin:/bin:/sbin:/usr/bin:/usr/sbin

UUID_PREFIX="UUID="

if [[ -d "/root/slash.d/" ]]; then
   fstab_location=/root/slash.d/etc/fstab
else
   fstab_location=/etc/fstab
fi

UUID_of_current_device=$UUID_PREFIX$(blkid -s UUID -o value /dev/sda2)
previous_fstab_UUID=`awk '/clone/ {print $1}' $fstab_location`

if [[ "$UUID_of_current_device" = "$previous_fstab_UUID" ]];then
   echo "No change"
else
   sed -i 's/^'"$previous_fstab_UUID".*'/'"$UUID_of_current_device"' \/clonezilla      ext3    defaults        1 2/' $fstab_location
fi
