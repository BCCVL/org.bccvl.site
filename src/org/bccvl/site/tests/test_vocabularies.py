import unittest2 as unittest
from zope.schema.interfaces import IContextSourceBinder, ISource
from org.bccvl.site.vocabularies import (
    species_presence_datasets_source,
    species_absence_datasets_source,
    species_abundance_datasets_source,
    environmental_datasets_source,
    future_climate_datasets_source,
    functions_source)
from org.bccvl.site.testing import BCCVL_INTEGRATION_TESTING
from plone.uuid.interfaces import IUUID
from org.bccvl.site import defaults


class PresenceSourceTest(unittest.TestCase):

    layer = BCCVL_INTEGRATION_TESTING

    def _get_class(self):
        return species_presence_datasets_source

    def _make_one(self):
        return self._get_class()(self.layer['portal'])

    def test_interfaces(self):
        self.assertTrue(IContextSourceBinder.providedBy(self._get_class()))
        self.assertTrue(ISource.providedBy(self._make_one()))

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
        return species_absence_datasets_source

    def _make_one(self):
        return self._get_class()(self.layer['portal'])

    def test_interfaces(self):
        self.assertTrue(IContextSourceBinder.providedBy(self._get_class()))
        self.assertTrue(ISource.providedBy(self._make_one()))

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
        return species_abundance_datasets_source

    def _make_one(self):
        return self._get_class()(self.layer['portal'])

    def test_interfaces(self):
        self.assertTrue(IContextSourceBinder.providedBy(self._get_class()))
        self.assertTrue(ISource.providedBy(self._make_one()))

    def test_elements(self):
        source = self._make_one()
        # TODO: need test data for this one
        self.assertEqual(len(source), 0)


class EnvironmentalSourceTest(unittest.TestCase):

    layer = BCCVL_INTEGRATION_TESTING

    def _get_class(self):
        return environmental_datasets_source

    def _make_one(self):
        return self._get_class()(self.layer['portal'])

    def test_interfaces(self):
        self.assertTrue(IContextSourceBinder.providedBy(self._get_class()))
        self.assertTrue(ISource.providedBy(self._make_one()))

    def test_elements(self):
        source = self._make_one()
        ds = self.layer['portal'][defaults.DATASETS_FOLDER_ID]
        data = ds[defaults.DATASETS_ENVIRONMENTAL_FOLDER_ID]['current']
        data_uuid = IUUID(data)
        self.assertIn(data_uuid, source)
        self.assertEqual(len(source), 1)


class FutureSourceTest(unittest.TestCase):

    layer = BCCVL_INTEGRATION_TESTING

    def _get_class(self):
        return future_climate_datasets_source

    def _make_one(self):
        return self._get_class()(self.layer['portal'])

    def test_interfaces(self):
        self.assertTrue(IContextSourceBinder.providedBy(self._get_class()))
        self.assertTrue(ISource.providedBy(self._make_one()))

    def test_elements(self):
        source = self._make_one()
        ds = self.layer['portal'][defaults.DATASETS_FOLDER_ID]
        data = ds[defaults.DATASETS_CLIMATE_FOLDER_ID]['future']
        data_uuid = IUUID(data)
        self.assertIn(data_uuid, source)
        self.assertEqual(len(source), 1)


class FunctionsSourceTest(unittest.TestCase):

    layer = BCCVL_INTEGRATION_TESTING

    def _get_class(self):
        return functions_source

    def _make_one(self):
        return self._get_class()(self.layer['portal'])

    def test_interfaces(self):
        self.assertTrue(IContextSourceBinder.providedBy(self._get_class()))
        self.assertTrue(ISource.providedBy(self._make_one()))

    def test_elements(self):
        source = self._make_one()
        ds = self.layer['portal'][defaults.TOOLKITS_FOLDER_ID]
        data = ds['bioclim']
        data_uuid = IUUID(data)
        self.assertIn(data_uuid, source)
        self.assertEqual(len(source), 1)
