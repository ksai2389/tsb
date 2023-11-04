#!/bin/bash

# Andrew Chandler
# Wed Dec  2 10:58:43 MST 2020
# Update - TBSCSSW-6753

PATH=/usr/local/bin:/usr/local/sbin:/bin:/sbin:/usr/bin:/usr/sbin

ARTIFACTORY_SERVER=qct-artifactory
STORAGE_DIR=/tmp
CREDENTIAL_FILE=credentials.txt
ARTIFACTORY_REPO=clonezillacredentials

find_mac_file () {
cd $STORAGE_DIR
# There should only be 1 file in the directory that looks like
# a MAC file. 
for i in `ls`; do
if [[ "$i" =~ ^([a-fA-F0-9]{2}-){5}[a-fA-F0-9]{2}$ ]] ; then
   TBS_TOKEN=$i
   break
fi
done
}

pull_credentials_from_artifactory() {
source $TBS_TOKEN
# Try to pull the credential file from the $ARTIFACTORY_SERVER using the short expiration $KEY 
echo -e "Getting the Credential file.\n\n\n\n\n\n"
wget --no-check-certificate --waitretry=0 --timeout=600 --tries=10 --retry-connrefused --user=tbsciaw --password=$KEY -P $STORAGE_DIR/ "https://$ARTIFACTORY_SERVER.qualcomm.com/artifactory/$ARTIFACTORY_REPO/$CREDENTIAL_FILE" -P /tmp

# If the token is not there print a message.
RC=$?
if [[ $RC -ne 0 ]];then
   printf "\n\n\n\n\n\n"
   echo "TOKEN is bad or $ARTIFACTORY_SERVER is down."
   printf "\n\n\n\n\n\n"
   sleep 86400
   exit
fi
}

delete_mac_files () {
curl -X DELETE $UCM_PROXY/univac/api/mac_file/$TBS_TOKEN
curl -X DELETE $UCM_PROXY/univac/api/mac_file/$MAC_ADDRESS
}

find_mac_file

#printf "\n\n\n$TBS_TOKEN\n\n\n"
#echo $TBS_TOKEN
#source $TBS_TOKEN
#printf "\n\n\n\n\n\n"
#echo $KEY
#printf "\n\n\n\n\n\n"

pull_credentials_from_artifactory
delete_mac_files
