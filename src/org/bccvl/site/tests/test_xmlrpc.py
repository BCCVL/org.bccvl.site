import unittest
from org.bccvl.site.testing import BCCVL_INTEGRATION_TESTING


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
