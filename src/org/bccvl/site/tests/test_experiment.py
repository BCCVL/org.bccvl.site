import unittest2 as unittest
from urlparse import urljoin
import re
import time
from itertools import chain
import transaction

from zope.component import createObject
from zope.component import queryUtility

from plone.app.testing import SITE_OWNER_NAME
from plone.app.testing import SITE_OWNER_PASSWORD

from zope.component import getMultiAdapter

from org.bccvl.site import defaults
from org.bccvl.site.interfaces import IJobTracker
from org.bccvl.site.testing import (BCCVL_INTEGRATION_TESTING,
                                    BCCVL_FUNCTIONAL_TESTING)


from zope.interface import alsoProvides, implementer
from plone.app.z3cform.interfaces import IPloneFormLayer
from zope.publisher.browser import TestRequest as TestRequestBase
from zope.annotation.interfaces import IAttributeAnnotatable


@implementer(IPloneFormLayer, IAttributeAnnotatable)
class TestRequest(TestRequestBase):
    """Zope 3's TestRequest doesn't support item assignment, but Zope 2's
    request does.
    """
    def __setitem__(self, key, value):
        pass


# do somebrowser testing here:
# 1. test new template
# - create new experiment (make sure content is here)
# - check view page for elements
# - see plone.app.contenttypes browser tests for how to

class ExperimentAddTest(unittest.TestCase):

    # Use functional layer for now to get a new demostorage layer for each test
    layer = BCCVL_FUNCTIONAL_TESTING
    # integration testing gives only a new transaction for each test (rolled back at end)
    #layer = BCCVL_INTEGRATION_TESTING

    def setUp(self):
        self.portal = self.layer['portal']
        self.experiments = self.portal[defaults.EXPERIMENTS_FOLDER_ID]
        # get some dataset shortcuts
        self.algorithm = self.portal[defaults.TOOLKITS_FOLDER_ID]['bioclim']
        self.datasets = self.portal[defaults.DATASETS_FOLDER_ID]
        abt = self.datasets[defaults.DATASETS_SPECIES_FOLDER_ID]['ABT']
        self.occur = abt['occurrence.csv']
        self.absen = abt['absence.csv']
        self.current = self.datasets[defaults.DATASETS_ENVIRONMENTAL_FOLDER_ID]['current']

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
        # go through all widgets on the form  and update the request with default values
        data = {}
        for widget in chain(
                form.widgets.values(),
                # skip standard plone groups
                #chain.from_iterable(g.widgets.values() for g in form.groups),
                chain.from_iterable(g.widgets.values() for g in form.param_groups)):
            data[widget.name] = widget.value
        data.update({
            'form.widgets.IDublinCore.title': u"My Experiment",
            'form.widgets.IDublinCore.description': u'This is my experiment description',
            'form.widgets.functions': [self.algorithm.UID()],  # BIOCLIM
            'form.widgets.species_occurrence_dataset': unicode(self.occur.UID()),  # ABT
            'form.widgets.species_absence_dataset': unicode(self.absen.UID()),
            'form.widgets.species_absence_points': [],
            'form.widgets.resolution': ('Resolution2_5m', ),
            # FIXME: shouldn't be necessary to use unicode here,... widget converter should take care of it
            'form.widgets.environmental_datasets.dataset.0': unicode(self.current.UID()),
            'form.widgets.environmental_datasets.layer.0': u'B01',
            'form.widgets.environmental_datasets.dataset.1': unicode(self.current.UID()),
            'form.widgets.environmental_datasets.layer.1': u'B02',
            'form.widgets.environmental_datasets.count': '3',
        })
        self.request.form.update(data)
        form = getMultiAdapter((self.experiments, self.request),
                               name="newSpeciesDistribution")
        return form

    def test_add_experiment_missing_input(self):
        form = self.get_form()
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
        form = self.get_form()
        form.request.form.update({
            'form.buttons.save': 'Create and start',
            })
        # update form with updated request
        form.update()
        self.assertEqual(form.status, u'')
        self.assertEqual(len(form.widgets.errors), 0)
        self.assertIn('my-experiment', self.experiments)
        exp = self.experiments['my-experiment']
        self.assertEqual(exp.environmental_datasets.keys(), [unicode(self.current.UID())])
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

    def test_run_experiment_twice(self):
        # create experiment
        form = self.get_form()
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
        # FIXME: why is this running?
        self.assertEqual(jt.state, u'RUNNING')
        transaction.commit()
        self.assertEqual(jt.state, u'COMPLETED')
        # TODO: assrt two result folders,....
        # TODO: check mix of jt.state (in multistate scenario with queued, running etc. mixed)

    def test_validate_resolution(self):
        current_1k_uuid = unicode(self.datasets[defaults.DATASETS_ENVIRONMENTAL_FOLDER_ID]['current_1k'].UID())
        form = self.get_form()
        form.request.form.update({
            'form.buttons.create': 'Create',
            # select 1k dataset as well
            'form.widgets.environmental_datasets.dataset.2': current_1k_uuid,
            'form.widgets.environmental_datasets.layer.2': u'B01'
        })
        form.update()
        # we should have a resolution mismatch error here
        errors = [e for e in form.widgets.errors]
        self.assertEqual(len(errors), 1)


class ExperimentViewTest(unittest.TestCase):

    pass

    # shall I have test data or run an experiment?
    #   e.g. create something programmatically with invokeFactory just for this test
