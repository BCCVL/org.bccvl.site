import unittest
from decimal import Decimal

import mock
import transaction

from org.bccvl.site import defaults
from org.bccvl.site.interfaces import IBCCVLMetadata
from org.bccvl.site.interfaces import IExperimentJobTracker
from org.bccvl.site.testing import BCCVL_FUNCTIONAL_TESTING
from org.bccvl.site.tests.utils import SDMExperimentHelper
from org.bccvl.site.tests.utils import ProjectionExperimentHelper
from org.bccvl.site.tests.utils import BiodiverseExperimentHelper
from org.bccvl.site.tests.utils import EnsembleExperimentHelper
from org.bccvl.site.tests.utils import SpeciesTraitsExperimentHelper

# do somebrowser testing here:
# 1. test new template
# - create new experiment (make sure content is here)
# - check view page for elements
# - see plone.app.contenttypes browser tests for how to



class ExperimentSDMAddTest(unittest.TestCase):

    # Use functional layer for now to get a new demostorage layer for each test
    layer = BCCVL_FUNCTIONAL_TESTING
    # integration testing gives only a new transaction for each test
    # (rolled back at end)
    # layer = BCCVL_INTEGRATION_TESTING

    def setUp(self):
        self.portal = self.layer['portal']
        self.experiments = self.portal[defaults.EXPERIMENTS_FOLDER_ID]
        self.datasets = self.portal[defaults.DATASETS_FOLDER_ID]
        self.form = SDMExperimentHelper(self.portal)

    def test_add_experiment_missing_input(self):
        form = self.form.get_form()
        # remove required field
        del form.request.form['form.widgets.IDublinCore.title']
        form.request.form.update({
            'form.buttons.create': 'Create',
        })
        # submit form
        form.update()
        errors = [e for e in form.widgets.errors]
        self.assertEqual(len(errors), 1)
        # check self.experiments still empty
        # IStatusMessage

    @mock.patch('org.bccvl.tasks.compute.run_script')
    def test_add_experiment(self, mock_run_script):
        form = self.form.get_form()
        form.request.form.update({
            'form.buttons.save': 'Create and start',
        })
        # update form with updated request
        form.update()
        self.assertEqual(form.status, u'')
        self.assertEqual(len(form.widgets.errors), 0)
        self.assertIn('my-experiment', self.experiments)
        exp = self.experiments['my-experiment']
        self.assertEqual(exp.environmental_datasets.keys(),
                         [unicode(self.form.current.UID())])
        self.assertEqual(exp.environmental_datasets.values(),
                         [set([u'B01', u'B02'])])
        # get result container: (there is only one)
        self.assertEqual(len(exp.objectIds()), 1)
        result = exp.objectValues()[0]
        # FIXME: test result.job_params
        self.assertEqual(result.job_params['function'], 'bioclim')
        self.assertEqual(result.job_params[
                         'environmental_datasets'], exp.environmental_datasets)
        # no result files yet
        self.assertEqual(len(result.keys()), 0)
        # test job state
        jt = IExperimentJobTracker(exp)
        self.assertEqual(jt.state, u'QUEUED')
        # setup mock_run_script
        mock_run_script.side_effect = self.form.mock_run_script
        # after transaction commit the job sholud finish
        transaction.commit()
        self.assertEqual(jt.state, u'COMPLETED')
        # and we should have a result as well
        self.assertGreaterEqual(len(result.keys()), 1)
        # TODO: assrt two result folders,....
        # TODO: check mix of jt.state (in multistate scenario with queued,
        # running etc. mixed)

    @mock.patch('org.bccvl.tasks.compute.run_script')
    def test_run_experiment_twice(self, mock_run_script):
        # create experiment
        form = self.form.get_form()
        form.request.form.update({
            'form.buttons.save': 'Create and start',
        })
        # update form with updated request
        form.update()
        # start experiment
        jt = IExperimentJobTracker(self.experiments['my-experiment'])
        self.assertEqual(jt.state, u'QUEUED')
        # error
        state = jt.start_job(form.request)
        self.assertEqual(state[0], 'error')
        # setup mock_run_script
        mock_run_script.side_effect = self.form.mock_run_script
        # finish current job
        transaction.commit()
        self.assertEqual(jt.state, u'COMPLETED')
        # TODO: after commit tasks cause site to disappear and the
        # following code will fail, bceause without site we can't find
        # a catalog without whchi we can't finde the toolkit by uuid
        jt.start_job(form.request)
        self.assertEqual(jt.state, u'RUNNING')
        transaction.commit()
        self.assertEqual(jt.state, u'COMPLETED')

    def test_mixed_resolution_highest(self):
        current_1k_uuid = unicode(
            self.datasets[defaults.DATASETS_ENVIRONMENTAL_FOLDER_ID]['current_1k'].UID())
        form = self.form.get_form()
        form.request.form.update({
            'form.buttons.create': 'Create',
            # select 1k dataset as well
            'form.widgets.scale_down': 'true',
            'form.widgets.scale_down-empty-marker': 1,
            'form.widgets.environmental_datasets.item.2': current_1k_uuid,
            'form.widgets.environmental_datasets.item.2.item': [u'B01'],
            'form.widgets.environmental_datasets.count': '3',
        })
        form.update()
        # resolution should be set to the lowest of selected datasets
        expmd = IBCCVLMetadata(self.experiments['my-experiment'])
        self.assertEqual(expmd['resolution'], 'Resolution30s')

    def test_mixed_resolution_lowest(self):
        current_1k_uuid = unicode(
            self.datasets[defaults.DATASETS_ENVIRONMENTAL_FOLDER_ID]['current_1k'].UID())
        form = self.form.get_form()
        form.request.form.update({
            'form.buttons.create': 'Create',
            # select 1k dataset as well
            'form.widgets.scale_down': 'false',
            'form.widgets.scale_down-empty-marker': 1,
            'form.widgets.environmental_datasets.item.2': current_1k_uuid,
            'form.widgets.environmental_datasets.item.2.item': [u'B01'],
            'form.widgets.environmental_datasets.count': '3',
        })
        form.update()
        # resolution should be set to the lowest of selected datasets
        expmd = IBCCVLMetadata(self.experiments['my-experiment'])
        self.assertEqual(expmd['resolution'], 'Resolution2_5m')


