from Products.CMFCore.utils import getToolByName
from collective.transmogrifier.transmogrifier import Transmogrifier
from zope.interface import alsoProvides
from Products.PluggableAuthService.interfaces.plugins import IExtractionPlugin
from Products.PluggableAuthService.interfaces.plugins import IAuthenticationPlugin
from zope.schema.interfaces import IVocabularyFactory
from zope.component import getUtility
from plone import api
from plone.app.uuid.utils import uuidToObject
import logging
import re
from urlparse import urldefrag


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
            if 'job_params' not in result.__dict__:
                continue
            new_params = dict(result.job_params)
            for key in result.job_params.get('environmental_datasets', []):
                new_params['environmental_datasets'][key] = convert_uri_list(result.job_params['environmental_datasets'][key])
            result.job_params = new_params
    # Replace all layer references in rdf
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
    # install plone default rolemap?
    setup.runImportStepFromProfile('profile-Products.CMFPlone:plone', 'rolemap')
    setup.runImportStepFromProfile(PROFILE_ID, 'rolemap')
    # rerun cmfeditions rolemap
    setup.runImportStepFromProfile('profile-Products.CMFEditions:CMFEditions', 'rolemap')
    # update initial content and toolkits
    setup.runImportStepFromProfile(PROFILE_ID, 'org.bccvl.site.content')


