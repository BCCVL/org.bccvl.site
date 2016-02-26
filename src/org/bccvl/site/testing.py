import os.path
import org.bccvl.site.tests
from plone.testing import z2
from plone.app.testing import login
from plone.app.testing import SITE_OWNER_NAME
from plone.app.testing import TEST_USER_NAME
from plone.app.testing import PloneSandboxLayer
from plone.app.testing import PLONE_FIXTURE
from plone.app.testing import IntegrationTesting
from plone.app.testing import FunctionalTesting
from collective.transmogrifier.transmogrifier import Transmogrifier


TESTCSV = '\n'.join(['%s, %d, %d' % ('Name', x, x + 1) for x in range(1, 10)])
TESTSDIR = os.path.dirname(org.bccvl.site.tests.__file__)


def configureCelery():
    CELERY_CONFIG = {
        "BROKER_URL": "memory://",
        'CELERY_RESULT_BACKEND': 'cache+memory://',
        "CELERY_IMPORTS":  [
            "org.bccvl.tasks.datamover",
            "org.bccvl.tasks.plone",
            "org.bccvl.tasks.compute",
        ],
        # Things we don't want during testing
        'CELERYD_HIJACK_ROOT_LOGGER': False,
        'CELERY_SEND_TASK_ERROR_EMAILS': False,
        'CELERY_ENABLE_UTC': True,
        'CELERY_TIMEZONE': 'UTC',
        'CELERYD_LOG_COLOR': False,
        'CELERY_ALWAYS_EAGER': True
    }

    from org.bccvl.tasks import celery
    celery.app.config_from_object(CELERY_CONFIG)


def getFile(filename):
    """ return contents of the file with the given name """
    filename = os.path.join(os.path.dirname(__file__), filename)
    return open(filename, 'r')


class BCCVLLayer(PloneSandboxLayer):

    defaultBases = (PLONE_FIXTURE, )

    def setUp(self):
        # TODO: rename to startCelery
        configureCelery()
        super(BCCVLLayer, self).setUp()

    def setUpZope(self, app, configurationContext):
        # load ZCML and use z2.installProduct here
        self.loadZCML('testing.zcml', package=org.bccvl.site.tests)
        z2.installProduct(app, 'Products.DateRecurringIndex')

    def setUpPloneSite(self, portal):
        # base test fixture sets default chain to nothing
        pwf = portal['portal_workflow']
        pwf.setDefaultChain('simple_publication_workflow')
        # apply configuration profile
        self.applyProfile(portal, 'org.bccvl.site:default')
        app = portal.getPhysicalRoot()
        z2.login(app['acl_users'], SITE_OWNER_NAME)
        self.addTestContent(portal)
        # run all tests as our new test user
        login(portal, TEST_USER_NAME)

    def tearDownZope(self, app):
        z2.uninstallProduct(app, 'Products.DateRecurringIndex')

    def addTestContent(self, portal):
        transmogrifier = Transmogrifier(portal)
        transmogrifier(u'org.bccvl.site.dataimport',
                       source={'path': 'org.bccvl.site.tests:data'})


BCCVL_FIXTURE = BCCVLLayer()

BCCVL_INTEGRATION_TESTING = IntegrationTesting(
    bases=(BCCVL_FIXTURE, ),
    name="BCCVLFixture:Integration")

BCCVL_FUNCTIONAL_TESTING = FunctionalTesting(
    bases=(BCCVL_FIXTURE, z2.ZSERVER_FIXTURE),
    name="BCCVLFixture:Functional")
