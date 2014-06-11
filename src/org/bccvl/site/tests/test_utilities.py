import unittest2 as unittest
from gu.z3cform.rdf.interfaces import IRDFTypeMapper, IORDF
from gu.plone.rdf.interfaces import IRDFContentTransform
from zope.interface.verify import verifyClass
from zope.interface.verify import verifyObject
from zope.component import getUtility, getGlobalSiteManager
from plone.app.z3cform.interfaces import IPloneFormLayer
from z3c.form.interfaces import IAddForm
from org.bccvl.site.utilities import RDFDataMapper, RDFTypeMapper
from org.bccvl.site.testing import BCCVL_INTEGRATION_TESTING
from zope.interface import Interface


# TODO: test this one in gu.plone.rdf
from gu.plone.rdf.component import ORDFUtility
# TODO: add tests for Subform lookup


class RDFTypeMapperTest(unittest.TestCase):

    def _getTargetClass(self):
        return RDFTypeMapper

    def _makeOne(self, *args, **kw):
        return self._getTargetClass()(None, None, None)

    def test_class_conforms_to_IRDFTypeMapper(self):
        verifyClass(IRDFTypeMapper, self._getTargetClass())

    def test_instance_conforms_to_IRDFTypeMapper(self):
        verifyObject(IRDFTypeMapper, self._makeOne())


class RDFDataMapperTest(unittest.TestCase):

    def _getTargetClass(self):
        return RDFDataMapper

    def _makeOne(self, *args, **kw):
        return self._getTargetClass()()

    def test_class_conforms_to_IRDFDataMapper(self):
        verifyClass(IRDFContentTransform, self._getTargetClass())

    def test_instance_conforms_to_IRDFDataMapper(self):
        verifyObject(IRDFContentTransform, self._makeOne())


class ComponentLookupTest(unittest.TestCase):

    layer = BCCVL_INTEGRATION_TESTING

    # TODO: test this one in gu.plone.rdf
    def test_iordf(self):
        tool = getUtility(IORDF)
        self.assertTrue(isinstance(tool, ORDFUtility))

    def test_typemapper(self):
        gar = getGlobalSiteManager().adapters
        tm = gar.registered((Interface,
                             IPloneFormLayer,
                             IAddForm), IRDFTypeMapper)
        self.assertIs(tm, RDFTypeMapper)
