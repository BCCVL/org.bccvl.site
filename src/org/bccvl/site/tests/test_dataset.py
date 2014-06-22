import unittest2 as unittest
from org.bccvl.site import defaults
from org.bccvl.site.testing import BCCVL_INTEGRATION_TESTING
from org.bccvl.site.content.interfaces import IDataset
from org.bccvl.site.interfaces import IDownloadInfo


class DatasetSetupTest(unittest.TestCase):

    layer = BCCVL_INTEGRATION_TESTING

    def get_dataset(self, *args):
        portal = self.layer['portal']

        dataset = portal[defaults.DATASETS_FOLDER_ID]
        for id in args:
            self.assertTrue(id in dataset)
            dataset = dataset[id]
        return dataset

    def test_climate_datasets_setup(self):
        ds = self.get_dataset(defaults.DATASETS_CLIMATE_FOLDER_ID,
                              'future')
        IDataset.providedBy(ds)
        self.assertTrue(hasattr(ds, 'file'))

        ds = self.get_dataset(defaults.DATASETS_CLIMATE_FOLDER_ID,
                              'remote')
        IDataset.providedBy(ds)
        self.assertTrue(hasattr(ds, 'remoteUrl'))

    def test_environmental_datasets_setup(self):
        ds = self.get_dataset(defaults.DATASETS_ENVIRONMENTAL_FOLDER_ID,
                              'current')
        IDataset.providedBy(ds)
        self.assertTrue(hasattr(ds, 'file'))

        ds = self.get_dataset(defaults.DATASETS_ENVIRONMENTAL_FOLDER_ID,
                              'current_1k')
        IDataset.providedBy(ds)
        self.assertTrue(hasattr(ds, 'file'))

    def test_species_datasets_setup(self):
        ds = self.get_dataset(defaults.DATASETS_SPECIES_FOLDER_ID,
                              'ABT', 'occurrence.csv')
        IDataset.providedBy(ds)
        self.assertTrue(hasattr(ds, 'file'))

        ds = self.get_dataset(defaults.DATASETS_SPECIES_FOLDER_ID,
                              'ABT', 'absence.csv')
        IDataset.providedBy(ds)
        self.assertTrue(hasattr(ds, 'file'))

    def test_download_info(self):
        ds = self.get_dataset(defaults.DATASETS_CLIMATE_FOLDER_ID,
                              'future')
        di = IDownloadInfo(ds)
        self.assertIn(u'future/@@download', di['url'])
        self.assertEqual(u'future', di['filename'])
        self.assertEqual(u'http://127.0.0.1:8201/plone/datasets/climate/future/@@download/file/future',
                         di['alturl'][0])

        ds = self.get_dataset(defaults.DATASETS_CLIMATE_FOLDER_ID,
                              'remote')
        di = IDownloadInfo(ds)
        self.assertEqual(u'https://swift.rc.nectar.org.au:8888/v1/AUTH_0bc40c2c2ff94a0b9404e6f960ae5677/australia_5km/RCP3PD_cccma-cgcm31_2015.zip',
                         di['url'])
        self.assertEqual(u'RCP3PD_cccma-cgcm31_2015.zip',
                         di['filename'])
        self.assertEqual(di['url'], di['alturl'][0])

    def test_filemetadata(self):
        ds = self.get_dataset(defaults.DATASETS_SPECIES_FOLDER_ID,
                              'ABT', 'occurrence.csv')
        from gu.z3cform.rdf.interfaces import IGraph
        from rdflib.resource import Resource
        from org.bccvl.site.namespace import BCCPROP
        graph = IGraph(ds)
        mdres = Resource(graph, graph.identifier)
        self.assertEqual(mdres.value(BCCPROP['rows']).toPython(), 3)
        #self.assertEqual(md.value(BCCPROP['bounds']), len(bounds)==4)
        #self.assertEqual(md.value(BCCPROP['headers']), ['Name', 'lon', 'lat'])
        #self.assertIn('species', md) # check if species attribute exists
