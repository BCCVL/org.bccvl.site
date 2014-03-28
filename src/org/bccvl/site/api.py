from org.bccvl.site import defaults
from org.bccvl.site.content.function import IFunction
from org.bccvl.site.content.dataset import IDataset
from org.bccvl.site.interfaces import IExperiment
from org.bccvl.site.namespace import BCCVOCAB
from zope.component import queryUtility
from Products.CMFPlone.interfaces import IPloneSiteRoot


class QueryAPI(object):
    """
    Provides API for common queries
    """
    def __init__(self, context):
        site = queryUtility(IPloneSiteRoot)

        self.context = context
        self.site = site
        self.site_physical_path = '/'.join(site.getPhysicalPath())
        self.portal_catalog = site.portal_catalog

    # def getDatasets(self, genre):
    def getDatasets(self, **query_params):

        # datasets_physical_path = '/'.join(
        #     [self.site_physical_path, defaults.DATASETS_FOLDER_ID]
        # )
        # brains = self.portal_catalog(
        #     path={'query': datasets_physical_path},
        #     # BCCDataGenre = genre,
        #     **query_params
        # )
        # path query won't find result datasets
        brains = self.portal_catalog(
            object_provides=IDataset.__identifier__,
            ** query_params)
        return brains

    def getSpeciesOccurrenceDatasets(self):
        return self.getDatasets(BCCDataGenre=BCCVOCAB['DataGenreSO'])

    def getSpeciesPresenceDatasets(self):
        return self.getDatasets(
            BCCDataGenre=BCCVOCAB['DataGenreSO'],
            BCCSpeciesLayer=BCCVOCAB['SpeciesLayerP']
        )

    def getSpeciesAbsenceDatasets(self):
        return self.getDatasets(
            BCCDataGenre=BCCVOCAB['DataGenreSO'],
            BCCSpeciesLayer=BCCVOCAB['SpeciesLayerX']
        )

    def getSpeciesAbundanceDatasets(self):
        return self.getDatasets(
            BCCDataGenre=BCCVOCAB['DataGenreSO'],
            BCCSpeciesLayer=BCCVOCAB['SpeciesLayerA']
        )

    def getSpeciesDistributionModelDatasets(self):
        return self.getDatasets(BCCDataGenre=BCCVOCAB['DataGenreSD'])

    def getSpeciesDistributionModelEvaluationDatasets(self):
        return self.getDatasets(BCCDateGenre=BCCVOCAB['DataGenreSDMEval'])

    def getEnvironmentalDatasets(self):
        return self.getDatasets(BCCDataGenre=BCCVOCAB['DataGenreE'])

    def getFutureClimateDatasets(self, year=None, emission_scenario=None,
                                 climate_model=None):
        query = dict(BCCDataGenre=BCCVOCAB['DataGenreFC'])
        # TODO: optional param selection goes here
        return self.getDatasets(**query)

    def getFutureProjectionDatasets(self):
        # use context to restrict to only ones that match layers?
        return self.getDatasets(
            BCCDataGenre=BCCVOCAB['DataGenreFP'],
        )

    def getFunctions(self):
        functions_physical_path = '/'.join(
            [self.site_physical_path, defaults.FUNCTIONS_FOLDER_ID]
        )
        brains = self.portal_catalog(
            path={'query': functions_physical_path},
            object_provides=IFunction.__identifier__,
            sort_on='sortable_title',

        )
        return brains

    def getEnviroLayers(self):
        return self.portal_catalog.uniqueValuesFor('BCCEnviroLayer')

    def getExperiments(self):
        experiments_physical_path = '/'.join(
            [self.site_physical_path, defaults.EXPERIMENTS_FOLDER_ID]
        )
        brains = self.portal_catalog(
            path={'query': experiments_physical_path},
            object_provides=IExperiment.__identifier__,
            sort_on='created',
            sort_order='descending'
        )
        return brains
