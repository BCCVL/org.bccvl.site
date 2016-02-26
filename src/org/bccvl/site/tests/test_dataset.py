import os.path
from pkg_resources import resource_string, resource_stream
import shutil
from string import Template
import unittest
from urlparse import urlsplit

# TODO: new deps mock=1.1, funcsigs

from plone.app.testing import TEST_USER_ID, setRoles
import mock
import transaction
from zope.component import getMultiAdapter

from org.bccvl.site import defaults
from org.bccvl.site.content.interfaces import IDataset
from org.bccvl.site.interfaces import IDownloadInfo
from org.bccvl.site.interfaces import IBCCVLMetadata
from org.bccvl.site.job.interfaces import IJobTracker
from org.bccvl.site.testing import BCCVL_INTEGRATION_TESTING, BCCVL_FUNCTIONAL_TESTING


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
        ds = self.get_dataset(defaults.DATASETS_CLIMATE_FOLDER_ID, 'remote')
        di = IDownloadInfo(ds)
        self.assertEqual(u'http://nohost/plone/datasets/climate/remote/@@download/RCP3PD_cccma-cgcm31_2015.zip',
                         di['url'])
        self.assertEqual(u'RCP3PD_cccma-cgcm31_2015.zip',
                         di['filename'])

    def test_filemetadata(self):
        ds = self.get_dataset(defaults.DATASETS_SPECIES_FOLDER_ID,
                              'ABT', 'occurrence.csv')
        md = IBCCVLMetadata(ds)
        self.assertEqual(md.get('rows'), 3)
        self.assertEqual(md.get('bounds'), {'bottom': 1, 'left': 1, 'top': 3, 'right': 3})
        self.assertEqual(md.get('headers'), ['Name', 'lon', 'lat'])
        self.assertIn('species', md) # check if species attribute exists


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
        self.assertEqual(len(data), 30)
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

    # params:
    #    search (button)
    #    import (button)
    #    searchOccurrence_query, searchOccurrence_source,
    #    lsid, taxon, common
    @mock.patch('org.bccvl.site.browser.ws.urlopen')
    def test_import_view_ala_search(self, mock_urlopen):
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
        mock_urlopen.return_value = resource_stream(__name__, 'mock_data/ala_search.json')
        result = list(view.searchResults())
        mock_urlopen.assert_called_with(u'http://bie.ala.org.au/ws/search.json?q=Koala&fq=rank%3Aspecies')

        self.assertGreater(len(result), 0)
        for item in result:
            self.assertEqual(set(item.keys()), item_keys)
            # thumbUrl may be empty
            item.pop('thumbUrl')
            self.assertTrue(all(item.values()))
            self.assertEqual(set(item['actions'].keys()), action_keys)
            self.assertTrue(all(item['actions'].values()))

    @mock.patch('org.bccvl.movelib.move')
    def test_import_view_ala_import(self, mock_move=None):
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
            'common': testdata['vernacularName'],
            'searchOccurrence_source': 'ala',
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
        md = IBCCVLMetadata(ds)
        self.assertEqual(md['species'], testdata)
        # check job state
        jt = IJobTracker(ds)
        self.assertEqual(jt.state, 'PENDING')
        # prepare mock side effect
        def move_ala_data(*args, **kw):
            src, dst = (urlsplit(x['url']) for x in args)
            if src.scheme == 'ala':
                # first call fetch ala data
                for name in ('ala_metadata.json', 'ala_dataset.json', 'ala_occurrence.csv'):
                    open(os.path.join(dst.path, name), 'w').write(Template(resource_string(__name__, 'mock_data/{}'.format(name))).safe_substitute(tmpdir=dst.path))
            if dst.scheme == 'scp':
                # 2nd call upload to plone
                shutil.copyfile(src.path, dst.path)

        mock_move.side_effect = move_ala_data
        # commit transaction to start job
        transaction.commit()
        # verify call
        self.assertEqual(mock_move.call_args_list[0][0][0]['url'], 'ala://ala?lsid=urn:lsid:biodiversity.org.au:afd.taxon:dadb5555-d286-4862-b1dd-ea549b1c05a5')
        # celery should run in eager mode so our job state should be up to date as well
        self.assertEqual(jt.state, 'COMPLETED')
        # expand testdata with additional metadata fetched from ala
        testdata.update({
            'clazz': 'BIVALVIA',
            'clazzGuid': 'urn:lsid:biodiversity.org.au:afd.taxon:0c18b965-d1e9-4518-8c21-72045a340a4b',
            'family': 'PTERIIDAE',
            'familyGuid': 'urn:lsid:biodiversity.org.au:afd.taxon:d6300a23-1386-4620-9cb8-0ce481ab4988',
            'genus': 'Pteria',
            'genusGuid': 'urn:lsid:biodiversity.org.au:afd.taxon:3a97cb93-351e-443f-addd-624eb5b2278c',
            'kingdom': 'ANIMALIA',
            'kingdomGuid': 'urn:lsid:biodiversity.org.au:afd.taxon:4647863b-760d-4b59-aaa1-502c8cdf8d3c',
            'order': 'PTERIOIDA',
            'orderGuid': 'urn:lsid:biodiversity.org.au:afd.taxon:f4d97823-14fb-4eb2-a980-9a62d5ee8f08',
            'phylum': 'MOLLUSCA',
            'phylumGuid': 'urn:lsid:biodiversity.org.au:afd.taxon:4fb59020-e4a8-4973-adca-a4f662c4645c',
            'rank': 'species',
        })
        # we should have a bit more metadat and still the same as before import
        self.assertEqual(md['species'], testdata)
        self.assertEqual(md['genre'], 'DataGenreSpeciesOccurrence')
        self.assertEqual(md['rows'], 29)
        self.assertEqual(md['headers'], ['species', 'lon', 'lat', 'uncertainty', 'date', 'year', 'month'])
        self.assertEqual(md['bounds'], {'top': 14.35, 'right': 177.41, 'left': 48.218334197998, 'bottom': -28.911835})
        # check that there is a file as well
        self.assertIsNotNone(ds.file)
        self.assertIsNotNone(ds.file.data)
        self.assertGreater(len(ds.file.data), 0)


