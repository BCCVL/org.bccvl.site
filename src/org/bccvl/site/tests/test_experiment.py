import unittest2 as unittest
from urlparse import urljoin
import re
import time
import transaction

from zope.component import createObject
from zope.component import queryUtility

from plone.app.testing import SITE_OWNER_NAME
from plone.app.testing import SITE_OWNER_PASSWORD

from org.bccvl.site import defaults
from org.bccvl.site.interfaces import IJobTracker, IBCCVLMetadata
from org.bccvl.site.testing import (BCCVL_INTEGRATION_TESTING,
                                    BCCVL_FUNCTIONAL_TESTING)
from org.bccvl.site.tests.utils import TestRequest, SDMExperimentHelper, ProjectionExperimentHelper





# do somebrowser testing here:
# 1. test new template
# - create new experiment (make sure content is here)
# - check view page for elements
# - see plone.app.contenttypes browser tests for how to

class ExperimentSDMAddTest(unittest.TestCase):

    # Use functional layer for now to get a new demostorage layer for each test
    layer = BCCVL_FUNCTIONAL_TESTING
    # integration testing gives only a new transaction for each test (rolled back at end)
    #layer = BCCVL_INTEGRATION_TESTING

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

    def test_add_experiment(self):
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
        self.assertEqual(exp.environmental_datasets.keys(), [unicode(self.form.current.UID())])
        self.assertEqual(exp.environmental_datasets.values(), [set([u'B01', u'B02'])])
        # get result container: (there is only one)
        self.assertEqual(len(exp.objectIds()), 1)
        result = exp.objectValues()[0]
        # FIXME: test result.job_params
        self.assertEqual(result.job_params['function'], 'bioclim')
        self.assertEqual(result.job_params['environmental_datasets'], exp.environmental_datasets)
        # no result files yet
        self.assertEqual(len(result.keys()), 0)
        # test job state
        jt = IJobTracker(exp)
        self.assertEqual(jt.state, u'QUEUED')
        # after transaction commit the job sholud finish
        transaction.commit()
        self.assertEqual(jt.state, u'COMPLETED')
        # and we should have a result as well
        self.assertGreaterEqual(len(result.keys()), 1)
        # TODO: assrt two result folders,....
        # TODO: check mix of jt.state (in multistate scenario with queued, running etc. mixed)

    def test_run_experiment_twice(self):
        # create experiment
        form = self.form.get_form()
        form.request.form.update({
            'form.buttons.save': 'Create and start',
            })
        # update form with updated request
        form.update()
        # start experiment
        jt = IJobTracker(self.experiments['my-experiment'])
        self.assertEqual(jt.state, u'QUEUED')
        #error
        state = jt.start_job(form.request)
        self.assertEqual(state[0], 'error')
        # finish current job
        transaction.commit()
        self.assertEqual(jt.state, u'COMPLETED')
        # TODO: after commit tasks cause site to disappear and the
        # following code will fail, bceause without site we can't find
        # a catalog without whchi we can't finde the toolkit by uuid
        jt.start_job(form.request)
        # FIXME: why is this running? (would a transaction abort work as well? to refresh my object?)
        self.assertEqual(jt.state, u'RUNNING')
        transaction.commit()
        self.assertEqual(jt.state, u'COMPLETED')

    def test_mixed_resolution(self):
        current_1k_uuid = unicode(self.datasets[defaults.DATASETS_ENVIRONMENTAL_FOLDER_ID]['current_1k'].UID())
        form = self.form.get_form()
        form.request.form.update({
            'form.buttons.create': 'Create',
            # select 1k dataset as well
            'form.widgets.environmental_datasets.dataset.2': current_1k_uuid,
            'form.widgets.environmental_datasets.layer.2': u'B01'
        })
        form.update()
        # resolution should be set to the lowest of selected datasets
        expmd = IBCCVLMetadata(self.experiments['my-experiment'])
        self.assertEqual(expmd['resolution'], 'Resolution2_5m')


