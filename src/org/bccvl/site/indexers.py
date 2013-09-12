from plone.indexer.decorator import indexer
from gu.repository.content.interfaces import IRepositoryItem
from gu.z3cform.rdf.interfaces import IGraph

from .namespace import BCCPROP


@indexer(IRepositoryItem)
def repositoryItem_BCCDataGenre(object, *kw):
    graph = IGraph(object)
    return tuple(graph.objects(graph.identifier, BCCPROP['datagenre']))


@indexer(IRepositoryItem)
def repositoryItem_BCCSpeciesLayer(object, *kw):
    graph = IGraph(object)
    return tuple(graph.objects(graph.identifier, BCCPROP['specieslayer']))
