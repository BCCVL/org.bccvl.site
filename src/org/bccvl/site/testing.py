#from plone.app.contenttypes.testing import PLONE_APP_CONTENTTYPES_FIXTURE
from plone.app.testing import PLONE_FIXTURE
from plone.app.testing import PloneSandboxLayer
from plone.app.testing import SITE_OWNER_NAME
from plone.app.testing import IntegrationTesting
from plone.app.testing import FunctionalTesting
from plone.testing import z2
from org.bccvl.site import defaults
import os.path

TESTCSV = '\n'.join(['%s, %d, %d' % ('Name', x, x + 1) for x in range(1, 10)])


def getFile(filename):
    """ return contents of the file with the given name """
    filename = os.path.join(os.path.dirname(__file__), filename)
    return open(filename, 'r')


class BCCVLFixture(PloneSandboxLayer):

    defaultBases = (PLONE_FIXTURE, )

    def setUpZope(self, app, configurationContext):
        # load ZCML and use z2.installProduct here
        import org.bccvl.site.tests
        self.loadZCML('testing.zcml', package=org.bccvl.site.tests)
        #self.loadZCML(os.path.join(os.path.dirname(__file__), 'tests/testing.zcml'))
        z2.installProduct(app, 'Products.membrane')
        z2.installProduct(app, 'plone.app.folderui')

        # FIXME: hack a config together...
        from App.config import getConfiguration
        cfg = getConfiguration()
        cfg.product_config = {'gu.plone.rdf': {
            'inifile': '/Users/gerhard/Documents/Projects/Uni/workspace_bccvl/bccvl_buildout/etc/ordf.ini',
            }}

    def setUpPloneSite(self, portal):
        # base test fixture sets default chain to nothing
        portal['portal_workflow'].setDefaultChain('simple_publication_workflow')
        # use testing profile, to avoid trubles with collective.geo.mapwidget
        self.applyProfile(portal, 'org.bccvl.site.tests:testing')
        self.addTestContent(portal)

    def tearDownZope(self, app):
        z2.uninstallProduct(app, 'Products.membrane')
        z2.uninstallProduct(app, 'plone.app.folderui')

    def addTestContent(self, portal):
        from Acquisition import aq_parent
        from AccessControl import getSecurityManager
        from AccessControl.SecurityManagement import setSecurityManager

        sm = getSecurityManager()
        app = aq_parent(portal)

        z2.login(app['acl_users'], SITE_OWNER_NAME)

        try:
            dsf = portal[defaults.DATASETS_FOLDER_ID]
            spf = dsf[defaults.DATASETS_SPECIES_FOLDER_ID]
            abtid = spf.invokeFactory('gu.repository.content.RepositoryItem',
                                    title=u"ABT",
                                    id="ABT")
            abt = spf[abtid]
            occid =  spf.invokeFactory('File', title="occurence.csv",
                                    id="occurence.csv",
                                    file=TESTCSV)
            absid = abt.invokeFactory('File', title="bkgd.csv",
                                    id="bkgd.csv",
                                    file=TESTCSV)
        finally:
            setSecurityManager(sm)
            pass



BCCVL_FIXTURE =  BCCVLFixture()

BCCVL_INTEGRATION_TESTING = IntegrationTesting(bases=(BCCVL_FIXTURE,), name="BCCVLFixutre:Integration")
BCCVL_FUNCTIONAL_TESTING = FunctionalTesting(bases=(BCCVL_FIXTURE, z2.ZSERVER_FIXTURE), name="BCCVLFixutre:Functional")
