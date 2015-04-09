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
        "CELERY_IGNORE_RESULT":  True,
        "CELERY_ACCEPT_CONTENT":  ["json", "msgpack", "yaml"],
        "CELERY_IMPORTS":  [
            #"org.bccvl.tasks.plone",
            "org.bccvl.site.tests.compute"],
        "CELERY_ROUTES": [
            {"org.bccvl.tasks.plone.set_progress": {"queue": "plone", "routing_key": "plone"}},
            {"org.bccvl.tasks.plone.import_ala": {"queue": "plone", "routing_key": "plone"}},
            {"org.bccvl.tasks.plone.import_cleanup": {"queue": "plone", "routing_key": "plone"}},
            {"org.bccvl.tasks.plone.import_result": {"queue": "plone", "routing_key": "plone"}},
            {"org.bccvl.tasks.datamover.move": {"queue": "datamover", "routing_key": "datamover"}},
            {"org.bccvl.tasks.ala_import.ala_import": {"queue": "datamover", "routing_key": "datamover"}},
            {"org.bccvl.tasks.compute.r_task": {"queue": "worker", "routing_key": "worker"}},
            {"org.bccvl.tasks.compute.perl_task": {"queue": "worker", "routing_key": "worker"}}
        ],
        "CELERY_TASK_SERIALIZER": "json",
        "CELERY_QUEUES": {
            "worker": {"routing_key": "worker"},
            "datamover": {"routing_key": "datamover"},
            "plone": {"routing_key": "plone"}
        },
        # Things we don't want during testing
        'CELERYD_HIJACK_ROOT_LOGGER': False,
        'CELERY_SEND_TASK_ERROR_EMAILS': False,
        'CELERY_ENABLE_UTC': True,
        'CELERY_TIMEZONE': 'UTC',
        'CELERYD_LOG_COLOR': False,
        'CELERY_ALWAYS_EAGER': True
    }

    from org.bccvl.tasks import celery
    # import ipdb; ipdb.set_trace()
    celery.app.config_from_object(CELERY_CONFIG)

    # worker = celery.app.WorkController(celery.app, pool_cls='solo',
    #                                    concurrency=1,
    #                                    log_level=logging.DEBUG)
    # t = Thread(target=worker.start)
    # t.daemon = True
    # t.start()
    # return worker


def getFile(filename):
    """ return contents of the file with the given name """
    filename = os.path.join(os.path.dirname(__file__), filename)
    return open(filename, 'r')


class BCCVLLayer(PloneSandboxLayer):

    defaultBases = (PLONE_FIXTURE, )

    def setUp(self):
        # TODO: rename to startCelery
        self.worker = configureCelery()
        super(BCCVLLayer, self).setUp()

    def setUpZope(self, app, configurationContext):
        # load ZCML and use z2.installProduct here
        self.loadZCML('testing.zcml', package=org.bccvl.site.tests)
        z2.installProduct(app, 'plone.app.folderui')
        z2.installProduct(app, 'Products.DateRecurringIndex')

    def setUpPloneSite(self, portal):
        # base test fixture sets default chain to nothing
        pwf = portal['portal_workflow']
        pwf.setDefaultChain('simple_publication_workflow')
        # use testing profile, to avoid trubles with collective.geo.mapwidget
        self.applyProfile(portal, 'org.bccvl.site.tests:testing')
        # FIXME: for testing we access the site via localhost,
        #        so we can't use the localscript extraction plugin
        from Products.PluggableAuthService.interfaces.plugins import IAuthenticationPlugin
        portal.acl_users.plugins.deactivatePlugin(IAuthenticationPlugin, 'localscript')

        app = portal.getPhysicalRoot()
        z2.login(app['acl_users'], SITE_OWNER_NAME)
        self.addTestContent(portal)
        # run all tests as our new test user
        login(portal, TEST_USER_NAME)

    def tearDown(self):
        # self.worker.stop()
        super(BCCVLLayer, self).tearDown()

    def tearDownZope(self, app):
        z2.uninstallProduct(app, 'Products.DateRecurringIndex')
        z2.uninstallProduct(app, 'plone.app.folderui')

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
