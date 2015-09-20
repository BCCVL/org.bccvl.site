from Products.CMFCore.utils import getToolByName
from Products.PluggableAuthService.interfaces.plugins import IAuthenticationPlugin
from Products.PluggableAuthService.interfaces.plugins import IExtractionPlugin
from plone import api
from zope.annotation.interfaces import IAnnotations
from zope.interface import alsoProvides
from org.bccvl.site import defaults
import logging


LOG = logging.getLogger(__name__)
PROFILE_ID = 'profile-org.bccvl.site:default'
PROFILE = 'org.bccvl.site'


AUTH_SCRIPT = """
# check for credentials extracted by extraction script
ipRangeKey = creds.get('ipRangeKey')
if ipRangeKey is None:
    return None
return ('admin', 'admin')
"""


EXTRACT_SCRIPT = """
credentials = {}

# get client IP
clientIP = (request.get('HTTP_X_FORWARDED_FOR') or
            request.get('REMOTE_ADDR', None))
if not clientIP:
    return None

# examine request for IP range
if clientIP.lower() in ('127.0.0.1', 'localhost'):
    credentials['ipRangeKey'] = 'allow'
return credentials
"""


def setupVarious(context, logger=None):
    if logger is None:
        logger = LOG
    logger.info('BCCVL site package setup handler')

    # only run for this product
    if context.readDataFile('org.bccvl.site.marker.txt') is None:
        return
    portal = context.getSite()

    # install Products.AutoUserMakerPASPLugin
    qi = getToolByName(portal, 'portal_quickinstaller')
    if 'AutoUserMakerPASPLugin' in (p['id'] for
                                    p in qi.listInstallableProducts()):
        qi.installProduct('AutoUserMakerPASPlugin')

    # install local login pas plugin
    acl = portal.acl_users
    if not 'localscript' in acl:
        factory = acl.manage_addProduct['PluggableAuthService']
        factory.addScriptablePlugin('localscript', 'Local manager access')
    plugin = acl['localscript']
    # add scripts
    factory = plugin.manage_addProduct['PythonScripts']
    if 'extractCredentials' not in plugin:
        factory.manage_addPythonScript('extractCredentials')
        alsoProvides(plugin, IExtractionPlugin)
        script = plugin['extractCredentials']
        script.ZPythonScript_edit('request', EXTRACT_SCRIPT)
    if 'authenticateCredentials' not in plugin:
        factory.manage_addPythonScript('authenticateCredentials')
        script = plugin['authenticateCredentials']
        script.ZPythonScript_edit('creds', AUTH_SCRIPT)
        alsoProvides(plugin, IAuthenticationPlugin)
    if 'localscript' not in acl.plugins.listPluginIds(IExtractionPlugin):
        acl.plugins.activatePlugin(IExtractionPlugin, 'localscript')
    if 'localscript' not in acl.plugins.listPluginIds(IAuthenticationPlugin):
        acl.plugins.activatePlugin(IAuthenticationPlugin, 'localscript')

    # set default front-page
    portal.setDefaultPage('front-page')

    # setup default groups
    groups = [
        {'id': 'Knowledgebase Contributor',
         'title': 'Knowledgebase Contributor',
         #'roles': ['...', '...']
         'description': 'Users in this group can contribute to knowledge base'
         },
        {'id': 'Knowledgebase Editor',
         'title': 'Knowledgebase Editor',
         'description': 'Users in this group can manage knowledgebase content'
         }]
    gtool = getToolByName(portal, 'portal_groups')
    for group in groups:
        if gtool.getGroupById(group['id']):
            gtool.editGroup(**group)
        else:
            gtool.addGroup(**group)


def upgrade_180_181_1(context, logger=None):
    # context is either the portal (called from setupVarious) or portal_setup when run via genericsetup
    if logger is None:
        # Called as upgrade step: define our own logger.
        logger = LOG

    # Run the following GS steps
    setup = getToolByName(context, 'portal_setup')
    setup.runImportStepFromProfile(PROFILE_ID, 'rolemap')
    setup.runImportStepFromProfile(PROFILE_ID, 'actions')


def upgrade_181_190_1(context, logger=None):
    if logger is None:
        logger = LOG
    # Run GS steps
    setup = getToolByName(context, 'portal_setup')
    setup.runImportStepFromProfile(PROFILE_ID, 'controlpanel')
    setup.runImportStepFromProfile(PROFILE_ID, 'catalog')
    setup.runImportStepFromProfile(PROFILE_ID, 'actions')
    setup.runImportStepFromProfile(PROFILE_ID, 'plone.app.registry')
    # finally remove the internal rdf graph which may still linger around
    pannots = IAnnotations(api.portal.get())
    if 'gu.plone.rdf' in pannots:
        del pannots['gu.plone.rdf']
    # rebuild the catalog to make sure new indices are populated
    logger.info("rebuilding catalog")
    pc = getToolByName(context, 'portal_catalog')
    pc.clearFindAndRebuild()
    logger.info("finished")


