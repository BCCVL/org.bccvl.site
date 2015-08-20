from pkg_resources import resource_string
import transaction
import unittest2 as unittest
from zope.component import getMultiAdapter
from plone.app.testing import TEST_USER_ID, setRoles
from org.bccvl.site import defaults
from org.bccvl.site.testing import BCCVL_INTEGRATION_TESTING, BCCVL_FUNCTIONAL_TESTING
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

        ds = self.get_dataset(defaults.DATASETS_CLIMATE_FOLDER_ID, 'remote')
        di = IDownloadInfo(ds)
        self.assertEqual(u'https://swift.rc.nectar.org.au:8888/v1/AUTH_0bc40c2c2ff94a0b9404e6f960ae5677/australia_5km/RCP3PD_cccma-cgcm31_2015.zip',
                         di['url'])
        self.assertEqual(u'RCP3PD_cccma-cgcm31_2015.zip',
                         di['filename'])
        self.assertEqual(di['url'], di['alturl'][0])

    def test_filemetadata(self):
        ds = self.get_dataset(defaults.DATASETS_SPECIES_FOLDER_ID,
                              'ABT', 'occurrence.csv')
        from org.bccvl.site.interfaces import IBCCVLMetadata
        md = IBCCVLMetadata(ds)
        self.assertEqual(md.get('rows'), 3)
        self.assertEqual(md.get('bounds'), {'bottom': 1, 'left': 1, 'top': 3, 'right': 3})
        self.assertEqual(md.get('headers'), ['Name', 'lon', 'lat'])
        self.assertIn('species', md) # check if species attribute exists


class TestDatasetListing(unittest.TestCase):

    layer = BCCVL_INTEGRATION_TESTING

    def getview(self):
        portal = self.layer['portal']
        datasets = portal[defaults.DATASETS_FOLDER_ID]
        view = getMultiAdapter((datasets, portal.REQUEST),
                               name='datasets_list')
        # FIXME: we have to call the view to get everything setup:(
        view()
        return view

    # view methods:
    # contentFilterAQ
    # contentFilter
    # datasetslisting
    # __call__
    # genre_list
    # resolution_list
    # source_list

    def test_datasetslisting(self):
        view = self.getview()
        batch = view.datasetslisting()
        # test datasets list
        self.assertEqual(batch.length, 7)
        self.assertEqual(batch.pagesize, 20)

    def test_datasetslisting_occur(self):
        req = self.layer['request']
        req.form.update({
            'b_size': '2',
            # 'datasets.filter.sort': '',
            # 'datasets.filter.order': '',
            # 'datasets.filter.text': '',
            'datasets.filter.genre': ['DataGenreSpeciesOccurrence', ],
            # 'datasets.filter.cesolution': '',
        })
        view = self.getview()
        batch = view.datasetslisting()
        self.assertEqual(batch.length, 1)
        self.assertEqual(batch.pagesize, 2)
        item = batch[0]
        self.assertEqual(item.Title, 'ABT')
        self.assertEqual(item.BCCDataGenre, 'DataGenreSpeciesOccurrence')


class TestDatasetTools(unittest.TestCase):

    layer = BCCVL_INTEGRATION_TESTING

    def getview(self):
        self.portal = self.layer['portal']
        datasets = self.portal[defaults.DATASETS_FOLDER_ID]
        self.dataset = datasets[defaults.DATASETS_SPECIES_FOLDER_ID]['ABT']['occurrence.csv']
        view = getMultiAdapter((self.portal, self.portal.REQUEST),
                               name='dataset_tools')
        return view

    def test_get_transition(self):
        view = self.getview()
        setRoles(self.portal, TEST_USER_ID, ('Manager', ))
        data = view.get_transition(self.dataset)
        self.assertEqual(data, 'retract')

    def test_get_download_info(self):
        # TODO: test all fields are populate
        view = self.getview()
        data = view.get_download_info(self.dataset)
        self.assertEqual(data['url'], "{0}/@@download/file/{1}".format(
            self.dataset.absolute_url(),
            self.dataset.file.filename))
        self.assertEqual(data['filename'], self.dataset.file.filename)

    # FIXME: can't test this without Zope Interaction setup
    # call newInteraction() from Products.Five.security in your test setup (e.g. the afterSetUp() method).
    # def test_can_modify(self):
    #     view = self.getview()
    #     setRoles(self.portal, TEST_USER_ID, ('Manager', ))
    #     data = view.can_modify(self.dataset)

    def test_local_roles_action(self):
        view = self.getview()
        setRoles(self.portal, TEST_USER_ID, ('Manager', ))
        data = view.local_roles_action(self.dataset)
        self.assertEqual(data['title'], 'Sharing')

    def test_metadata(self):
        # TODO: test all fields are populated
        view = self.getview()
        data = view.metadata(self.dataset)
        self.assertEqual(data['rows'], 3)
        self.assertEqual(data['url'], self.dataset.absolute_url())

    def test_job_state(self):
        view = self.getview()
        pc = self.portal.portal_catalog
        brain = pc.searchResults(path='/'.join(self.dataset.getPhysicalPath()))[0]
        from plone.app.contentlisting.interfaces import IContentListingObject
        ds = IContentListingObject(brain)
        data = view.job_state(ds)
        self.assertEqual(data, 'COMPLETED')

    def test_genre_vocab(self):
        view = self.getview()
        data = view.genre_vocab
        self.assertEqual(len(data), 29)
        item = next(iter(data))
        self.assertEqual(item.title, 'Species Occurrence')
        self.assertEqual(item.value, 'DataGenreSpeciesOccurrence')

    def test_genre_title(self):
        view = self.getview()
        data = view.genre_title('DataGenreSpeciesOccurrence')
        self.assertEqual(data, 'Species Occurrence')