def migrate_to_bccvlmetadata(context, logger):
    """
    migrate rdf content to annotation based metadata.

    TODO: check if this is re-runnable?
    """
    from org.bccvl.site.namespace import DWC, GML, NFO, TN
    from org.bccvl.site.namespace import BCCPROP, BIOCLIM
    from ordf.namespace import DC as DCTERMS
    from rdflib import URIRef
    from rdflib.resource import Resource
    from gu.z3cform.rdf.interfaces import IORDF,  IResource
    from org.bccvl.site.interfaces import IBCCVLMetadata
    from Acquisition import aq_base

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

    def extract_vocab_values(context, resource, mdata, mdkey, props, convert=unicode):
        """
        get dict from props[1] and convert value if exists with convert methad.
        check if there is more than one value and use first that exists in vocab.
        """
        for prop, key, vocab in props:
            vocabulary = getUtility(IVocabularyFactory, vocab)(context)
            values = list(resource.objects(prop))
            found = False
            for val in values:
                if hasattr(val, 'identifier'):
                    val = val.identifier
                if isinstance(val, URIRef):
                    _, frag = urldefrag(val)
                    if frag:
                        val = frag
                val = convert(val)
                if val not in vocabulary:
                    continue
                # We have found something 
                found = True
                break
            if not found and values:
                # special handling for traitrs results
                if val == 'UNKNOWN':
                    val = 'DataGenreSTResult'
                    found = True
                    logger.warn('Fixing traits result %s', '/'.join(context.getPhysicalPath()))
                elif val == 'BiodiverseModel':
                    val = 'DataGenreBiodiverseModel'
                    found = True
                    logger.warn('Fixing biodiverse genre %s', '/'.join(context.getPhysicalPath()))
                else:
                    # We had some values but didn't find anything
                    for t in vocabulary:
                        if t.value.lower() in context.title.lower():
                            val = t.value
                            logger.warn("Guessing %s: %s for %s", key, t.title, '/'.join(context.getPhysicalPath()))
                            found = True
                            break
            if found:
                if mdkey:
                    if mdata[mdkey] is None:
                        mdata[mdkey] = {}
                    mdata[mdkey][key] = val
                else:
                    mdata[key] = val
            if not found and values:
                logger.fatal("Couldn't find vocab value for %s: %s", key, '/'.join(context.getPhysicalPath()))
        

    def convert_uri_to_id(uri):
        ns, frag = urldefrag(uri)
        if frag:
            return frag
        if ns:
            # probably already converted
            return ns
        raise ValueError("Can't convert concept uri to vocab identifier: %s", uri)

    def extract_raster_metadata(res, lmd, key):
        # res ... IResource
        # lmd ... dict with
        # key ... layer key in md['layers']
        #
        # datatype, height, width, max, min, srs
        extract_values(res, lmd, key,
                       ((BCCPROP['height'], 'height'),
                        (BCCPROP['width'], 'width')),
                       int)
        extract_values(res, lmd, key,
                       ((BCCPROP['min'], 'min'),
                        (BCCPROP['max'], 'max')),
                       float)
        extract_values(res, lmd, key,
                       ((BCCPROP['datatype'], 'datatype'),
                        (BCCPROP['rat'], 'rat'),
                        (GML['srsName'], 'srs'),
                        (NFO['fileName'], 'filename')),
                       unicode)
        # fixup datatype if any:
        if key:
            layermd = lmd.get(key, {})
        else:
            layermd = lmd
        if layermd is not None and 'datatype' in layermd:
            dt_map = {u'DataSetTypeC': 'continuous'}
            # set to continuous or default categorical
            layermd['datatype'] = dt_map.get(layermd['datatype'], 'categorical')

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
    # FIXME: headernames ... put this info into separate section in md? (headers are not in rdf)
    #        can csv be sort of layer as well?
    # FIXME: CSV can have bounding box (not in rdf)

    ###########################################################################
    # transition layer metadata
    # layers within an archive have an additional attribute fileName
    #    to identify the file within the archive.
    layers = [l.identifier for l in res.objects(BIOCLIM['bioclimVariable'])]
    if layers:
        md['layers'] = dict((unicode(l), None) for l in layers)
        # if there are no archiveItems we can assume there is only one layer
        key = md['layers'].keys()[0]
        extract_raster_metadata(res, md['layers'], key)

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
        key = archiveItem.value(BIOCLIM['bioclimVariable'])
        if key:
            key = key.identifier
            newlayermd = {}
            extract_raster_metadata(archiveItem, newlayermd, None)
            if newlayermd:
                if 'layers' not in md or md['layers'] is None:
                    md['layers'] = {}
                md['layers'][key] = newlayermd

    # convert layer keys
    for key in md.get('layers', {}).keys():
        # TODO: rather replace 'layers' completely if possible?
        # TODO: check ... wolud this remove layers if key == frag?
        ns, frag = urldefrag(key)
        if frag in md['layers']:
            del md['layers'][frag]
        if frag:
            md['layers'][frag] = md['layers'][key]
            del md['layers'][key]

    # if datagenre is not Current or Future Climate, we need layers_used instead of layers
    # applies to at least DataGenreSDMModel, DataGenreClampingMask, DataGenreFP, DataGenreCP
    if md.get('layers') and not all(l for l in md.get('layers').values()):
        # Fix up 'layers' vs. 'layers_used'
        layers_used = []
        for lid, lval in md.get('layers').items():
            if not lval:
                layers_used.append(lid)
        # remove keys from dict
        map(lambda k: md['layers'].pop(k), layers_used)
        # set new layers_used key
        md['layers_used'] = tuple(layers_used)
        # remove 'layers' key entirely if empty
        if not md['layers']:
            del md['layers']

    # convert raster metadata directly on object
    extract_raster_metadata(res, md, None)


    ###########################################################################
    # Other literals
    extract_vocab_values(context, res, md, None,
                         ((BCCPROP['datagenre'], 'genre', 'genre_source'),
                          (BCCPROP['emissionscenario'], 'emsc', 'emsc_source'),
                          (BCCPROP['gcm'], 'gcm', 'gcm_source'),
                          (BCCPROP['resolution'], 'resolution', 'resolution_source')),
                          unicode)
    # check if resolution is a property on context
    if 'resolution' in context.__dict__:
        if context.resolution: # value is not None?
            # TODO: check vocab here as well
            md['resolution'] = convert_uri_to_id(context.resolution)
        del context.resolution

    extract_values(res, md, None,
                   ((DCTERMS['temporal'], 'temporal'),),
                   unicode)

    ###########################################################################
    # custom attributes directly on dataset:
    if 'thresholds' in context.__dict__:
        if context.thresholds:
            md['thresholds'] = context.thresholds
        del context.thresholds

    ###########################################################################
    # renamed attributes
    if not 'rightsstatement' in context.__dict__ and context.rights:
        # only copy rights if not already set (for dexterity content
        # we have to check __dict__ otherwise the attribute will be
        # found in the schema.  This check makes this migration step
        # repeatable.
        context.rightsstatement = context.rights
        context.rights = None
        
    ############ SDM experiment environmental_datasets
    for uuid, layers in getattr(aq_base(context), 'environmental_datasets', {}).items():
        new_layer_set = set(convert_uri_to_id(layeruri) for layeruri in layers)
        # set if different
        if layers != new_layer_set:
            context.environmental_datasets[uuid] = new_layer_set

    ########### fix up missing metadata
    from org.bccvl.site.content.interfaces import IExperiment
    if 'genre' not in md or not md['genre']:
        if (
            context.title.endswith('false_posivite_rates.Full.png') or
            context.title.endswith('pdf.Full.png') or
            context.title.endswith('hist.Full.png') or 
            context.title.endswith('plots.pdf') or            
            context.title.endswith('pstats.json') or
            context.title.endswith('workenv.zip') or
            context.title.endswith('.projection.out') or
            IExperiment.providedBy(context)):
            # return abov condition
            return
        if 'file' in context.__dict__ and context.file:
            if context.file.filename == u'pROC.Full.png':
                md['genre'] = 'DataGenreSDMEval'
                context.title = u'ROC curve'
                logger.warn('Fixup genre %s', '/'.join(context.getPhysicalPath()))
            elif context.file.filename == u'mean_response_curves_Phascolarctus.cinereus_AllData_Full_ANN.png':
                md['genre'] = 'DataGenreSDMEval'
                context.title = u'Mean Response Curves'
                logger.warn('Fixup genre %s', '/'.join(context.getPhysicalPath()))
            elif context.file.filename.endswith('.csv'):
                # probably a occurrence dataset
                from csv import DictReader
                csv = DictReader(context.file.open('r'))
                if csv.fieldnames and 'lon' in csv.fieldnames and 'lat' in csv.fieldnames and 'species' in csv.fieldnames:
                    row = csv.next()
                    # convert filename
                    taxon = context.file.filename.replace('_', ':').replace('biodiversity-org-au', 'biodiversity.org.au').replace('afd-taxon', 'afd.taxon').replace('.csv', '')
                    # check if we have a -<n> at the end
                    m = re.match(r'(.*:.*-.*-.*-.*-.*)(-\d)*', taxon)
                    if m:
                        taxon = m.group(1)
                        md['genre'] = 'DataGenreSpeciesOccurrence'
                        md['species'] = {
                            'scientificName': row['species'],
                            'taxonID': taxon
                            }
                        context.title = '{0} occurrence'.format(row['species'])
                        logger.warn('Fixup genre and species %s', '/'.join(context.getPhysicalPath()))
            elif context.file.filename == 'biodiverse_prefix_RAREW_RICHNESS.tif':
                logger.warn('Fixup genre %s', '/'.join(context.getPhysicalPath()))
                md['genre'] = 'DataGenreRAREW_RICHNESS'
                context.title = u'Rarity whole - Richness used in RAREW_CWE'
            elif context.file.filename == 'biodiverse_prefix_RAREW_WE.tif':
                logger.warn('Fixup genre %s', '/'.join(context.getPhysicalPath()))
                md['genre'] = 'DataGenreRAREW_WE'
                context.title = u'Rarity whole - weighted rarity'
            elif context.file.filename == 'biodiverse_prefix_RAREW_CWE.tif':
                logger.warn('Fixup genre %s', '/'.join(context.getPhysicalPath()))
                md['genre'] = 'DataGenreRAREW_CWE'
                context.title = u'Rarity whole - Corrected weighted rarity'
            elif context.file.filename == 'proj_current_ClampingMask.tif':
                md['genre'] = 'DataGenreClampingMask'
                context.title = u'Clamping Mask'
                logger.warn('Fixup genre %s', '/'.join(context.getPhysicalPath()))
            elif re.match(r'proj_current_.*\.tif', context.file.filename):
                md['genre'] = 'DataGenreCP'
                context.title = u'Projection to current'
                logger.warn('Fixup genre %s', '/'.join(context.getPhysicalPath()))
            elif context.file.filename == u'model.object.RData.zip':
                md['genre'] = 'DataGenreSDMModel'
                context.title = u'R SDM Model object'
                logger.warn('Fixup genre %s', '/'.join(context.getPhysicalPath()))
            elif context.file.filename == u'ann.Rout':
                md['genre'] = 'DataGenreLog'
                context.title = u'Log file'
                logger.warn('Fixup genre %s', '/'.join(context.getPhysicalPath()))
            elif context.file.filename == u'variableImportance.Full.txt':
                md['genre'] = 'DataGenreSDMEval'
                context.title = u'Model Evaluation'
        else:
            logger.fatal('Genre not set: %s', '/'.join(context.getPhysicalPath()))


