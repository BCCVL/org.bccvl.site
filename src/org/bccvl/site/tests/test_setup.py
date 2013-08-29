import unittest2 as unittest
from org.bccvl.site import defaults
from org.bccvl.site.testing import BCCVL_INTEGRATION_TESTING


class SiteSetupTest(unittest.TestCase):

    layer = BCCVL_INTEGRATION_TESTING

    def test_site_structure(self):
        portal = self.layer['portal']

        self.assertTrue(defaults.DATASETS_FOLDER_ID in portal)
        dsf =  portal[defaults.DATASETS_FOLDER_ID]
        self.assertTrue(defaults.DATASETS_SPECIES_FOLDER_ID in dsf)
        self.assertTrue(defaults.DATASETS_ENVIRONMENTAL_FOLDER_ID in dsf)
        self.assertTrue(defaults.DATASETS_CLIMATE_FOLDER_ID in dsf)

        self.assertTrue(defaults.FUNCTIONS_FOLDER_ID in portal)
        self.assertTrue(defaults.KNOWLEDGEBASE_FOLDER_ID in portal)
