from Products.Five import BrowserView
from Products.CMFPlone.interfaces import IPloneSiteRoot
from plone.app.content.browser.interfaces import IFolderContentsView
from zope.interface import implementer
from plone.app.uuid.utils import uuidToObject, uuidToCatalogBrain
from org.bccvl.site.namespace import DWC, BCCPROP
from org.bccvl.site.content.interfaces import IExperiment
from collections import defaultdict
from zope.component import getUtility, queryUtility
from zope.schema.interfaces import IVocabularyFactory
from gu.z3cform.rdf.interfaces import IGraph
from gu.z3cform.rdf.utils import Period
from ordf.namespace import DC
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
                              name='org.bccvl.site.BioclimVocabulary')
        # TODO: could also cache the next call per request?
        self.envlayervocab = envvocab(self.context)
        return super(ExperimentsListingView, self).__call__()

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
            exp = expbrain.getObject()
            sdm = uuidToObject(exp.species_distribution_models)
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
                dsmd = IGraph(dsobj)
                species.add(unicode(dsmd.value(dsmd.identifier,
                                               DWC['scientificName'])))
                period = dsmd.value(dsmd.identifier, DC['temporal'])
                if period:
                    years.add(Period(period).start)
                gcm = dsmd.value(dsmd.identifier, BCCPROP['gcm'])
                if gcm:
                    gcms.add(gcm.split('#', 1)[-1])
                emsc = dsmd.value(dsmd.identifier, BCCPROP['emissionscenario'])
                if emsc:
                    emscs.add(emsc.split('#', 1)[-1])

            details.update({
                'type': 'BIODIVERSE',
                'functions': 'endemism, redundancy',
                'species_occurrence': ', '.join(sorted(species)),
                'species_absence': '{}, {}'.format(', '.join(sorted(emscs)),
                                                   ', '.join(sorted(gcms))),
                'environmental_layers': ', '.join(sorted(years)),
            })
        return details
