from Products.CMFCore.utils import getToolByName
from Products.GenericSetup.interfaces import IBody
from Products.GenericSetup.context import SnapshotImportContext
from eea.facetednavigation.layout.interfaces import IFacetedLayout
from plone import api
from plone.uuid.interfaces import IUUID
from plone.app.uuid.utils import uuidToObject
from plone.registry.interfaces import IRegistry
from zope.annotation.interfaces import IAnnotations
from zope.component import getUtility, getMultiAdapter
from org.bccvl.site import defaults
import logging


LOG = logging.getLogger(__name__)
PROFILE_ID = 'profile-org.bccvl.site:default'
PROFILE = 'org.bccvl.site'
THEME_PROFILE_ID = 'profile-org.bccvl.theme:default'


def get_object_by_uuid(pc, uuid):
    brain = pc.unrestrictedSearchResults(UID=uuid)
    if len(brain) != 1:
        return None
    return brain[0].getObject()


def setupTools(context, logger=None):
    if logger is None:
        logger = LOG
    logger.info('BCCVL site tools handler')
    # only run for this product
    if context.readDataFile('org.bccvl.site.marker.txt') is None:
        return
    portal = context.getSite()

    # setup job catalog
    from org.bccvl.site.job.catalog import setup_job_catalog
    setup_job_catalog(portal)

    # setup userannotation storage
    from org.bccvl.site.userannotation.utility import init_user_annotation
    init_user_annotation()

    # setup stats tool
    from org.bccvl.site.stats.utility import init_stats
    init_stats()


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

    # enable self registration
    from plone.app.controlpanel.security import ISecuritySchema
    security = ISecuritySchema(portal)
    security.enable_self_reg = True
    security.enable_user_pwd_choice = True

    # setup html filtering
    from plone.app.controlpanel.filter import IFilterSchema
    filters = IFilterSchema(portal)
    # remove some nasty tags:
    current_tags = filters.nasty_tags
    for tag in ('embed', 'object'):
        if tag in current_tags:
            current_tags.remove(tag)
    filters.nasty_tags = current_tags
    # remove some stripped tags:
    current_tags = filters.stripped_tags
    for tag in ('button', 'object', 'param'):
        if tag in current_tags:
            current_tags.remove(tag)
    filters.stripped_tags = current_tags
    # add custom allowed tags
    current_tags = filters.custom_tags
    for tag in ('embed', ):
        if tag not in current_tags:
            current_tags.append(tag)
    filters.custom_tags = current_tags
    # add custom allowed styles
    current_styles = filters.style_whitelist
    for style in ('border-radius', 'padding', 'margin-top', 'margin-bottom', 'background', 'color'):
        if style not in current_styles:
            current_styles.append(style)
    filters.style_whitelist = current_styles

    # configure TinyMCE plugins (can't be done zia tinymce.xml
    tinymce = getToolByName(portal, 'portal_tinymce')
    current_plugins = tinymce.plugins
    if 'media' in current_plugins:
        # disable media plugin which get's in the way all the time
        current_plugins.remove('media')
    tinymce.plugins = current_plugins

    # FIXME: some stuff is missing,... initial setup of site is not correct


def setupFacets(context, logger=None):
    if logger is None:
        logger = LOG
    logger.info('BCCVL site facet setup handler')

    # only run for this product
    if context.readDataFile('org.bccvl.site.marker.txt') is None:
        return
    portal = context.getSite()

    from org.bccvl.site.faceted.interfaces import IFacetConfigUtility
    from org.bccvl.site.faceted.tool import import_facet_config

    def _setup_facets(content, config, layout=None):
        # enable faceting
        subtyper = getMultiAdapter((content, content.REQUEST),
                                   name=u'faceted_subtyper')
        subtyper.enable()
        # update default layout if requested
        if layout:
            IFacetedLayout(content).update_layout(layout)
        # load facet config
        widgets = getMultiAdapter((content, content.REQUEST),
                                  name=config)
        xml = widgets()
        environ = SnapshotImportContext(content, 'utf-8')
        importer = getMultiAdapter((content, environ), IBody)
        importer.body = xml

    # setup datasets search facets
    datasets = portal[defaults.DATASETS_FOLDER_ID]
    _setup_facets(datasets, 'datasets_default.xml', 'faceted-table-items')

    # go through all facet setups in portal_facetconfig and update them as well
    facet_tool = getUtility(IFacetConfigUtility)
    for obj in facet_tool.types(proxy=False):
        import_facet_config(obj)


