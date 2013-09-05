from plone.indexer.decorator import indexer
from gu.repository.content.interfaces import IRepositoryItem
from gu.repository.content.interfaces import IRepositoryMetadata

from .namespace import BCCPROP


@indexer(IRepositoryItem)
def repositoryItem_BCCDataGenre(object, *kw):
    graph = IRepositoryMetadata(object)
    return graph.value(graph.identifier, BCCPROP['datagenre'])


@indexer(IRepositoryItem)
def repositoryItem_BCCSpeciesLayer(object, *kw):
    graph = IRepositoryMetadata(object)
    return tuple(graph.objects(graph.identifier, BCCPROP['specieslayer']))
