from Products.Five import BrowserView
from plone.app.content.browser.interfaces import IFolderContentsView
from zope.interface import implementer
from plone.app.uuid.utils import uuidToObject, uuidToCatalogBrain
from org.bccvl.site.vocabularies import envirolayer_source
from org.bccvl.site.api import QueryAPI
from org.bccvl.site.namespace import DWC, BCCPROP
from collections import defaultdict
from zope.component import getUtility
from zope.schema.interfaces import IContextSourceBinder
from gu.z3cform.rdf.interfaces import IGraph
from gu.z3cform.rdf.utils import Period
from ordf.namespace import DC


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

    def experiments(self):
        api = QueryAPI(self.context)
        return api.getExperiments()

    def experiment_details(self, expbrain):
        details = {}

        if expbrain.portal_type == 'org.bccvl.content.projectionexperiment':
            # TODO: duplicate code here... see org.bccvl.site.browser.widget.py
            exp = expbrain.getObject()
            sdm = uuidToObject(exp.species_distribution_models)
            if sdm is not None:
                sdmresult = sdm.__parent__
                sdmexp = sdmresult.__parent__
                envlayervocab = getUtility(IContextSourceBinder, name='envirolayer_source')(self.context)
                # TODO: absence data
                envlayers = ', '.join(
                    '{}: {}'.format(uuidToCatalogBrain(envuuid).Title,
                                    ', '.join(envlayervocab.getTerm(envlayer).title
                                            for envlayer in sorted(layers)))
                    for (envuuid, layers) in sorted(sdmexp.environmental_datasets.items()))
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
                'environmental_layers': envlayers
            })
        elif expbrain.portal_type == 'org.bccvl.content.sdmexperiment':
            # this is ripe for optimising so it doesn't run every time
            # experiments are listed
            envirolayer_vocab = envirolayer_source(self.context)
            environmental_layers = defaultdict(list)
            exp = expbrain.getObject()
            if exp.environmental_datasets:
                for dataset, layers in exp.environmental_datasets.items():
                    for layer in layers:
                        environmental_layers[dataset].append(
                            envirolayer_vocab.getTerm(layer).title
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