class TestDatasetImport(unittest.TestCase):

    # need functional testing here, because we commit transactions
    # and access outside systems (ala)
    # functional test layers setup and teardown a DemoStorage
    layer = BCCVL_FUNCTIONAL_TESTING

    def getview(self):
        self.portal = self.layer['portal']
        datasets = self.portal[defaults.DATASETS_FOLDER_ID]
        view = getMultiAdapter((datasets, self.portal.REQUEST),
                               name='datasets_import_view')
        return view

    def setUp(self):
        # install fake Datamover
        from .utils import MockDataMover
        from org.bccvl.tasks import datamover
        self._old_DataMover = datamover.DataMover
        datamover.DataMover = MockDataMover

    def tearDown(self):
        # restore original DataMover
        from org.bccvl.tasks import datamover
        datamover.DataMover = self._old_DataMover

    # params:
    #    search (button)
    #    import (button)
    #    searchOccurrence_query, searchOccurrence_source,
    #    lsid, taxon, common
    def test_import_view_ala_search(self):
        item_keys = set(['actions', 'description', 'friendlyName',
                         'thumbUrl', 'title'])
        action_keys = set(['alaimport', 'viz'])
        view = self.getview()
        view.request.form.update({
            'search': 'Search',
            'searchOccurrence_query': 'Koala'
        })
        # FIXME: that's not how we should call the view
        view.params = view.parseRequest()
        result = list(view.searchResults())
        self.assertGreater(len(result), 0)
        for item in result:
            self.assertEqual(set(item.keys()), item_keys)
            # thumbUrl may be empty
            item.pop('thumbUrl')
            self.assertTrue(all(item.values()))
            self.assertEqual(set(item['actions'].keys()), action_keys)
            self.assertTrue(all(item['actions'].values()))

    def test_import_view_ala_import(self):
        # TODO: this test needs a running DataMover. (see below))
        testdata = {
            'taxonID': 'urn:lsid:biodiversity.org.au:afd.taxon:dadb5555-d286-4862-b1dd-ea549b1c05a5',
            'scientificName': 'Pteria penguin',
            'vernacularName': 'Black Banded Winged Pearl Shell'
        }
        view =  self.getview()
        view.request.form.update({
            'import': 'Import',
            'lsid': testdata['taxonID'],
            'taxon': testdata['scientificName'],
            'common': testdata['vernacularName']
        })
        # call view:
        view()
        # response should redirect to datasets
        self.assertEqual(view.request.response.getStatus(), 302)
        self.assertEqual(view.request.response.getHeader('Location'),
                         self.portal.datasets.absolute_url())
        # get new dataset and check state?
        ds = self.portal.datasets.species.ala['org-bccvl-content-dataset']
        # check metadata
        from org.bccvl.site.interfaces import IBCCVLMetadata
        md = IBCCVLMetadata(ds)
        self.assertEqual(md['species'], testdata)
        # check job state
        from org.bccvl.site.interfaces import IJobTracker
        jt =  IJobTracker(ds)
        self.assertEqual(jt.state, 'PENDING')
        # commit transaction to start job
        # TODO: this test needs a running DataMover. (see below))
        # TODO: we should Mock org.bccvl.tasks.datamover.DataMover (generate files as requested?)
        #       and maybe org.bccvl.tasks.plone.import_ala
        transaction.commit()
        # celery should run in eager mode so our job state should be up to date as well
        self.assertEqual(jt.state, 'COMPLETED')
        # we should have a bit more metadat and still the same as before import
        self.assertEqual(md['species'], testdata)
        self.assertEqual(md['genre'], 'DataGenreSpeciesOccurrence')
        self.assertEqual(md['rows'], 5)
        self.assertEqual(md['headers'], ['species', 'lon', 'lat'])
        self.assertEqual(md['bounds'], {'top': -5.166, 'right': 167.68167, 'left': 114.166, 'bottom': -28.911835})
        # check that there is a file as well
        self.assertIsNotNone(ds.file)
        self.assertIsNotNone(ds.file.data)
        self.assertGreater(len(ds.file.data), 0)