def upgrade_180_181_1(context, logger=None):
    # context is either the portal (called from setupVarious) or portal_setup
    # when run via genericsetup
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
            # Add algorithm to job_params if missing algorithm
            try:
                sdmds = uuidToObject(
                    result.job_params['species_distribution_models'])
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
        jobtool.new_job(
            created=ds.created(),
            message=old_job['progress']['message'],
            progress=old_job['progress']['state'],
            state=old_job['state'],
            title=old_job['name'],
            taskid=old_job['taskid'],
            userid=ds.getOwner().getId(),
            content=IUUID(ds),
            type=brain.portal_type
        )

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
            if result.job_params.get('function'):
                toolkit = IUUID(portal[defaults.TOOLKITS_FOLDER_ID][job.function])
            else:
                toolkit = None
            jobtool.new_job(
                created=result.created(),
                message=old_job['progress']['message'],
                progress=old_job['progress']['state'],
                state=old_job['state'],
                title=old_job['name'],
                taskid=old_job['taskid'],
                userid=result.getOwner().getId(),
                content=IUUID(result),
                type=brain.portal_type,
                function=result.job_params.get('function'),
                toolkit=toolkit
            )
            del annots['org.bccvl.state']

    LOG.info('Updating layer metadata for projection outputs')
    from org.bccvl.site.interfaces import IBCCVLMetadata
    for brain in pc.searchResults(BCCDataGenre=('DataGenreCP', 'DataGenreCP_ENVLOP', 'DataGenreFP', 'DataGenreClampingMask')):
        ds = brain.getObject()
        md = IBCCVLMetadata(ds)
        # md['layers'][ds.file.filename] ... there should be only one key
        keys = md['layers'].keys()
        if len(keys) != 1:
            LOG.warning(
                'Found multiple layer keys; do not know what to do: %s', ds.absolute_url())
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
    setup.runImportStepFromProfile(PROFILE_ID, 'rolemap')
    setup.runImportStepFromProfile(PROFILE_ID, 'actions')
    setup.runImportStepFromProfile(PROFILE_ID, 'typeinfo')
    setup.runImportStepFromProfile(PROFILE_ID, 'workflow')
    setup.runImportStepFromProfile(PROFILE_ID, 'viewlets')
    setup.runImportStepFromProfile(PROFILE_ID, 'plone.app.registry')
    setup.runImportStepFromProfile(PROFILE_ID, 'org.bccvl.site.content')
    setup.runImportStepFromProfile(PROFILE_ID, 'org.bccvl.site.facet')

    # install new dependencies
    qi = getToolByName(portal, 'portal_quickinstaller')
    installable = [p['id'] for p in qi.listInstallableProducts()]
    for product in ['collective.emailconfirmationregistration',
                    'plone.formwidget.captcha',
                    'collective.z3cform.norobots']:
        if product in installable:
            qi.installProduct(product)

    # enable self registration
    from plone.app.controlpanel.security import ISecuritySchema
    security = ISecuritySchema(portal)
    security.enable_self_reg = True
    security.enable_user_pwd_choice = True

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

    # setup html filtering
    from plone.app.controlpanel.filter import IFilterSchema
    filters = IFilterSchema(portal)
    # remove some nasty tags:
    current_tags = filters.nasty_tags
    for tag in ('embed', 'object'):
        if tag in current_tags:
            current_tags.remove(tag)
    filters.nasty_tags = current_tags
    # remove some stripped tags:
    current_tags = filters.stripped_tags
    for tag in ('button', 'object', 'param'):
        if tag in current_tags:
            current_tags.remove(tag)
    filters.stripped_tags = current_tags
    # add custom allowed tags
    current_tags = filters.custom_tags
    for tag in ('embed', ):
        if tag not in current_tags:
            current_tags.append(tag)
    filters.custom_tags = current_tags
    # add custom allowed styles
    current_styles = filters.style_whitelist
    for style in ('border-radius', 'padding', 'margin-top', 'margin-bottom', 'background', 'color'):
        if style not in current_styles:
            current_styles.append(style)
    filters.style_whitelist = current_styles

    # configure TinyMCE plugins (can't be done zia tinymce.xml
    tinymce = getToolByName(portal, 'portal_tinymce')
    current_plugins = tinymce.plugins
    if 'media' in current_plugins:
        current_plugins.remove('media')
    tinymce.plugins = current_plugins


def upgrade_240_250_1(context, logger=None):
    if logger is None:
        logger = LOG
    # Run GS steps
    portal = api.portal.get()
    setup = api.portal.get_tool('portal_setup')
    # update permissions on actions
    setup.runImportStepFromProfile(PROFILE_ID, 'actions')
    # update vocabularies
    setup.runImportStepFromProfile(PROFILE_ID, 'plone.app.registry')
    # update initial site content and r scripts
    setup.runImportStepFromProfile(PROFILE_ID, 'org.bccvl.site.content')
    # update facet settings
    setup.runImportStepFromProfile(PROFILE_ID, 'org.bccvl.site.facet')
    # update theme (reimport it?)
    setup.runImportStepFromProfile(THEME_PROFILE_ID, 'plone.app.theming')


def upgrade_250_260_1(context, logger=None):
    if logger is None:
        logger = LOG
    # Run GS steps
    portal = api.portal.get()
    setup = api.portal.get_tool('portal_setup')
    # update permissions on actions
    setup.runImportStepFromProfile(PROFILE_ID, 'actions')
    # update vocabularies
    setup.runImportStepFromProfile(PROFILE_ID, 'plone.app.registry')
    # update initial site content and r scripts
    setup.runImportStepFromProfile(PROFILE_ID, 'org.bccvl.site.content')
    # update facet settings
    setup.runImportStepFromProfile(PROFILE_ID, 'org.bccvl.site.facet')


