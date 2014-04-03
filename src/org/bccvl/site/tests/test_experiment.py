import unittest2 as unittest
from urlparse import urljoin
import re

from zope.component import createObject
from zope.component import queryUtility

from plone.app.testing import SITE_OWNER_NAME
from plone.app.testing import SITE_OWNER_PASSWORD
from plone.app.testing import TEST_USER_ID, setRoles
from plone.testing.z2 import Browser

from org.bccvl.site import defaults
from org.bccvl.site.interfaces import IJobTracker
from org.bccvl.site.testing import BCCVL_FUNCTIONAL_TESTING
from org.bccvl.site.testing import BCCVL_ASYNC_FUNCTIONAL_TESTING
from org.bccvl.site.namespace import BIOCLIM, BCCVOCAB

from zc.async.testing import wait_for_result


# do somebrowser testing here:
# 1. test new template
# - create new experiment (make sure content is here)
# - check view page for elements
# - see plone.app.contenttypes browser tests for how to

class ExperimentAddTest(unittest.TestCase):

    layer = BCCVL_ASYNC_FUNCTIONAL_TESTING

    def setUp(self):
        app = self.layer['app']
        self.portal = self.layer['portal']
        self.portal_url = self.portal.absolute_url()
        self.experiments_url = '/'.join((self.portal_url, defaults.EXPERIMENTS_FOLDER_ID))
        self.experiments_add_url = '/'.join((self.experiments_url,
                                           '++add++org.bccvl.content.sdmexperiment'))
        self.browser = Browser(app)
        # make publisher errors avilable
        self.browser.handleErrors = False
        # ignore http errors (we can still inspect e.g. 404 errors on the browser)
        # self.browser.raiseHttpErrors= False
        self.browser.addHeader(
            'Authorization',
            'Basic %s:%s' % (SITE_OWNER_NAME, SITE_OWNER_PASSWORD,)
        )

    def test_add_experiment_missing_input(self):
        self.browser.open(self.experiments_url)
        self.browser.getLink(url=self.experiments_add_url).click()
        # uncomment set title as long as I don't know how to send any
        # other field without value
        #self.browser.getControl(name='form.widgets.IDublinCore.title')\
        #    .value = "My Experiment"
        self.browser.getControl(name='form.widgets.IDublinCore.description')\
            .value = "This is my experiment description."
        # form.widgets.functions:list
        # form.widgets.species_occurrence_dataset:list
        # form.widgets.species_absence_dataset:list
        # form.widgets.species_environmental_dataset:list
        # get listcontrol options and get/set value
        # control.options/ control.value
        # get listcontrol display options and get/set display value
        #  control.displayOptions/ control.displayValue
        # get sub controls (items)
        # control.controls/ control.getControls
        # itemcontrol.selected (get/set selcted state)
        # form.widgets.species_climate_dataset:list
        self.browser.getControl('Create and start').click()
        self.assertTrue('Required input is missing' in self.browser.contents)
        self.assertEquals(self.browser.url, self.experiments_add_url)

        # self.assertTrue(self.browser.url.endswith('my-experiment'))
        # self.assertTrue('My Experiment' in self.browser.contents)
        # self.assertTrue('This is my experiment' in self.browser.contents)
        # check for submit button

    def in_out_select(self, form, name, value):
        """
        little helper to deal with in-out widget.

        form ... the form we are manipulating
        name ... the name of the target control to generate
        value ... the value to submit with the new control
        """
        form.mech_form.new_control(
            type='hidden', name=name,
            attrs=dict(value=value))

    def test_add_experiment(self):
        self.browser.open(self.experiments_url)
        self.browser.getLink(url=self.experiments_add_url).click()
        self.browser.getControl(name='form.widgets.IDublinCore.title')\
            .value = "My Experiment"
        self.browser.getControl(name='form.widgets.IDublinCore.description')\
            .value = "This is my experiment description."
        self.browser.getControl(name='form.widgets.functions:list')\
            .displayValue = ["Bioclim"]
        self.browser.getControl(name='form.widgets.species_occurrence_dataset:list')\
            .displayValue = ["ABT"]
        # self.browser.getControl(name='form.widgets.species_absence_dataset:list')\
        #     .displayValue = ["ABT"]
        # select two layers in test dataset
        self.browser.getControl(name='form.widgets.resolution:list')\
            .value = [unicode(BCCVOCAB['Resolution30s'])]

        datasets = self.portal[defaults.DATASETS_FOLDER_ID][defaults.DATASETS_ENVIRONMENTAL_FOLDER_ID]
        curuid = datasets['current'].UID()  # get current datasets uuid
        cbname = 'form.widgets.environmental_datasets.{}.select'.format(curuid)
        # select current dataset
        self.browser.getControl(name=cbname).value = [curuid]
        # select 1st two layers within current dataset
        lname = 'form.widgets.environmental_datasets.{}:list'.format(curuid)
        form = self.browser.getForm(index=1)
        self.in_out_select(form, lname, str(BIOCLIM['B01']))
        self.in_out_select(form, lname, str(BIOCLIM['B02']))

        # form.widgets.functions:list
        # form.widgets.species_occurrence_dataset:list
        # form.widgets.species_absence_dataset:list
        # form.widgets.species_environmental_dataset:list
        # get listcontrol options and get/set value
        # control.options/ control.value
        # get listcontrol display options and get/set display value
        #  control.displayOptions/ control.displayValue
        # get sub controls (items)
        # control.controls/ control.getControls
        # itemcontrol.selected (get/set selcted state)
        # form.widgets.species_climate_dataset:list
        self.browser.getControl('Create and start').click()
        self.assertTrue('Item created' in self.browser.contents)
        self.assertTrue('Job submitted' in self.browser.contents)
        new_exp_url = urljoin(self.experiments_add_url, 'my-experiment/view')
        self.assertEquals(self.browser.url, new_exp_url)
        self.assertTrue('My Experiment' in self.browser.contents)
        self.assertTrue('This is my experiment description' in self.browser.contents)
        self.assertTrue("Job submitted [('testalgorithm', u'Queued')]" in self.browser.contents)
        # wait for job to finish
        self._wait_for_job('my-experiment')
        self.browser.open(new_exp_url)
        self.assertTrue('Completed' in self.browser.contents)
        # TODO:
        # check for submit button; should be grayed?

    def test_run_experiment_twice(self):
        # create experiment
        self.browser.open(self.experiments_url)
        self.browser.getLink(url=self.experiments_add_url).click()
        self.browser.getControl(name='form.widgets.IDublinCore.title')\
            .value = "My Experiment"
        self.browser.getControl(name='form.widgets.IDublinCore.description')\
            .value = "This is my experiment description."
        self.browser.getControl(name='form.widgets.functions:list')\
            .displayValue = ["Bioclim"]
        self.browser.getControl(name='form.widgets.species_occurrence_dataset:list')\
            .displayValue = ["ABT"]
        # self.browser.getControl(name='form.widgets.species_absence_dataset:list')\
        #     .displayValue = ["ABT"]
        # select two layers in test dataset
        datasets = self.portal[defaults.DATASETS_FOLDER_ID][defaults.DATASETS_ENVIRONMENTAL_FOLDER_ID]
        curuid = datasets['current'].UID()  # get current datasets uuid
        cbname = 'form.widgets.environmental_datasets.{}.select'.format(curuid)
        # select current dataset
        self.browser.getControl(name=cbname).value = [curuid]
        # select 1st two layers within current dataset
        lname = 'form.widgets.environmental_datasets.{}:list'.format(curuid)
        form = self.browser.getForm(index=1)
        self.in_out_select(form, lname, str(BIOCLIM['B01']))
        self.in_out_select(form, lname, str(BIOCLIM['B02']))
        # start
        self.browser.getControl('Create and start').click()
        self.assertTrue('Item created' in self.browser.contents)
        self.assertTrue('Job submitted' in self.browser.contents)
        new_exp_url = urljoin(self.experiments_add_url, 'my-experiment/view')
        self.assertEquals(self.browser.url, new_exp_url)
        self.assertTrue("Job submitted [('testalgorithm', u'Queued')]" in self.browser.contents)
        # wait for result
        self._wait_for_job('my-experiment')
        # reload exp page and check for status on page
        self.browser.open(new_exp_url)
        self.assertTrue('Completed' in self.browser.contents)
        # TODO: check Result list
        results = re.findall(r'<a href=.*My Experiment - bioclim.*</a>', self.browser.contents)
        self.assertEqual(len(results), 1)
        # start again
        self.browser.getControl('Start Job').click()
        self.assertTrue('Job submitted' in self.browser.contents)
        self._wait_for_job('my-experiment')
        # reload experiment page
        self.browser.open(new_exp_url)
        self.assertTrue('Completed' in self.browser.contents)
        # We should have two results now
        results = re.findall(r'<a href=.*My Experiment - bioclim.*</a>', self.browser.contents)
        self.assertEqual(len(results), 2)

    def _wait_for_job(self, expid):
        exp = self.portal[defaults.EXPERIMENTS_FOLDER_ID][expid]
        jobs = IJobTracker(exp).get_jobs()
        for job in jobs:
            wait_for_result(job, seconds=30)
        # TODO: check if we only have error messages if at all?
        # if job.result is not None:
        #     job.result.raiseException()


class ExperimentsViewFunctionalTest(unittest.TestCase):

    layer = BCCVL_FUNCTIONAL_TESTING

    def setUp(self):
        app = self.layer['app']
        self.portal = self.layer['portal']
        self.request = self.layer['request']
        self.experiments = self.portal[defaults.EXPERIMENTS_FOLDER_ID]
        self.experiments_url = self.experiments.absolute_url()
        # this creates an experiment with no values set at all
        self.experiments.invokeFactory('org.bccvl.content.sdmexperiment', id='exp', title='My Experiment')
        self.exp = self.experiments['exp']
        self.exp_url = self.exp.absolute_url()
        import transaction
        transaction.commit()
        self.browser = Browser(app)
        self.browser.handleErrors = False
        self.browser.addHeader(
            'Authorization',
            'Basic %s:%s' % (SITE_OWNER_NAME, SITE_OWNER_PASSWORD,)
        )

    def test_experiment_view(self):
        self.browser.open(self.exp_url + '/view')
        self.assertTrue('My Experiment' in self.browser.contents)
        self.assertTrue('Start Job' in self.browser.contents)
        # check for themeing target
        self.assertTrue('<div id="bccvl-experiment-view">' in self.browser.contents)
