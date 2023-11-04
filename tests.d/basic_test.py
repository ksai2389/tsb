import os
import sys
import pytest

sys.path.append(os.path.join(os.path.dirname(os.getcwd()), "code.d"))

import restore_system

def department_from_uid(username):
    ph_record_output = restore_system.build_ph_data(username)
    ph_dictionary = restore_system.create_ph_dictionary(ph_record_output)
    department = restore_system.get_department_number(ph_dictionary)
    return department

def test_mytest():
    """Rich was haviing issues with the following names because of the
    inconsistent naming of department key."""
    uid_dep_dict = {"andcha": "55044",
                    "snv": "20601",
                    "richardf": "55053",
                    "bhavanig": "12026",
                    "swatis": "20603",
                    "jacobc": "02075"}

    for uid, dep_number in uid_dep_dict.items():
        assert department_from_uid(uid) == dep_number

def test_is_up():
    with pytest.raises(SystemExit):
        restore_system.is_ipmi_up("some-tbs_that_doesnt-exist")

def test_git_branch():
    assert restore_system.get_branch_project("andcha/clonezilla-img-mgmt:TBSCSSW-7105") == \
           "git clone https://github.qualcomm.com/andcha/clonezilla-img-mgmt " \
           "clonezilla-img-mgmt_v2.0 && cd clonezilla-img-mgmt_v2.0/code.d; git checkout TBSCSSW-7105"
