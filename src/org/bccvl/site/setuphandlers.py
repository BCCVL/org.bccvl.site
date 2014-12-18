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
        for brain in pc.unrestrictedSearchResults(portal_type=('org.bccvl.content.dataset', 'org.bccvl.content.remotedataset')):
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
    setup.runImportStepFromProfile(PROFILE_ID, 'typeinfo')
    setup.runImportStepFromProfile(PROFILE_ID, 'portlets')
    setup.runImportStepFromProfile(PROFILE_ID, 'actions')
    setup.runImportStepFromProfile(PROFILE_ID, 'plone.app.registry')
    # install plone default workflows
    setup.runImportStepFromProfile('profile-Products.CMFPlone:plone', 'workflow')
    setup.runImportStepFromProfile(PROFILE_ID, 'workflow')
    # TODO: reindex security?
    # install plone default rolemap?
    setup.runImportStepFromProfile('profile-Products.CMFPlone:plone', 'rolemap')
    setup.runImportStepFromProfile(PROFILE_ID, 'rolemap')
    # rerun cmfeditions rolemap
    setup.runImportStepFromProfile('profile-Products.CMFEditions:CMFEditions', 'rolemap')
    # update initial content and toolkits
    setup.runImportStepFromProfile(PROFILE_ID, 'org.bccvl.site.content')

    # TODO: possible data structure strange on sdmexperiments
    #    environmental_datasets a dict of sets (instead of list?)
    # Examples:
    # setup.runImportStepFromProfile(PROFILE_ID, 'catalog')
    # logger.info("%s fields converted." % count)


