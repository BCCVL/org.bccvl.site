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
from org.bccvl.site.namespace import (BCCPROP, BCCVOCAB, TN, NFO, GML, EPSG,
                                      BIOCLIM, BCCVLLAYER)
from gu.plone.rdf.namespace import CVOCAB
from zope.component import getUtility
from gu.z3cform.rdf.interfaces import IORDF, IGraph
from gu.z3cform.rdf.utils import Period
import logging
import json


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
                resource.set(prop, obt(val))

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
        rdfmd.set(BCCPROP['datagenre'], BCCVOCAB['DataGenreSpeciesOccurrence'])
        rdfmd.set(BCCPROP['specieslayer'], BCCVOCAB['SpeciesLayerP'])
        rdfmd.add(RDF['type'], CVOCAB['Dataset'])
        # TODO: important thing ... date of export (import date in
        #       plone)/ date modified in ALA

        # FIXME: import of the same guid changes current existing dataset
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
                # FIXME: don't load files into ram
                '_files': {
                    'data.csv': {
                        'name': 'data.csv',
                        'data': open(csv).read()
                    },
                    'rdf.ttl': {
                        'name': 'rdf.ttl',
                        'data': rdf.serialize(format='turtle')
                    }
                }}
        # if we have an id use it to possibly update existing content
        # TODO: check if improt context is already correct folder, or
        #       do we need full path here instead of just the id?
        if self.id:
            item['_path'] = self.id

        yield item