class TestDatasetUpload(unittest.TestCase):

    layer = BCCVL_FUNCTIONAL_TESTING

    def getview(self):
        from plone.app.z3cform.interfaces import IPloneFormLayer
        from zope.interface import alsoProvides
        self.portal = self.layer['portal']
        alsoProvides(self.portal.REQUEST, IPloneFormLayer)
        datasets = self.portal[defaults.DATASETS_FOLDER_ID]
        view = getMultiAdapter((datasets, self.portal.REQUEST),
                               name='datasets_upload_view')
        return view

    @mock.patch('org.bccvl.movelib.move')
    def test_upload_occurrence(self, mock_move):
        testcsv = resource_string(__name__, 'mock_data/ala_occurrence.csv')
        view = self.getview()
        from ZPublisher.HTTPRequest import FileUpload
        from cgi import FieldStorage
        from StringIO import StringIO
        env = {'REQUEST_METHOD': 'PUT'}
        headers = {'content-type': 'text/csv',
                   'content-length': str(len(testcsv)),
                   'content-disposition': 'attachment; filename=test.csv'}
        fileupload = FileUpload(FieldStorage(fp=StringIO(testcsv),
                                             environ=env, headers=headers))

        view.request.form.update({
            'speciesoccurrence.buttons.save': u'Save',
            'speciesoccurrence.widgets.file': fileupload,
            'speciesoccurrence.widgets.title': u'test species title',
            'speciesoccurrence.widgets.description': u'some test.csv file',
            'speciesoccurrence.widgets.legalcheckbox': [u'selected'],
            'speciesoccurrence.widgets.legalcheckbox-empty-marker': u'1',
            'speciesoccurrence.widgets.rights': u'test rights',
            'speciesoccurrence.widgets.scientificName': u'test species',
            'speciesoccurrence.widgets.taxonID': u'test taxonid',
            'speciesoccurrence.widgets.vernacularName': u'test it'
        })
        _ = view()
        self.assertEqual(self.portal.REQUEST.response.status, 302)
        self.assertEqual(self.portal.REQUEST.response.getHeader('Location'),
                         'http://{0}:{1}/plone/datasets'.format(self.layer.get('host'), self.layer.get('port')))
        # dataset should exist now
        ds = self.portal.datasets.species.user['test.csv']
        self.assertEqual(ds.rights, u'test rights')
        self.assertEqual(ds.file.data, testcsv)
        md = IBCCVLMetadata(ds)
        self.assertEqual(md['genre'], 'DataGenreSpeciesOccurrence')
        self.assertEqual(md['species']['taxonID'], u'test taxonid')
        self.assertEqual(md['species']['scientificName'], u'test species')
        self.assertEqual(md['species']['vernacularName'], u'test it')

        jt = IJobTracker(ds)
        self.assertEqual(jt.state, 'PENDING')

        # patch movelib.move
        def move_occurrence_data(*args, **kw):
            # try to move test.csv from dataset
            src, dst = (urlsplit(x['url']) for x in args)
            # copy test.csv to dst
            shutil.copyfileobj(resource_stream(__name__, 'mock_data/ala_occurrence.csv'),
                               open(dst.path, 'w'))

        mock_move.side_effect = move_occurrence_data

        # triger background process
        transaction.commit()
        # one move should have happened
        self.assertEqual(mock_move.call_args[0][0]['url'], 'http://{0}:{1}/plone/datasets/species/user/test.csv/@@download/file/test.csv'.format(self.layer.get('host'), self.layer.get('port')))
        # job state should be complete
        self.assertEqual(jt.state, 'COMPLETED')
        # metadata should be up to date
        self.assertEqual(md['rows'], 29)

    @mock.patch('org.bccvl.movelib.move')
    def test_upload_tif(self, mock_move):
        # upload a single layer tiff file
        view = self.getview()
        from ZPublisher.HTTPRequest import FileUpload
        from cgi import FieldStorage
        from StringIO import StringIO
        data = resource_string(__name__, 'mock_data/spc_obl_merc.tif')
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
            'climatecurrent.widgets.rights': u'test rights',
            'climatecurrent.widgets.resolution': u'Resolution5m',
        })
        _ = view()
        self.assertEqual(self.portal.REQUEST.response.status, 302)
        self.assertEqual(self.portal.REQUEST.response.getHeader('Location'),
                         'http://{0}:{1}/plone/datasets'.format(self.layer.get('host'), self.layer.get('port')))
        ds = self.portal.datasets.climate.user['spc_obl_merc.tif']
        self.assertEqual(ds.rights, u'test rights')
        self.assertEqual(ds.file.data, data)
        md = IBCCVLMetadata(ds)
        self.assertEqual(md['genre'], 'DataGenreCC')
        self.assertEqual(md['resolution'], u'Resolution5m')

        jt = IJobTracker(ds)
        self.assertEqual(jt.state, 'PENDING')

        # patch movelib.move
        def move_occurrence_data(*args, **kw):
            # try to move test.csv from dataset
            src, dst = (urlsplit(x['url']) for x in args)
            # copy test.csv to dst
            shutil.copyfileobj(resource_stream(__name__, 'mock_data/spc_obl_merc.tif'),
                               open(dst.path, 'w'))

        mock_move.side_effect = move_occurrence_data

        # triger background process
        transaction.commit()
        # one move should have happened
        self.assertEqual(mock_move.call_args[0][0]['url'], 'http://{0}:{1}/plone/datasets/climate/user/spc_obl_merc.tif/@@download/file/spc_obl_merc.tif'.format(self.layer.get('host'), self.layer.get('port')))
        # job state should be complete
        self.assertEqual(jt.state, 'COMPLETED')

        layermd = md['layers']['spc_obl_merc.tif']
        self.assertEqual(layermd['filename'], 'spc_obl_merc.tif')
        self.assertEqual(layermd['min'], 19.0)
        self.assertEqual(layermd['max'], 128.0)
        self.assertEqual(layermd['datatype'], 'continuous')
        self.assertEqual(layermd['height'], 200)
        self.assertEqual(layermd['width'], 200)
        self.assertEqual(layermd['srs'], None)

    @mock.patch('org.bccvl.movelib.move')
    def test_upload_zip(self, mock_move):
        # upload a zip in bccvl bagit format
        view = self.getview()
        from ZPublisher.HTTPRequest import FileUpload
        from cgi import FieldStorage
        from StringIO import StringIO
        data = resource_string(__name__, 'mock_data/spc_obl_merc.zip')
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
            'climatefuture.widgets.rights': u'test rights',
            'climatefuture.widgets.emsc': u'SRESB2',
            'climatefuture.widgets.gcm': u'cccma-cgcm31',
            'climatefuture.widgets.resolution': u'Resolution5m',
        })
        _ = view()
        self.assertEqual(self.portal.REQUEST.response.status, 302)
        self.assertEqual(self.portal.REQUEST.response.getHeader('Location'),
                         'http://{0}:{1}/plone/datasets'.format(self.layer.get('host'), self.layer.get('port')))
        ds = self.portal.datasets.climate.user['spc_obl_merc.zip']
        self.assertEqual(ds.rights, u'test rights')
        self.assertEqual(ds.file.data, data)
        md = IBCCVLMetadata(ds)
        self.assertEqual(md['genre'], 'DataGenreFC')
        self.assertEqual(md['resolution'], u'Resolution5m')
        self.assertEqual(md['emsc'], u'SRESB2')
        self.assertEqual(md['gcm'], u'cccma-cgcm31')

        jt = IJobTracker(ds)
        self.assertEqual(jt.state, 'PENDING')

        # patch movelib.move
        def move_occurrence_data(*args, **kw):
            # try to move test.csv from dataset
            src, dst = (urlsplit(x['url']) for x in args)
            # copy test.csv to dst
            shutil.copyfileobj(resource_stream(__name__, 'mock_data/spc_obl_merc.zip'),
                               open(dst.path, 'w'))

        mock_move.side_effect = move_occurrence_data

        # triger background process
        transaction.commit()
        # one move should have happened
        self.assertEqual(mock_move.call_args[0][0]['url'], 'http://{0}:{1}/plone/datasets/climate/user/spc_obl_merc.zip/@@download/file/spc_obl_merc.zip'.format(self.layer.get('host'), self.layer.get('port')))
        # job state should be complete
        self.assertEqual(jt.state, 'COMPLETED')

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


    @mock.patch('org.bccvl.movelib.move')
    def test_upload_multi_csv(self, mock_move=None):
        testcsv = resource_string(__name__, 'mock_data/multi_occurrence.csv')
        view = self.getview()
        from ZPublisher.HTTPRequest import FileUpload
        from cgi import FieldStorage
        from StringIO import StringIO
        env = {'REQUEST_METHOD': 'PUT'}
        headers = {'content-type': 'text/csv',
                   'content-length': str(len(testcsv)),
                   'content-disposition': 'attachment; filename=test.csv'}
        fileupload = FileUpload(FieldStorage(fp=StringIO(testcsv),
                                             environ=env, headers=headers))
        view.request.form.update({
            'multispeciesoccurrence.buttons.save': u'Save',
            'multispeciesoccurrence.widgets.file': fileupload,
            'multispeciesoccurrence.widgets.title': u'test species title',
            'multispeciesoccurrence.widgets.description': u'some test.csv file',
            'multispeciesoccurrence.widgets.legalcheckbox': [u'selected'],
            'multispeciesoccurrence.widgets.legalcheckbox-empty-marker': u'1',
            'multispeciesoccurrence.widgets.rights': u'test rights',
        })
        _ = view()
        self.assertEqual(self.portal.REQUEST.response.status, 302)
        self.assertEqual(self.portal.REQUEST.response.getHeader('Location'),
                         'http://{0}:{1}/plone/datasets'.format(self.layer.get('host'), self.layer.get('port')))
        ds = self.portal.datasets.species.user['test.csv']
        self.assertEqual(ds.rights, u'test rights')
        self.assertEqual(ds.file.data, testcsv)
        md = IBCCVLMetadata(ds)
        self.assertEqual(md['genre'], 'DataGenreSpeciesCollection')

        jt = IJobTracker(ds)
        self.assertEqual(jt.state, 'PENDING')

        # patch movelib.move
        def move_occurrence_data(*args, **kw):
            # try to move test.csv from dataset
            src, dst = (urlsplit(x['url']) for x in args)
            if src.scheme == 'http' and dst.scheme == 'file':
                # copy test.csv to dst

                shutil.copyfileobj(resource_stream(__name__, 'mock_data/multi_occurrence.csv'),
                                   open(dst.path, 'w'))
            elif src.scheme == 'file' and dst.scheme == 'scp':
                # copy result back
                shutil.copyfile(src.path, dst.path)
            else:
                raise Exception('Data move failed')

        mock_move.side_effect = move_occurrence_data
        # triger background process
        transaction.commit()
        # 6 move should have happened
        self.assertEqual(mock_move.call_count, 6)
        self.assertEqual(mock_move.call_args_list[0][0][0]['url'],
                         'http://{0}:{1}/plone/datasets/species/user/test.csv/@@download/file/test.csv'.format(self.layer.get('host'), self.layer.get('port')))
        self.assertEqual(mock_move.call_args_list[1][0][0]['url'],
                         'http://{0}:{1}/plone/datasets/species/user/test.csv/@@download/file/test.csv'.format(self.layer.get('host'), self.layer.get('port')))
        # TODO: should test other call orguments as well
        # job state should be complete
        self.assertEqual(jt.state, 'COMPLETED')
        # metadata should be up to date
        self.assertEqual(md['rows'], 999)
        # check other datasets:
        for name, rows in (('abbreviata.csv', 65),
                           ('acinacea.csv', 596),
                           ('acanthoclada.csv', 322),
                           ('acanthaster.csv', 16)):
            self.assertIn(name, self.portal.datasets.species.user)
            tds = self.portal.datasets.species.user[name]
            tmd = IBCCVLMetadata(tds)
            self.assertEqual(tmd['rows'], rows)

        self.assertEqual(len(ds.parts), 4)




# TODO: test upload raster file with RAT


# IDataset/edit
# IDataset/editfilemetadata
# IDataset/view


# IDataset/details
# datasets/datasets_list (different template for the above)
# datasets/dataset_list_item (template only view)
