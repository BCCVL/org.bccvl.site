from itertools import chain
import os.path
from PIL import Image
from urlparse import urlsplit

from plone.app.z3cform.interfaces import IPloneFormLayer
from zope.annotation.interfaces import IAttributeAnnotatable
from zope.component import getMultiAdapter
from zope.interface import implementer
from zope.publisher.browser import TestRequest as TestRequestBase

from org.bccvl.site import defaults
from org.bccvl.site.content.interfaces import ISDMExperiment
from org.bccvl.tasks.utils import import_result_job, import_cleanup
from org.bccvl.tasks.utils import set_progress


@implementer(IPloneFormLayer, IAttributeAnnotatable)
class TestRequest(TestRequestBase):
    """Zope 3's TestRequest doesn't support item assignment, but Zope 2's
    request does.
    """

    def __setitem__(self, key, value):
        pass


class SDMExperimentHelper(object):
    """
    A helper class to configure and run a SDM experiment during testing.
    """

    def __init__(self, portal):
        # configure local variables on instance
        self.portal = portal
        self.experiments = self.portal[defaults.EXPERIMENTS_FOLDER_ID]
        # get some dataset shortcuts
        self.algorithm = self.portal[defaults.TOOLKITS_FOLDER_ID]['bioclim']
        self.datasets = self.portal[defaults.DATASETS_FOLDER_ID]
        abt = self.datasets[defaults.DATASETS_SPECIES_FOLDER_ID]['ABT']
        self.occur = abt['occurrence.csv']
        self.absen = abt['absence.csv']
        self.current = self.datasets[
            defaults.DATASETS_ENVIRONMENTAL_FOLDER_ID]['current']

    def get_form(self):
        """
        fill out common stuff when creating a new experiment
        """
        # setup request layer
        self.request = TestRequest()
        # get add view
        form = getMultiAdapter((self.experiments, self.request),
                               name="newSpeciesDistribution")
        # update the form once to initialise all widgets
        form.update()
        # go through all widgets on the form  and update the request with
        # default values
        data = {}
        for widget in chain(
                # form fields
                form.widgets.values(),
                # param group fields
                chain.from_iterable(g.widgets.values()
                                    for param_group in form.param_groups.values() for g in param_group),
                # param group fieldset fields
                chain.from_iterable(sg.widgets.values() for param_group in form.param_groups.values() for g in param_group for sg in g.groups)):
            data[widget.name] = widget.value
        data.update({
            'form.widgets.IDublinCore.title': u"My Experiment",
            'form.widgets.IDublinCore.description': u'This is my experiment description',
            'form.widgets.functions': [self.algorithm.UID()],  # BIOCLIM
            # ABT
            'form.widgets.species_occurrence_dataset': [unicode(self.occur.UID())],
            'form.widgets.species_absence_dataset': [unicode(self.absen.UID())],
            'form.widgets.resolution': ('Resolution2_5m', ),
            # FIXME: shouldn't be necessary to use unicode here,... widget
            # converter should take care of it
            'form.widgets.environmental_datasets.item.0': unicode(self.current.UID()),
            'form.widgets.environmental_datasets.item.0.item': [u'B01'],
            'form.widgets.environmental_datasets.item.1': unicode(self.current.UID()),
            'form.widgets.environmental_datasets.item.1.item': [u'B02'],
            'form.widgets.environmental_datasets.count': '2',
        })
        self.request.form.update(data)
        form = getMultiAdapter((self.experiments, self.request),
                               name="newSpeciesDistribution")
        return form

    def mock_run_script(self, *args, **kw):
        # simulate a script run
        wrapper, params, context = args
        # 1. write file into results_dir
        tmpdir = urlsplit(params['result']['results_dir']).path
        try:
            # 2. create some result files
            for fname in ('model.RData',
                          'proj_test.tif'):
                img = Image.new('F', (10, 10))
                img.save(os.path.join(tmpdir, fname), 'TIFF')
            # 3. store results
            items = [
                {
                    'file': {
                        'url': 'file://{}/model.RData'.format(tmpdir),
                        'contenttype': 'application/x-r-data',
                        'filename': 'model.RData',
                    },
                    'title': 'Model Title',
                    'description': 'Model Description',
                    'bccvlmetadata': {
                        'genre': 'DataGenreSDMModel',
                    },
                    'filemetadata': {},
                    'layermd': {}
                },
                {
                    'file': {
                        'url': 'file://{}/proj_test.tif'.format(tmpdir),
                        'contenttype': 'image/tiff',
                        'filename': 'proj_test.tif',
                    },
                    'title': 'Test Projection',
                    'description': 'Test Projection Description',
                    'bccvlmetadata': {
                        'genre': 'DataGenreCP',
                    },
                    'filemetadata': {
                        'band': [{
                            'min': 0.0,
                            'STATISTICS_MINIMUM': 0.0,
                            'max': 1.0
                        }]
                    },
                    'layermd': {'files': {'proj_test.tif': {'layer': 'projection_probability', 'data_type': 'Continuous'}}}
                },
                {
                    'file': {
                        'url': 'file://{}/proj_test.tif'.format(tmpdir),
                        'contenttype': 'image/tiff',
                        'filename': 'proj_test.tif',
                    },
                    'title': 'Test Envelop Projection',
                    'description': 'Test Envelop Projection Description',
                    'bccvlmetadata': {
                        'genre': 'DataGenreCP_ENVLOP',
                    },
                    'filemetadata': {
                        'band': [{
                            'min': 0.0,
                            'STATISTICS_MINIMUM': 0.0,
                            'max': 1.0
                        }]
                    },
                    'layermd': {'files': {'proj_test.tif': {'layer': 'projection_probability', 'data_type': 'Continuous'}}}
                }

            ]
            # TODO: tasks called dierctly here; maybe call them as tasks as
            # well? (chain?)
            import_result_job(items, params['result'][
                              'results_dir'], context).delay()
            import_cleanup(params['result']['results_dir'], context)
            set_progress('COMPLETED', 'Test Task succeeded', None, context)
        except Exception as e:
            # 4. clean up if problem otherwise import task cleans up
            #    TODO: should be done by errback or whatever
            import_cleanup(params['result']['results_dir'], context)
            set_progress('FAILED', 'Test Task failed', None, context)
            raise


