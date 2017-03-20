from datetime import datetime
import json
import logging
import os
import os.path
import posixpath
import re
from urlparse import urlsplit

from Acquisition import aq_base

from collective.transmogrifier.interfaces import ISectionBlueprint
from collective.transmogrifier.interfaces import ISection
from collective.transmogrifier.utils import defaultMatcher
from collective.transmogrifier.utils import traverse
from plone.dexterity.utils import createContentInContainer
from plone.uuid.interfaces import IUUID
from rdflib import Graph, Namespace, Literal
from rdflib.namespace import RDF, DCTERMS, XSD
from rdflib.resource import Resource
from zope.interface import implementer, provider

from org.bccvl.site.content.interfaces import IExperiment
from org.bccvl.site.interfaces import IBCCVLMetadata, IProvenanceData


LOG = logging.getLogger(__name__)


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
        self.content_id = options.get('content_id')
        self.items = options.get('items')

    def create_item(self, import_item):
        content = self.context[self.content_id]
        url = import_item.get('file', {}).get('url')
        name = import_item.get('file', {}).get('filename')
        mimetype = import_item.get('file', {}).get('contenttype')
        if not mimetype:
            mimetype = content.format

        bccvlmd = dict(IBCCVLMetadata(content))
        bccvlmd.update(import_item.get('bccvlmetadata', {}))

        item = {
            self.pathkey: content.getId(),
            '_type': content.portal_type,
            'bccvlmetadata': bccvlmd,
        }
        for key in ('title', 'description'):
            if import_item.get(key):
                item[key] = import_item[key]
        # TODO: funny part here.... we already have a specific type of dataset
        # dataset or remotedataset?
        # We have an existing content object... use it to decide portal_type
        if content.portal_type == 'org.bccvl.content.remotedataset':
            # remote
            if url:
                remoteurl = re.sub(r'^swift\+', '', import_item['file']['url'])
            else:
                remoteurl = content.remoteUrl
            item.update({
                'remoteUrl': remoteurl,
                # FIXME: hack to pass on content type to FileMetadataToBCCVL
                # blueprint
                '_files': {
                    remoteurl: {
                        'contenttype': mimetype,
                    }
                },
                '_filemetadata': {
                    # key relates to 'remoteUrl'
                    # make sure it's not none
                    remoteurl: import_item.get('filemetadata', {}) or {},
                }
            })
        else:
            # assume local storage
            if not name:
                name = content.file.filename
            if url:
                urlparts = urlsplit(url)
                item.update({
                    'file': {
                        'file': name,
                        'contenttype': mimetype,
                        'filename': name
                    },
                    '_files': {
                        name: {
                            'name': name,
                            # 'path': urlparts.path, TODO: do I need this key?
                            'data': open(urlparts.path, 'r')
                        }
                    },
                })
            else:
                # FIXME: this is an ugly hack to get the FileMetadataToBCCVL
                # step working for metadata updates
                item['remoteUrl'] = name
            item['_filemetadata'] = {
                # key relates to 'file':'file'
                # make sure it's not none
                name: import_item.get('filemetadata', {}) or {},
            }
        return item

    def __iter__(self):
        # exhaust previous iterator
        for item in self.previous:
            yield item

        for import_item in self.items:
            item = self.create_item(import_item)
            yield item


@provider(ISectionBlueprint)
@implementer(ISection)
class BCCVLMetadataUpdater(object):

    def __init__(self, transmogrifier, name, options, previous):
        self.transmogrifier = transmogrifier
        self.name = name
        self.options = options
        self.previous = previous
        self.context = transmogrifier.context

        # keys for sections further down the chain
        self.pathkey = defaultMatcher(options, 'path-key', name, 'path')
        self.bccvlmdkey = options.get('bccvlmd-key', 'bccvlmetadata').strip()

    def __iter__(self):
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

            bccvlmd = item.get(self.bccvlmdkey)
            if not bccvlmd:
                yield item
                continue
            # apply bccvl metadata
            # FIXME: replace or update?
            IBCCVLMetadata(obj).update(bccvlmd)
            yield item