def upgrade_260_270_1(context, logger=None):
    if logger is None:
        logger = LOG
    # Run GS steps
    portal = api.portal.get()
    setup = api.portal.get_tool('portal_setup')
    # update vocabularies
    setup.runImportStepFromProfile(PROFILE_ID, 'plone.app.registry')
    # update initial site content and r scripts
    setup.runImportStepFromProfile(PROFILE_ID, 'org.bccvl.site.content')

    # remove old trait scripts
    toolkits = portal[defaults.TOOLKITS_FOLDER_ID]
    for algo_id in ('lm', 'gamlss', 'aov', 'manova'):
        if algo_id in toolkits:
            toolkits.manage_delObjects(algo_id)

    # rename traits dataset facet
    from org.bccvl.site.faceted.interfaces import IFacetConfigUtility
    facet_tool = getUtility(IFacetConfigUtility)
    if 'data_table' in facet_tool.context:
        # data_table is still there....
        if 'species_traits_dataset' in facet_tool.context:
            # new facet is already ... delete old one
            facet_tool.context.manage_delObjects('data_table')
        else:
            # rename old one
            facet_tool.context.manage_renameObject(
                'data_table', 'species_traits_dataset')


def upgrade_270_280_1(context, logger=None):
    if logger is None:
        logger = LOG
    # Run GS steps
    portal = api.portal.get()
    setup = api.portal.get_tool('portal_setup')
    # update vocabularies
    setup.runImportStepFromProfile(PROFILE_ID, 'rolemap')
    setup.runImportStepFromProfile(PROFILE_ID, 'controlpanel')
    setup.runImportStepFromProfile(PROFILE_ID, 'plone.app.registry')
    setup.runImportStepFromProfile(PROFILE_ID, 'org.bccvl.site.content')
    # search for all IOAuth2Client settings in the registry and make sure all fields are defined
    registry = getUtility(IRegistry)
    from org.bccvl.site.oauth.interfaces import IOAuth2Client
    coll = registry.collectionOfInterface(IOAuth2Client, check=False)
    # update all items with new interface
    coll.update(coll)
    # install plone.restapi
    qi = getToolByName(portal, 'portal_quickinstaller')
    installable = [p['id'] for p in qi.listInstallableProducts()]
    for product in ['plone.restapi']:
        if product in installable:
            qi.installProduct(product)


def upgrade_280_290_1(context, logger=None):
    if logger is None:
        logger = LOG
    # Run GS steps
    portal = api.portal.get()
    setup = getToolByName(context, 'portal_setup')
    setup.runImportStepFromProfile(PROFILE_ID, 'org.bccvl.site.content')

    pc = getToolByName(context, 'portal_catalog')
    # update category of multispecies dataset to 'multispecies'
    from org.bccvl.site.interfaces import IBCCVLMetadata
    for brain in pc(BCCDataGenre='DataGenreSpeciesCollection'):
        obj = brain.getObject()
        md = IBCCVLMetadata(obj)
        md['categories'] = ['multispecies']
        obj.reindexObject()


def upgrade_290_300_1(context, logger=None):
    if logger is None:
        logger = LOG
    # Run GS steps
    portal = api.portal.get()
    setup = getToolByName(context, 'portal_setup')
    setup.runImportStepFromProfile(PROFILE_ID, 'org.bccvl.site.content')

    pc = getToolByName(context, 'portal_catalog')
    # Add parent dataset to the derived datasets of multispecies
    for brain in pc(BCCDataGenre='DataGenreSpeciesCollection'):
        obj = brain.getObject()
        for part_uuid in obj.parts:
            part_obj = uuidToObject(part_uuid)
            part_obj.part_of = IUUID(obj)
            part_obj.reindexObject()


