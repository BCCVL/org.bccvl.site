import os.path
import org.bccvl.site.tests
from zope.component import getUtility
from plone.testing import z2
from plone.app.testing import login
from plone.app.testing import SITE_OWNER_NAME
from plone.app.testing import TEST_USER_NAME
from plone.app.testing import PLONE_SITE_ID
from plone.app.testing import PloneSandboxLayer
from plone.app.testing import PLONE_FIXTURE
from plone.app.testing import IntegrationTesting
from plone.app.testing import FunctionalTesting
# from plone.app.async.testing import AsyncLayer
# from plone.app.async.testing import AsyncFunctionalTesting
from plone.app.async.testing import registerAsyncLayers
# from plone.app.async.testing import PLONE_APP_ASYNC_FIXTURE
from org.bccvl.site.namespace import BCCVOCAB, BCCPROP, NFO
from org.bccvl.site import defaults
from gu.z3cform.rdf.interfaces import IORDF, IGraph
from plone.namedfile.file import NamedBlobFile
from collective.transmogrifier.transmogrifier import Transmogrifier
from rdflib import Literal


TESTCSV = '\n'.join(['%s, %d, %d' % ('Name', x, x + 1) for x in range(1, 10)])
TESTSDIR = os.path.dirname(org.bccvl.site.tests.__file__)


def getFile(filename):
    """ return contents of the file with the given name """
    filename = os.path.join(os.path.dirname(__file__), filename)
    return open(filename, 'r')


class BCCVLLayer(PloneSandboxLayer):

    defaultBases = (PLONE_FIXTURE, )

    def setUpZope(self, app, configurationContext):
        # load ZCML and use z2.installProduct here
        self.loadZCML('testing.zcml', package=org.bccvl.site.tests)
        z2.installProduct(app, 'Products.membrane')
        z2.installProduct(app, 'plone.app.folderui')
        z2.installProduct(app, 'Products.DateRecurringIndex')

    def setUpPloneSite(self, portal):
        # base test fixture sets default chain to nothing
        pwf = portal['portal_workflow']
        pwf.setDefaultChain('simple_publication_workflow')
        # use testing profile, to avoid trubles with collective.geo.mapwidget
        self.applyProfile(portal, 'org.bccvl.site.tests:testing')
        # TODO: consider the following as alternative to set up content
        # setRoles(portal, TEST_USER_ID, ['Manager'])
        # login(portal, TEST_USER_NAME)
        # do stuff
        # setRoles(portal, TEST_USER_ID, ['Member'])
        app = portal.getPhysicalRoot()
        z2.login(app['acl_users'], SITE_OWNER_NAME)
        self.addTestContent(portal)
        login(portal, TEST_USER_NAME)

    def tearDownZope(self, app):
        z2.uninstallProduct(app, 'Products.DateRecurringIndex')
        z2.uninstallProduct(app, 'plone.app.folderui')
        z2.uninstallProduct(app, 'Products.membrane')

    def updateMetadata(self, context, mdgraph):
        rdfhandler = getUtility(IORDF).getHandler()
        # TODO: the transaction should take care of
        #       donig the diff
        cc = rdfhandler.context(user='Importer',
                                reason='Test data')
        cc.add(mdgraph)
        cc.commit()
        context.reindexObject()

    def addTestContent(self, portal):
        # TODO get rid of this modue hack
        from org.bccvl import compute
        from org.bccvl.site.tests.compute import testalgorithm
        compute.testalgorithm = testalgorithm

        transmogrifier = Transmogrifier(portal)
        transmogrifier(u'org.bccvl.site.dataimport',
                       source={'path': 'org.bccvl.site.tests:data'})
        # update metadata on imported content:
        # TODO: sholud be done in transomgrifier step
        from rdflib import Graph, URIRef
        from org.bccvl.site.namespace import BIOCLIM
        rdfhandler = getUtility(IORDF).getHandler()
        current = portal.datasets.environmental.current
        g = IGraph(current)
        for fid, i in ((URIRef("http://example.com/file%02d" % i), i)
                    for i in range(1, 3)):
            f = Graph(identifier=fid)
            f.add((fid,  BIOCLIM['bioclimVariable'], BIOCLIM['B%02d' % i]))
            f.add((fid,  NFO['fileName'], Literal('file%02d' % i)))
            g.add((g.identifier, BCCPROP['hasArchiveItem'], f.identifier))
            rdfhandler.put(f)
        rdfhandler.put(g)
        current.reindexObject()


BCCVL_FIXTURE = BCCVLLayer()

BCCVL_INTEGRATION_TESTING = IntegrationTesting(
    bases=(BCCVL_FIXTURE, ),
    name="BCCVLFixture:Integration")

