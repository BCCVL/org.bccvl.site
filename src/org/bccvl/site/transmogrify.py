from zope.interface import implementer, provider
from collective.transmogrifier.interfaces import ISectionBlueprint
from collective.transmogrifier.interfaces import ISection
import os
import os.path
from collective.transmogrifier.utils import resolvePackageReferenceOrFile
from collective.transmogrifier.utils import defaultMatcher
import simplejson
from ordf.graph import Graph
from ordf.namespace import DC
from rdflib import RDF, URIRef, Literal
from org.bccvl.site.namespace import BCCPROP, BCCVOCAB
from gu.plone.rdf.namespace import CVOCAB
from zope.component import getUtility
from gu.z3cform.rdf.interfaces import IORDF, IGraph


@provider(ISectionBlueprint)
@implementer(ISection)
class JSONSource(object):

    def __init__(self, transmogrifier, name, options, previous):
        self.transmogrifier = transmogrifier
        self.name = name
        self.options = options
        self.previous = previous
        self.path = resolvePackageReferenceOrFile(options['path'])
        if self.path is None or not os.path.isdir(self.path):
            raise Exception('Path ({}) does not exists.'.format(str(self.path)))
        self.path = self.path.rstrip(os.sep)

        # add path prefix to imported content
        self.prefix = options.get('prefix', '').strip().strip(os.sep)
        # keys for sections further down the chain
        self.pathkey = options.get('path-key', '_path').strip()
        self.fileskey = options.get('files-key', '_files').strip()

    def __iter__(self):
        # exhaust previous iterator
        for item in self.previous:
            yield item

        # start our own source
        # 1. iterate through dir  files first
        for (root, dirs, files) in os.walk(self.path):
            for filename in files:
                if (not filename.endswith('.json') or
                    filename.startswith('.')):
                    # if it's not json it's not an item
                    # if it starts with . we don't want it
                    continue
                # read the json
                f = open(os.path.join(root, filename), 'r')
                # TODO: could put this into _files as well with 'content' key
                item = simplejson.loads(f.read())
                f.close()
                # TODO: need _type?
                # _path
                name, ext = os.path.splitext(filename)
                # TODO: so many split and joins, consider self.prefix as well
                path = root[len(self.path):].strip(os.sep)
                path = '/'.join((path, name))
                item[self.pathkey] = '/'.join(path.split(os.sep))
                # _files
                if name in dirs:
                    # matching dir for entry? then read all the files within it.
                    _files = item.setdefault(self.fileskey, {})
                    for _filename in os.listdir(os.path.join(root, name)):
                        if (_filename.startswith('.') or
                            _filename.endswith('.json')):
                            # TODO: figure out way to allow attachments with .json
                            # ignore . and .json in case item is a folder
                            continue
                        _absfilename = os.path.join(root, name, _filename)
                        if os.path.isdir(_absfilename):
                            # ignore dirs, in case we generated a folder
                            continue
                        _files[_filename] = {
                            'name': _filename,
                            'data': open(_absfilename).read()
                            }
                yield item


