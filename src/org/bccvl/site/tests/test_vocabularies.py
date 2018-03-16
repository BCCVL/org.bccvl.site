import unittest
from zope.schema.interfaces import IVocabularyFactory, IVocabulary
from org.bccvl.site.testing import BCCVL_INTEGRATION_TESTING
from plone.uuid.interfaces import IUUID
from org.bccvl.site import defaults
from zope.component import getUtility


class LayerSourceTest(unittest.TestCase):

    layer = BCCVL_INTEGRATION_TESTING

    def _get_class(self):
        return getUtility(IVocabularyFactory, name='layer_source')

    def _make_one(self):
        return self._get_class()(self.layer['portal'])

    def test_interfaces(self):
        self.assertTrue(IVocabularyFactory.providedBy(self._get_class()))
        self.assertTrue(IVocabulary.providedBy(self._make_one()))

    def test_elements(self):
        source = self._make_one()
        self.assertIn(u'B01', source)
        term = source.getTerm(u'B01')
        self.assertEqual(term.value, u'B01')
        self.assertEqual(len(source), 446)


class GCMSourceTest(unittest.TestCase):

    layer = BCCVL_INTEGRATION_TESTING

    def _get_class(self):
        return getUtility(IVocabularyFactory, name='gcm_source')

    def _make_one(self):
        return self._get_class()(self.layer['portal'])

    def test_interfaces(self):
        self.assertTrue(IVocabularyFactory.providedBy(self._get_class()))
        self.assertTrue(IVocabulary.providedBy(self._make_one()))

    def test_elements(self):
        source = self._make_one()
        self.assertIn(u'cccma-cgcm31', source)
        term = source.getTerm(u'cccma-cgcm31')
        self.assertEqual(term.value, u'cccma-cgcm31')
        self.assertEqual(len(source), 38)


class EMSCSourceTest(unittest.TestCase):

    layer = BCCVL_INTEGRATION_TESTING

    def _get_class(self):
        return getUtility(IVocabularyFactory, name='emsc_source')

    def _make_one(self):
        return self._get_class()(self.layer['portal'])

    def test_interfaces(self):
        self.assertTrue(IVocabularyFactory.providedBy(self._get_class()))
        self.assertTrue(IVocabulary.providedBy(self._make_one()))

    def test_elements(self):
        source = self._make_one()
        self.assertIn(u'RCP3PD', source)
        term = source.getTerm(u'RCP3PD')
        self.assertEqual(term.value, u'RCP3PD')
        self.assertEqual(len(source), 9)


class ResolutionSourceTest(unittest.TestCase):

    layer = BCCVL_INTEGRATION_TESTING

    def _get_class(self):
        return getUtility(IVocabularyFactory, name='resolution_source')

    def _make_one(self):
        return self._get_class()(self.layer['portal'])

    def test_interfaces(self):
        self.assertTrue(IVocabularyFactory.providedBy(self._get_class()))
        self.assertTrue(IVocabulary.providedBy(self._make_one()))

    def test_elements(self):
        source = self._make_one()
        self.assertIn(u'Resolution30s', source)
        term = source.getTerm(u'Resolution30s')
        self.assertEqual(term.value, u'Resolution30s')
        self.assertEqual(len(source), 13)


class CRSSourceTest(unittest.TestCase):

    layer = BCCVL_INTEGRATION_TESTING

    def _get_class(self):
        return getUtility(IVocabularyFactory, name='crs_source')

    def _make_one(self):
        return self._get_class()(self.layer['portal'])

    def test_interfaces(self):
        self.assertTrue(IVocabularyFactory.providedBy(self._get_class()))
        self.assertTrue(IVocabulary.providedBy(self._make_one()))

    def test_elements(self):
        source = self._make_one()
        self.assertIn(u'epsg:4326', source)
        term = source.getTerm(u'epsg:4326')
        self.assertEqual(term.value, u'epsg:4326')
        self.assertEqual(len(source), 5)