BCCVL_FUNCTIONAL_TESTING = FunctionalTesting(
    bases=(BCCVL_FIXTURE, z2.ZSERVER_FIXTURE),
    name="BCCVLFixture:Functional")


# Async Layers

# don't name this class to anything that might appear in ASYNC_LAYERS list
# otherwise the plone.app.async db monkey patch might kick in
class BCCVLAsyncLayer(PloneSandboxLayer):
    # install and set up plone.app.async

    defaultBases = (BCCVL_FIXTURE, )
    #need a layer hear, ... teardown orders them wrong

    def setUpZope(self, app, configurationContext):
        #self._stuff = Zope2.bobo_application._stuff
        z2.installProduct(app, 'Products.PythonScripts')
        import plone.app.async
        self.loadZCML('configure.zcml', package=plone.app.async)

    def tearDownZope(self, app):
        z2.uninstallProduct(app, 'Products.PythonScripts')


class BCCVLAsyncFunctionalTesting(FunctionalTesting):

    def testSetUp(self):
        # do proper db stacking and async db setup
        from plone.testing import zodb
        from ZODB import DB
        from ZODB.DemoStorage import DemoStorage
        db = zodb.stackDemoStorage(self.get('zodbDB'), name="BCCVLAsyncFunctionalTesting")
        async_db = DB(DemoStorage(name='async'), database_name='async')
        db = DB(db.storage,
                databases={'async': async_db})
        self['zodbDB'] = db

        # do z2.FunctionalTesting stuff here
        import Zope2
        import transaction

        # Save the app

        environ = {
            'SERVER_NAME': self['host'],
            'SERVER_PORT': str(self['port']),
        }

        app = z2.addRequestContainer(Zope2.app(), environ=environ)
        request = app.REQUEST
        request['PARENTS'] = [app]

        # Make sure we have a zope.globalrequest request
        try:
            from zope.globalrequest import setRequest
            setRequest(request)
        except ImportError:
            pass

        # Start a transaction
        transaction.begin()

        # Save resources for the test
        self['app'] = app
        self['request'] = request

        # also do PloneTestLifeCycle stuff here
        self['portal'] = portal = self['app'][PLONE_SITE_ID]
        self.setUpEnvironment(portal)

        from zope import component
        from plone.app.async.testing import cleanUpDispatcher
        from plone.app.async.testing import _dispatcher_uuid
        from plone.app.async.testing import setUpQueue
        from plone.app.async.testing import setUpDispatcher
        from zc.async.subscribers import agent_installer
        from zc.async.interfaces import IDispatcherActivated
        from plone.app.async.subscribers import notifyQueueReady, configureQueue
        from plone.app.async.interfaces import IAsyncDatabase, IQueueReady
        component.provideUtility(async_db, IAsyncDatabase)
        component.provideHandler(agent_installer, [IDispatcherActivated])
        component.provideHandler(notifyQueueReady, [IDispatcherActivated])
        component.provideHandler(configureQueue, [IQueueReady])
        setUpQueue(db)
        setUpDispatcher(db, _dispatcher_uuid)
        transaction.commit()

    def testTearDown(self):
        # first tear down async stuff
        import transaction
        from zope import component
        from plone.app.async.testing import cleanUpDispatcher
        from plone.app.async.testing import _dispatcher_uuid
        from zc.async.subscribers import agent_installer
        from zc.async.interfaces import IDispatcherActivated
        from plone.app.async.interfaces import IAsyncDatabase, IQueueReady
        from plone.app.async.subscribers import notifyQueueReady, configureQueue
        cleanUpDispatcher(_dispatcher_uuid)
        gsm = component.getGlobalSiteManager()
        gsm.unregisterHandler(agent_installer, [IDispatcherActivated])
        gsm.unregisterHandler(notifyQueueReady, [IDispatcherActivated])
        gsm.unregisterHandler(configureQueue, [IQueueReady])
        db = gsm.getUtility(IAsyncDatabase)
        gsm.unregisterUtility(db, IAsyncDatabase)
        # then tear down z2.FunctionalTesting things
        super(BCCVLAsyncFunctionalTesting, self).testTearDown()


# use this one to setup async in current test instance
BCCVL_ASYNC_FIXTURE = BCCVLAsyncLayer()

# put only one layer that does zodb stacking in bases list, otherwise tearDown
# may be called in wrong order, and zodb will be unstacked in the wrong order
# causes AttributeError: 'DB' object has no attribute 'storage'
BCCVL_ASYNC_FUNCTIONAL_TESTING = BCCVLAsyncFunctionalTesting(
    bases=(BCCVL_ASYNC_FIXTURE, z2.ZSERVER_FIXTURE),
    name="BCCVLAsyncFixture:Functional")
