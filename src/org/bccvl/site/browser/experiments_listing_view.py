from Products.Five import BrowserView
from plone.app.content.browser.interfaces import IFolderContentsView
from zope.interface import implementer
from plone.app.uuid.utils import uuidToObject, uuidToCatalogBrain
from org.bccvl.site.vocabularies import envirolayer_source
from org.bccvl.site.api import QueryAPI
from collections import defaultdict
from zope.component import getUtility
from zope.schema.interfaces import IContextSourceBinder


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
            sdmresult = sdm.__parent__
            sdmexp = sdmresult.__parent__
            envlayervocab = getUtility(IContextSourceBinder, name='envirolayer_source')(self.context)
            # TODO: absence data
            envlayers = ', '.join(
                '{}: {}'.format(uuidToCatalogBrain(envuuid).Title,
                                ', '.join(envlayervocab.getTerm(envlayer).title
                                          for envlayer in sorted(layers)))
                    for (envuuid, layers) in sorted(sdmexp.environmental_datasets.items()))

            details.update({
                'type': 'PROJECTION',
                'functions': sdmresult.toolkit,
                'species_occurrence': get_title_from_uuid(sdmexp.species_occurrence_dataset),
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
            details.update({
                'type': 'Biodiverse',
                'functions': 'biodiverse options',
                'species_occurrence': 'Species1, Species2, Species3',
                'species_absence': '',
                'environmental_layers': '2015, 2020, 2025'  # should be years?
            })
        return details