def upgrade_300_310_1(context, logger=None):
    if logger is None:
        logger = LOG
    # Run GS steps
    portal = api.portal.get()
    setup = getToolByName(context, 'portal_setup')
    setup.runImportStepFromProfile(PROFILE_ID, 'typeinfo')
    setup.runImportStepFromProfile(PROFILE_ID, 'org.bccvl.site.content')
    setup.runImportStepFromProfile(PROFILE_ID, 'plone.app.registry')
    setup.runImportStepFromProfile(PROFILE_ID, 'org.bccvl.site.facet')

    pc = getToolByName(context, 'portal_catalog')
    # Update the state of all experiments
    from org.bccvl.site.content.interfaces import IExperiment
    for brain in pc.searchResults(object_provides=IExperiment.__identifier__):
        obj = brain.getObject()
        obj.reindexObject()

    # fix up Data genres for unconstrained results
    from org.bccvl.site.interfaces import IBCCVLMetadata
    # 1. get all sdm experiments
    for brain in pc.searchResults(portal_type='org.bccvl.content.sdmexperiment'):
        # 2. go through all eresults
        for result in pc.searchResults(path=brain.getPath()):
            # 3. find all DataGenreCP per result
            for dsbrain in pc.searchResults(path=result.getPath(), BCCDataGenre='DataGenreCP'):
                # if _unconstraint is in the title it should be a DataGenreCP_ENVLOP
                if '_unconstraint' in dsbrain.Title and dsbrain.BCCDataGenre != 'DataGenreCP_ENVLOP':
                    obj = dsbrain.getObject()
                    IBCCVLMetadata(obj)['genre'] = 'DataGenreCP_ENVLOP'

    # fix up data genre for unconstrained results
    # 1. get all sdm experiments
    for brain in pc.searchResults(portal_type='org.bccvl.content.projectionexperiment'):
        # 2. go through all eresults
        for result in pc.searchResults(path=brain.getPath()):
            # 3. find all DataGenreCP per result
            for dsbrain in pc.searchResults(path=result.getPath(), BCCDataGenre='DataGenreFP'):
                # if _unconstraint is in the title it should be a DataGenreFP_ENVLOP
                if '_unconstraint' in dsbrain.Title and dsbrain.BCCDataGenre != 'DataGenreFP_ENVLOP':
                    obj = dsbrain.getObject()
                    IBCCVLMetadata(obj)['genre'] = 'DataGenreFP_ENVLOP'


def upgrade_310_320_1(context, logger=None):
    if logger is None:
        logger = LOG
    # Run GS steps
    portal = api.portal.get()
    setup = getToolByName(context, 'portal_setup')
    setup.runImportStepFromProfile(PROFILE_ID, 'org.bccvl.site.content')
    setup.runImportStepFromProfile(PROFILE_ID, 'plone.app.registry')
    setup.runImportStepFromProfile(PROFILE_ID, 'org.bccvl.site.facet')

    pc = getToolByName(context, 'portal_catalog')

    # Tag untagged climate and environmental datasets as terrestrial
    for brain in pc.searchResults(portal_type='org.bccvl.content.remotedataset',
                                  BCCDataGenre=('DataGenreE', 'DataGenreCC', 'DataGenreFC')):
        if 'Freshwater datasets' not in brain.Subject:
            if 'Terrestrial datasets' not in brain.Subject:
                obj = brain.getObject()
                if not obj.subject:
                    obj.subject = ['Terrestrial datasets']
                elif isinstance(obj.subject, tuple):
                    obj.subject = list(obj.subject) + ['Terrestrial datasets']
                else:
                    obj.subject.append('Terrestrial datasets')
                obj.reindexObject()


def upgrade_320_330_1(context, logger=None):
    if logger is None:
        logger = LOG
    # Run GS steps
    portal = api.portal.get()
    setup = getToolByName(context, 'portal_setup')
    setup.runImportStepFromProfile(PROFILE_ID, 'catalog')
    setup.runImportStepFromProfile(PROFILE_ID, 'org.bccvl.site.content')
    setup.runImportStepFromProfile(PROFILE_ID, 'plone.app.registry')
    setup.runImportStepFromProfile(PROFILE_ID, 'org.bccvl.site.facet')

    pc = getToolByName(context, 'portal_catalog')

    # Add BCCDomian index tp catalog
    for brain in pc.searchResults(portal_type='org.bccvl.content.remotedataset',
                                  BCCDataGenre=('DataGenreE', 'DataGenreCC', 'DataGenreFC')):
        obj = brain.getObject()
        obj.reindexObject()


def upgrade_330_340_1(context, logger=None):
    if logger is None:
        logger = LOG
    # Run GS steps
    portal = api.portal.get()
    setup = getToolByName(context, 'portal_setup')
    setup.runImportStepFromProfile(PROFILE_ID, 'catalog')
    setup.runImportStepFromProfile(PROFILE_ID, 'org.bccvl.site.content')
    setup.runImportStepFromProfile(PROFILE_ID, 'plone.app.registry')
    setup.runImportStepFromProfile(PROFILE_ID, 'org.bccvl.site.facet')

    pc = getToolByName(context, 'portal_catalog')

    # transactions can get very big here, this upgrade step is idempotent,
    # so we just commit everything inbetween
    # commiting the full transaction makes it slow, but if we still run
    # out of memory we don't have to repeat the full index walk
    import transaction
    transaction.commit()
    spcounter = 0

    # Update Description for species absence output file
    experiments = portal[defaults.EXPERIMENTS_FOLDER_ID]
    for brain in pc.searchResults(portal_type=('org.bccvl.content.dataset', 'org.bccvl.content.remotedataset'),
                                  BCCDataGenre='DataGenreSpeciesAbsence',
                                  path='/'.join(experiments.getPhysicalPath())):
        obj = brain.getObject()
        if obj.description != u'Absence records (map)':
            obj.description = u'Absence records (map)'
            obj.reindexObject()
            spcounter += 1
            if spcounter % 500 == 0:
                logger.info("Absence rename %d", spcounter)
                transaction.commit()

    transaction.commit()
    spcounter = 0

    # Update description for Australia Dynamic Land Cover dataset
    for brain in pc.searchResults(portal_type='org.bccvl.content.remotedataset',
                                  BCCDataGenre='DataGenreE'):
        if brain.Title == "Australia, Dynamic Land Cover (2000-2008), 9 arcsec (~250 m)":
            obj = brain.getObject()
            obj.description = u"Observed biophysical cover on the Earth's surface."
            obj.reindexObject()
            spcounter += 1
            if spcounter % 500 == 0:
                logger.info("Absence rename %d", spcounter)
                transaction.commit()