class ExperimentProjectionAddTest(unittest.TestCase):

    # Use functional layer for now to get a new demostorage layer for each test
    layer = BCCVL_FUNCTIONAL_TESTING
    # integration testing gives only a new transaction for each test (rolled back at end)
    #layer = BCCVL_INTEGRATION_TESTING

    def setUp(self):
        self.portal = self.layer['portal']
        self.experiments = self.portal[defaults.EXPERIMENTS_FOLDER_ID]
        self.datasets = self.portal[defaults.DATASETS_FOLDER_ID]
        # create and run sdm experiment
        sdmform = SDMExperimentHelper(self.portal).get_form()
        sdmform.request.form.update({
            'form.buttons.save': 'Create and start',
            })
        # update form with updated request
        sdmform.update()
        transaction.commit()
        # We should have only one SDM
        sdmexp = self.experiments.values()[0]
        self.form = ProjectionExperimentHelper(self.portal, sdmexp)
        # TODO: setup shortcuts suitable for CC
        #   need 2 future datasets with different resolutions
        #   need 2 raster datasets for input, to check fallback of non-future layer

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

    def test_add_experiment(self):
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
        self.assertEqual(exp.future_climate_datasets, [unicode(self.form.future.UID())])
        # FIXME: submitting with an empty model list doesn't cause form to fail
        self.assertEqual(exp.species_distribution_models,
                         { self.form.sdmexp.UID(): [self.form.sdmmodel.UID()] })

        # get result container: (there is only one)
        self.assertEqual(len(exp.objectIds()), 1)
        result = exp.objectValues()[0]
        # FIXME: test result.job_params
        self.assertEqual(result.job_params['future_climate_datasets'],
                         {exp.future_climate_datasets[0]: set([u'B01',
                                                               u'B02'])})
        self.assertEqual(result.job_params['species_distribution_models'], exp.species_distribution_models.values()[0][0])  # only one experiment so only first model
        self.assertEqual(result.job_params['resolution'], u'Resolution30m')
        self.assertEqual(result.job_params['emsc'], u'RCP3PD')
        self.assertEqual(result.job_params['gcm'], u'cccma-cgcm31')
        self.assertEqual(result.job_params['year'], u'2015')        
        # no result files yet
        self.assertEqual(len(result.keys()), 0)
        # test job state
        jt = IJobTracker(exp)
        self.assertEqual(jt.state, u'QUEUED')
        # after transaction commit the job should finish
        transaction.commit()
        self.assertEqual(jt.state, u'COMPLETED')
        # and we should have a result as well
        self.assertGreaterEqual(len(result.keys()), 1)
        # TODO: check result metadata

    def test_mixed_resolution(self):
        future_1k_uuid = unicode(self.datasets[defaults.DATASETS_CLIMATE_FOLDER_ID]['future_1k'].UID())
        form = self.form.get_form()
        form.request.form.update({
            'form.buttons.save': 'Create and start',
            # select 1k dataset as well
            'form.widgets.future_climate_datasets': [future_1k_uuid],
        })
        form.update()
        # run experiment
        transaction.commit()
        exp = self.experiments['my-cc-experiment']
        result = exp.values()[0]
        expmd = IBCCVLMetadata(exp)
        # We should have the missing layers filled by sdm env layer datasets
        self.assertEqual(result.job_params['future_climate_datasets'],
                         {future_1k_uuid: set([u'B01']),
                          self.form.sdmexp.environmental_datasets.keys()[0]: set([u'B02'])})
        # resolution should be set to the lowest of selected datasets
        self.assertEqual(expmd['resolution'], 'Resolution2_5m')
        

# Biodiverse: ... no real validation here
# Ensemble: ... does resolution adaption
# SpeciesTraits: ... has toolkit sub forms

class ExperimentSDMViewTest(unittest.TestCase):

    pass

    # shall I have test data or run an experiment?
    #   e.g. create something programmatically with invokeFactory just for this test
