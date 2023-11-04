# TBS clonezilla

# New 
With the exception of the images containing TBS images all of the scripts needed are in a 
git repo rather than having a dependency on /prj.

This change makes testing easier because everything is now in one place.

# Jenkins intergration

1 - Follow documentation here https://plugins.jenkins.io/github/
2 - Addtitional documentation can be found here - 
    https://gcube.wiki.gcube-system.org/gcube/GitHub/Jenkins:_Setting_up_Webhooks

Qualcomm github api location is here https://github.qualcomm.com/api/v3


# Clonezilla documentation from docs strings
Documentation for this can be found under

../docs.d/_build/html/index.html

and viewed with a webbrowser. 

The location at the moment might not be perfect 
but I wanted to try and see how sphinx worked.

Notes.
From doc.d
sphinx-apidoc -o . ../code.d/
make html
