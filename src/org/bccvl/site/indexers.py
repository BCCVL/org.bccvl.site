from plone.indexer.decorator import indexer
from org.bccvl.site.content.dataset import IDataset
from gu.z3cform.rdf.interfaces import IGraph

from .namespace import BCCPROP


@indexer(IDataset)
def dataset_BCCDataGenre(object, *kw):
    graph = IGraph(object)
    return tuple(graph.objects(graph.identifier, BCCPROP['datagenre']))


@indexer(IDataset)
def dataset_BCCSpeciesLayer(object, *kw):
    graph = IGraph(object)
    return tuple(graph.objects(graph.identifier, BCCPROP['specieslayer']))