class ProjectionExperimentHelper(object):
    """
    A helper class to configure and run a SDM experiment during testing.
    """

    def __init__(self, portal, sdmexp):
        # configure local variables on instance
        self.portal = portal
        self.sdmexp = sdmexp
        self.sdmmodel = sdmexp.values()[0]['model-rdata']
        self.experiments = self.portal[defaults.EXPERIMENTS_FOLDER_ID]
        # get some dataset shortcuts
        self.datasets = self.portal[defaults.DATASETS_FOLDER_ID]
        self.future = self.datasets[
            defaults.DATASETS_CLIMATE_FOLDER_ID]['future']

    def get_form(self):
        """
        fill out common stuff when creating a new experiment
        """
        # setup request layer
        self.request = TestRequest()
        # get add view
        form = getMultiAdapter((self.experiments, self.request),
                               name="newProjection")
        # update the form once to initialise all widgets
        form.update()
        # go through all widgets on the form  and update the request with
        # default values
        data = {}
        for widget in form.widgets.values():
            data[widget.name] = widget.value
        data.update({
            'form.widgets.IDublinCore.title': u"My CC Experiment",
            'form.widgets.IDublinCore.description': u'This is my experiment description',
            'form.widgets.species_distribution_models.count': 1,
            'form.widgets.species_distribution_models.item.0': unicode(self.sdmexp.UID()),
            #'form.widgets.species_distribution_models.item.0.item.0.uuid': unicode(self.sdmmodel.UID()),
            'form.widgets.species_distribution_models.item.0.count': 1,
            'form.widgets.species_distribution_models.item.0.item.0.uuid': unicode(self.sdmmodel.UID()),
            'form.widgets.species_distribution_models.item.0.item.0.threshold': u'0.5',
            'form.widgets.future_climate_datasets': [unicode(self.future.UID())]
        })
        self.request.form.update(data)
        form = getMultiAdapter((self.experiments, self.request),
                               name="newProjection")
        return form

    def mock_run_script(self, *args, **kw):
        # simulate a script run
        wrapper, params, context = args
        # 1. write file into results_dir
        tmpdir = urlsplit(params['result']['results_dir']).path
        try:
            # 2. create some result files
            for fname in ('proj_test.tif',):
                img = Image.new('F', (10, 10))
                img.save(os.path.join(tmpdir, fname), 'TIFF')
            # 3. store results
            items = [
                {
                    'file': {
                        'url': 'file://{}/proj_test.tif'.format(tmpdir),
                        'contenttype': 'image/tiff',
                        'filename': 'proj_test.tif',
                    },
                    'title': 'Test Projection',
                    'description': 'Test Projection Description',
                    'bccvlmetadata': {
                        'genre': 'DataGenreFP',
                    },
                    'filemetadata': {
                        'band': [{
                            'min': 0.0,
                            'STATISTICS_MINIMUM': 0.0,
                            'max': 1.0
                        }]
                    },
                    'layermd': {'files': {'proj_test.tif': {'layer': 'projection_probability', 'data_type': 'Continuous'}}}
                }
            ]
            # TODO: tasks called dierctly here; maybe call them as tasks as
            # well? (chain?)
            import_result_job(items, params['result'][
                              'results_dir'], context).delay()
            import_cleanup(params['result']['results_dir'], context)
            set_progress('COMPLETED', 'Test Task succeeded', None, context)
        except Exception as e:
            # 4. clean up if problem otherwise import task cleans up
            #    TODO: should be done by errback or whatever
            import_cleanup(params['result']['results_dir'], context)
            set_progress('FAILED', 'Test Task failed', None, context)
            raise


