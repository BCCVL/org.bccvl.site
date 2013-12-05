from org.bccvl.site import defaults
from org.bccvl.site.namespace import BCCVOCAB
from org.bccvl.site.content.function import IFunction

class QueryAPI(object):
    """
    Provides API for common queries
    """
    def __init__(self, context):
        site = context.portal_url.getPortalObject()

        self.context = context
        self.site = site
        self.site_physical_path = '/'.join(site.getPhysicalPath())
        self.portal_catalog = site.portal_catalog

    # def getDatasets(self, genre):
    def getDatasets(self, **query_params):

        datasets_physical_path = '/'.join(
            [self.site_physical_path, defaults.DATASETS_FOLDER_ID]
        )
        brains = self.portal_catalog(
            path={'query': datasets_physical_path},
            # BCCDataGenre = genre,
            **query_params
        )
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

    def getSpeciesDistributionDatasets(self):
        return self.getDatasets(BCCDataGenre=BCCVOCAB['DataGenreSD'])

    def getEnvironmentalDatasets(self):
        return self.getDatasets(BCCDataGenre=BCCVOCAB['DataGenreE'])

    def getFutureClimateDatasets(self):
        return self.getDatasets(BCCDataGenre=BCCVOCAB['DataGenreFC'])

    def getFunctions(self):
        functions_physical_path = '/'.join(
            [self.site_physical_path, defaults.FUNCTIONS_FOLDER_ID]
        )
        brains = self.portal_catalog(
            path={'query': functions_physical_path},
            object_provides=IFunction.__identifier__
        )
        return brains

    def getEnviroLayers(self):
        return self.portal_catalog.uniqueValuesFor('BCCEnviroLayer')
