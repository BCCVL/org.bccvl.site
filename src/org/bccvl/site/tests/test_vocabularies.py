import unittest2 as unittest
from zope.schema.interfaces import IVocabularyFactory, IVocabulary
from org.bccvl.site.vocabularies import (
    species_presence_datasets_vocab,
    species_absence_datasets_vocab,
    species_abundance_datasets_vocab,
    environmental_datasets_vocab,
    future_climate_datasets_vocab,
    sdm_functions_source,
    traits_functions_source,
    envirolayer_source)
from org.bccvl.site.testing import BCCVL_INTEGRATION_TESTING
from plone.uuid.interfaces import IUUID
from org.bccvl.site import defaults
from zope.component import getUtility
from org.bccvl.site.namespace import BIOCLIM


class PresenceSourceTest(unittest.TestCase):

    layer = BCCVL_INTEGRATION_TESTING

    def _get_class(self):
        return species_presence_datasets_vocab

    def _make_one(self):
        return self._get_class()(self.layer['portal'])

    def test_interfaces(self):
        self.assertTrue(IVocabularyFactory.providedBy(self._get_class()))
        self.assertTrue(IVocabulary.providedBy(self._make_one()))

    def test_elements(self):
        source = self._make_one()
        ds = self.layer['portal'][defaults.DATASETS_FOLDER_ID]
        spec = ds[defaults.DATASETS_SPECIES_FOLDER_ID]['ABT']['occurrence.csv']
        spec_occ_uuid = IUUID(spec)
        self.assertIn(spec_occ_uuid, source)
        self.assertEqual(len(source), 1)


class AbsenceSourceTest(unittest.TestCase):

    layer = BCCVL_INTEGRATION_TESTING

    def _get_class(self):
        return species_absence_datasets_vocab

    def _make_one(self):
        return self._get_class()(self.layer['portal'])

    def test_interfaces(self):
        self.assertTrue(IVocabularyFactory.providedBy(self._get_class()))
        self.assertTrue(IVocabulary.providedBy(self._make_one()))

    def test_elements(self):
        source = self._make_one()
        ds = self.layer['portal'][defaults.DATASETS_FOLDER_ID]
        spec = ds[defaults.DATASETS_SPECIES_FOLDER_ID]['ABT']['absence.csv']
        spec_abs_uuid = IUUID(spec)
        self.assertIn(spec_abs_uuid, source)
        self.assertEqual(len(source), 1)


class AbundanceSourceTest(unittest.TestCase):

    layer = BCCVL_INTEGRATION_TESTING

    def _get_class(self):
        return species_abundance_datasets_vocab

    def _make_one(self):
        return self._get_class()(self.layer['portal'])

    def test_interfaces(self):
        self.assertTrue(IVocabularyFactory.providedBy(self._get_class()))
        self.assertTrue(IVocabulary.providedBy(self._make_one()))

    def test_elements(self):
        source = self._make_one()
        # TODO: need test data for this one
        self.assertEqual(len(source), 0)


class EnvironmentalSourceTest(unittest.TestCase):

    layer = BCCVL_INTEGRATION_TESTING

    def _get_class(self):
        return environmental_datasets_vocab

    def _make_one(self):
        return self._get_class()(self.layer['portal'])

    def test_interfaces(self):
        self.assertTrue(IVocabularyFactory.providedBy(self._get_class()))
        self.assertTrue(IVocabulary.providedBy(self._make_one()))

    def test_elements(self):
        source = self._make_one()
        ds = self.layer['portal'][defaults.DATASETS_FOLDER_ID]
        data = ds[defaults.DATASETS_ENVIRONMENTAL_FOLDER_ID]['current']
        data_uuid = IUUID(data)
        self.assertIn(data_uuid, source)
        self.assertEqual(len(source), 2)


class FutureSourceTest(unittest.TestCase):

    layer = BCCVL_INTEGRATION_TESTING

    def _get_class(self):
        return future_climate_datasets_vocab

    def _make_one(self):
        return self._get_class()(self.layer['portal'])

    def test_interfaces(self):
        self.assertTrue(IVocabularyFactory.providedBy(self._get_class()))
        self.assertTrue(IVocabulary.providedBy(self._make_one()))

    def test_elements(self):
        source = self._make_one()
        ds = self.layer['portal'][defaults.DATASETS_FOLDER_ID]
        data = ds[defaults.DATASETS_CLIMATE_FOLDER_ID]['future']
        data_uuid = IUUID(data)
        self.assertIn(data_uuid, source)
        self.assertEqual(len(source), 2)


class SdmFunctionsSourceTest(unittest.TestCase):

    layer = BCCVL_INTEGRATION_TESTING

    def _get_class(self):
        return sdm_functions_source

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
        # TODO: this test depends on whatever is setup in org.bccvl.compute:content
        self.assertEqual(len(source), 12)


class TraitsFunctionsSourceTest(unittest.TestCase):

    layer = BCCVL_INTEGRATION_TESTING

    def _get_class(self):
        return traits_functions_source

    def _make_one(self):
        return self._get_class()(self.layer['portal'])

    def test_interfaces(self):
        self.assertTrue(IVocabularyFactory.providedBy(self._get_class()))
        self.assertTrue(IVocabulary.providedBy(self._make_one()))

    def test_elements(self):
        source = self._make_one()
        ds = self.layer['portal'][defaults.TOOLKITS_FOLDER_ID]
        data = ds['lm']
        data_uuid = IUUID(data)
        self.assertIn(data_uuid, source)
        # TODO: this test depends on whatever is setup in org.bccvl.compute:content
        self.assertEqual(len(source), 1)


class EnviroLayerSourceTest(unittest.TestCase):

    layer = BCCVL_INTEGRATION_TESTING

    def _get_class(self):
        return envirolayer_source

    def _make_one(self, context):
        return self._get_class()(context)

    def test_interfaces(self):
        self.assertTrue(IVocabularyFactory.providedBy(self._get_class()))
        self.assertTrue(IVocabulary.providedBy(self._make_one(self.layer['portal'])))

    def test_registration(self):
        one = self._get_class()
        tool = getUtility(IVocabularyFactory, name='envirolayer_source')
        self.assertIs(one, tool)

    def test_elements(self):
        ds = self.layer['portal'][defaults.DATASETS_FOLDER_ID]
        data = ds[defaults.DATASETS_ENVIRONMENTAL_FOLDER_ID]['current']
        source = self._make_one(data)
        self.assertIn(BIOCLIM['B01'], source)
        # FIXME: add tests with layers for data in source