def migrate_to_bccvlmetadata(context, logger):
    """
    migrate rdf content to annotation based metadata.
    """
    from org.bccvl.site.namespace import DWC, GML, NFO, TN
    from org.bccvl.site.namespace import BCCPROP, BIOCLIM
    from ordf.namespace import DC as DCTERMS
    from rdflib import URIRef
    from rdflib.resource import Resource
    from zope.component import getUtility
    from gu.z3cform.rdf.interfaces import IORDF,  IResource
    from org.bccvl.site.interfaces import IBCCVLMetadata
    from urlparse import urldefrag
    from Acquisition import aq_base
    # TODO: convert URIRef's to unicode
    #        also do that in indices and vocabularies
    res = IResource(context)
    md = IBCCVLMetadata(context)

    ###################################################################
    # helper methods:
    def extract_values(resource, mdata, mdkey, props, convert=unicode):
        """
        get dict key from props[1] and convert value if exists
        with convert method
        """
        for prop, key in props:
            val = resource.value(prop)
            if val:
                if hasattr(val, 'identifier'):
                    val = val.identifier
                if isinstance(val, URIRef):
                    _, frag = urldefrag(val)
                    if frag:
                        val = frag
                if mdkey:
                    if mdata[mdkey] is None:
                        mdata[mdkey] = {}
                    mdata[mdkey][key] = convert(val)
                else:
                    mdata[key] = convert(val)

    ###########################################################################
    # species info:
    species = {}
    extract_values(res, species, None,
                   ((DWC['scientificName'], 'scientificName'),
                    (DWC['vernacularName'], 'vernacularName'),
                    (DWC['taxonID'], 'taxonID'),
                    (TN['nameComplete'], 'taxonName')),
                   unicode)
    if species:
        md['species'] = species

    # CSV metadata
    if res.value(BCCPROP['rows']):
        md['rows'] = int(res.value(BCCPROP['rows']))
    # FIXME: headernames ... put this info into separate section in md?
    #        can csv be sort of layer as well?
    # FIXME: CSV can have bounding box

    ###########################################################################
    # transition layer metadata
    # layers within an archive have an additional attribute fileName
    #    to identify the file within the archive.
    # FIXME: experiments and results may have set this stuff differently?
    layers = [l.identifier for l in res.objects(BIOCLIM['bioclimVariable'])]
    if layers:
        md['layers'] = dict((unicode(l), None) for l in layers)
        # there may be layer metadata directly on the object (usually only for single layer files)
        # assume only one layer
        key = md['layers'].keys()[0]
        extract_values(res, md['layers'], key,
                       ((BCCPROP['height'], 'height'),
                        (BCCPROP['width'], 'width')),
                       int)
        extract_values(res, md['layers'], key,
                       ((BCCPROP['min'], 'min'),
                        (BCCPROP['max'], 'max')),
                       float)
        extract_values(res, md['layers'], key,
                       ((BCCPROP['datatype'], 'datatype'),
                        (BCCPROP['rat'], 'rat'),
                        (GML['srsName'], 'srsName')),
                       unicode)
    # hasArchiveItem
    for archiveItem in res.objects(BCCPROP['hasArchiveItem']):
        # check if archiveItem is empty ... need to load graph otherwise
        obj = next(archiveItem.objects(), None)
        if obj is None:
            # load archiveItem from triple store
            handler = getUtility(IORDF).getHandler()
            archiveItem = Resource(handler.get(archiveItem.identifier),
                                   archiveItem.identifier)
        # we have a couple of things stored on the archiveitem
        newitem = {}
        extract_values(archiveItem, newitem, None,
                       ((BCCPROP['height'], 'height'),
                        (BCCPROP['width'], 'width'),
                        (NFO['fileSize'], 'fileSize')),
                       int)
        extract_values(archiveItem, newitem, None,
                       ((BCCPROP['min'], 'min'),
                        (BCCPROP['max'], 'max')),
                       float)
        extract_values(archiveItem, newitem, None,
                       ((BCCPROP['datatype'], 'datatype'),
                        (BCCPROP['rat'], 'rat'),
                        (GML['srsName'], 'srsName'),
                        (NFO['fileName'], 'fileName')),
                       unicode)

        key = archiveItem.value(BIOCLIM['bioclimVariable'])
        if key:
            key = key.identifier
            if newitem:
                if md.get('layers') is None:
                    md['layers'] = {}
                md['layers'][key] = newitem

    # convert layer keys
    for key in md.get('layers', {}).keys():
        _, frag = urldefrag(key)
        md['layers'][frag] = md['layers'][key]
        del md['layers'][key]


    ###########################################################################
    # Other literals
    # FIXME:  these are all vocab entries
    extract_values(res, md, None,
                   ((BCCPROP['datagenre'], 'genre'),
                    (BCCPROP['emissionsscenario'], 'emsc'),
                    (BCCPROP['gcm'], 'gcm'),
                    (BCCPROP['resolution'], 'resolution')),
                   unicode)
    # FIXME: dc:format should match mimetype? what about zip files and conatined files?
    extract_values(res, md, None,
                   ((DCTERMS['temporal'], 'temporal'),),
                   unicode)

    ###########################################################################
    # custom attributes directly on dataset:
    if hasattr(aq_base(context), 'thresholds'):
        md['thresholds'] = context.thresholds

    ###########################################################################
    # renamed attributes
    if not 'rightsstatement' in context.__dict__ and context.rights:
        # only copy rights if not already set (for dexterity content
        # we have to check __dict__ otherwise the attribute will be
        # found in the schema.  This check makes this migration step
        # repeatable.
        context.rightsstatement = context.rights
        context.rights = None


def upgrade_170_200_1(context, logger=None):
    # context is either the portal (called from setupVarious) or portal_setup when run via genericsetup
    if logger is None:
        # Called as upgrade step: define our own logger.
        logger = LOG

    # Run the following GS steps
    setup = getToolByName(context, 'portal_setup')
    setup.runImportStepFromProfile(PROFILE_ID, 'plone.app.registry')
    setup.runImportStepFromProfile(PROFILE_ID, 'typeinfo')

    # migrate rdf metadata
    pc = getToolByName(context, 'portal_catalog')
    # FIXME: maybe not just datasets?
    # TODO: maybe don't create bccvl annotations for content we don't need it
    for brain in pc.unrestrictedSearchResults(portal_type=('org.bccvl.content.dataset', 'org.bccvl.content.remotedataset')):
            obj = brain.getObject()
            migrate_to_bccvlmetadata(obj, logger)
            obj.reindexObject()

    # TODO: migrate all gu.repository.content.RepositoryItem to Folder
