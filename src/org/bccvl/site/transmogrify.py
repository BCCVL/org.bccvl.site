from zope.interface import implementer, provider
from collective.transmogrifier.interfaces import ISectionBlueprint
from collective.transmogrifier.interfaces import ISection
import re
import os
import os.path
from collective.transmogrifier.utils import defaultMatcher
import simplejson
from ordf.graph import Graph
from ordf.namespace import DC
from rdflib import RDF, URIRef, Literal, OWL
from rdflib.resource import Resource
from org.bccvl.site.namespace import (BCCPROP, BCCVOCAB, TN, NFO, GLM, EPSG,
                                      BIOCLIM)
from gu.plone.rdf.namespace import CVOCAB
from zope.component import getUtility
from gu.z3cform.rdf.interfaces import IORDF, IGraph
import logging


LOG = logging.getLogger(__name__)


@provider(ISectionBlueprint)
@implementer(ISection)
class ALASource(object):

    # map a path in json to RDF property and object type
    JSON_TO_RDFMAP = [
        ('taxonConcept/nameString', DC['title'], Literal),
        ('taxonConcept/nameString', TN['nameComplete'], Literal),
        ('taxonConcept/guid', OWL['sameAs'], URIRef),
        ('taxonConcept/guid', DC['identifier'], URIRef),
        ('commonNames/0/nameString', DC['description'], Literal),
        ('images/0/thumbnail', BCCVOCAB['thumbnail'], URIRef),
    ]

    def __init__(self, transmogrifier, name, options, previous):
        self.transmogrifier = transmogrifier
        self.context = transmogrifier.context
        self.name = name
        self.options = options
        self.previous = previous

        self.file = options['file'].strip()
        if self.file is None or not os.path.isfile(self.file):
            raise Exception('File ({}) does not exists.'.format(str(self.file)))
        self.lsid = options['lsid']
        self.id = options.get('id')
        # add path prefix to imported content
        self.prefix = options.get('prefix', '').strip().strip(os.sep)
        # keys for sections further down the chain
        self.pathkey = options.get('path-key', '_path').strip()
        self.fileskey = options.get('files-key', '_files').strip()

    def traverse_dict(self, source, path):
        current = source
        try:
            for el in path.split('/'):
                if isinstance(current, list):
                    el = int(el)
                current = current[el]
        except:
            # TODO: at least log error?
            current = None
        return current

    def map_json_to_resource(self, json, resource):
        for path, prop, obt in self.JSON_TO_RDFMAP:
            val = self.traverse_dict(json, path)
            if val:
                resource.add(prop, obt(val))

    def __iter__(self):
        # exhaust previous iterator
        for item in self.previous:
            yield item

        # start our own source
        # 1. read meatada from json
        json = simplejson.load(open(self.file, 'r'))
        # index files by dataset_type
        files = {}
        for file in json['files']:
            files[file['dataset_type']] = file
        title = json['title']
        description = json['description']

        # 2. read ala metadata form json
        json = simplejson.load(open(files['attribution']['url'], 'r'))
        csv = files['occurrences']['url']

        rdf = Graph()
        rdfmd = Resource(rdf, rdf.identifier)
        self.map_json_to_resource(json,  rdfmd)
        rdfmd.add(BCCPROP['datagenre'], BCCVOCAB['DataGenreSO'])
        rdfmd.add(BCCPROP['specieslayer'], BCCVOCAB['SpeciesLayerP'])
        rdfmd.add(RDF['type'], CVOCAB['Dataset'])
        # TODO: important thing ... date of export (import data in
        #       plone)/ date modified in ALA

        # FIXME: important of the same guid changes current existing dataset
        #_, id = json['taxonConcept']['guid'].rsplit(':', 1)
        item = {'_type': 'org.bccvl.content.dataset',
                'title': title,
                'description': description,
                'file': {
                    'file': 'data.csv',
                    'contentype': 'text/csv',
                    'filename': '{}.csv'.format(self.lsid),
                },
                # TODO: not necessary to use '_files' with '_rdf';
                #       _rdf is custom already
                #       -> same for _filemetadata ?
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
                }}
        # if we have an id use it to possibly update existing content
        if self.id:
            item['_path'] = self.id

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
            # FIXME: replace data or not?
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