def upgrade_340_350_1(context, logger=None):
    if logger is None:
        logger = LOG
    # Run GS steps
    portal = api.portal.get()
    setup = getToolByName(context, 'portal_setup')
    pq = getToolByName(context, 'portal_quickinstaller')

    # remove data_table once and for all
    from org.bccvl.site.faceted.interfaces import IFacetConfigUtility
    facet_tool = getUtility(IFacetConfigUtility)
    if 'data_table' in facet_tool.context:
        # data_table is still there....
        facet_tool.context.manage_delObjects('data_table')

    # reinstall facetednavigation
    pq.uninstallProducts(['eea.jquery', 'eea.facetednavigation'])
    # make sure some of the eea jquery plugins are installed
    # for some reason reinstalling eea.facetednavigation does not always re-apply profile dependencies
    # manually apply dependencies for eea.facetednavigation 10.8
    setup.runAllImportStepsFromProfile('profile-eea.jquery:01-jquery')
    setup.runAllImportStepsFromProfile('profile-eea.jquery:03-ajaxfileupload')
    setup.runAllImportStepsFromProfile('profile-eea.jquery:04-bbq')
    setup.runAllImportStepsFromProfile('profile-eea.jquery:05-cookie')
    setup.runAllImportStepsFromProfile('profile-eea.jquery:10-jstree')
    setup.runAllImportStepsFromProfile('profile-eea.jquery:12-select2uislider')
    setup.runAllImportStepsFromProfile('profile-eea.jquery:14-tagcloud')
    setup.runAllImportStepsFromProfile('profile-eea.jquery:23-select2')
    pq.installProducts(['eea.facetednavigation'])
    # make sure actions and rolemap is setup
    setup.runImportStepFromProfile('profile-eea.facetednavigation:universal', 'actions')
    setup.runImportStepFromProfile('profile-eea.facetednavigation:universal', 'rolemap')
    # make sure diavo is disabled on ajax requests
    from eea.facetednavigation.interfaces import IEEASettings
    registry = getUtility(IRegistry)
    facetsettings = registry.forInterface(IEEASettings)
    facetsettings.disable_diazo_rules_ajax = True

    setup.runImportStepFromProfile(PROFILE_ID, 'jsregistry')
    setup.runImportStepFromProfile(PROFILE_ID, 'cssregistry')
    setup.runImportStepFromProfile(PROFILE_ID, 'org.bccvl.site.content')
    setup.runImportStepFromProfile(PROFILE_ID, 'org.bccvl.site.facet')

    pc = getToolByName(context, 'portal_catalog')

    # Update the headers indexer for occurrence and absence datasets
    # make sure large transactions don't run out of memory
    import transaction
    transaction.commit()
    spcounter = 0

    from org.bccvl.site.interfaces import IBCCVLMetadata
    for brain in pc.unrestrictedSearchResults(portal_type=('org.bccvl.content.dataset', 'org.bccvl.content.remotedataset', 'org.bccvl.content.multispeciesdataset'),
                                              BCCDataGenre=('DataGenreSpeciesOccurrence', 'DataGenreSpeciesCollection',
                                                            'DataGenreSpeciesAbsence', 'DataGenreSpeciesAbsenceCollection')):
        obj = brain.getObject()
        obj.reindexObject()
        spcounter += 1
        if spcounter % 500 == 0:
            logger.info("Reindex Species data %d", spcounter)
            transaction.commit()

    # Do this as very last step in case something goes wrong above and we need
    # to re-run a partially commited upgrade.
    setup.upgradeProfile(THEME_PROFILE_ID)