def migrate_result_folder(resultob):
    from plone.app.contenttypes.content import Folder
    from org.bccvl.site.interfaces import IBCCVLMetadata

    def convert_uri_to_id(uri):
        ns, frag = urldefrag(uri)
        if frag:
            return frag
        if ns:
            # probably already converted
            return ns
        raise ValueError("Can't convert concept uri to vocab identifier: %s", uri)

    gcm_vocab = getUtility(IVocabularyFactory, 'gcm_source')(resultob)
    emsc_vocab = getUtility(IVocabularyFactory, 'emsc_source')(resultob)    
    if 'job_params' not in resultob.__dict__:
        # FIXME: could be an item in knowledge base
        # we may have a body text and a logo here
        # can't get rid of IRepositoryItem if we don't convert them
        return
    resultid = resultob.getId()
    parent = resultob.__parent__
    parent._delOb(resultid)
    resultob.__class__ = Folder
    resultob.portal_type = 'Folder'
    parent._setOb(resultid, resultob)
    # SDM:
    job_params = resultob.job_params
    for dsuuid, layers in job_params.get("environmental_datasets", {}).items():
        # convert layeruris to ids
        job_params['environmental_datasets'][dsuuid] = set(
            convert_uri_to_id(layeruri) for layeruri in layers)
    if 'resolution' in job_params:
        job_params['resolution'] = convert_uri_to_id(job_params['resolution'])
    # Projection:
    if 'emission_scenario' in job_params:
        job_params['emsc'] = job_params['emission_scenario']
        if job_params['emsc'] not in emsc_vocab:
            ob = uuidToObject(job_params['future_climate_datasets'])
            job_params['emsc'] = IBCCVLMetadata(ob)['emsc']
        del job_params['emission_scenario']
    if 'climate_models' in job_params:
        job_params['gcm'] = job_params['climate_models']
        if job_params['gcm'] not in gcm_vocab:
            ob = uuidToObject(job_params['future_climate_datasets'])
            job_params['gcm'] = IBCCVLMetadata(ob)['gcm']
        del job_params['climate_models']
    if 'future_climate_datasets' in job_params:
        if not isinstance(job_params['future_climate_datasets'], dict):
            job_params['future_climate_datasets'] = {
                job_params['future_climate_datasets']: set()
            }
    if 'projections' in job_params:
        newproj = {}
        for item in job_params['projections']:
            dsob = uuidToObject(item['dataset'])
            dsexp = dsob.__parent__.__parent__
            newproj.setdefault(dsexp.UID(), {})[item['dataset']] = {
                'label': unicode(item['threshold']),
                'value': item['threshold'] }
        job_params['projections'] = newproj
    
