from Products.CMFCore.utils import getToolByName
from Products.GenericSetup.interfaces import IBody
from Products.GenericSetup.context import SnapshotImportContext
from eea.facetednavigation.layout.interfaces import IFacetedLayout
from plone import api
from plone.uuid.interfaces import IUUID
from plone.app.uuid.utils import uuidToObject
from zope.annotation.interfaces import IAnnotations
from zope.component import getUtility, getMultiAdapter
from org.bccvl.site import defaults
import logging


LOG = logging.getLogger(__name__)
PROFILE_ID = 'profile-org.bccvl.site:default'
PROFILE = 'org.bccvl.site'


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

    # set default front-page
    portal.setDefaultPage('front-page')

    # Setup cookie settings
    sess = portal.acl_users.session
    sess.manage_changeProperties(
        mod_auth_tkt=True,
    )
    # set cookie secret from celery configuration
    from org.bccvl.tasks.celery import app
    cookie_cfg = app.conf.get('bccvl', {}).get('cookie', {})
    if cookie_cfg.get('secret', None):
        sess._shared_secret = cookie_cfg.get('secret').encode('utf-8')
        sess.manage_changeProperties(
            secure=cookie_cfg.get('secure', True)
        )

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

    # setup job catalog
    from org.bccvl.site.job.catalog import setup_job_catalog
    setup_job_catalog(portal)

    # setup userannotation storage
    from org.bccvl.site.userannotation.utility import init_user_annotation
    init_user_annotation()
    # FIXME: some stuff is missing,... initial setup of site is not correct

def setupFacets(context, logger=None):
    if logger is None:
        logger = LOG
    logger.info('BCCVL site facet setup handler')

    # only run for this product
    if context.readDataFile('org.bccvl.site.marker.txt') is None:
        return
    portal = context.getSite()

    # setup datasets search facets
    datasets = portal[defaults.DATASETS_FOLDER_ID]
    subtyper = getMultiAdapter((datasets, datasets.REQUEST),
                               name=u'faceted_subtyper')
    subtyper.enable()
    IFacetedLayout(datasets).update_layout('faceted-table-items')
    widgets = getMultiAdapter((datasets, datasets.REQUEST),
                              name='datasets_default.xml')
    xml = widgets()
    environ = SnapshotImportContext(datasets, 'utf-8')
    importer = getMultiAdapter((datasets, environ), IBody)
    importer.body = xml


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
    setup.runImportStepFromProfile(PROFILE_ID, 'workflow')
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
                sm = re.search(r'start=(.*?);', md['temporal'])
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