class ExperimentProjectionAddTest(unittest.TestCase):

    # Use functional layer for now to get a new demostorage layer for each test
    layer = BCCVL_FUNCTIONAL_TESTING
    # integration testing gives only a new transaction for each test
    # (rolled back at end)
    # layer = BCCVL_INTEGRATION_TESTING

    @mock.patch('org.bccvl.tasks.compute.run_script')
    def setUp(self, mock_run_script):
        self.portal = self.layer['portal']
        self.experiments = self.portal[defaults.EXPERIMENTS_FOLDER_ID]
        self.datasets = self.portal[defaults.DATASETS_FOLDER_ID]
        # create and run sdm experiment
        formhelper = SDMExperimentHelper(self.portal)
        sdmform = formhelper.get_form()
        sdmform.request.form.update({
            'form.buttons.save': 'Create and start',
        })
        # update form with updated request
        sdmform.update()
        # setup mock_run_script
        mock_run_script.side_effect = formhelper.mock_run_script
        transaction.commit()
        # We should have only one SDM
        sdmexp = self.experiments.values()[0]
        self.form = ProjectionExperimentHelper(self.portal, sdmexp)
        # TODO: setup shortcuts suitable for CC
        #   need 2 future datasets with different resolutions
        # need 2 raster datasets for input, to check fallback of non-future
        # layer

    def test_add_experiment_missing_input(self):
        form = self.form.get_form()
        # remove required field
        del form.request.form['form.widgets.IDublinCore.title']
        form.request.form.update({
            'form.buttons.create': 'Create',
        })
        # submit form
        form.update()
        errors = [e for e in form.widgets.errors]
        self.assertEqual(len(errors), 1)
        # check self.experiments still empty
        # IStatusMessage

    @mock.patch('org.bccvl.tasks.compute.run_script')
    def test_add_experiment(self, mock_run_script):
        form = self.form.get_form()
        form.request.form.update({
            'form.buttons.save': 'Create and start',
        })
        # update form with updated request
        form.update()
        self.assertEqual(form.status, u'')
        self.assertEqual(len(form.widgets.errors), 0)
        self.assertIn('my-cc-experiment', self.experiments)
        exp = self.experiments['my-cc-experiment']
        # TODO: update asserts
        self.assertEqual(exp.future_climate_datasets, [
                         unicode(self.form.future.UID())])
        # FIXME: submitting with an empty model list doesn't cause form to fail
        self.assertEqual(exp.species_distribution_models,
                         {self.form.sdmexp.UID(): [self.form.sdmmodel.UID()]})

        # get result container: (there is only one)
        self.assertEqual(len(exp.objectIds()), 1)
        result = exp.objectValues()[0]
        # FIXME: test result.job_params
        self.assertEqual(result.job_params['future_climate_datasets'],
                         {exp.future_climate_datasets[0]: set([u'B01',
                                                               u'B02'])})
        # only one experiment so we only need to check first model
        self.assertEqual(result.job_params['species_distribution_models'],
                         exp.species_distribution_models.values()[0][0])
        self.assertEqual(result.job_params['resolution'], u'Resolution30m')
        self.assertEqual(result.job_params['emsc'], u'RCP3PD')
        self.assertEqual(result.job_params['gcm'], u'cccma-cgcm31')
        self.assertEqual(result.job_params['year'], 2015)
        # no result files yet
        self.assertEqual(len(result.keys()), 0)
        # test job state
        jt = IExperimentJobTracker(exp)
        self.assertEqual(jt.state, u'QUEUED')
        # setup mock_run_script
        mock_run_script.side_effect = self.form.mock_run_script
        # after transaction commit the job should finish
        transaction.commit()
        self.assertEqual(jt.state, u'COMPLETED')
        # and we should have a result as well
        self.assertGreaterEqual(len(result.keys()), 1)
        # TODO: check result metadata

    @mock.patch('org.bccvl.tasks.compute.run_script')
    def test_mixed_resolution(self, mock_run_script):
        future_1k_uuid = unicode(
            self.datasets[defaults.DATASETS_CLIMATE_FOLDER_ID]['future_1k'].UID())
        form = self.form.get_form()
        form.request.form.update({
            'form.buttons.save': 'Create and start',
            # select 1k dataset as well
            'form.widgets.future_climate_datasets': [future_1k_uuid],
        })
        form.update()
        # setup mock_run_script
        mock_run_script.side_effect = self.form.mock_run_script
        # run experiment
        transaction.commit()
        exp = self.experiments['my-cc-experiment']
        result = exp.values()[0]
        expmd = IBCCVLMetadata(exp)
        # We should have the missing layers filled by sdm env layer datasets
        self.assertEqual(
            result.job_params['future_climate_datasets'],
            {
                future_1k_uuid: set([u'B01']),
                self.form.sdmexp.environmental_datasets.keys()[0]: set([u'B02'])
            }
        )
        # resolution should be set to the lowest of selected datasets
        self.assertEqual(expmd['resolution'], 'Resolution2_5m')


