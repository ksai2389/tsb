#!/bin/bash

unset $HOSTNAME

echo $HOSTNAME

if [[ $wipe_disk = "true" ]]; then
   ENTIRE=""
else
   ENTIRE="-w False"
fi

if [[ ! -z "$NOTIFICATION_LIST" ]]; then
   NOTIFICATIONS="-N $NOTIFICATION_LIST"
fi


if [[ ! -z "$SITE" ]]; then
   SITE_LOCATION="-s $SITE"
fi

if [[ ! -z "$LOCATION" ]]; then
   LAB_LOCATION="-l $LOCATION"
fi

if [[ ! -z "$OWNER" ]]; then
   OWNER_INFORMATION="-o $OWNER"
else
   OWNER_INFORMATION="-o Dhogan"
fi

set -xe
env

LAB_LOCATION=`echo "$LAB_LOCATION" | sed 's/[[:space:]]//g'`
echo $LAB_LOCATION

if [[ "$GIT_BRANCH" == *:* ]]; then
   IFS=':' read -r GIT_PRJ GIT_BRANCH <<< "$GIT_BRANCH"
   echo $GIT_BRANCH
   git_string="-g $GIT_PRJ:$GIT_BRANCH"
   echo $git_string
else
   GIT_PRJ="tbs/clonezilla-img-mgmt"
fi
git clone https://github.qualcomm.com/$GIT_PRJ clonezilla-img-mgmt_v2.0

cd clonezilla-img-mgmt_v2.0/code.d
git checkout $GIT_BRANCH

python3.6 restore_system.py -u $CIAW_UN -p $CIAW_PW -H $HOSTNAME -r $HOSTNAME_CHECK $ENTIRE \
-i $IMAGE -j $BUILD_URL $OWNER_INFORMATION $NOTIFICATIONS $SITE_LOCATION $LAB_LOCATION $git_string

echo $HOSTNAME

echo "ID=$UNIQUE_ID,HOSTNAME=$HOSTNAME,STAGE=START,FUNC=IMAGING,METHOD=$BUILD_CAUSE" >&2


echo "ID=$UNIQUE_ID,HOSTNAME=$HOSTNAME,STAGE=START,FUNC=IMAGING,METHOD=$BUILD_CAUSE" | logger

