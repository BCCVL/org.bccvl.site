from plone.indexer.decorator import indexer
from gu.repository.content.interfaces import IRepositoryItem
from gu.repository.content.interfaces import IRepositoryMetadata

from rdflib import RDF
from .namespace import BCCPROP

@indexer(IRepositoryItem)
def repositoryItem_BCCDataGenre(object, *kw):
    graph = IRepositoryMetadata(object)
    return graph.value(graph.identifier, BCCPROP['datagenre'])
    
    