class BiodiverseExperimentHelper(object):
    """
    A helper class to configure and run a SDM experiment during testing.
    """

    def __init__(self, portal, sdmexp):
        # configure local variables on instance
        self.portal = portal
        self.sdmexp = sdmexp
        self.sdmproj = sdmexp.values()[0]['proj_test.tif']
        self.experiments = self.portal[defaults.EXPERIMENTS_FOLDER_ID]

    def get_form(self):
        """
        fill out common stuff when creating a new experiment
        """
        # setup request layer
        self.request = TestRequest()
        # get add view
        form = getMultiAdapter((self.experiments, self.request),
                               name="newBiodiverse")
        # update the form once to initialise all widgets
        form.update()
        # go through all widgets on the form  and update the request with
        # default values
        data = {}
        for widget in form.widgets.values():
            data[widget.name] = widget.value
        data.update({
            'form.widgets.IDublinCore.title': u"My BD Experiment",
            'form.widgets.IDublinCore.description': u'This is my experiment description',
            'form.widgets.projection.count': '1',
            'form.widgets.projection.item.0': unicode(self.sdmexp.UID()),
            'form.widgets.projection.item.0.count': 1,
            'form.widgets.projection.item.0.item.0.uuid': unicode(self.sdmproj.UID()),
            'form.widgets.projection.item.0.item.0.threshold': u'0.5',
            'form.widgets.cluster_size': '5000',
        })
        self.request.form.update(data)
        form = getMultiAdapter((self.experiments, self.request),
                               name="newBiodiverse")
        return form

    def mock_run_script(self, *args, **kw):
        # simulate a script run
        wrapper, params, context = args
        # 1. write file into results_dir
        tmpdir = urlsplit(params['result']['results_dir']).path
        try:
            # 2. create some result files
            for fname in ('endw_cwe.tif',):
                img = Image.new('F', (10, 10))
                img.save(os.path.join(tmpdir, fname), 'TIFF')
            # 3. store results
            items = [
                {
                    'file': {
                        'url': 'file://{}/endw_cwe.tif'.format(tmpdir),
                        'contenttype': 'image/tiff',
                        'filename': 'endw_cwe.tif',
                    },
                    'title': 'Biodiverse Output',
                    'description': 'Biodiverse Output Description',
                    'bccvlmetadata': {
                        'genre': 'DataGenreENDW_CWE',
                    },
                    'filemetadata': {
                        'band': [{
                            'min': 0.0,
                            'STATISTICS_MINIMUM': 0.0,
                            'max': 1.0
                        }]
                    },
                    'layermd': {},
                }
            ]
            # TODO: tasks called dierctly here; maybe call them as tasks as
            # well? (chain?)
            import_result_job(items, params['result'][
                              'results_dir'], context).delay()
            import_cleanup(params['result']['results_dir'], context)
            set_progress('COMPLETED', 'Test Task succeeded', None, context)
        except Exception as e:
            # 4. clean up if problem otherwise import task cleans up
            #    TODO: should be done by errback or whatever
            import_cleanup(params['result']['results_dir'], context)
            set_progress('FAILED', 'Test Task failed', None, context)
            raise


