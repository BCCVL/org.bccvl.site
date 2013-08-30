import unittest2 as unittest

from zope.component import createObject
from zope.component import queryUtility

from plone.app.testing import SITE_OWNER_NAME
from plone.app.testing import SITE_OWNER_PASSWORD
from plone.app.testing import TEST_USER_ID, setRoles
from plone.testing.z2 import Browser

from org.bccvl.site import defaults
from org.bccvl.site.testing import BCCVL_FUNCTIONAL_TESTING


# do somebrowser testing here:
# 1. test new template
# - create new experiment (make sure content is here)
# - check view page for elements
# - see plone.app.contenttypes browser tests for how to

class ExperimentFunctionalTest(unittest.TestCase):

    layer = BCCVL_FUNCTIONAL_TESTING

    def setUp(self):
        app = self.layer['app']
        self.portal = self.layer['portal']
        self.portal_url = self.portal.absolute_url()
        self.experiments_url = '/'.join((self.portal_url, defaults.EXPERIMENTS_FOLDER_ID))
        self.experiments_add_url = '/'.join((self.experiments_url,
                                           '++add++org.bccvl.content.experiment'))
        self.browser = Browser(app)
        # make publisher errors avilable
        self.browser.handleErrors = False
        # ignore http errors (we can still inspect e.g. 404 errors on the browser)
        # self.browser.raiseHttpErrors= False
        self.browser.addHeader(
            'Authorization',
            'Basic %s:%s' % (SITE_OWNER_NAME, SITE_OWNER_PASSWORD,)
        )

    def test_add_experiment(self):
        self.browser.open(self.experiments_url)
        self.browser.getLink(url=self.experiments_add_url).click()
        self.browser.getControl(name='form.widgets.IDublinCore.title')\
            .value = "My Experiment"
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
        self.browser.getControl('Save').click()
        self.assertTrue('Required input is missing' in self.browser.contents)
        self.assertEquals(self.browser.url, self.experiments_add_url)

        # self.assertTrue(self.browser.url.endswith('my-experiment'))
        # self.assertTrue('My Experiment' in self.browser.contents)
        # self.assertTrue('This is my experiment' in self.browser.contents)
        # check for submit button


class ExperimentsViewFunctionalTest(unittest.TestCase):

    layer = BCCVL_FUNCTIONAL_TESTING

    def setUp(self):
        app = self.layer['app']
        self.portal = self.layer['portal']
        self.request = self.layer['request']
        setRoles(self.portal, TEST_USER_ID, ['Manager'])
        self.experiments = self.portal[defaults.EXPERIMENTS_FOLDER_ID]
        self.experiments_url = self.experiments.absolute_url()
        self.experiments.invokeFactory('org.bccvl.content.experiment', id='exp', title='My Experiment')
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
