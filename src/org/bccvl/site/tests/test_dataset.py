import unittest2 as unittest
from zope.component import getMultiAdapter
from plone.app.testing import TEST_USER_ID, setRoles
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
        self.assertEqual(batch.length, 6)
        self.assertEqual(batch.pagesize, 20)
        item = batch[0]
        self.assertEqual(item.Title, 'Future')
        self.assertEqual(item.BCCDataGenre, 'DataGenreFC')

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
        self.assertEqual(len(data), 7)
        item = next(iter(data))
        self.assertEqual(item.title, 'Species Occurrence')
        self.assertEqual(item.value, 'DataGenreSpeciesOccurrence')

    def test_genre_title(self):
        view = self.getview()
        data = view.genre_title('DataGenreSpeciesOccurrence')
        self.assertEqual(data, 'Species Occurrence')


class TestDatasetImport(unittest.TestCase):

    layer = BCCVL_INTEGRATION_TESTING

    def getview(self):
        self.portal = self.layer['portal']
        datasets = self.portal[defaults.DATASETS_FOLDER_ID]
        view = getMultiAdapter((datasets, self.portal.REQUEST),
                               name='datasets_import_view')
        return view

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
        ds = self.portal.datasets.species['org-bccvl-content-dataset']
        # check metadata
        from org.bccvl.site.interfaces import IBCCVLMetadata
        md = IBCCVLMetadata(ds)
        self.assertEqual(md['species'], testdata)
        # check job state
        from org.bccvl.site.interfaces import IJobTracker
        jt =  IJobTracker(ds)
        self.assertEqual(jt.state, 'QUEUED')
        # commit transaction to start job
        import transaction
        transaction.commit()
        # celery should run in eager mode so our job state should be up to date as well
        self.assertEqual(jt.state, 'COMPLETED')
        # we should have a bit more metadat and still the same as before import
        self.assertEqual(md['species'], testdata)
        self.assertEqual(md['genre'], 'DataGenreSpeciesOccurrence')
        self.assertEqual(md['rows'], 16)
        self.assertEqual(md['headers'], ['species', 'lon', 'lat'])
        self.assertEqual(md['bounds'], {'top': -5.166, 'right': 159.95, 'left': 48.218334197998, 'bottom': -23.94166})
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
        data = "Name,lon,lat\nSpecies,1,2\nSpecies,2,3\n"
        env = {'REQUEST_METHOD': 'PUT'}
        headers = {'content-type': 'text/csv',
                   'content-length': str(len(data)),
                   'content-disposition': 'attachment; filename=test.csv'}
        fileupload = FileUpload(FieldStorage(fp=StringIO(data),
                                             environ=env, headers=headers))

        view.request.form.update({
            'speciesabsence.buttons.save': u'Save',
            'speciesabsence.widgets.description': u'some test.csv file',
            'speciesabsence.widgets.file': fileupload,
            'speciesabsence.widgets.legalcheckbox': [u'selected'],
            'speciesabsence.widgets.legalcheckbox-empty-marker': u'1',
            'speciesabsence.widgets.rightsstatement': u'test rights',
            'speciesabsence.widgets.rightsstatement.mimeType': u'text/html',
            'speciesabsence.widgets.scientificName': u'test species',
            'speciesabsence.widgets.taxonID': u'test taxonid',
            'speciesabsence.widgets.title': u'test species title',
            'speciesabsence.widgets.vernacularName': u'test it'
        })
        _ = view()
        self.assertEqual(self.portal.REQUEST.response.status, 302)
        self.assertEqual(self.portal.REQUEST.response.getHeader('Location'),
                         'http://nohost/plone/datasets')
        ds = self.portal.datasets['test.csv']
        self.assertEqual(ds.rightsstatement.raw, u'test rights')
        self.assertEqual(ds.file.data, 'Name,lon,lat\nSpecies,1,2\nSpecies,2,3\n')
        from org.bccvl.site.interfaces import IBCCVLMetadata
        md = IBCCVLMetadata(ds)
        self.assertEqual(md['genre'], 'DataGenreSpeciesAbsence')
        self.assertEqual(md['species']['scientificName'], u'test species')
        self.assertEqual(md['rows'], 2)


# IDataset/edit
# IDataset/editfilemetadata
# IDataset/view


# IDataset/details
# datasets/datasets_list (different template for the above)
# datasets/dataset_list_item (template only view)
