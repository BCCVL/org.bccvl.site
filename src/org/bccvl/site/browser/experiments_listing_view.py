from Products.Five import BrowserView
from Products.CMFPlone.interfaces import IPloneSiteRoot
from Products.CMFCore.utils import getToolByName
from Products.ZCatalog.interfaces import ICatalogBrain
from plone.app.content.browser.interfaces import IFolderContentsView
from zope.interface import implementer
from plone.app.uuid.utils import uuidToObject, uuidToCatalogBrain
from plone.app.contenttypes.browser.folder import FolderView
from plone.app.contentlisting.interfaces import IContentListing
from plone.app.contentlisting.interfaces import IContentListingObject
from org.bccvl.site.interfaces import IBCCVLMetadata
from org.bccvl.site.content.interfaces import IExperiment
from org.bccvl.site.interfaces import IExperimentJobTracker
from collections import defaultdict
from zope.component import queryUtility, getMultiAdapter
from org.bccvl.site import defaults
from itertools import chain
from org.bccvl.site.browser.interfaces import IExperimentTools
from zope.security import checkPermission


def get_title_from_uuid(uuid):
    obj = uuidToCatalogBrain(uuid)
    if obj:
        return obj.Title
    return None

@implementer(IExperimentTools)
class ExperimentTools(BrowserView):

    def check_if_used(self, itemob=None):
        itemob = itemob or self.context
        portal_catalog = getToolByName(itemob, 'portal_catalog')
        return len(list(portal_catalog.unrestrictedSearchResults(experiment_reference=itemob.UID()))) > 0

    def get_depending_experiment_titles(self, itemob=None):
        itemob = itemob or self.context
        portal_catalog = getToolByName(itemob, 'portal_catalog')
        ur = list(portal_catalog.unrestrictedSearchResults(experiment_reference=itemob.UID()))
        rrpaths = map(lambda x: x.getPath(), portal_catalog.searchResults(experiment_reference=itemob.UID()))
        return map(lambda x: x.Title if x.getPath() in rrpaths else "(Private - owned by %s)" % x._unrestrictedGetObject().getOwner().getUserName(), ur)

    def can_modify(self, itemob=None):
        try:
            itemob = itemob or self.context
            return checkPermission('cmf.ModifyPortalContent', itemob)
        except Exception as e:
            import pdb; pdb.set_trace()

    def get_state_css(self, itemob=None):
        itemob = itemob or self.context
        if ICatalogBrain.providedBy(itemob) or IContentListingObject.providedBy(itemob):
            itemob = itemob.getObject()
        css_map = {
            None: 'success',
            'QUEUED': 'info',
            'RUNNING': 'info',
            'COMPLETED': 'success',
            'FAILED': 'error',
            'REMOVED': 'removed'
        }
        # check job_state and return either success, error or block
        job_state = IExperimentJobTracker(itemob).state
        return css_map.get(job_state, 'info')

    def experiment_details(self, expbrain):
        details = {}
        if expbrain.portal_type == 'org.bccvl.content.projectionexperiment':
            details = projection_listing_details(expbrain)
        elif expbrain.portal_type == 'org.bccvl.content.sdmexperiment':
            details = sdm_listing_details(expbrain)
        elif expbrain.portal_type == 'org.bccvl.content.biodiverseexperiment':
            details = biodiverse_listing_details(expbrain)
        elif expbrain.portal_type == 'org.bccvl.content.ensemble':
            details = ensemble_listing_details(expbrain)
        elif expbrain.portal_type == 'org.bccvl.content.speciestraitsexperiment':
            details = speciestraits_listing_details(expbrain)
        return details


@implementer(IFolderContentsView)
class ExperimentsListingView(FolderView):

    def __init__(self, context, request):
        # update limit_display if it is not already set
        limit_display = getattr(request, 'limit_display', None)
        if limit_display is None:
            request.limit_display = 100
        super(ExperimentsListingView, self).__init__(context, request)

    def new_experiment_actions(self):
        experimenttypes = ('org.bccvl.content.sdmexperiment',
                           'org.bccvl.content.msdmexperiment',
                           'org.bccvl.content.projectionexperiment',
                           'org.bccvl.content.ensemble',
                           'org.bccvl.content.biodiverseexperiment',
                           'org.bccvl.content.speciestraitsexperiment')
        ftool = getMultiAdapter((self.context, self.request),
                                name='folder_factories')
        actions = ftool.addable_types(experimenttypes)
        return dict((action['id'], action) for action in actions)

    def results(self, **kwargs):
        # set our search filters in kwargs and pass on to super class
        kwargs.update({
            'path': {
                'query': '/'.join((self.portal_state.navigation_root_path(),
                                   defaults.EXPERIMENTS_FOLDER_ID))
            },
            'object_provides': IExperiment.__identifier__,
            'sort_on': 'created',
            'sort_order': 'descending',
        })
        return super(ExperimentsListingView, self).results(**kwargs)


