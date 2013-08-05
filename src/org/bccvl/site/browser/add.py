from gu.plone.rdf.browser.metadata import RDFAddForm, RDFAddView
from gu.plone.rdf.browser.metadata import CVOCAB
from org.bccvl.site.namespace import BCCVOCAB
from ordf.namespace import RDF
from ordf.graph import Graph

from urlparse import parse_qs


TYPE_MAP = {
    'DataGenreFC': BCCVOCAB['DataGenreFC'],
    'DataGenreE': BCCVOCAB['DataGenreE'],
    'DataGenreSO': BCCVOCAB['DataGenreSO'],
    'DataGenreSC': BCCVOCAB['DataGenreSD'],
}

TYPE_DEFAULT = CVOCAB['Item']

#class TypeFromRequestAddForm(RDFAddForm):
#    pass

# TODO: re-add this once the accompanying edit is added
#    _rdfType = None
#
#    def getEmptyGraph(self):
#        if self._graph is None:
#            _graph = Graph()
#            _graph.add((_graph.identifier, RDF['type'], self._rdfType))
##            if self._rdfType in TYPE_MAP.values():
##                _graph.add((_graph.identifier, RDF['DataGenre'], self._rdfType))
#            self._graph = _graph
#        return self._graph
#    
#    def update(self):
#        if self._rdfType is None:
#            query = parse_qs(self.request.QUERY_STRING)
#            if 'type' in query and query['type'][0] in TYPE_MAP:
#                self._rdfType = TYPE_MAP[query['type'][0]]
#            else:
#                self._rdfType = TYPE_DEFAULT
#        super(TypeFromRequestAddForm, self).update()        

#class TypeFromRequestAddView(RDFAddView):
#    form = TypeFromRequestAddForm