def upgrade_340_350_2(context, logger=None):
    if logger is None:
        logger = LOG

    portal = api.portal.get()
    # setup stats tool
    from org.bccvl.site.stats.utility import init_stats
    from org.bccvl.site.stats.interfaces import IStatsUtility
    from org.bccvl.site.content.interfaces import IDataset, IExperiment
    init_stats()
    import transaction

    stats = getUtility(IStatsUtility)
    # initialise stats with existing content
    # TODO: do this only if we re-created the stats tool
    # 1. add all existing datasets
    transaction.commit()
    trcounter = 0

    pc = getToolByName(context, 'portal_catalog')

    datasets = portal[defaults.DATASETS_FOLDER_ID]
    for brain in pc.unrestrictedSearchResults(object_provides=IDataset.__identifier__,
                                              path='/'.join(datasets.getPhysicalPath())):
        ds = brain.getObject()
        if not ds.dataSource:
            if brain.Creator in ('BCCVL', 'admin'):
                ds.dataSource = 'ingest'
            else:
                # does it have part_of?
                if ds.part_of:
                    master = get_object_by_uuid(pc, ds.part_of)
                    if not master.dataSource:
                        master.dataSource = 'upload'
                    ds.dataSource = master.dataSource
                else:
                    ds.dataSource = 'upload'
        stats.count_dataset(
            source=ds.dataSource,
            portal_type=brain.portal_type,
            date=brain.created.asdatetime().date()
        )
        trcounter += 1
        if trcounter % 500 == 0:
            logger.info("Collect stats for datasets %d", trcounter)
            transaction.commit()

    transaction.commit()
    trcounter = 0
    # 2. add all experiments
    from org.bccvl.site.job.interfaces import IJobTracker
    experiments = portal[defaults.EXPERIMENTS_FOLDER_ID]
    for brain in pc.unrestrictedSearchResults(object_provides=IExperiment.__identifier__,
                                              path='/'.join(experiments.getPhysicalPath())):
        # we have to count each experiment twice; created, finished
        stats.count_experiment(
            user=brain.Creator,
            portal_type=brain.portal_type,
            date=brain.created.asdatetime().date(),
        )
        exp = brain.getObject()
        exp_runtime = getattr(exp, 'runtime', None)
        if exp_runtime is None:
            # no runtime set on experiment ... calc it from results
            exp_runtime = 0
            for result in exp.values():
                jt = IJobTracker(result)
                rusage = getattr(jt, 'rusage', None)
                if rusage:
                    exp_runtime += rusage.get('ru_utime', 0) + rusage.get('ru_stime', 0)
        stats.count_experiment(
            user=brain.Creator,
            portal_type=brain.portal_type,
            runtime=exp_runtime,
            state=brain.job_state,
            date=brain.modified.asdatetime().date()
        )
        trcounter += 1
        if trcounter % 10 == 0:
            logger.info("Collect stats for experiments %d", trcounter)
            transaction.commit()


    transaction.commit()
    trcounter = 0
    # 3. add all experiment datasets
    for brain in pc.unrestrictedSearchResults(object_provides=IDataset.__identifier__,
                                              path='/'.join(experiments.getPhysicalPath())):
        ds = brain.getObject()
        if not ds.dataSource:
            ds.dataSource = 'experiment'
        stats.count_dataset(
            source=ds.dataSource,
            portal_type=brain.portal_type,
            date=brain.created.asdatetime().date()
        )
        trcounter += 1
        if trcounter % 500 == 0:
            logger.info("Collect stats for experiment results %d", trcounter)
            transaction.commit()

    transaction.commit()
    trcounter = 0
    # 4. count all jobs
    from org.bccvl.site.job.interfaces import IJobUtility
    jobtool = getUtility(IJobUtility)
    jobcatalog = jobtool._catalog()
    for jobid in jobcatalog.jobs:
        job = jobtool.get_job_by_id(jobid)
        # again count each job twice (with and without state)

        portal_type = getattr(job, 'type', None)
        if not portal_type:
            # check title if it is a dataset:
            if ('ala_import' in job.title or
                'traits_import' in job.title or
                'metadata_update' in job.title or
                'import_multi_species_csv' in job.title):
                portal_type = 'org.bccvl.content.remotedataset'
            else:
                # likely an experiment, but which one?
                if 'sdm_experiment' in job.title:
                    # might be a sdm, sdm, mm or traits
                    obj = get_object_by_uuid(pc, job.content)
                    if obj:
                        portal_type = obj.portal_type
                    else:
                        # No idea ... just guess
                        portal_type = 'org.bccvl.content.sdmexperiment'
                elif 'projection experiment' in job.title:
                    portal_type = 'org.bccvl.content.projectionexperiment'
                elif 'ensemble' in job.title:
                    portal_type = 'org.bccvl.content.ensemble'
                elif 'biodiverse' in job.title:
                    portal_type = 'org.bccvl.content.biodiverseexperiment'
                else:
                    logger.warn('Could not determine portal_type for job %s', job.id)
            # update job object as well
            job.type = portal_type

        function = getattr(job, 'function', None)
        if not function:
            # this is either an experiment without function or a dateset
            if portal_type in ('org.bccvl.content.dataset',
                               'org.bccvl.content.remotedataset',
                               'org.bccvl.content.multispeciesdataset'):
                # it is a dateset job... get the dataset and check source
                ds = get_object_by_uuid(pc, job.content)
                if ds:
                    # ds still exists
                    function = ds.dataSource
                else:
                    # ds no longer available ... what now?
                    # this may count things in the wrong category, but we are not too fuzzed about it.
                    if 'ala_import' in job.title:
                        function = 'ala'
                    elif 'traits_import' in job.title:
                        function = 'aekos'
                    elif 'metadata_update' in job.title:
                        function = 'upload'
                    elif 'update_metadata' in job.title:
                        function = 'upload'
                    elif 'import_multi_species_csv' in job.title:
                        # no idea where that came from
                        function = 'upload'
                    # the fallback
                    else:
                        function = 'upload'
            else:
                # it's an experiment without function ... all good
                function = getattr(job, 'function', None)
            # update job object as well
            job.function = function
        # count create
        stats.count_job(
            function=function,
            portal_type=portal_type,
            date=job.created.asdatetime().date()
        )
        if getattr(job, 'rusage', None):
            rusage = job.rusage.get('rusage', {})
            rusage = (rusage.get('ru_utime', 0) + rusage.get('ru_stime', 0))
        else:
            rusage = 0
        # count finished
        stats.count_job(
            function=function,
            portal_type=portal_type,
            runtime=rusage,
            state=job.state,
            # not quite exact, as it is the creation date and not last modified state
            date=job.created.asdatetime().date()
        )
        trcounter += 1
        if trcounter % 500 == 0:
            logger.info("Collect stats for jobs %d", trcounter)
            transaction.commit()

    transaction.commit()