class ExperimentBiodiverseAddTest(unittest.TestCase):

    # Use functional layer for now to get a new demostorage layer for each test
    layer = BCCVL_FUNCTIONAL_TESTING
    # integration testing gives only a new transaction for each test
    # (rolled back at end)
    # layer = BCCVL_INTEGRATION_TESTING

    @mock.patch('org.bccvl.tasks.compute.run_script')
    def setUp(self, mock_run_script):
        self.portal = self.layer['portal']
        self.experiments = self.portal[defaults.EXPERIMENTS_FOLDER_ID]
        # create and run sdm experiment
        formhelper = SDMExperimentHelper(self.portal)
        sdmform = formhelper.get_form()
        sdmform.request.form.update({
            'form.buttons.save': 'Create and start',
        })
        # update form with updated request
        sdmform.update()
        # setup mock_run_script
        mock_run_script.side_effect = formhelper.mock_run_script
        # We should have only one SDM
        sdmexp = self.experiments.values()[0]
        transaction.commit()
        # setup som threshold values our projection
        sdmproj = sdmexp.values()[0]['proj_test.tif']
        md = IBCCVLMetadata(sdmproj)
        # there is only one layer
        layermd = md['layers'].values()[0]
        layermd['min'] = 0.0
        layermd['max'] = 1.0
        transaction.commit()
        self.form = BiodiverseExperimentHelper(self.portal, sdmexp)

    def test_add_experiment_missing_input(self):
        form = self.form.get_form()
        # remove required field
        del form.request.form['form.widgets.IDublinCore.title']
        form.request.form.update({
            'form.buttons.create': 'Create',
        })
        # submit form
        form.update()
        errors = [e for e in form.widgets.errors]
        self.assertEqual(len(errors), 1)
        # check self.experiments still empty
        # IStatusMessage

    @mock.patch('org.bccvl.tasks.compute.run_script')
    def test_add_experiment(self, mock_run_script):
        form = self.form.get_form()
        form.request.form.update({
            'form.buttons.save': 'Create and start',
        })
        # update form with updated request
        form.update()
        self.assertEqual(form.status, u'')
        self.assertEqual(len(form.widgets.errors), 0)
        self.assertIn('my-bd-experiment', self.experiments)
        exp = self.experiments['my-bd-experiment']
        # TODO: update asserts
        self.assertEqual(exp.projection,
                         {unicode(self.form.sdmexp.UID()):
                          {unicode(self.form.sdmproj.UID()): {'value': Decimal('0.5'), 'label': '0.5'}}})
        # FIXME: submitting with an empty model list doesn't cause form to fail
        self.assertEqual(exp.cluster_size, 5000)

        # get result container: (there is only one)
        self.assertEqual(len(exp.objectIds()), 1)
        result = exp.objectValues()[0]
        # FIXME: test result.job_params
        self.assertEqual(result.job_params['cluster_size'], 5000)
        self.assertEqual(result.job_params['projections'], [{
            "dataset": self.form.sdmproj.UID(),
            "threshold": {'label': '0.5', 'value': Decimal('0.5')}}])
        # no result files yet
        self.assertEqual(len(result.keys()), 0)
        # test job state
        jt = IExperimentJobTracker(exp)
        self.assertEqual(jt.state, u'QUEUED')
        # setup mock_run_script
        mock_run_script.side_effect = self.form.mock_run_script
        # after transaction commit the job should finish
        transaction.commit()
        self.assertEqual(jt.state, u'COMPLETED')
        # and we should have a result as well
        self.assertGreaterEqual(len(result.keys()), 1)
        # TODO: check result metadata