def upgrade_200_210_1(context, logger=None):
    if logger is None:
        logger = LOG
    # Run GS steps
    portal = api.portal.get()

    # Do some registry cleanup:
    from plone.registry.interfaces import IRegistry
    registry = getUtility(IRegistry)
    for key in list(registry.records.keys()):
        if (key.startswith('plone.app.folderui')
            or key.startswith('dexterity.membrane')
            or key.startswith('collective.embedly')):
            del registry.records[key]

    setup = api.portal.get_tool('portal_setup')
    setup.runImportStepFromProfile(PROFILE_ID, 'propertiestool')
    setup.runImportStepFromProfile(PROFILE_ID, 'typeinfo')
    setup.runImportStepFromProfile(PROFILE_ID, 'toolset')
    setup.runImportStepFromProfile(PROFILE_ID, 'controlpanel')
    setup.runImportStepFromProfile(PROFILE_ID, 'org.bccvl.site.content')
    setup.runImportStepFromProfile(PROFILE_ID, 'plone.app.registry')
    setup.runImportStepFromProfile(PROFILE_ID, 'workflow')

    # make error logs visible
    ignored_exceptions = portal.error_log._ignored_exceptions
    portal.error_log._ignored_exceptions = ()
    from org.bccvl.site.job.catalog import setup_job_catalog
    setup_job_catalog(portal)

    pc = api.portal.get_tool('portal_catalog')
    # Update job_params with algorithm used for Climate Change Experiments
    LOG.info('Updating job params of old projection experiments')
    for brain in pc.searchResults(portal_type='org.bccvl.content.projectionexperiment'):
        # go through all results
        for result in brain.getObject().values():
            if 'function' in result.job_params:
                continue
            #Add algorithm to job_params if missing algorithm
            try:
                sdmds = uuidToObject(result.job_params['species_distribution_models'])
                algorithm = sdmds.__parent__.job_params['function']
                if algorithm:
                    result.job_params['function'] = algorithm
            except Exception as e:
                LOG.warning("Can't add algorithm id to %s: %s", result, e)

    from org.bccvl.site.job.interfaces import IJobUtility
    jobtool = getUtility(IJobUtility)
    # search all datasets and create job object with infos from dataset
    # -> delete job info on dataset
    LOG.info('Migrating job data for datasets')
    DS_TYPES = ['org.bccvl.content.dataset',
                'org.bccvl.content.remotedataset']
    for brain in pc.searchResults(portal_type=DS_TYPES):
        job = jobtool.find_job_by_uuid(brain.UID)
        if job:
            # already processed ... skip
            continue
        try:
            ds = brain.getObject()
        except Exception as e:
            LOG.warning('Could not resolve %s: %s', brain.getPath(), e)
            continue
        annots = IAnnotations(ds)
        old_job = annots.get('org.bccvl.state', None)
        if not old_job:
            # no job state here ... skip it
            continue
        job = jobtool.new_job()
        job.created = ds.created()
        job.message = old_job['progress']['message']
        job.progress = old_job['progress']['state']
        job.state = old_job['state']
        job.title = old_job['name']
        job.taskid = old_job['taskid']
        job.userid = ds.getOwner().getId()
        job.content = IUUID(ds)
        job.type = brain.portal_type

        jobtool.reindex_job(job)
        del annots['org.bccvl.state']

    # search all experiments and create job object with infos from experiment
    # -> delete job info on experiment
    LOG.info('Migrating job data for experiments')
    EXP_TYPES = ['org.bccvl.content.sdmexperiment',
                 'org.bccvl.content.projectionexperiment',
                 'org.bccvl.content.biodiverseexperiment',
                 'org.bccvl.content.ensemble',
                 'org.bccvl.content.speciestraitsexperiment'
    ]
    for brain in pc.searchResults(portal_type=EXP_TYPES):
        # go through all results
        for result in brain.getObject().values():
            job = None
            try:
                job = jobtool.find_job_by_uuid(IUUID(result))
            except Exception as e:
                LOG.info('Could not resolve %s: %s', result, e)
                continue
            if job:
                # already processed ... skip
                continue
            annots = IAnnotations(result)
            old_job = annots.get('org.bccvl.state', None)
            if not old_job:
                # no job state here ... skip it
                continue
            job = jobtool.new_job()
            job.created = result.created()
            job.message = old_job['progress']['message']
            job.progress = old_job['progress']['state']
            job.state = old_job['state']
            job.title = old_job['name']
            job.taskid = old_job['taskid']
            job.userid = result.getOwner().getId()
            job.content = IUUID(result)
            job.type = brain.portal_type
            job.function = result.job_paramsi.get('function')
            if job.function:
                job.toolkit = IUUID(portal[defaults.TOOLKITS_FOLDER_ID][job.function])

            jobtool.reindex_job(job)
            del annots['org.bccvl.state']

    LOG.info('Updating layer metadata for projection outputs')
    from org.bccvl.site.interfaces import IBCCVLMetadata
    for brain in pc.searchResults(BCCDataGenre=('DataGenreCP', 'DataGenreFP', 'DataGenreClampingMask')):
        ds = brain.getObject()
        md = IBCCVLMetadata(ds)
        # md['layers'][ds.file.filename] ... there should be only one key
        keys = md['layers'].keys()
        if len(keys) != 1:
            LOG.warning('Found multiple layer keys; do not know what to do: %s', ds.absolute_url())
            continue
        layermd = md['layers'][keys[0]]
        if 'layer' in layermd:
            # already converted
            continue
        if md['genre'] == 'DataGenreClampingMask':
            layerid = 'clamping_mask'
        else:  # DataGenreCP and DataGenreFP
            algorithm = ds.__parent__.job_params['function']
            if algorithm in ('circles', 'convhull', 'voronoiHull'):
                layerid = 'projection_binary'
            elif algorithm in ('maxent',):
                layerid = 'projection_suitability'
            else:
                layerid = 'projection_probability'
        layermd['layer'] = layerid
        md['layers'] = {layerid: layermd}

    # restore error_log filter
    portal.error_log._ignored_exceptions = ignored_exceptions
    LOG.info('Upgrade step finished')


