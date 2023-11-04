#!/bin/bash

# Andrew Chandler achandler@qualcomm.com
# Tue Feb 26 16:26:35 MST 2019

# Destroy the partition table before reimaging with clonezilla
# This should only run on machines with disk_wipe selected from 
# clonezilla. If it runs on a machine wishing to preserve data 
# ALL data will be lost

# Only works on SATA disks at the moment. If NVME etc comes online 
# this will need to be looked at.

PATH=/usr/local/bin:/usr/local/sbin:/bin:/sbin:/usr/bin:/usr/sbin

for disk in `lsblk -o Name| grep -o 'sd[a-z]1'| sed s'/[0-9]//g'`; do
   dd if=/dev/zero of=/dev/$disk bs=512 count=1
done