class ExperimentEnsembleAddTest(unittest.TestCase):

    # Use functional layer for now to get a new demostorage layer for each test
    layer = BCCVL_FUNCTIONAL_TESTING
    # integration testing gives only a new transaction for each test
    # (rolled back at end)
    # layer = BCCVL_INTEGRATION_TESTING

    @mock.patch('org.bccvl.tasks.compute.run_script')
    def setUp(self, mock_run_script):
        self.portal = self.layer['portal']
        self.experiments = self.portal[defaults.EXPERIMENTS_FOLDER_ID]
        # create and run sdm experiment
        formhelper = SDMExperimentHelper(self.portal)
        sdmform = formhelper.get_form()
        sdmform.request.form.update({
            'form.buttons.save': 'Create and start',
        })
        # update form with updated request
        sdmform.update()
        # setup mock_run_script
        mock_run_script.side_effect = formhelper.mock_run_script
        transaction.commit()
        # We should have only one SDM
        sdmexp = self.experiments.values()[0]
        self.form = EnsembleExperimentHelper(self.portal, sdmexp)

    def test_add_experiment_missing_input(self):
        form = self.form.get_form()
        # remove required field
        del form.request.form['form.widgets.IDublinCore.title']
        form.request.form.update({
            'form.buttons.create': 'Create',
        })
        # submit form
        form.update()
        errors = [e for e in form.widgets.errors]
        self.assertEqual(len(errors), 1)
        # check self.experiments still empty
        # IStatusMessage

    @mock.patch('org.bccvl.tasks.compute.run_script')
    def test_add_experiment(self, mock_run_script):
        form = self.form.get_form()
        form.request.form.update({
            'form.buttons.save': 'Create and start',
        })
        # update form with updated request
        form.update()
        self.assertEqual(form.status, u'')
        self.assertEqual(len(form.widgets.errors), 0)
        self.assertIn('my-en-experiment', self.experiments)
        exp = self.experiments['my-en-experiment']
        self.assertEqual(exp.datasets,
                         {unicode(self.form.sdmexp.UID()):
                          [unicode(self.form.sdmproj.UID())]})
        # get result container: (there is only one)
        self.assertEqual(len(exp.objectIds()), 1)
        result = exp.objectValues()[0]
        # FIXME: test result.job_params
        self.assertEqual(result.job_params['datasets'],
                         [unicode(self.form.sdmproj.UID())])
        self.assertEqual(result.job_params['resolution'], u'Resolution30s')
        # no result files yet
        self.assertEqual(len(result.keys()), 0)
        # test job state
        jt = IExperimentJobTracker(exp)
        self.assertEqual(jt.state, u'QUEUED')
        # setup mock_run_script
        mock_run_script.side_effect = self.form.mock_run_script
        # after transaction commit the job should finish
        transaction.commit()
        self.assertEqual(jt.state, u'COMPLETED')
        # and we should have a result as well
        self.assertGreaterEqual(len(result.keys()), 1)
        # TODO: check result metadata