def upgrade_210_220_1(context, logger=None):
    if logger is None:
        logger = LOG
    # Run GS steps
    portal = api.portal.get()
    setup = getToolByName(context, 'portal_setup')
    setup.runImportStepFromProfile(PROFILE_ID, 'plone.app.registry')
    setup.runImportStepFromProfile(PROFILE_ID, 'controlpanel')
    setup.runImportStepFromProfile(PROFILE_ID, 'org.bccvl.site.content')

    # remove local login hack
    for acl in (portal.acl_users, portal.__parent__.acl_users):
        if 'localscript' in acl:
            acl.manage_delObjects('localscript')


def upgrade_220_230_1(context, logger=None):
    if logger is None:
        logger = LOG
    # Run GS steps
    portal = api.portal.get()
    setup = api.portal.get_tool('portal_setup')
    setup.runImportStepFromProfile(PROFILE_ID, 'org.bccvl.site.content')
    setup.runImportStepFromProfile(PROFILE_ID, 'plone.app.registry')
    setup.runImportStepFromProfile(PROFILE_ID, 'actions')
    pc = api.portal.get_tool('portal_catalog')

   # search all experiments and update job object with infos from experiment
    # -> delete job info on experiment
    LOG.info('Migrating job data for experiments')
    EXP_TYPES = ['org.bccvl.content.sdmexperiment',
                 'org.bccvl.content.projectionexperiment',
                 'org.bccvl.content.biodiverseexperiment',
                 'org.bccvl.content.ensemble',
                 'org.bccvl.content.speciestraitsexperiment'
    ]

    from org.bccvl.site.job.interfaces import IJobTracker
    import json
    for brain in pc.searchResults(portal_type=EXP_TYPES):
        # Update job with process statistic i.e. rusage
        for result in brain.getObject().values():
            if not 'pstats.json' in result:
                continue

            jt = IJobTracker(result)
            job = None
            try:
                job = jt.get_job()
            except Exception as e:
                LOG.info('Could not resolve %s: %s', result, e)
            if not job:
                continue

            pstats = result['pstats.json']
            if hasattr(pstats, 'file'):
                job.rusage = json.loads(pstats.file.data)
                del result['pstats.json']

    # Setup cookie settings
    sess = portal.acl_users.session
    sess.manage_changeProperties(
        mod_auth_tkt=True,
        secure=True
    )

    # update facet configurations
    from org.bccvl.site.faceted.interfaces import IFacetConfigUtility
    from org.bccvl.site.faceted.tool import import_facet_config
    fct = getUtility(IFacetConfigUtility)
    for cfgobj in fct.types():
        LOG.info("Import facet config for %s", cfgobj.id)
        import_facet_config(cfgobj)

    # set cookie secret from celery configuration
    from org.bccvl.tasks.celery import app
    cookie_cfg = app.conf.get('bccvl', {}).get('cookie', {})
    if cookie_cfg.get('secret', None):
        sess._shared_secret = cookie_cfg.get('secret').encode('utf-8')
        sess = portal.acl_users.session
        sess.manage_changeProperties(
            mod_auth_tkt=True,
            secure=cookie_cfg.get('secure', True)
        )


def upgrade_230_240_1(context, logger=None):
    if logger is None:
        logger = LOG
    # Run GS steps
    portal = api.portal.get()
    setup = api.portal.get_tool('portal_setup')
    setup.runImportStepFromProfile(PROFILE_ID, 'org.bccvl.site.content')


    # setup userannotation storage
    from org.bccvl.site.userannotation.utility import init_user_annotation
    from org.bccvl.site.userannotation.interfaces import IUserAnnotationsUtility
    init_user_annotation()
    # migrate current properties into userannotations
    pm = api.portal.get_tool('portal_membership')
    pmd = api.portal.get_tool('portal_memberdata')
    custom_props = [p for p in pmd.propertyIds() if '_oauth_' in p]
    ut = getUtility(IUserAnnotationsUtility)
    for member in pm.listMembers():
        member_annots = ut.getAnnotations(member)
        for prop in custom_props:
            if not member.hasProperty(prop):
                continue
            value = member.getProperty(prop)
            if not value:
                continue
            member_annots[prop] = value
            member.setMemberProperties({prop: ''})
    # remove current properties
    pmd.manage_delProperties(custom_props)