def upgrade_190_200_1(context, logger=None):
    if logger is None:
        logger = LOG
    # Run GS steps
    portal = api.portal.get()
    setup = getToolByName(context, 'portal_setup')
    setup.runImportStepFromProfile(PROFILE_ID, 'typeinfo')
    setup.runImportStepFromProfile(PROFILE_ID, 'plone.app.registry')
    setup.runImportStepFromProfile(PROFILE_ID, 'properties')
    setup.runImportStepFromProfile(PROFILE_ID, 'catalog')
    setup.runImportStepFromProfile(PROFILE_ID, 'propertiestool')
    setup.runImportStepFromProfile(PROFILE_ID, 'actions')
    # set portal_type of all collections to 'org.bccvl.content.collection'
    for tlf in portal.datasets.values():
        for coll in tlf.values():
            if coll.portal_type == 'Folder':
                coll.portal_type = 'org.bccvl.content.collection'

    setup.runImportStepFromProfile(PROFILE_ID, 'org.bccvl.site.content')
    # rebuild the catalog to make sure new indices are populated
    logger.info("rebuilding catalog")
    pc = getToolByName(context, 'portal_catalog')
    pc.reindexIndex('BCCCategory', None)
    # add category to existing species data
    genre_map = {
        'DataGenreSpeciesOccurrence': 'occurrence',
        'DataGenreSpeciesAbsence': 'absence',
        'DataGenreSpeciesAbundance': 'abundance',
        'DataGenreCC': 'current',
        'DataGenreFC': 'future',
        'DataGenreE': 'environmental',
        'DataGenreTraits': 'traits',
    }
    from org.bccvl.site.interfaces import IBCCVLMetadata
    for brain in pc(BCCDataGenre=genre_map.keys()):
        obj = brain.getObject()
        md = IBCCVLMetadata(obj)
        if not md.get('categories', None):
            md['categories'] = [genre_map[brain.BCCDataGenre]]
            obj.reindexObject()

    # update temporal and year an all datasets
    from org.bccvl.site.content.interfaces import IDataset
    import re
    for bran in pc(object_provides=IDataset.__identifier__):
        obj = brain.getObject()
        md = IBCCVLMetadata(obj)
        if hasattr(obj, 'rightsstatement'):
            del obj.rightsstatement
        # temporal may be an attribute or is in md
        if 'temporal' in md:
            if 'year' not in md:
                # copy temporal start to year
                sm = re.search(r'start=(.*?);', str)
                if sm:
                    md['year'] = int(sm.group(1))
                    # delete temporal
                    del md['temporal']
                    obj.reindexObject()
            if 'year' not in md:
                LOG.info('MD not updated for:', brain.getPath)

    # clean up any local utilities from gu.z3cform.rdf
    count = 0
    from zope.component import getSiteManager
    sm = getSiteManager()
    from zope.schema.interfaces import IVocabularyFactory
    from gu.z3cform.rdf.interfaces import IFresnelVocabularyFactory
    for vocab in [x for x in sm.getAllUtilitiesRegisteredFor(IVocabularyFactory) if IFresnelVocabularyFactory.providedBy(x)]:
        sm.utilities.unsubscribe((), IVocabularyFactory, vocab)
        count += 1
    logger.info('Unregistered %d local vocabularies', count)

    # migrate OAuth configuration registry to use new interfaces
    from zope.component import getUtility
    from zope.schema import getFieldNames
    from plone.registry.interfaces import IRegistry
    from .oauth.interfaces import IOAuth1Settings
    from .oauth.figshare import IFigshare
    registry = getUtility(IRegistry)
    # there is only Figshare there atm.
    coll = registry.collectionOfInterface(IOAuth1Settings)
    newcoll = registry.collectionOfInterface(IFigshare)
    for cid, rec in coll.items():
        # add new

        newrec = newcoll.add(cid)
        newfields = getFieldNames(IFigshare)
        # copy all attributes over
        for field in getFieldNames(IOAuth1Settings):
            if field in newfields:
                setattr(newrec, field, getattr(rec, field))
    # remove all old settings
    coll.clear()
    logger.info("Migrated OAuth1 settings to Figshare settings")

    for toolkit in portal[defaults.TOOLKITS_FOLDER_ID].values():
        if hasattr(toolkit, 'interface'):
            del toolkit.interface
        if hasattr(toolkit, 'method'):
            del toolkit.method
        toolkit.reindexObject()

    # possible way to update interface used in registry collections:
    # 1. get collectionOfInterface(I...) ... get's Collections proxy
    # 2. use proxy.add(key)  ... (add internally re-registers the given interface)
    #    - do this for all entries in collections proxy

    logger.info("finished")