class ExperimentSpeciesTraitsAddTest(unittest.TestCase):

    # Use functional layer for now to get a new demostorage layer for each test
    layer = BCCVL_FUNCTIONAL_TESTING
    # integration testing gives only a new transaction for each test
    # (rolled back at end)
    # layer = BCCVL_INTEGRATION_TESTING

    def setUp(self):
        self.portal = self.layer['portal']
        self.experiments = self.portal[defaults.EXPERIMENTS_FOLDER_ID]
        self.form = SpeciesTraitsExperimentHelper(self.portal)

    def test_add_experiment_missing_input(self):
        form = self.form.get_form()
        # remove required field
        del form.request.form['form.widgets.IDublinCore.title']
        form.request.form.update({
            'form.buttons.create': 'Create',
        })
        # submit form
        form.update()
        errors = [e for e in form.widgets.errors]
        self.assertEqual(len(errors), 1)
        # check self.experiments still empty
        # IStatusMessage

    @mock.patch('org.bccvl.tasks.compute.run_script')
    def test_add_experiment(self, mock_run_script):
        form = self.form.get_form()
        form.request.form.update({
            'form.buttons.save': 'Create and start',
        })
        # update form with updated request
        form.update()
        self.assertEqual(form.status, u'')
        self.assertEqual(len(form.widgets.errors), 0)
        self.assertIn('my-st-experiment', self.experiments)
        exp = self.experiments['my-st-experiment']
        # TODO: update asserts
        self.assertEqual(exp.data_table, unicode(self.form.traitsds.UID()))
        self.assertEqual(exp.algorithm, unicode(self.form.algorithm.UID()))
        self.assertEqual(exp.formula, u'Z ~ X + Y')
        # FIXME: submitting with an empty model list doesn't cause form to fail
        # get result container: (there is only one)
        self.assertEqual(len(exp.objectIds()), 1)
        result = exp.objectValues()[0]
        # FIXME: test result.job_params
        self.assertEqual(result.job_params[
                         'algorithm'], self.form.algorithm.getId())
        self.assertEqual(result.job_params['data_table'], unicode(
            self.form.traitsds.UID()))
        # no result files yet
        self.assertEqual(len(result.keys()), 0)
        # test job state
        jt = IExperimentJobTracker(exp)
        self.assertEqual(jt.state, u'QUEUED')
        # setup mock_run_script
        mock_run_script.side_effect = self.form.mock_run_script
        # after transaction commit the job should finish
        transaction.commit()
        self.assertEqual(jt.state, u'COMPLETED')
        # and we should have a result as well
        self.assertGreaterEqual(len(result.keys()), 1)
        # TODO: check result metadata


class ExperimentSDMViewTest(unittest.TestCase):

    pass

    # shall I have test data or run an experiment?
    # e.g. create something programmatically with invokeFactory just for this
    # test
