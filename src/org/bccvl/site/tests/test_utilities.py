import unittest2 as unittest
from zope.interface.verify import verifyClass
from zope.interface.verify import verifyObject
from zope.component import getUtility, getGlobalSiteManager
from plone.app.z3cform.interfaces import IPloneFormLayer
from z3c.form.interfaces import IAddForm
from org.bccvl.site.testing import BCCVL_INTEGRATION_TESTING
from zope.interface import Interface


class ComponentLookupTest(unittest.TestCase):

    layer = BCCVL_INTEGRATION_TESTING

    # TODO: test this one in gu.plone.rdf
    def test_dummy(self):
        # FIXME add some tests here
        #        test get Utility and test interface conformance
        pass


# DatasetDownloadInfo
# RemoteDatasetDownloadIngo
# CatalogBrainDownloadInfo
# JobTracker
# MultiJobTracker
# SDMJobTracker
# ProjectionJobTracker
# BiodiverseJobTracker
# EnsembleJobTracker
# SpeciesTraitsJobTracker
# ALAJobTracker