class EnsembleExperimentHelper(object):
    """
    A helper class to configure and run a SDM experiment during testing.
    """

    def __init__(self, portal, sdmexp):
        # configure local variables on instance
        self.portal = portal
        self.sdmexp = sdmexp
        self.sdmproj = sdmexp.values()[0]['proj_test.tif']
        self.experiments = self.portal[defaults.EXPERIMENTS_FOLDER_ID]

    def get_form(self):
        """
        fill out common stuff when creating a new experiment
        """
        # setup request layer
        self.request = TestRequest()
        # get add view
        form = getMultiAdapter((self.experiments, self.request),
                               name="newEnsemble")
        # update the form once to initialise all widgets
        form.update()
        # go through all widgets on the form  and update the request with
        # default values
        data = {}
        for widget in form.widgets.values():
            data[widget.name] = widget.value
        data.update({
            'form.widgets.IDublinCore.title': u"My EN Experiment",
            'form.widgets.IDublinCore.description': u'This is my experiment description',
            'form.widgets.experiment_type': ISDMExperiment.__identifier__,
            'form.widgets.datasets.count': '1',
            'form.widgets.datasets.item.0': unicode(self.sdmexp.UID()),
            'form.widgets.datasets.item.0.item': [unicode(self.sdmproj.UID())],
        })
        self.request.form.update(data)
        form = getMultiAdapter((self.experiments, self.request),
                               name="newEnsemble")
        return form

    def mock_run_script(self, *args, **kw):
        # simulate a script run
        wrapper, params, context = args
        # 1. write file into results_dir
        tmpdir = urlsplit(params['result']['results_dir']).path
        try:
            # 2. create some result files
            for fname in ('ensemble.tif',):
                img = Image.new('F', (10, 10))
                img.save(os.path.join(tmpdir, fname), 'TIFF')
            # 3. store results
            items = [
                {
                    'file': {
                        'url': 'file://{}/ensemble.tif'.format(tmpdir),
                        'contenttype': 'image/tiff',
                        'filename': 'ensemble.tif',
                    },
                    'title': 'Ensemble Output',
                    'description': 'Ensemble Output Description',
                    'bccvlmetadata': {
                        'genre': 'DataGenreEnsembleResult',
                    },
                    'filemetadata': {
                        'band': [{
                            'min': 0.0,
                            'STATISTICS_MINIMUM': 0.0,
                            'max': 1.0
                        }]
                    },
                    'layermd': {},
                }
            ]
            # TODO: tasks called dierctly here; maybe call them as tasks as
            # well? (chain?)
            import_result_job(items, params['result'][
                              'results_dir'], context).delay()
            import_cleanup(params['result']['results_dir'], context)
            set_progress('COMPLETED', 'Test Task succeeded', None, context)
        except Exception as e:
            # 4. clean up if problem otherwise import task cleans up
            #    TODO: should be done by errback or whatever
            import_cleanup(params['result']['results_dir'], context)
            set_progress('FAILED', 'Test Task failed', None, context)
            raise


