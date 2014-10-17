from Products.CMFCore.utils import getToolByName
from collective.transmogrifier.transmogrifier import Transmogrifier
from zope.interface import alsoProvides
from Products.PluggableAuthService.interfaces.plugins import IExtractionPlugin
from Products.PluggableAuthService.interfaces.plugins import IAuthenticationPlugin
from plone import api
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


def update_bioclim_layer_uris(portal):
    """
    Used in 0.9.0 -> 1.6.0 upgrade
    """
    # SDMS: environmental_datasets
    #   sdmresult.job_params['environmental_datasets']
    from rdflib import URIRef, Namespace
    pc =  portal.portal_catalog
    from org.bccvl.site.content.interfaces import ISDMExperiment
    for brain in pc.unrestrictedSearchResults(object_provides = ISDMExperiment.__identifier__):
        sdm = brain.getObject()
        # Fixup environmental_datasets
        OLDNS = Namespace(u'http://namespaces.bccvl.org.au/bioclim#')
        from org.bccvl.site.namespace import BCCVLLAYER as NEWNS

        def convert_uri_list(oldlist):
            newlist = []
            for val in oldlist:
                if val.startswith(OLDNS):
                    val = URIRef(val.replace(OLDNS, NEWNS))
                newlist.append(val)
            return newlist

        newdict = {}
        for key in sdm.environmental_datasets:
            newdict[key] = convert_uri_list(sdm.environmental_datasets[key])
        sdm.environmental_datasets = newdict
        # do the same for all result.job_params within an sdm
        for result in sdm.values():
            if not hasattr(result, 'job_params'):
                continue
            new_params = dict(result.job_params)
            for key in result.job_params.get('environmental_datasets', []):
                new_params['environmental_datasets'][key] = convert_uri_list(result.job_params['environmental_datasets'][key])
            result.job_params = new_params
    # Replace all layer references in rdf
    from zope.component import getUtility
    from gu.z3cform.rdf.interfaces import IORDF
    from org.bccvl.site.namespace import BIOCLIM
    handler = getUtility(IORDF).getHandler()
    qr = handler.query("SELECT * WHERE { Graph ?g { ?s <http://namespaces.bccvl.org.au/bioclim#bioclimVariable> ?o. FILTER(STRSTARTS(STR(?o), 'http://namespaces.bccvl.org.au/bioclim#')) }}")
    for row in qr:
        olduri = row['o']
        newuri = URIRef(olduri.replace(OLDNS, NEWNS))
        g = handler.get(row['g'])
        g.remove((row['s'], BIOCLIM['bioclimVariable'], olduri))
        g.add((row['s'], BIOCLIM['bioclimVariable'], newuri))
        handler.put(g)


def upgrade_090_160_1(context, logger=None):
    # context is either the portal (called from setupVarious) or portal_setup when run via genericsetup
    if logger is None:
        # Called as upgrade step: define our own logger.
        logger = LOG
    # flag whethe to trigger reindex
    reindex = False

    # Run the following GS steps
    setup = getToolByName(context, 'portal_setup')
    setup.runImportStepFromProfile(PROFILE_ID, 'gu.plone.rdf.ontologies')
    setup.runImportStepFromProfile(PROFILE_ID, 'workflow')
    setup.runImportStepFromProfile(PROFILE_ID, 'actions')
    # update toolkits
    setup.runImportStepFromProfile(PROFILE_ID, 'org.bccvl.site.content')

    # fixup bioclimlayer URIs in current content
    portal = api.portal.get()
    update_bioclim_layer_uris(portal)

    # update portal_catalog
    pc = getToolByName(context, 'portal_catalog')
    if 'BCCSpeciesLayer' in pc.indexes():
        pc.delIndex('BCCSpeciesLayer')
    if 'BCCDataGenre' not in pc.schema():
        pc.addColumn('BCCDataGenre')
        reindex = True

    if reindex:
        # populate new column
        for brain in pc.unrestrictedSearchResults(portal_type='org.bccvl.content.dataset'):
            obj = brain.getObject()
            obj.reindexObject()
    # pc.addIndex(name,  'type', extra)
    # pc.getrid(path)
    # pc.getIndexDataForRID(rid)
    # pc.getIndexDataForUID(path)


def upgrade_160_170_1(context, logger=None):
    # context is either the portal (called from setupVarious) or portal_setup when run via genericsetup
    if logger is None:
        # Called as upgrade step: define our own logger.
        logger = LOG

    # Run the following GS steps
    setup = getToolByName(context, 'portal_setup')
    setup.runImportStepFromProfile(PROFILE_ID, 'types')