def upgrade_170_180_1(context, logger=None):
    # context is either the portal (called from setupVarious) or portal_setup when run via genericsetup
    if logger is None:
        # Called as upgrade step: define our own logger.
        logger = LOG

    # Run the following GS steps
    setup = getToolByName(context, 'portal_setup')
    setup.runImportStepFromProfile(PROFILE_ID, 'plone.app.registry')
    setup.runImportStepFromProfile(PROFILE_ID, 'typeinfo')
    setup.runImportStepFromProfile(PROFILE_ID, 'org.bccvl.site.content')    

    # migrate rdf metadata
    pc = getToolByName(context, 'portal_catalog')
        
    # convert rdf metadata on all known objects..
    for brain in list(pc.unrestrictedSearchResults(portal_type=('org.bccvl.content.dataset', 'org.bccvl.content.remotedataset', 'org.bccvl.content.sdmexperiment', 'org.bccvl.content.biodiverseexperiment', 'org.bccvl.content.projectionexperiment', 'org.bccvl.content.speciestraitsexperiment', 'org.bccvl.content.ensemble'))):
        obj = brain.getObject()
        logger.info("Migrating metadata %s", brain.getPath())
        migrate_to_bccvlmetadata(obj, logger)
        obj.reindexObject()

    # convert result folder base class (and update job_params)
    for brain in list(pc.unrestrictedSearchResults(portal_type='gu.repository.content.RepositoryItem')):
        # needs to run after metadata migration and fix up
        obj = brain.getObject()
        logger.info("Migrating repositoryitem %s", brain.getPath())
        migrate_result_folder(obj)
        obj.reindexObject()
    # migrate experiment objects (new properties and structures)
    from org.bccvl.site.content.interfaces import IExperiment, ISDMExperiment, IProjectionExperiment, IBiodiverseExperiment
    for brain in list(pc.unrestrictedSearchResults(object_provides=IExperiment.__identifier__)):
        exp = brain.getObject()
        logger.info("Migrating experiment %s", brain.getPath())
        # Ensemble:
        if 'dataset' in exp.__dict__:
            dsdict = {}
            for dsuuid in exp.dataset:
                dsob = uuidToObject(dsuuid)
                dsexp = dsob.__parent__.__parent__
                dsdict.setdefault(dsexp.UID(), []).append(dsuuid)
                if ISDMExperiment.providedBy(exp):
                    exp.experiment_type = ISDMExperiment.__identifier__
                elif IProjectionExperiment.providedBy(exp):
                    exp.experiment_type = IProjectionExperiment.__identifier__
                elif IBiodiverseExperiment.providedBy(exp):
                    exp.experiment_type = IBiodiverseExperiment.__identifier__
            del exp.dataset
            exp.datasets = dsdict
        # Projection: (if species_distribution_models is dict then it's already in new format)
        if 'species_distribution_models' in exp.__dict__ and not isinstance(exp.species_distribution_models, dict):
            dsdict = {}
            for dsuuid in exp.species_distribution_models:
                dsob = uuidToObject(dsuuid)
                dsexp = dsob.__parent__.__parent__
                dsdict.setdefault(dsexp.UID(), []).append(dsuuid)
            exp.species_distribution_models = dsdict
            # go through results and create future_climate_datasets
            fcd = set()
            for result in exp.values():
                if isinstance(result.job_params['future_climate_datasets'], dict):
                    fcd.update(result.job_params['future_climate_datasets'].keys())
            exp.future_climate_datasets = list(fcd)
        if 'years' in exp.__dict__:
            del exp.years
        if 'emission_scenarios' in exp.__dict__:
            del exp.emission_scenarios
        if 'climate_models' in exp.__dict__:
            del exp.climate_models
        # Biodiverse: (if exp.projection is a list we have to migrate it to dict)
        if 'projection' in exp.__dict__ and isinstance(exp.projection, list):
            newproj = {}
            for item in exp.projection:
                dsob = uuidToObject(item['dataset'])
                dsexp = dsob.__parent__.__parent__
                newproj.setdefault(dsexp.UID(), {})[item['dataset']] = {
                    'label': unicode(item['threshold']),
                    'value': item['threshold'] }                
            exp.projection = newproj

        exp.reindexObject()
    # FIXME: need to reindex at least object_provides (empty / index)
    # FIXME: sdm layer reindex (and probably other metadata)

    # TODO: missing threshold values?
    # TODO: migrate RepositoryItems in knowledge base to Folder
    #       don't forget to reindex once interface is gone entirely
    # TODO: add more data fixups:
    #       - if there is no 'rows', 'headers' for csv files
    #       - no height, width, ... for raster files
    # TODO: convert srs? (or leave as URI strings?)
    # TODO: does md['layers'] need 'layer' id key as well in layermd?
    # TODO: various png visualisations have no genre
    # FIXME: pretty much all *projection.out files have a malformed mime type (None)
    # TODO: move away from storing temproal metadat as dc:period
    # TODO: delete subjecturi index column