def upgrade_340_350_3(context, logger=None):
    if logger is None:
        logger = LOG

    portal = api.portal.get()
    # setup stats tool
    from org.bccvl.site.content.interfaces import IDataset
    from org.bccvl.site.interfaces import IBCCVLMetadata
    import transaction

    # Add new time-period tag for existing user upload datasets
    transaction.commit()
    trcounter = 0

    pc = getToolByName(context, 'portal_catalog')

    datasets = portal[defaults.DATASETS_FOLDER_ID]
    for folder in (defaults.DATASETS_ENVIRONMENTAL_FOLDER_ID, defaults.DATASETS_CLIMATE_FOLDER_ID):
        for brain in pc.unrestrictedSearchResults(object_provides=IDataset.__identifier__,
                                                  path='/'.join(datasets.getPhysicalPath() + (folder, 'user'))):
            if 'Current datasets' not in brain.Subject and 'Future datasets' not in brain.Subject:
                obj = brain.getObject()
                if not obj.subject:
                    obj.subject = []
                elif isinstance(obj.subject, tuple):
                    obj.subject = list(obj.subject)

                genre = IBCCVLMetadata(obj)['genre']
                if genre == 'DataGenreFC':
                    obj.subject += ["Future datasets"]
                else:
                    obj.subject += ["Current datasets"]
                if genre in ['DataGenreCC', 'DataGenreFC']:
                    IBCCVLMetadata(obj)['categories'] = ['climate']
                obj.reindexObject()
                trcounter += 1
                if trcounter % 500 == 0:
                    logger.info("Add time-period tag for user-uploaded datasets %d", trcounter)
                    transaction.commit()

    transaction.commit()
    trcounter = 0

def upgrade_350_360_1(context, logger=None):
    if logger is None:
        logger = LOG
    # Run GS steps
    portal = api.portal.get()
    setup = getToolByName(context, 'portal_setup')
    pq = getToolByName(context, 'portal_quickinstaller')

    setup.upgradeProfile(THEME_PROFILE_ID)

    setup.runImportStepFromProfile(PROFILE_ID, 'catalog')
    setup.runImportStepFromProfile(PROFILE_ID, 'jsregistry')
    setup.runImportStepFromProfile(PROFILE_ID, 'cssregistry')
    setup.runImportStepFromProfile(PROFILE_ID, 'org.bccvl.site.content')
    setup.runImportStepFromProfile(PROFILE_ID, 'plone.app.registry')
    setup.runImportStepFromProfile(PROFILE_ID, 'org.bccvl.site.facet')

    pc = getToolByName(context, 'portal_catalog')

    # Update the modelling_region/projection_region for experiments
    # make sure large transactions don't run out of memory
    import transaction
    transaction.commit()
    spcounter = 0

    # Update modelling_region to NamedBlobFile
    from plone.namedfile.file import NamedBlobFile
    EXP_TYPES = ['org.bccvl.content.sdmexperiment',
             'org.bccvl.content.mmexperiment',
             'org.bccvl.content.msdmexperiment',
             'org.bccvl.content.speciestraitsexperiment'
             ]
    for brain in pc.searchResults(portal_type=EXP_TYPES):
        # go through all experiments and convert modelling_region to NamedBlobFile
        exp = brain.getObject()
        if hasattr(exp, 'modelling_region') and exp.modelling_region is not None and type(exp.modelling_region) is not NamedBlobFile:
            exp.modelling_region = NamedBlobFile(exp.modelling_region)
            exp.reindexObject()
            spcounter += 1
            if spcounter % 100 == 0:
                logger.info("Convert modelling_region to NamedBlobFile %d", spcounter)
                transaction.commit()

        for job in exp.values():
            if 'modelling_region' in job.job_params and exp.modelling_region is not None and type(job.job_params['modelling_region']) is not NamedBlobFile:
                job.job_params['modelling_region'] = exp.modelling_region
                job.reindexObject()
                spcounter += 1
                if spcounter % 100 == 0:
                    logger.info("Convert job's modelling_region to NamedBlobFile %d", spcounter)
                    transaction.commit()

    # # Update projection_region to NamedBlobFile for CC experiment
    for brain in pc.searchResults(portal_type='org.bccvl.content.projectionexperiment'):
        exp = brain.getObject()
        if hasattr(exp, 'projection_region') and exp.projection_region is not None and type(exp.projection_region) is not NamedBlobFile:
            exp.projection_region = NamedBlobFile(exp.projection_region)
            exp.reindexObject()
            spcounter += 1
            if spcounter % 100 == 0:
                logger.info("Convert projection_region to NamedBlobFile %d", spcounter)
                transaction.commit()
        for job in exp.values():
            if 'projection_region' in job.job_params and exp.projection_region is not None and type(job.job_params['projection_region']) is not NamedBlobFile:
                job.job_params['projection_region'] = exp.projection_region
                job.reindexObject()
                spcounter += 1
                if spcounter % 100 == 0:
                    logger.info("Convert job's projection_region to NamedBlobFile %d", spcounter)
                    transaction.commit()

    transaction.commit()
    spcounter = 0

