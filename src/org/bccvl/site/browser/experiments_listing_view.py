from Products.Five import BrowserView
from Products.CMFPlone.interfaces import IPloneSiteRoot
from Products.CMFCore.utils import getToolByName
from plone.app.content.browser.interfaces import IFolderContentsView
from zope.interface import implementer
from plone.app.uuid.utils import uuidToObject, uuidToCatalogBrain
from plone.app.contentlisting.interfaces import IContentListing
from org.bccvl.site.interfaces import IBCCVLMetadata
from org.bccvl.site.content.interfaces import IExperiment, ISDMExperiment
from collections import defaultdict
from zope.component import getUtility, queryUtility, getMultiAdapter
from zope.schema.interfaces import IVocabularyFactory
from gu.z3cform.rdf.utils import Period
from org.bccvl.site import defaults


def get_title_from_uuid(uuid):
    obj = uuidToCatalogBrain(uuid)
    if obj:
        return obj.Title
    return None


# FIXME: this view needs to exist for default browser layer as well
#        otherwise diazo.off won't find the page if set up.
#        -> how would unthemed markup look like?
#        -> theme would only have updated template.
@implementer(IFolderContentsView)
class ExperimentsListingView(BrowserView):

    def __call__(self):
        envvocab = getUtility(IVocabularyFactory,
                              name='layer_source')
        # TODO: could also cache the next call per request?
        self.envlayervocab = envvocab(self.context)
        return super(ExperimentsListingView, self).__call__()

    def new_experiment_actions(self):
        experimenttypes = ('org.bccvl.content.sdmexperiment',
                           'org.bccvl.content.projectionexperiment',
                           'org.bccvl.content.ensemble',
                           'org.bccvl.content.biodiverseexperiment',
                           'org.bccvl.content.speciestraitsexperiment')
        ftool = getMultiAdapter((self.context, self.request),
                                name='folder_factories')
        actions = ftool.addable_types(experimenttypes)
        return dict((action['id'], action) for action in actions)

    def contentFilter(self):
        # alternative would be to use @@plone_portal_state
        # TODO: maybe we can simply parse the request here to change
        #       sort_order, or do batching?
        site_path = queryUtility(IPloneSiteRoot).getPhysicalPath()
        return {
            'path': {
                'query': '/'.join(site_path + (defaults.EXPERIMENTS_FOLDER_ID, ))
            },
            'object_provides': IExperiment.__identifier__,
            'sort_on': 'created',
            'sort_order': 'descending',
        }

    def experiment_details(self, expbrain):
        # FIXME: this method is really slow, e.g. all the vocabs are re-read for each item
        details = {}

        if expbrain.portal_type == 'org.bccvl.content.projectionexperiment':
            # TODO: duplicate code here... see org.bccvl.site.browser.widget.py
            # TODO: generated list here not very useful,.... all layers over all sdms are concatenated
            exp = expbrain.getObject()
            for sdmuuid in exp.species_distribution_models:
                sdm = uuidToObject(sdmuuid)
                if sdm is not None:
                    # TODO: in theory it could fail when trying to access parents as well?
                    sdmresult = sdm.__parent__
                    sdmexp = sdmresult.__parent__
                    # TODO: absence data
                    envlayers = []
                    for envuuid, layers in sorted(sdmexp.environmental_datasets.items()):
                        envbrain = uuidToCatalogBrain(envuuid)
                        envtitle = envbrain.Title if envbrain else u'Missing dataset'
                        envlayers.append(
                            '{}: {}'.format(envtitle,
                                            ', '.join(self.envlayervocab.getTerm(envlayer).title
                                                      for envlayer in sorted(layers)))
                        )

                    toolkit = sdmresult.job_params['function']
                    species_occ = get_title_from_uuid(sdmexp.species_occurrence_dataset)
                else:
                    # FIXME: should we prevent users from deleting / unsharing?
                    toolkit = 'missing experiment'
                    species_occ = ''
                    envlayers = []

            details.update({
                'type': 'PROJECTION',
                'functions': toolkit,
                'species_occurrence': species_occ,
                'species_absence': '',
                'environmental_layers': ', '.join(envlayers)
            })
        elif expbrain.portal_type == 'org.bccvl.content.sdmexperiment':
            # TODO: this is ripe for optimising so it doesn't run every time
            # experiments are listed
            environmental_layers = defaultdict(list)
            exp = expbrain.getObject()
            if exp.environmental_datasets:
                for dataset, layers in exp.environmental_datasets.items():
                    for layer in layers:
                        environmental_layers[dataset].append(
                            self.envlayervocab.getTerm(layer).title
                        )

            details.update({
                'type': 'SDM',
                'functions': ', '.join(
                    get_title_from_uuid(func) for func in exp.functions
                ),
                'species_occurrence': get_title_from_uuid(
                    exp.species_occurrence_dataset),
                'species_absence': get_title_from_uuid(
                    exp.species_absence_dataset),
                'environmental_layers': ', '.join(
                    '{}: {}'.format(get_title_from_uuid(dataset),
                                    ', '.join(layers))
                    for dataset, layers in environmental_layers.items()
                ),
            })
        elif expbrain.portal_type == 'org.bccvl.content.biodiverseexperiment':
            # FIXME: implement this
            exp = expbrain.getObject()
            species = set()
            years = set()
            emscs = set()
            gcms = set()
            for dsuuid in (x['dataset'] for x in exp.projection):
                dsobj = uuidToObject(dsuuid)
                if not dsobj:
                    # TODO: can't access dateset anymore, let user know somehow
                    continue
                md = IBCCVLMetadata(dsobj)
                species.add(md.get('species', {}).get('scientificName'))
                period = md.get('temporal')
                if period:
                    years.add(Period(period).start)
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
                'environmental_layers': ', '.join(sorted(years)),
            })
        elif expbrain.portal_type == 'org.bccvl.content.ensemble':
            # FIXME: implement this
            details.update({
                'type': 'ENSEMBLE',
                'functions': '',
                'species_occurrence': '',
                'species_absence': '',
                'environmental_layers': '',
            })
        elif expbrain.portal_type == 'org.bccvl.content.speciestraitsexperiment':
            # FIXME: implement this
            details.update({
                'type': 'SECIES TRAITS',
                'functions': '',
                'species_occurrence': '',
                'species_absence': '',
                'environmental_layers': '',
            })

        return details


class ExperimentsListingPopup(BrowserView):

    def __call__(self):

        return super(ExperimentsListingPopup, self).__call__()

    def experimentslisting(self):
        site_path = queryUtility(IPloneSiteRoot).getPhysicalPath()
        b_start = self.request.get('b_start', 0)
        b_size = self.request.get('b_size', 20)
        experiment_type = self.request.get('datasets.filter.experimenttype', None)
        query = {
            'path': {
                'query': '/'.join(site_path + (defaults.EXPERIMENTS_FOLDER_ID, ))
            },
            'object_provides': experiment_type,
            'sort_on': 'created',
            'sort_order': 'descending',
            # provide batch hints to catalog
            'b_start': b_start,
            'b_size': b_size
        }
        pc = getToolByName(self.context, 'portal_catalog')
        results = pc.searchResults(query)
        from Products.CMFPlone import Batch

        return Batch(IContentListing(results), b_size, b_start)