class DatatypeSourceTest(unittest.TestCase):

    layer = BCCVL_INTEGRATION_TESTING

    def _get_class(self):
        return getUtility(IVocabularyFactory, name='datatype_source')

    def _make_one(self):
        return self._get_class()(self.layer['portal'])

    def test_interfaces(self):
        self.assertTrue(IVocabularyFactory.providedBy(self._get_class()))
        self.assertTrue(IVocabulary.providedBy(self._make_one()))

    def test_elements(self):
        source = self._make_one()
        self.assertIn(u'continuous', source)
        term = source.getTerm(u'continuous')
        self.assertEqual(term.value, u'continuous')
        self.assertEqual(len(source), 2)


class SdmFunctionsSourceTest(unittest.TestCase):

    layer = BCCVL_INTEGRATION_TESTING

    def _get_class(self):
        return getUtility(IVocabularyFactory, name='sdm_functions_source')

    def _make_one(self):
        return self._get_class()(self.layer['portal'])

    def test_interfaces(self):
        self.assertTrue(IVocabularyFactory.providedBy(self._get_class()))
        self.assertTrue(IVocabulary.providedBy(self._make_one()))

    def test_elements(self):
        source = self._make_one()
        ds = self.layer['portal'][defaults.TOOLKITS_FOLDER_ID]
        data = ds['bioclim']
        data_uuid = IUUID(data)
        self.assertIn(data_uuid, source)
        # TODO: this test depends on whatever is setup in
        # org.bccvl.compute:content
        self.assertEqual(len(source), 17)


class TraitsFunctionsSpeciesSourceTest(unittest.TestCase):

    layer = BCCVL_INTEGRATION_TESTING

    def _get_class(self):
        return getUtility(IVocabularyFactory, name='traits_functions_species_source')

    def _make_one(self):
        return self._get_class()(self.layer['portal'])

    def test_interfaces(self):
        self.assertTrue(IVocabularyFactory.providedBy(self._get_class()))
        self.assertTrue(IVocabulary.providedBy(self._make_one()))

    def test_elements(self):
        source = self._make_one()
        ds = self.layer['portal'][defaults.TOOLKITS_FOLDER_ID]
        data = ds['speciestrait_glm']
        data_uuid = IUUID(data)
        self.assertIn(data_uuid, source)
        # TODO: this test depends on whatever is setup in
        # org.bccvl.compute:content
        self.assertEqual(len(source), 4)


class TraitsFunctionsDiffSourceTest(unittest.TestCase):

    layer = BCCVL_INTEGRATION_TESTING

    def _get_class(self):
        return getUtility(IVocabularyFactory, name='traits_functions_diff_source')

    def _make_one(self):
        return self._get_class()(self.layer['portal'])

    def test_interfaces(self):
        self.assertTrue(IVocabularyFactory.providedBy(self._get_class()))
        self.assertTrue(IVocabulary.providedBy(self._make_one()))

    def test_elements(self):
        source = self._make_one()
        ds = self.layer['portal'][defaults.TOOLKITS_FOLDER_ID]
        data = ds['traitdiff_glm']
        data_uuid = IUUID(data)
        self.assertIn(data_uuid, source)
        # TODO: this test depends on whatever is setup in
        # org.bccvl.compute:content
        self.assertEqual(len(source), 1)


class GenreSourceTest(unittest.TestCase):

    layer = BCCVL_INTEGRATION_TESTING

    def _get_class(self):
        return getUtility(IVocabularyFactory, name='genre_source')

    def _make_one(self):
        return self._get_class()(self.layer['portal'])

    def test_interfaces(self):
        self.assertTrue(IVocabularyFactory.providedBy(self._get_class()))
        self.assertTrue(IVocabulary.providedBy(self._make_one()))

    def test_elements(self):
        source = self._make_one()
        self.assertIn(u'DataGenreE', source)
        term = source.getTerm(u'DataGenreE')
        self.assertEqual(term.value, u'DataGenreE')
        self.assertEqual(len(source), 40)
