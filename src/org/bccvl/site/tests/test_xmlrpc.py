import unittest2 as unittest
from zope.component import getMultiAdapter
from plone.app.testing import TEST_USER_ID, setRoles
from org.bccvl.site import defaults
from org.bccvl.site.testing import BCCVL_INTEGRATION_TESTING
from org.bccvl.site.content.interfaces import IDataset
from org.bccvl.site.interfaces import IDownloadInfo


class DatasetManagerTest(unittest.TestCase):
# DataSetManager():/dm/...
#    on site root
#     metadata, getMetadata
#     getRAT
#     query
#     queryDataset
#     getFutureClimateDatasets
#     getSDMDatasets
#     getBiodiverseDatasets
#     getProjectionDatasets
#     getVocabulary
#     getThresholds

    layer = BCCVL_INTEGRATION_TESTING

    def test_dummy(self):
        pass


class DatasetAPITest(unittest.TestCase):
# DataSetAPI():/dm/...
#  on dataset
#    getMetadata
#    share
#    unshare

    layer = BCCVL_INTEGRATION_TESTING


class JobManagerAPITest(unittest.TestCase):
# JobManagerAPI():/jm/...
#  on experiment and dataset
#    getJobStatus
#    getJobStates

    layer = BCCVL_INTEGRATION_TESTING


class ALAProxyTest(unittest.TestCase):
# ALAProxy():/ala/...
#  anywhere
#   autojson
#   searchjson

    layer = BCCVL_INTEGRATION_TESTING


class DataMoverTest(unittest.TestCase):
# DataMover():/dv/...
#  on folder
#    pullOccurrenceFromALA
#    checkALAJobStatus

    layer = BCCVL_INTEGRATION_TESTING

    # needs a running DataMover ... probably have to mock it?