@provider(ISectionBlueprint)
@implementer(ISection)
class FileMetadataToBCCVL(object):
    """Convert metedata extracted from files (_filemetadata) and store it
    in _bccvlmetadata so that it can be applied to IBCCVLMetadata

    Nothing will be stored on content here.
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
        self.bccvlmdkey = options.get('bccvlmd-key', 'bccvlmetadata').strip()

    def __iter__(self):
        for item in self.previous:
            fileid = None
            if 'remoteUrl' in item:
                # TODO: assumse, that there is a _file entry to it which has
                #       the name for _filemetadata dictionary
                _files = item.get('_files', {}).get(item.get('remoteUrl'), {})
                fileid = item.get('remoteUrl')
                # 'application/octet-stream')
                contenttype = _files.get('contenttype')
            elif 'file' in item:
                fileid = item.get('file', {}).get('file')
                contenttype = item.get('file', {}).get('contenttype')
            if not fileid:
                # there should be no other None key
                yield item
                continue

            # FIXME: we don't need content object here (Only for format)
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

            # We have a file or url, and should have a contenttype
            # set format attribute on content to this mime type
            if contenttype and content.format != contenttype:
                # FIXME: somehow this doesn't work?
                content.format = contenttype

            # get metadata for file itself _filemetadata
            filemd = item.setdefault(self.filemetadatakey, {}).get(fileid, {})
            if not filemd:
                # no filemetadata (delete or leave untouched?)
                genre = item.get('bccvlmetadata', {}).get('genre', IBCCVLMetadata(content).get('genre', None))
                if (genre in
                        ['DataGenreSpeciesOccurrence',
                         'DataGenreSpeciesAbundance',
                         'DataGenreSpeciesAbsence',
                         'DataGenreSpeciesCollection',
                         'DataGenreTraits',
                         'DataGenreCC',
                         'DataGenreFC',
                         'DataGenreE']):
                    raise Exception("Missing file metadata")
                yield item
                continue

            # TODO: probably needs a different check for multi layer files in future
            # store metadata in self.bccvlmdkey
            bccvlmd = item.setdefault(self.bccvlmdkey, {})
            self._update_bccvl_metadata(bccvlmd, filemd)
            if content.format in ('application/zip', ):
                # TODO: we also have metadata about the file itself, like filesize
                # FIXME: here and in _extract_layer_metadata: filemetadata should probably be under key 'layers' and not 'files'
                #        for now I put them under files to get them extracted
                # get jsonmd if available
                jsonmd = filemd.get('_bccvlmetadata.json', {})
                # multi layer metadata has archive filenames as keys in filemd (for main file)
                # if it is a multi layer file check layers (files)
                # go through all files in the dictionary and generate
                # "layer/file" metadata
                for filename, layermd in filemd.items():
                    # FIXME: because we are copying occurrence file metadata up
                    # to zip level, we have these extra weird keys in the main
                    # dict
                    if filename == '_bccvlmetadata.json' or filename in ('rows', 'bounds', 'headers'):
                        # ignore json metadata and the rows field associated
                        # with occurrence dataset
                        continue
                    if not layermd.get('metadata'):
                        # might happen for metadata json file, or aux.xml
                        # files, ...
                        continue
                    self._update_layer_metadata(
                        bccvlmd, layermd['metadata'], filename, jsonmd)
                    # FIXME: extract some of json metadata? like
                    # acknowledgement, etc...
            elif content.format not in ('text/csv', ):
                # TODO: we should have a better check here whether to extract layer metadata for a single file dataset
                # FIXME: hack to get correct key into _layermd dictionary in
                # case we have a remote file
                fileid = os.path.basename(fileid)
                self._update_layer_metadata(
                    bccvlmd, filemd, fileid, item.get('_layermd', {}))

            # continue pipeline
            yield item

    def _update_bccvl_metadata(self, bccvlmd, filemd):
        # mostly CSV file metadata copy

        # FIXME: filemd ... getting bounds, headers etc... from here... but what about multi file metadata? should get this stuff per file not from one..
        #  -> maybe need to make sure that filemd is always a dictionary even for single file upload? (there is a difference for single and multilayer files)

        # csv metadata:
        for key in ('bounds', 'headers', 'rows'):
            if filemd.get(key):
                bccvlmd[key] = filemd[key]

        # species:
        if filemd.get('species'):
            # check if 'species' is a list ... if it is the csv had multiple species names in it
            # issue a warning and pick a random species name (in case there is
            # non set already)
            bccvlmd.setdefault('species', {})
            if not bccvlmd['species'].get('scientificName'):
                speciesmd = filemd['species']
                # TODO: currently the file metadata extractor creates a list of species names
                #       in case there are multiple species names in the csv file we should
                # create multiple datasets (possibly grouped?) or suppert
                # datasets for multiple species
                if isinstance(speciesmd, list):
                    speciesmd = speciesmd[0]
                bccvlmd['species']['scientificname'] = speciesmd

    def _update_layer_metadata(self, bccvlmd, filemd, fileid, jsonmd):
        layermd = {}
        # projection
        for key in ('srs', 'bounds', 'size', 'projection'):
            if key in filemd:
                layermd[key] = filemd[key]
        # other global fileds:
        #    AREA_OR_POINT, PIXEL_SIZE, origin
        # check band metadata
        bandmd = filemd.get('band')
        if bandmd:
            # TODO: assumes there is only one band
            bandmd = bandmd[0]
            min_ = bandmd.get('STATISTICS_MINIMUM') if bandmd.get(
                'min') is None else bandmd.get('min')
            max_ = bandmd.get('STATISTICS_MAXIMUM') if bandmd.get(
                'max') is None else bandmd.get('max')
            mean_ = bandmd.get('STATISTICS_MEAN') if bandmd.get(
                'mean') is None else bandmd.get('mean')
            stddev_ = bandmd.get('STATISTICS_STDDEV') if bandmd.get(
                'stddev') is None else bandmd.get('stddev')
            width, height = bandmd.get('size', (None, None))
            if min_ is not None:
                layermd['min'] = min_
            if max_ is not None:
                layermd['max'] = max_
            if mean_ is not None:
                layermd['mean'] = mean_
            if stddev_ is not None:
                layermd['stddev'] = stddev_
            if 'nodata' in bandmd:
                layermd['nodata'] = bandmd['nodata']
            if width is not None and height is not None:
                layermd['width'] = width
                layermd['height'] = height
            # check if we have more info in layer?
            rat = bandmd.get('rat')
            if rat:
                # FIXME: really a good way to store this?
                layermd['rat'] = json.dumps(rat)
            # other band metadata:
            #    'color interpretation', 'data type', 'description', 'index',
            #    'type': 'continuous'

            ##############################
            # Layer
            #    try to get a layer identifier from somewhere...
            #    from bccvlmetadata
            data_type = None
            jsonfileinfo = jsonmd.get('files', {})
            jsonfileinfo = jsonfileinfo.get(fileid, {})
            if 'layer' in jsonfileinfo:
                # TODO: check layer identifier?
                layermd['layer'] = jsonfileinfo['layer']
                data_type = jsonfileinfo.get('data_type')
            # check data_type (continuous, discrete)
            if not data_type:
                # get global data_type if not a file specific one set
                data_type = bandmd.get('type', jsonmd.get('data_type'))

            # FIXME: everywhere ... is data_type capital or lower case?
            #        also. the following lines override any data_type coming from jsonmd. .. some weird code here
            # Assume Continous data type by default
            layermd['datatype'] = 'continuous'
            if data_type:
                if data_type.lower() == 'categorical':
                    layermd['datatype'] = 'categorical'
                elif data_type.lower() == 'discrete':
                    layermd['datatype'] = 'discrete'
        elif bccvlmd.get('dblayers'):
            # For other type than geotiff i.e. geofabric
            bounds = jsonmd.get('bounding_box', {})
            if bounds:
                layermd['bounds'] = bounds
            layermd['srs'] = jsonmd.get('srs', 'EPSG:4283')

            layermd['datatype'] = 'continuous'
            data_type = jsonmd.get('data_type', None)

            # Assume Continous data type by default
            layermd['datatype'] = 'continuous'
            if data_type:
                if data_type.lower() == 'categorical':
                    layermd['datatype'] = 'categorical'
                elif data_type.lower() == 'discrete':
                    layermd['datatype'] = 'discrete'

            # Get the min and max for each layer, and vocabulary as well.
            for layer, info in filemd.items():
                # TODO: Get full layername and vocabulary from dblayers
                dblayerinfo = bccvlmd.get('dblayers').get(layer)
                if dblayerinfo:
                    layermd['layer'] = dblayerinfo.get('layer')
                layermd['min'] = info['min']
                layermd['max'] = info['max']

                layermd['filename'] = layer
                bccvlmd.setdefault('layers', {})[layer] = dict(layermd)
            return

            # TODO: bbox: which units do we want bbox?
            #       lat/long?, whatever coordinates layer uses?
            # End Layer
            #############################
        if layermd:
            # TODO: check if filename really matches fileid? (or is this just
            # item['_files'] id?)
            layermd['filename'] = fileid
            bccvlmd.setdefault('layers', {})[
                layermd.get('layer', fileid)] = layermd


@provider(ISectionBlueprint)
@implementer(ISection)
class ProvenanceImporter(object):

    """ProvenenceImport ... intended to update provenence stored
    on result container when experiment is finished.

    generated data is stored on the result container object.
    """

    def __init__(self, transmogrifier, name, options, previous):
        """missing docstring."""
        self.transmogrifier = transmogrifier
        self.name = name
        self.options = options
        self.previous = previous
        self.context = transmogrifier.context

        # keys for sections further down the chain
        self.pathkey = defaultMatcher(options, 'path-key', name, 'path')

        # DELETE?
        self.fileskey = options.get('files-key', '_files').strip()
        self.filemetadatakey = options.get('filemetadata-key',
                                           '_filemetadata').strip()

    def __iter__(self):
        """missing docstring."""
        for item in self.previous:
            # check if we have a dataset

            if item['_type'] not in ('org.bccvl.content.dataset',
                                     'org.bccvl.content.remotedataset'):
                # not a dataset
                yield item
                continue

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

            # FIXME: this is really not a great way to check where to find provenenace data
            # check if we are inside an experiment (means we import result)
            if IExperiment.providedBy(self.context.__parent__):
                # result import
                context = self.context
            else:
                # dataset import?
                context = obj

            # TODO: do some sanity checks
            provdata = IProvenanceData(context)
            PROV = Namespace(u"http://www.w3.org/ns/prov#")
            BCCVL = Namespace(u"http://ns.bccvl.org.au/")
            LOCAL = Namespace(u"urn:bccvl:")
            graph = Graph()
            graph.parse(data=provdata.data or '', format='turtle')
            activity = Resource(graph, LOCAL['activity'])
            # FIXME: shouldn't I use uuid instead of id?
            entity = Resource(graph, LOCAL[obj.id])
            # create this dataset as new entity -> output of activity
            entity.add(RDF['type'], PROV['Entity'])
            # generated by
            entity.add(PROV['wasGeneratedBy'], activity)
            # PROV['prov:wasAttributedTo'] to user and software?
            # File metadata
            entity.add(DCTERMS['creator'], Literal(obj.Creator()))
            entity.add(DCTERMS['title'], Literal(obj.title))
            entity.add(DCTERMS['description'], Literal(obj.description))
            entity.add(DCTERMS['rights'], Literal(obj.rights))
            if obj.portal_type == 'org.bccvl.content.dataset':
                entity.add(DCTERMS['format'], Literal(obj.file.contentType))
            else:
                # FIXME: this doesn't seem to do the right thing
                entity.add(DCTERMS['format'], Literal(obj.format))
            # TODO: add metadata about file?
            #    genre, layers, emsc, gcm, year

            # set activities end time
            #   first one wins
            if activity.value(PROV['endedAtTime']) is None:
                activity.add(PROV['endedAtTime'],
                             Literal(datetime.now().replace(microsecond=0).isoformat(), datatype=XSD['dateTime']))

            # TODO: extend activity metadata with execution environment data
            #       (logfile import?, pstats import) .. and script + params.json file
            # ALA import url
            pd = item.get('_ala_provenance', {})
            if pd:
                entity.add(BCCVL['download_url'], Literal(pd['url']))

            # store prov data
            provdata.data = graph.serialize(format="turtle")

            yield item


@provider(ISectionBlueprint)
@implementer(ISection)
class PartOfImporter(object):
    """If an item has a field '_partof', it will add itself
    as part to the targeted item.
    """

    def __init__(self, transmogrifier, name, options, previous):
        self.transmogrifier = transmogrifier
        self.name = name
        self.options = options
        self.previous = previous
        self.context = transmogrifier.context

        # keys for sections further down the chain
        self.pathkey = defaultMatcher(options, 'path-key', name, 'path')
        self.partofkey = options.get('partof-key',
                                     '_partof').strip()

    def __iter__(self):
        """missing docstring."""
        for item in self.previous:
            # check if we have a dataset

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

            partof = item.get(self.partofkey)
            if not partof:
                yield item
                continue
            collpath = partof.get('path')
            if not collpath:
                # no path found
                yield item
                continue

            # TODO: shouldn't allow absolute path here?
            collobj = self.context.unrestrictedTraverse(
                collpath.encode(), None)

            # path doesn't exist
            if collobj is None:
                yield item
                continue

            # we have a collection and an item,
            # let's add this item as part of the collection
            collobj.parts = collobj.parts + [IUUID(obj)]
            obj.part_of = IUUID(collobj)
            yield item


@provider(ISectionBlueprint)
@implementer(ISection)
class Constructor(object):
    """Copy of collective.transmogrifier constructor blueprint, which
    optionally supports updateing / force create new object even if id
    already exists"""

    def __init__(self, transmogrifier, name, options, previous):
        self.previous = previous
        self.context = transmogrifier.context

        self.typekey = defaultMatcher(options, 'type-key', name, 'type',
                                      ('portal_type', 'Type'))
        self.pathkey = defaultMatcher(options, 'path-key', name, 'path')
        self.update = options.get('update', 'true').lower() in (
            "yes", "true", "t", "1")
        self.required = bool(options.get('required'))

    def __iter__(self):
        for item in self.previous:
            keys = item.keys()
            typekey = self.typekey(*keys)[0]
            pathkey = self.pathkey(*keys)[0]

            if not (typekey and pathkey):
                LOG.warn('Not enough info for item: %s' % item)
                yield item
                continue

            type_, path = item[typekey], item[pathkey]

            path = path.encode('ASCII')
            container, id = posixpath.split(path.strip('/'))
            context = traverse(self.context, container, None)
            if context is None:
                error = 'Container %s does not exist for item %s' % (
                    container, path)
                if self.required:
                    raise KeyError(error)
                LOG.warn(error)
                yield item
                continue

            if self.update and getattr(aq_base(context), id, None) is not None:
                # item exists and update flag has been set
                yield item
                continue

            # item does not exist or update flag is false, so we create a new
            # object in any case
            obj = createContentInContainer(context, type_, id=id)

            if obj.getId() != id:
                item[pathkey] = posixpath.join(container, obj.getId())

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
