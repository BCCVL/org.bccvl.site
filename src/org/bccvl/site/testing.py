import os.path
import org.bccvl.site.tests
from zope.component import getUtility
from plone.testing import z2
from plone.app.testing import login
from plone.app.testing import SITE_OWNER_NAME
from plone.app.testing import TEST_USER_NAME
from plone.app.testing import PloneSandboxLayer
from plone.app.testing import PLONE_FIXTURE
from plone.app.testing import IntegrationTesting
from plone.app.testing import FunctionalTesting
from org.bccvl.site.namespace import BCCVOCAB, BCCPROP
from org.bccvl.site import defaults
from gu.z3cform.rdf.interfaces import IORDF
from gu.repository.content.interfaces import IRepositoryMetadata


TESTCSV = '\n'.join(['%s, %d, %d' % ('Name', x, x + 1) for x in range(1, 10)])
TESTSDIR = os.path.dirname(org.bccvl.site.tests.__file__)


def getFile(filename):
    """ return contents of the file with the given name """
    filename = os.path.join(os.path.dirname(__file__), filename)
    return open(filename, 'r')


class BCCVLFixture(PloneSandboxLayer):

    defaultBases = (PLONE_FIXTURE, )

    def setUpZope(self, app, configurationContext):
        # load ZCML and use z2.installProduct here
        self.loadZCML('testing.zcml', package=org.bccvl.site.tests)
        z2.installProduct(app, 'Products.membrane')
        z2.installProduct(app, 'plone.app.folderui')

        # FIXME: hack a config together...
        from App.config import getConfiguration
        cfg = getConfiguration()
        cfg.product_config = {'gu.plone.rdf': {
            'inifile': os.path.join(TESTSDIR, 'ordf.ini'),
            }}

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
        z2.uninstallProduct(app, 'Products.membrane')
        z2.uninstallProduct(app, 'plone.app.folderui')

    def updateMetadata(self, context, mdgraph):
        rdfhandler = getUtility(IORDF).getHandler()
        cc = rdfhandler.context(user='Importer',
                                reason='Test data')
        cc.add(mdgraph)
        cc.commit()
        context.reindexObject()

    def addTestContent(self, portal):
        dsf = portal[defaults.DATASETS_FOLDER_ID]
        # Species Observation data
        spf = dsf[defaults.DATASETS_SPECIES_FOLDER_ID]
        abtid = spf.invokeFactory('gu.repository.content.RepositoryItem',
                                title=u"ABT",
                                id="ABT")
        abt = spf[abtid]
        abtmd = IRepositoryMetadata(abt)
        abtmd.add((abtmd.identifier, BCCPROP['datagenre'], BCCVOCAB['DataGenreSO']))
        abtmd.add((abtmd.identifier, BCCPROP['specieslayer'], BCCVOCAB['SpeciesLayerP']))
        self.updateMetadata(abt, abtmd)
        spf.invokeFactory('File', title="occurence.csv",
                                id="occurence.csv",
                                file=TESTCSV)
        abt.invokeFactory('File', title="bkgd.csv",
                          id="bkgd.csv",
                          file=TESTCSV)
        # Environmental Data
        edf = dsf[defaults.DATASETS_ENVIRONMENTAL_FOLDER_ID]
        curid = edf.invokeFactory('gu.repository.content.RepositoryItem',
                                  title=u'Current',
                                  id='current')
        cur = edf[curid]
        curmd = IRepositoryMetadata(cur)
        curmd.add((curmd.identifier, BCCPROP['datagenre'], BCCVOCAB['DataGenreE']))
        self.updateMetadata(cur, curmd)
        # TODO: add files?
        # Functions
        funcf = portal[defaults.FUNCTIONS_FOLDER_ID]
        funcid = funcf.invokeFactory('gu.repository.content.RepositoryItem',
                                     title=u"Bioclim",
                                     id="bioclim")
        # TODO: add func metadata here


BCCVL_FIXTURE = BCCVLFixture()

BCCVL_INTEGRATION_TESTING = IntegrationTesting(
    bases=(BCCVL_FIXTURE, ),
    name="BCCVLFixutre:Integration")

TEST_ASYNC = True
if not TEST_ASYNC:

    BCCVL_FUNCTIONAL_TESTING = FunctionalTesting(
        bases=(BCCVL_FIXTURE, z2.ZSERVER_FIXTURE),
        name="BCCVLFixutre:Functional")

else:

    from plone.app.async.testing import AsyncLayer
    from plone.app.async.testing import AsyncFunctionalTesting
    from plone.app.async.testing import registerAsyncLayers

    class BCCVLAsyncLayer(AsyncLayer):

        defaultBases = (BCCVL_FIXTURE, )

        def setUpPloneSite(self,  portal):
            # do nothing here, all the setup already done in
            # base layers
            pass

    BCCVL_ASYNC_FIXTURE = BCCVLAsyncLayer()

    BCCVL_FUNCTIONAL_TESTING = AsyncFunctionalTesting(
        bases=(BCCVL_ASYNC_FIXTURE, z2.ZSERVER_FIXTURE),
        name="BCCVLFixutre:Functional")

    registerAsyncLayers([BCCVL_ASYNC_FIXTURE,
                         BCCVL_FUNCTIONAL_TESTING])
