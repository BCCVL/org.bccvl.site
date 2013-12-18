from Products.Five import BrowserView
from Products.Five.browser.pagetemplatefile import ViewPageTemplateFile
from plone.app.content.browser.interfaces import IFolderContentsView
from zope.interface import implementer
from plone.app.uuid.utils import uuidToObject
from org.bccvl.site.content import experiment
from org.bccvl.site.vocabularies import envirolayer_source
from org.bccvl.site.api import QueryAPI
from collections import defaultdict

def get_title_from_uuid(uuid):
    return uuidToObject(uuid).title
    


@implementer(IFolderContentsView)
class ExperimentsFolderView(BrowserView):
    def experiments(self):
        api = QueryAPI(self.context)
        experiments_brains = [
            brain.getObject() for brain in api.getExperiments()
        ]
        experiments = sorted(experiments_brains, 
            key=lambda x: x.creation_date,
            reverse=True
        )
        
        experiments_details = [
            self._experiment_details(experiment) for experiment in experiments
        ]
        return experiments_details

    def _experiment_details(self, exp):
        details = dict(
            title = exp.title,
            summary = exp.description,
            creation_date = exp.creation_date.strftime('%b %d, %Y %I:%M %p'),
            url = exp.absolute_url_path(),
            # hook for any other requirements
            self = exp,
        )
        
        if exp.__class__ is experiment.ProjectionExperiment:
            details.update(dict(
                type='PROJECTION',
            ))
 
        if exp.__class__ is experiment.SDMExperiment:
            # this is ripe for optimising so it doesn't run every time
            # experiments are listed
            envirolayer_vocab = envirolayer_source(self.context)
            environmental_layers = defaultdict(list)
            for layer, dataset in exp.environmental_layers.items():
                environmental_layers[dataset].append(
                    envirolayer_vocab.getTermByToken(str(layer)).title
                )

            details.update(dict(
                type = 'SDM',
                functions = ', '.join(
                     get_title_from_uuid(func) for func in exp.functions
                ),
                species_occurrence = get_title_from_uuid(exp.species_occurrence_dataset),
                species_absence = get_title_from_uuid(exp.species_absence_dataset),
                environmental_layers = ', '.join(
                    '%s: %s' % (get_title_from_uuid(dataset), ', '.join(layers))
                    for dataset, layers in environmental_layers.items()
                )
            ))
        return details