# TODO: maybe turn this into a RDF updater section.
@provider(ISectionBlueprint)
@implementer(ISection)
class FileMetadataToRDF(object):
    """Generates all sorts of metadata out of item.

    All metadata generated will be stored via ordf in the triple store
    associated with the current content object.
    """

    def __init__(self, transmogrifier, name, options, previous):
        self.transmogrifier = transmogrifier
        self.name = name
        self.options = options
        self.previous = previous
        self.context = transmogrifier.context

        # keys for sections further down the chain
        self.pathkey = defaultMatcher(options, 'path-key', name, 'path')
        self.filemetadatakey = options.get('filemetadata-key',
                                           '_filemetadata').strip()
        self.fileskey = options.get('files-key', '_files').strip()
        self.rdfkey = options.get('rdf-key', '_rdf').strip()

    def __iter__(self):
        # exhaust previous iterator
        for item in self.previous:

            filename = None
            if 'remoteUrl' in item:
                # TODO: assumse, that there is a _file entry to it which has
                #       the name for _filemetadata dictionary
                _files = item.get('_files', {}).get(item.get('remoteUrl'), {})
                filename = _files.get('filename')
                contenttype = _files.get('contenttype', 'application/octet-stream')
            elif 'file' in item:
                filename = item.get('file', {}).get('file')  # TODO: or is this filename?
                contenttype = item.get('file', {}).get('contenttype')
            if not filename:
                # there should be no other None key
                yield item
                continue

            filemd = item.get(self.filemetadatakey, {})
            filemd = filemd.get(filename)
            if not filemd:
                # no filemetadata (delete or leave untouched?)
                yield item
                continue

            # we'll also need a content object
            pathkey = self.pathkey(*item.keys())[0]
            if not pathkey:
                yield item
                continue

            path = item[pathkey]
            # skip import context
            if not path:
                yield item
                continue

            content = self.context.unrestrictedTraverse(
                path.encode().lstrip('/'), None)

            if content is None:
                yield item
                continue

            # get or create rdf graph
            # TODO: Ending up here means we have a file as main content
            #       let's set the format attribute to this mime type
            #       ? if there is none set yet?
            if contenttype and content.format != contenttype:
                content.format = contenttype
            self.update_archive_items(content, filemd)
            self.update_metadata(content, filemd)

            # continue pipe line
            yield item

    def update_archive_items(self, content, md):
        graph = IGraph(content)
        res = Resource(graph, graph.identifier)

        if (res.value(BCCPROP['hasArchiveItem'])):
            # We delete old archive items and create new ones
            ordf = getUtility(IORDF).getHandler()
            # delete from graph
            for uri in res.objects(BCCPROP['hasArchiveItem']):
                # delete subgraphs from graph
                graph.remove((uri.identifier, None, None))
                # BBB: delete from store (old method)
                ordf.remove(uri.identifier)
            res.remove(BCCPROP['hasArchiveItem'])

        for key, submd in md.items():
            if not isinstance(submd, dict):
                continue
            if 'metadata' not in submd:
                # skip non sub file items
                continue
            # generate new archive item
            ordf = getUtility(IORDF)
            ares = Resource(graph, ordf.generateURI())
            # size (x, y on file)
            ares.add(NFO['fileName'], Literal(submd['filename']))
            ares.add(NFO['fileSize'], Literal(submd['file_size']))
            ares.add(RDF['type'], NFO['ArchiveItem'])
            # bonuds
            # date
            # csv: headers, rows, species (set)
            amd = submd.get('metadata', {})
            # SRS
            if 'srs' in amd:
                srs = amd['srs']
                if srs.lower().startswith('epsg:'):
                    srs = EPSG[srs[len("epsg:"):]]
                else:
                    srs = URIRef(srs)
                ares.add(GLM['srsName'], srs)
            # band metadata
            bandmd = amd.get('band')
            if bandmd:
                bandmd = bandmd[0]
                # mean, STATISTICS_MEAN
                # stddev, STATISTICS_STDDEV
                # size (x, y on band)
                min = bandmd.get('min') or bandmd.get('STATISTICS_MINIMUM')
                max = bandmd.get('ax') or bandmd.get('STATISTICS_MAXIMUM')
                width, height = bandmd.get('size', (None, None))
                if min:
                    ares.add(BCCPROP['min'], Literal(min))
                if max:
                    ares.add(BCCPROP['max'], Literal(max))
                if width and height:
                    ares.add(BCCPROP['width'], Literal(width))
                    ares.add(BCCPROP['height'], Literal(height))
                # Layer
                layer = bandmd.get('layer')
                if layer:
                    match = re.match(r'.*bioclim.*(\d\d)', layer)
                    if match:
                        bid = match.group(1)
                        ares.add(BIOCLIM['bioclimVariable'], BIOCLIM['B' + bid])
                    else:
                        # TODO: really write something?
                        ares.add(BIOCLIM['bioclimVariable'], BIOCLIM[layer])
                else:
                    match = re.match(r'.*bioclim.*(\d\d).tif', submd['filename'])
                    if match:
                        bid = match.group(1)
                        ares.add(BIOCLIM['bioclimVariable'], BIOCLIM['B' + bid])
                # emsc, gcm, year, layer
            # origin, 'Pixel Size', bounds
            res.add(BCCPROP['hasArchiveItem'], ares)

        # mark graph as modified
        getUtility(IORDF).getHandler().put(graph)

    def update_metadata(self, content, md):
        # CSV: bounds, headers, rows, species (set)
        graph = IGraph(content)
        res = Resource(graph, graph.identifier)

        #bounds = md.get('boutds')
        rows = md.get('rows')
        if rows:
            res.add(BCCPROP['rows'], Literal(rows))
            # mark graph as modified - we have a copy of the graph... if anyone else
            #     wants to see changes we have to put our copy back
            getUtility(IORDF).getHandler().put(graph)
            import transaction
            transaction.commit()


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
