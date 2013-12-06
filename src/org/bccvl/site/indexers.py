from plone.indexer.decorator import indexer
from org.bccvl.site.content.dataset import IDataset
from gu.z3cform.rdf.interfaces import IGraph
from org.bccvl.site.browser.xmlrpc import getbiolayermetadata

from .namespace import BCCPROP
from ordf.namespace import DCES

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
def dataset_DCTemporal(object, *kw):
    graph = IGraph(object)
    return tuple(graph.objects(graph.identifier, DCES['temporal']))


@indexer(IDataset)
def dataset_environmental_layer(object, **kw):
    layers = getbiolayermetadata(object)
    if layers:
        return tuple(layers.keys())
    return None