class SpeciesTraitsExperimentHelper(object):
    """
    A helper class to configure and run a SDM experiment during testing.
    """

    def __init__(self, portal):
        # configure local variables on instance
        self.portal = portal
        self.experiments = self.portal[defaults.EXPERIMENTS_FOLDER_ID]
        self.algorithm = self.portal[
            defaults.TOOLKITS_FOLDER_ID]['speciestrait_glm']
        # get some dataset shortcuts
        self.datasets = self.portal[defaults.DATASETS_FOLDER_ID]
        self.traitsds = self.datasets['traits.csv']

    def get_form(self):
        """
        fill out common stuff when creating a new experiment
        """
        # setup request layer
        self.request = TestRequest()
        # get add view
        form = getMultiAdapter((self.experiments, self.request),
                               name="newSpeciesTraits")
        # update the form once to initialise all widgets
        form.update()
        # go through all widgets on the form  and update the request with
        # default values
        data = {}
        for widget in chain(
                # form fields
                form.widgets.values(),
                # param group fields
                chain.from_iterable(g.widgets.values()
                                    for param_group in form.param_groups.values() for g in param_group),
                # param group fieldset fields
                chain.from_iterable(sg.widgets.values() for param_group in form.param_groups.values() for g in param_group for sg in g.groups)):
            data[widget.name] = widget.value
        data.update({
            'form.widgets.IDublinCore.title': u"My ST Experiment",
            'form.widgets.IDublinCore.description': u'This is my experiment description',
            'form.widgets.algorithms_species': [self.algorithm.UID()],
            'form.widgets.species_traits_dataset': [unicode(self.traitsds.UID())],
            'form.widgets.species_traits_dataset_params': {
                u'species': u'species',
                u'lon': u'lon',
                u'lat': u'lat',
                u't1': u'trait_con',
                u't2': u'trait_cat',
                u'e1': u'env_var_con',
                u'e2': u'env_var_cat',
            }
        })
        self.request.form.update(data)
        form = getMultiAdapter((self.experiments, self.request),
                               name="newSpeciesTraits")
        return form

    def mock_run_script(self, *args, **kw):
        # simulate a script run
        wrapper, params, context = args
        # 1. write file into results_dir
        tmpdir = urlsplit(params['result']['results_dir']).path
        try:
            for fname in ('model.RData',
                          'traits.txt'):
                open(os.path.join(tmpdir, fname), 'w').write('Mock Result')
            # 3. store results
            items = [
                {
                    'file': {
                        'url': 'file://{}/model.RData'.format(tmpdir),
                        'contenttype': 'application/x-r-data',
                        'filename': 'model.RData',
                    },
                    'title': 'Model Title',
                    'description': 'Model Description',
                    'bccvlmetadata': {
                        'genre': 'DataGenreSTModel',
                    },
                    'filemetadata': {},
                    'layermd': {}
                },
                {
                    'file': {
                        'url': 'file://{}/traits.txt'.format(tmpdir),
                        'contenttype': 'text/plain',
                        'filename': 'traits.txt',
                    },
                    'title': 'Test Traits',
                    'description': 'Test Traits Description',
                    'bccvlmetadata': {
                        'genre': 'DataGenreSTResult',
                    },
                    'filemetadata': {},
                    'layermd': {},
                }
            ]
            # TODO: tasks called dierctly here; maybe call them as tasks as
            # well? (chain?)
            import_result_job(items, params['result'][
                              'results_dir'], context).delay()
            import_cleanup(params['result']['results_dir'], context)
            set_progress('COMPLETED', 'Test Task succeeded', None, context)
        except Exception as e:
            # 4. clean up if problem otherwise import task cleans up
            #    TODO: should be done by errback or whatever
            import_cleanup(params['result']['results_dir'], context)
            set_progress('FAILED', 'Test Task failed', None, context)
            raise