# FIXME: the methods below, should be looked up via named adapter or similar.
#        furthermore, in the experimentlisting view it might be good to use
#        templates / or macros that are lookup up via (view, request, context)
#        to support different list item rendering based on view and context (re-use on listing page and popup listing?)

def sdm_listing_details(expbrain):
    # TODO: this is ripe for optimising so it doesn't run every time
    # experiments are listed
    details = {}
    environmental_layers = defaultdict(list)
    exp = expbrain.getObject()
    if exp.environmental_datasets:
        details.update({
            'type': 'SDM',
            'functions': ', '.join(
                get_title_from_uuid(func) for func in exp.functions
            ),
            'species_occurrence': get_title_from_uuid(
                exp.species_occurrence_dataset),
            'species_absence': get_title_from_uuid(
                exp.species_absence_dataset),
            'environmental_layers': ({
                'title': get_title_from_uuid(dataset),
                'layers': sorted(layers)
                } for dataset, layers in exp.environmental_datasets.items()
            ),
        })
    return details



def projection_listing_details(expbrain):

    # TODO: duplicate code here... see org.bccvl.site.browser.widget.py
    # TODO: generated list here not very useful,.... all layers over all sdms are concatenated
    # TODO: whata about future datasets?
    details = {}
    exp = expbrain.getObject()
    for sdmuuid in exp.species_distribution_models:
        sdmexp = uuidToObject(sdmuuid)
        if sdmexp is not None:
            # TODO: absence data
            envlayers = []
            for envuuid, layers in sorted(sdmexp.environmental_datasets.items()):
                envbrain = uuidToCatalogBrain(envuuid)
                envtitle = envbrain.Title if envbrain else u'Missing dataset'
                envlayers.append({
                    'title': envtitle,
                    'layers': sorted(layers)
                })
                # TODO: job_params has only id of function not uuid ... not sure how to get to the title
                toolkits = ', '.join(uuidToObject(sdmmodel).__parent__.job_params['function'] for sdmmodel in exp.species_distribution_models[sdmuuid])
                species_occ = get_title_from_uuid(sdmexp.species_occurrence_dataset)
        else:
            toolkits = 'missing experiment'
            species_occ = ''
            envlayers = []

        details.update({
            'type': 'PROJECTION',
            'functions': toolkits,
            'species_occurrence': species_occ,
            'species_absence': '',
            'environmental_layers': envlayers
        })
    return details


def biodiverse_listing_details(expbrain):
    details = {}
    exp = expbrain.getObject()
    species = set()
    years = set()
    months = set()
    emscs = set()
    gcms = set()
    for dsuuid in chain.from_iterable(map(lambda x: x.keys(), exp.projection.itervalues())):
        dsobj = uuidToObject(dsuuid)
        # TODO: should inform user about missing dataset
        if dsobj:
            md = IBCCVLMetadata(dsobj)
            species.add(md.get('species', {}).get('scientificName', ''))
            year = md.get('year')
            if year:
                years.add(year)
            month = md.get('month')
            if month:
                months.add(month)
            gcm = md.get('gcm')
            if gcm:
                gcms.add(gcm)
            emsc = md.get('emsc')
            if emsc:
                emscs.add(emsc)
    details.update({
        'type': 'BIODIVERSE',
        'functions': 'endemism, redundancy',
        'species_occurrence': ', '.join(sorted(species)),
        'species_absence': '{}, {}'.format(', '.join(sorted(emscs)),
                                           ', '.join(sorted(gcms))),
        'years': ', '.join(sorted(years)),
        'months': ', '.join(sorted(months))
    })
    return details


def ensemble_listing_details(expbrain):
    # FIXME: implement this
    details = {}
    details.update({
        'type': 'ENSEMBLE',
        'functions': '',
        'species_occurrence': '',
        'species_absence': '',
        'environmental_layers': '',
    })
    return details


def speciestraits_listing_details(expbrain):
    # FIXME: implement this
    details = {}
    details.update({
        'type': 'SECIES TRAITS',
        'functions': '',
        'species_occurrence': '',
        'species_absence': '',
        'environmental_layers': '',
    })
    return details