def upgrade_350_360_2(context, logger=None):
    if logger is None:
        logger = LOG

    # Run GS steps
    portal = api.portal.get()
    setup = getToolByName(context, 'portal_setup')
    setup.runImportStepFromProfile(PROFILE_ID, 'jsregistry')
    setup.runImportStepFromProfile(PROFILE_ID, 'cssregistry')
    setup.runImportStepFromProfile(PROFILE_ID, 'org.bccvl.site.content')
    setup.runImportStepFromProfile(PROFILE_ID, 'plone.app.registry')

    pc = getToolByName(context, 'portal_catalog')

    # setup stats tool
    import transaction

    # Add new time-period tag for existing user upload datasets
    transaction.commit()
    trcounter = 0

def upgrade_360_370_1(context, logger=None):
    if logger is None:
        logger = LOG

    # Run GS steps
    portal = api.portal.get()
    setup = getToolByName(context, 'portal_setup')
    setup.runImportStepFromProfile(PROFILE_ID, 'jsregistry')
    setup.runImportStepFromProfile(PROFILE_ID, 'cssregistry')
    setup.runImportStepFromProfile(PROFILE_ID, 'org.bccvl.site.content')
    setup.runImportStepFromProfile(PROFILE_ID, 'plone.app.registry')
    setup.runImportStepFromProfile(PROFILE_ID, 'org.bccvl.site.facet')

    pc = getToolByName(context, 'portal_catalog')

    # setup stats tool
    import transaction

    # Add new time-period tag for existing user upload datasets
    transaction.commit()
    trcounter = 0

def upgrade_370_380_1(context, logger=None):
    if logger is None:
        logger = LOG

    # Run GS steps
    portal = api.portal.get()
    setup = getToolByName(context, 'portal_setup')
    setup.runImportStepFromProfile(PROFILE_ID, 'jsregistry')
    setup.runImportStepFromProfile(PROFILE_ID, 'cssregistry')
    setup.runImportStepFromProfile(PROFILE_ID, 'org.bccvl.site.content')
    setup.runImportStepFromProfile(PROFILE_ID, 'plone.app.registry')
    setup.runImportStepFromProfile(PROFILE_ID, 'org.bccvl.site.facet')

    pc = getToolByName(context, 'portal_catalog')

    # setup stats tool
    import transaction

    # Add new time-period tag for existing user upload datasets
    transaction.commit()
    trcounter = 0

def upgrade_380_390_1(context, logger=None):
    if logger is None:
        logger = LOG

    # Run GS steps
    portal = api.portal.get()
    setup = getToolByName(context, 'portal_setup')
    setup.runImportStepFromProfile(PROFILE_ID, 'jsregistry')
    setup.runImportStepFromProfile(PROFILE_ID, 'cssregistry')
    setup.runImportStepFromProfile(PROFILE_ID, 'org.bccvl.site.content')
    setup.runImportStepFromProfile(PROFILE_ID, 'plone.app.registry')
    setup.runImportStepFromProfile(PROFILE_ID, 'org.bccvl.site.facet')

    pc = getToolByName(context, 'portal_catalog')

    # setup stats tool
    import transaction

    # Add new time-period tag for existing user upload datasets
    transaction.commit()
    trcounter = 0

def upgrade_380_390_2(context, logger=None):
    if logger is None:
        logger = LOG

    # Run GS steps
    portal = api.portal.get()
    setup = getToolByName(context, 'portal_setup')
    setup.runImportStepFromProfile(PROFILE_ID, 'jsregistry')
    setup.runImportStepFromProfile(PROFILE_ID, 'cssregistry')
    setup.runImportStepFromProfile(PROFILE_ID, 'org.bccvl.site.content')
    setup.runImportStepFromProfile(PROFILE_ID, 'plone.app.registry')
    setup.runImportStepFromProfile(PROFILE_ID, 'org.bccvl.site.facet')

    pc = getToolByName(context, 'portal_catalog')

    # setup stats tool
    import transaction

    # Add new time-period tag for existing user upload datasets
    transaction.commit()
    trcounter = 0