class TestDatasetUpload(unittest.TestCase):

    layer = BCCVL_INTEGRATION_TESTING

    def getview(self):
        from plone.app.z3cform.interfaces import IPloneFormLayer
        from zope.interface import alsoProvides
        self.portal = self.layer['portal']
        alsoProvides(self.portal.REQUEST, IPloneFormLayer)
        datasets = self.portal[defaults.DATASETS_FOLDER_ID]
        view = getMultiAdapter((datasets, self.portal.REQUEST),
                               name='datasets_upload_view')
        return view

    def test_upload_occurrence(self):
        view = self.getview()
        from ZPublisher.HTTPRequest import FileUpload
        from cgi import FieldStorage
        from StringIO import StringIO
        data = "species,lon,lat\nSpecies,1,2\nSpecies,2,3\n"
        env = {'REQUEST_METHOD': 'PUT'}
        headers = {'content-type': 'text/csv',
                   'content-length': str(len(data)),
                   'content-disposition': 'attachment; filename=test.csv'}
        fileupload = FileUpload(FieldStorage(fp=StringIO(data),
                                             environ=env, headers=headers))

        view.request.form.update({
            'speciesoccurrence.buttons.save': u'Save',
            'speciesoccurrence.widgets.description': u'some test.csv file',
            'speciesoccurrence.widgets.file': fileupload,
            'speciesoccurrence.widgets.title': u'test species title',
            'speciesoccurrence.widgets.legalcheckbox': [u'selected'],
            'speciesoccurrence.widgets.legalcheckbox-empty-marker': u'1',
            'speciesoccurrence.widgets.rightsstatement': u'test rights',
            'speciesoccurrence.widgets.rightsstatement.mimeType': u'text/html',
            'speciesoccurrence.widgets.scientificName': u'test species',
            'speciesoccurrence.widgets.taxonID': u'test taxonid',
            'speciesoccurrence.widgets.vernacularName': u'test it'
        })
        _ = view()
        self.assertEqual(self.portal.REQUEST.response.status, 302)
        self.assertEqual(self.portal.REQUEST.response.getHeader('Location'),
                         'http://nohost/plone/datasets')
        ds = self.portal.datasets.species.user['test.csv']
        self.assertEqual(ds.rightsstatement.raw, u'test rights')
        self.assertEqual(ds.file.data, 'species,lon,lat\nSpecies,1,2\nSpecies,2,3\n')
        from org.bccvl.site.interfaces import IBCCVLMetadata
        md = IBCCVLMetadata(ds)
        self.assertEqual(md['genre'], 'DataGenreSpeciesOccurrence')
        self.assertEqual(md['species']['taxonID'], u'test taxonid')
        self.assertEqual(md['species']['scientificName'], u'test species')
        self.assertEqual(md['species']['vernacularName'], u'test it')
        self.assertEqual(md['rows'], 2)

    def test_upload_tif(self):
        # upload a single layer tiff file
        view = self.getview()
        from ZPublisher.HTTPRequest import FileUpload
        from cgi import FieldStorage
        from StringIO import StringIO
        data = resource_string(__name__, 'spc_obl_merc.tif')
        env = {'REQUEST_METHOD': 'PUT'}
        headers = {'content-type': 'text/csv',
                   'content-length': str(len(data)),
                   'content-disposition': 'attachment; filename=spc_obl_merc.tif'}
        fileupload = FileUpload(FieldStorage(fp=StringIO(data),
                                             environ=env, headers=headers))

        view.request.form.update({
            'climatecurrent.buttons.save': u'Save',
            'climatecurrent.widgets.description': u'some test.tif file',
            'climatecurrent.widgets.file': fileupload,
            'climatecurrent.widgets.title': u'test single layer title',
            'climatecurrent.widgets.legalcheckbox': [u'selected'],
            'climatecurrent.widgets.legalcheckbox-empty-marker': u'1',
            'climatecurrent.widgets.rightsstatement': u'test rights',
            'climatecurrent.widgets.rightsstatement.mimeType': u'text/html',
            'climatecurrent.widgets.resolution': u'Resolution5m',
            'climatecurrent.widgets.temporal': u'2015',
        })
        _ = view()
        self.assertEqual(self.portal.REQUEST.response.status, 302)
        self.assertEqual(self.portal.REQUEST.response.getHeader('Location'),
                         'http://nohost/plone/datasets')
        ds = self.portal.datasets.climate.user['spc_obl_merc.tif']
        self.assertEqual(ds.rightsstatement.raw, u'test rights')
        self.assertEqual(ds.file.data, data)
        from org.bccvl.site.interfaces import IBCCVLMetadata
        md = IBCCVLMetadata(ds)
        self.assertEqual(md['genre'], 'DataGenreCC')
        self.assertEqual(md['resolution'], u'Resolution5m')
        self.assertEqual(md['temporal'], u'2015')
        layermd = md['layers']['spc_obl_merc.tif']
        self.assertEqual(layermd['filename'], 'spc_obl_merc.tif')
        self.assertEqual(layermd['min'], 19.0)
        self.assertEqual(layermd['max'], 128.0)
        self.assertEqual(layermd['datatype'], 'continuous')
        self.assertEqual(layermd['height'], 200)
        self.assertEqual(layermd['width'], 200)
        self.assertEqual(layermd['srs'], None)

    def test_upload_zip(self):
        # upload a zip in bccvl bagit format
        view = self.getview()
        from ZPublisher.HTTPRequest import FileUpload
        from cgi import FieldStorage
        from StringIO import StringIO
        data = resource_string(__name__, 'spc_obl_merc.zip')
        env = {'REQUEST_METHOD': 'PUT'}
        headers = {'content-type': 'text/csv',
                   'content-length': str(len(data)),
                   'content-disposition': 'attachment; filename=spc_obl_merc.zip'}
        fileupload = FileUpload(FieldStorage(fp=StringIO(data),
                                             environ=env, headers=headers))

        view.request.form.update({
            'climatefuture.buttons.save': u'Save',
            'climatefuture.widgets.description': u'some test.tif file',
            'climatefuture.widgets.file': fileupload,
            'climatefuture.widgets.title': u'test smulti layer title',
            'climatefuture.widgets.legalcheckbox': [u'selected'],
            'climatefuture.widgets.legalcheckbox-empty-marker': u'1',
            'climatefuture.widgets.rightsstatement': u'test rights',
            'climatefuture.widgets.rightsstatement.mimeType': u'text/html',
            'climatefuture.widgets.emsc': u'SRESB2',
            'climatefuture.widgets.gcm': u'cccma-cgcm31',
            'climatefuture.widgets.resolution': u'Resolution5m',
            'climatefuture.widgets.temporal': u'2015',
        })
        _ = view()
        self.assertEqual(self.portal.REQUEST.response.status, 302)
        self.assertEqual(self.portal.REQUEST.response.getHeader('Location'),
                         'http://nohost/plone/datasets')
        ds = self.portal.datasets.climate.user['spc_obl_merc.zip']
        self.assertEqual(ds.rightsstatement.raw, u'test rights')
        self.assertEqual(ds.file.data, data)
        from org.bccvl.site.interfaces import IBCCVLMetadata
        md = IBCCVLMetadata(ds)
        self.assertEqual(md['genre'], 'DataGenreFC')
        self.assertEqual(md['resolution'], u'Resolution5m')
        self.assertEqual(md['temporal'], u'2015')
        self.assertEqual(md['emsc'], u'SRESB2')
        self.assertEqual(md['gcm'], u'cccma-cgcm31')
        layermd = md['layers']['spc_obl_merc/data/spc_obl_merc_1.tif']
        self.assertEqual(layermd['filename'], 'spc_obl_merc/data/spc_obl_merc_1.tif')
        self.assertEqual(layermd['min'], 19.0)
        self.assertEqual(layermd['max'], 128.0)
        self.assertEqual(layermd['datatype'], 'continuous')
        self.assertEqual(layermd['height'], 200)
        self.assertEqual(layermd['width'], 200)
        self.assertEqual(layermd['srs'], None)
        layermd = md['layers']['spc_obl_merc/data/spc_obl_merc_2.tif']
        self.assertEqual(layermd['filename'], 'spc_obl_merc/data/spc_obl_merc_2.tif')
        self.assertEqual(layermd['min'], 19.0)
        self.assertEqual(layermd['max'], 128.0)
        self.assertEqual(layermd['datatype'], 'continuous')
        self.assertEqual(layermd['height'], 200)
        self.assertEqual(layermd['width'], 200)
        self.assertEqual(layermd['srs'], None)

# TODO: test upload raster file with RAT


# IDataset/edit
# IDataset/editfilemetadata
# IDataset/view


# IDataset/details
# datasets/datasets_list (different template for the above)
# datasets/dataset_list_item (template only view)
