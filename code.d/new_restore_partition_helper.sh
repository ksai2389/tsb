#!/bin/bash

# Andrew Chandler
# Thu Feb  6 16:25:31 MST 2020
# Only to be used when restoring partitions.

source_token(){
STORAGE_DIR=/tmp
cd $STORAGE_DIR
# There should only be 1 file in the directory that looks like
# a MAC file.
for i in `ls`; do
if [[ "$i" =~ ^([a-fA-F0-9]{2}-){5}[a-fA-F0-9]{2}$ ]] ; then
   TBS_TOKEN=$i
   break
fi
done

source $TBS_TOKEN
}

get_blkid_for_image(){
blkid_for_image=`awk -F= '/id/ {print $2}' /home/partimag/$IMAGE/lvm_vg00.conf | head -n1| sed 's/"//g'| sed s'/ //g'`
}

get_local_blkid(){
local_blkid=`blkid /dev/sda3| awk '{print $2}'| sed 's/UUID=//g'|sed 's/"//g'| sed s'/ //g'`
}

delete_sda_partition(){
echo -e "\nd\n3\nw" | fdisk /dev/sda
}

create_sda3_partition(){
echo -e "\nn\np\n3\n\n\nt\n3\n8e\nw" | fdisk /dev/sda 
}

create_pv_sda3(){
pvcreate -ff -y --norestorefile --uuid $blkid_for_image /dev/sda3
}

clean_mounts(){
if [[ $blkid_for_image != $local_blkid ]];then
   for i in `/usr/sbin/dmsetup ls| awk '{print $1}'`;do
	umount /dev/mapper/$i
	/usr/sbin/dmsetup remove /dev/mapper/$i
   done
delete_sda_partition
create_sda3_partition
create_pv_sda3
fi
}

source_token
get_blkid_for_image
get_local_blkid
clean_mounts
