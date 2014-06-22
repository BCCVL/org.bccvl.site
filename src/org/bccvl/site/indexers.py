from plone.indexer.decorator import indexer
from plone.indexer.interfaces import IIndexer
from zope.interface import implementer
from org.bccvl.site.content.interfaces import IDataset
from org.bccvl.site.content.interfaces import IExperiment
from org.bccvl.site.content.interfaces import IBlobDataset
from org.bccvl.site.content.interfaces import IRemoteDataset
from org.bccvl.site.interfaces import IJobTracker
from gu.z3cform.rdf.interfaces import IGraph
from org.bccvl.site.api.dataset import getbiolayermetadata
from .namespace import BCCPROP, BCCVOCAB, BIOCLIM


@indexer(IDataset)
def dataset_BCCDataGenre(object, *kw):
    graph = IGraph(object)
    return tuple(graph.objects(graph.identifier, BCCPROP['datagenre']))


@indexer(IDataset)
def dataset_BCCSpeciesLayer(object, *kw):
    graph = IGraph(object)
    return tuple(graph.objects(graph.identifier, BCCPROP['specieslayer']))


@indexer(IDataset)
def dataset_BCCEmissionScenario(object, *kw):
    graph = IGraph(object)
    return tuple(graph.objects(graph.identifier, BCCPROP['emissionscenario']))


@indexer(IDataset)
def dataset_BCCGlobalClimateModel(object, *kw):
    graph = IGraph(object)
    return tuple(graph.objects(graph.identifier, BCCPROP['gcm']))


@indexer(IDataset)
def BCCDatasetResolution(object, **kw):
    graph = IGraph(object)
    return graph.value(graph.identifier, BCCPROP['resolution'])


@indexer(IExperiment)
def BCCExperimentResolution(object, **kw):
    graph = IGraph(object)
    return graph.value(graph.identifier, BCCPROP['resolution'])


# TODO: should be a DateRangeIndex (resolve partial dates to 1stday
#       (start) and last day (end))
# @indexer(IDataset)
# def dataset_DCTemporal(object, *kw):
#     graph = IGraph(object)
#     return tuple(graph.objects(graph.identifier, DCES['temporal']))


@indexer(IDataset)
def dataset_environmental_layer(object, **kw):
    # graph = IGraph(object)
    # if (graph.identifier, BCCPROP['datagenre'], BCCVOCAB['DataGenreSD']) in graph:
    #     return tuple(graph.objects(graph.identifier, BIOCLIM['bioclimVariable']))
    layers = getbiolayermetadata(object)
    if layers:
        return tuple(layers.keys())
    return None


@implementer(IIndexer)
class JobStateIndexer(object):

    def __init__(self, context, catalog):
        self.context = context
        self.catalog = catalog

    def __call__(self, **kw):
        jt = IJobTracker(self.context)
        # TODO: if state is empty check if there is a downloadable file
        #       Yes: COMPLETED
        #       No: FAILED
        state = jt.state
        if not state:
            if IBlobDataset.providedBy(self.context):
                # we have no state, may happen for imported datasets,
                # let's check if we have a file
                if self.context.file is not None:
                    state = 'COMPLETED'
            elif IRemoteDataset.providedBy(self.context):
                if self.context.remoteUrl:
                    state = 'COMPLETED'
        return state
