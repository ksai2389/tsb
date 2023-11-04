import unittest
import restore_system

class TestCase(unittest.TestCase):
    def tests(self):
        """Does a random site become Sandiego? Catch all for missing filers."""
        self.assertEqual(restore_system.determine_correct_filer
                          ("sandiego", "1"), ('sundae', True))
        self.assertEqual(restore_system.determine_correct_filer
                          ("boulder", "1"), ('titanic', True))
        self.assertEqual(restore_system.determine_correct_filer
                          ("hyderabad", "1"), ('cube', True))
        self.assertEqual(restore_system.determine_correct_filer
                         ("HyDerAbad", "1"), ('cube', True))
        self.assertEqual(restore_system.determine_correct_filer
                          ("some random site", "1"), ('sundae', False))


        self.assertEqual(restore_system.get_mac_via_ipmi_from
                         ("qct-8022-enbu-0", "ADMIN", "ADMIN"),
                         "0C-C4-7A-6D-24-D4")

        self.assertEqual(restore_system.try_and_identify_hardware
                         ("qct-8022-enbu-0"), ('0C-C4-7A-6D-24-D4', False))

        self.assertEqual(restore_system.get_parameter_from_mdb("andcha1-lnx", "office_location"),
                         ("BLDR.E-124I"))
        self.assertEqual(restore_system.get_parameter_from_mdb("plunger-lnx", "office_location"),
                         ("BLDR.E-108G"))

        #Check duplicate emails
        self.assertEqual(restore_system.notifcation_string("morduno"),
                         ("andcha,morduno,dyepez,esunarto,jacobc,richardf,srjana,asaini"))
        self.assertEqual(restore_system.notifcation_string("morduno2"),
                         ("andcha,morduno,dyepez,esunarto,jacobc,richardf,srjana,asaini,morduno2"))
        self.assertEqual(restore_system.notifcation_string("morduno2,bbuhlig"),
                         ("andcha,morduno,dyepez,esunarto,jacobc,richardf,srjana,asaini,morduno2,bbuhlig"))
        self.assertEqual(restore_system.notifcation_string("morduno2,bbuhlig,,,,,,,,,,,,,,,,,,,,,"),
                         ("andcha,morduno,dyepez,esunarto,jacobc,richardf,srjana,asaini,morduno2,bbuhlig"))

        # Need to look at the contains options.
        self.assertEqual(restore_system.get_ucm_proxy_from_mdb('boulder'),
                         ("wbuimg02.qualcomm.com"))

        self.assertEqual(restore_system.get_ucm_proxy_from_mdb('sandiego'),
                         ("wbuimg02.qualcomm.com"))


        # This is all an experiment in unit testing... needs work.
        '''
        self.assertEqual(restore_system.build_mac_file("1594663558", "dsf", "titanic",
                                                       "boulder", "dsfsdf", "dfgdg", "",
                                                       "mac","someprco", "qct-8022-enbu-0", "v10",
                                                       "email", "andcga","sine smb",
                                                       "True", "True","dsfsd"), (('# purge after: 1594663558\ndefault Clon[1619 chars]nfs')) )'''




if __name__ == '__main__':
    unittest.main()