@provider(ISectionBlueprint)
@implementer(ISection)
class ALASource(object):

    def __init__(self, transmogrifier, name, options, previous):
        self.transmogrifier = transmogrifier
        self.name = name
        self.options = options
        self.previous = previous

        self.path = options['path']
        if self.path is None or not os.path.isdir(self.path):
            raise Exception('Path ({}) does not exists.'.format(str(self.path)))
        self.path = self.path.rstrip(os.sep)
        self.lsid = options['lsid']


        # add path prefix to imported content
        self.prefix = options.get('prefix', '').strip().strip(os.sep)
        # keys for sections further down the chain
        self.pathkey = options.get('path-key', '_path').strip()
        self.fileskey = options.get('files-key', '_files').strip()

    def __iter__(self):
        # exhaust previous iterator
        for item in self.previous:
            yield item

        # start our own source
        # 1. read meatada from json
        csv = os.path.join(self.path, '{}.csv'.format(self.lsid))
        json = os.path.join(self.path, '{}.json'.format(self.lsid))

        # read json
        json = simplejson.load(open(json, 'r'))
        # extract metadata
        rdf = Graph()
        # rdf.add((rdf.identifier, DC['source'], URIRef(json['taxonConcept']['dcterms_source'])))
        # rdf.add((rdf.identifier, DC['title'], URIRef(json['taxonConcept']['dcterms_title'])))
        # rdf.add((rdf.identifier, DC['modified'], URIRef(json['taxonConcept']['dcterms_modified'])))
        # rdf.add((rdf.identifier, DC['available'], URIRef(json['taxonConcept']['dcterms_available'])))
        # URIRef(json['taxonConcept']['lsid'])
        # json['taxonConcept']['RankCode'] == 'sp'
        # json['taxonConcept']['rankString'] == 'species'
        # json['taxonConcept']['']
        rdf.add((rdf.identifier, DC['title'], Literal(json['taxonConcept']['nameString'])))
        rdf.add((rdf.identifier, DC['identifier'], URIRef(json['taxonConcept']['guid'])))
        rdf.add((rdf.identifier, DC['description'], Literal(json['commonNames'][0]['nameString'])))
        rdf.add((rdf.identifier, BCCPROP['datagenre'], BCCVOCAB['DataGenreSO']))
        rdf.add((rdf.identifier, BCCPROP['specieslayer'], BCCVOCAB['SpeciesLayerP']))
        rdf.add((rdf.identifier, RDF['type'], CVOCAB['Dataset']))

        # FIXME: important of the same guid changes current existing dataset
        _, id = json['taxonConcept']['guid'].rsplit(':', 1)
        item = {'_path': id,
                '_type': 'org.bccvl.content.dataset',
                'title': '{} ({})'.format(json['taxonConcept']['nameString'], json['commonNames'][0]['nameString']),
                'file': {
                    'file': 'data.csv',
                    'contentype': 'text/csv',
                    'filename': '{}.csv'.format(self.lsid),
                    },
                '_rdf': {
                    'file': 'rdf.ttl',
                    'contenttype': 'text/turtle',
                    },
                '_files': {
                    'data.csv': {
                        'data': open(csv).read()
                        },
                    'rdf.ttl': {
                        'data': rdf.serialize(format='turtle')
                        }
                    }
                }
        yield item


@provider(ISectionBlueprint)
@implementer(ISection)
class RDFMetadataUpdater(object):

    def __init__(self, transmogrifier, name, options, previous):
        self.transmogrifier = transmogrifier
        self.name = name
        self.options = options
        self.previous = previous
        self.context = transmogrifier.context

        # keys for sections further down the chain
        self.pathkey = defaultMatcher(options, 'path-key', name, 'path')
        self.fileskey = options.get('files-key', '_files').strip()
        self.rdfkey = options.get('rdf-key', '_rdf').strip()

    def __iter__(self):
        # exhaust previous iterator
        for item in self.previous:
            pathkey = self.pathkey(*item.keys())[0]
            # no path .. can't do anything
            if not pathkey:
                yield item
                continue

            path = item[pathkey]
            # Skip the Plone site object itself
            if not path:
                yield item
                continue

            obj = self.context.unrestrictedTraverse(
                path.encode().lstrip('/'), None)

            # path doesn't exist
            if obj is None:
                yield item
                continue

            rdfinfo = item.get(self.rdfkey)
            if not rdfinfo:
                yield item
                continue

            filename = rdfinfo.get('file')
            if not filename:
                yield item
                continue

            # get files
            files = item.setdefault(self.fileskey, {})
            file = files.get(filename)
            if not file:
                yield item
                continue

            rdfdata = file['data']
            if not rdfdata:
                yield item
                continue

            # parse rdf and apply to content
            rdfgraph = Graph()
            rdfgraph.parse(data=rdfdata, format='turtle')
            mdgraph = IGraph(obj)
            for p, o in rdfgraph.predicate_objects(None):
                mdgraph.add((mdgraph.identifier, p, o))
            rdfhandler = getUtility(IORDF).getHandler()
            # TODO: the transaction should take care of
            #       donig the diff
            cc = rdfhandler.context(user='Importer',
                                    reason='Test data')
            cc.add(mdgraph)
            cc.commit()

            yield item




# '_files': {u'_field_file_bkgd.csv':
#               {'contenttype': 'text/csv',
#                'data': 'Name, 1, 2\nName, 2, 3\nName, 3, 4\nName, 4, 5\nName, 5, 6\nName, 6, 7\nName, 7, 8\nName, 8, 9\nName, 9, 10',
#                'name': u'_field_file_bkgd.csv'},
#             'content': {'contenttype': 'application/json',
#                         'data': '{
#                             "changeNote": "",
#                             "contributors": [],
#                             "creators": ["admin"],
#                             "exclude_from_nav": false,
#                             "file": {
#                                  "contenttype": "text/csv",
#                                  "file": "_field_file_bkgd.csv",
#                                  "filename": "bkgd.csv"\n    },
#                             "plone.uuid": "09f7adaf5b7b431ea4a3df5959dc238e",
#                             "relatedItems": [],
#                             "rights": "",
#                             "title": "ABT"}',
#              'name': '_content.json'}}