@provider(ISectionBlueprint)
@implementer(ISection)
class ContextSource(object):
    """Generate an item for transmogrifier context.

    This is useful to re-use transmogrifier blueprints on a single
    existing content object.

    """
    # TODO: at the moment this is only useful for bccvl datasets,
    #       but if used together with transmogrify.dexterity.schemareader
    #       it may work well for any content type

    def __init__(self, transmogrifier, name, options, previous):
        self.transmogrifier = transmogrifier
        self.name = name
        self.options = options
        self.previous = previous
        self.context = transmogrifier.context

        self.pathkey = options.get('path-key', '_path')

    def __iter__(self):
        # exhaust previous iterator
        for item in self.previous:
            yield item

        filename = self.context.file.filename
        item = {
            self.pathkey: '/'.join(self.context.getPhysicalPath()),
            '_type': self.context.portal_type,
            'file': {
                'file': filename,
            },
            '_files': {
                filename: {
                    # FIXME: there is some chaos here... do I really need name and filename?
                    'name': self.context.file.filename,
                    'filename': self.context.file.filename,
                    'contenttype': self.context.file.contentType,
                    'path': self.context.file.open('r').name
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

            # FIXME: this assumes, that the key in _files matches the filename, but the key may be arbitrary
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
            if content.format in ('application/zip', ):
                self.update_archive_items(content, filemd)
            else:
                self.update_file_metadata(content, filemd)
            self.update_metadata(content, filemd)
            # continue pipe line
            yield item

    def update_resource_metadata(self, res, filemd, md, filename):
        if not md:
            return
        # bonuds
        # date
        # csv: headers, rows, species (set)
        # SRS
        if 'srs' in md:
            srs = md['srs']
            if srs.lower().startswith('epsg:'):
                srs = EPSG[srs[len("epsg:"):]]
            else:
                srs = URIRef(srs)
            res.set(GML['srsName'], srs)
        # band metadata
        bandmd = md.get('band')
        if bandmd:
            bandmd = bandmd[0]
            # mean, STATISTICS_MEAN
            # stddev, STATISTICS_STDDEV
            # size (x, y on band)
            min_ = bandmd.get('min') or bandmd.get('STATISTICS_MINIMUM')
            max_ = bandmd.get('max') or bandmd.get('STATISTICS_MAXIMUM')
            width, height = bandmd.get('size', (None, None))
            if min_:
                res.set(BCCPROP['min'], Literal(min_))
            if max_:
                res.set(BCCPROP['max'], Literal(max_))
            if width and height:
                res.set(BCCPROP['width'], Literal(width))
                res.set(BCCPROP['height'], Literal(height))
            # TODO: emsc, gcm, year, layer, resolution, bounding box?
            if bandmd.get('type') and bandmd.get('type').lower() == 'categorical':
                res.set(BCCPROP['datatype'], BCCVOCAB['DataSetTypeD'])
            else:
                res.set(BCCPROP['datatype'], BCCVOCAB['DataSetTypeC'])

            rat = bandmd.get('rat')
            if rat:
                # FIXME: really a good way to store this?
                res.set(BCCPROP['rat'], Literal(json.dumps(rat)))
            # origin, 'Pixel Size', bounds

            ##############################
            # Layer
            #    try to get a layer identifier from somewhere...
            #    from bccvlmetadata
            fileinfo = filemd.get('_bccvlmetadata', {})
            fileinfo = fileinfo.get(filename, {})
            if 'layer' in fileinfo:
                res.add(BIOCLIM['bioclimVariable'], BCCVLLAYER[fileinfo['layer']])
            # End Layer
            #############################

    def update_file_metadata(self, content, md):
        graph = IGraph(content)
        res = Resource(graph, graph.identifier)
        self.update_resource_metadata(res, md, md, content.file.filename)
        # mark graph as modified
        getUtility(IORDF).getHandler().put(graph)

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
            ares.set(NFO['fileName'], Literal(submd['filename']))
            ares.set(NFO['fileSize'], Literal(submd['file_size']))
            ares.add(RDF['type'], NFO['ArchiveItem'])
            #
            self.update_resource_metadata(ares, md, submd.get('metadata', {}), key)

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
            res.set(BCCPROP['rows'], Literal(rows))

        # do general '_bccvlmetadata' here
        bmd = md.get('_bccvlmetadata')
        if bmd:
            if 'resolution' in bmd:
                resmap = {'3 arcsec': BCCVOCAB['Resolution3s'],
                          '9 arcsec': BCCVOCAB['Resolution9s'],
                          '30 arcsec': BCCVOCAB['Resolution30s'],
                          '180 arcsec': BCCVOCAB['Resolution3m'],
                          '2.5 arcmin': BCCVOCAB['Resolution2_5m']}
                if bmd['resolution'] in resmap:
                    res.set(BCCPROP['resolution'], resmap[bmd['resolution']])
                else:
                    LOG.warn('Unknown resolution: %s', bmd['resolution'])
            if 'temporal_coverage' in bmd:
                p = Period('')
                p.start = bmd['temporal_coverage'].get('start')
                p.end = bmd['temporal_coverage'].get('end')
                p.scheme = 'W3C-DTF'
                res.set(DC['temporal'], Literal(unicode(p), datatype=DC['Period']))
            if 'genre' in bmd:
                # It's a bit weird here, we have the genre
                genremap = {'Environmental': BCCVOCAB['DataGenreE'],
                            'Climate': BCCVOCAB['DataGenreCC'],
                            'FutureClimate': BCCVOCAB['DataGenreFC']}
                if bmd['genre'] in genremap:
                    res.set(BCCPROP['datagenre'], genremap[bmd['genre']])
            rights = []
            if 'license' in bmd:
                rights.append(u'<h4>License:</h4><p>{0}</p>'.format(bmd['license']))
            if 'external_url' in bmd:
                rights.append(u'<h4>External URL</h4><p><a href="{0}">{0}</a></p>'.format(bmd['external_url']))
            if 'acknowledgement' in bmd:
                acks = bmd['acknowledgement']
                if not isinstance(acks, list):
                    acks = [acks]
                rights.append(u'<h4>Acknowledgement</h4><ul>')
                for ack in acks:
                    rights.append(u'<li>{0}</li>'.format(ack))
                rights.append(u'</ul>')
            if rights:
                content.rights = u'\n'.join(rights)


        # mark graph as modified - we have a copy of the graph... if anyone else
        #     wants to see changes we have to put our copy back
        getUtility(IORDF).getHandler().put(graph)



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
