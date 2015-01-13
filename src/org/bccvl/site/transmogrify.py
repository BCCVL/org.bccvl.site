from zope.interface import implementer, provider
from collective.transmogrifier.interfaces import ISectionBlueprint
from collective.transmogrifier.interfaces import ISection
import os
import os.path
from collective.transmogrifier.utils import defaultMatcher
import simplejson
from org.bccvl.site.interfaces import IBCCVLMetadata
from zope.component import getUtility
from gu.z3cform.rdf.utils import Period
import logging
import json


LOG = logging.getLogger(__name__)


@provider(ISectionBlueprint)
@implementer(ISection)
class ALASource(object):

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

        bccvlmd = {}
        bccvlmd['genre'] = 'DataGenreSpeciesOccurrence'
        bccvlmd['species'] = {
            'scientificName': self.traverse_dict(json, 'taxonConcept/nameString'),
            'vernacularName': self.traverse_dict(json, 'commonNames/0/nameString'),
            'taxonID': self.traverse_dict(json, 'taxonConcept/guid')
        }
        # TODO: other interesting bits:
        #       images/0/thumbnail ... URL to thumbnail image
        # TODO: important thing ... date of export (import date in
        #       plone)/ date modified in ALA
        # FIXME: import of the same guid changes current existing dataset
        #_, id = json['taxonConcept']['guid'].rsplit(':', 1)
        item = {'_type': 'org.bccvl.content.dataset',
                'title': title,
                'description': description,
                'file': {
                    'file': 'data.csv',
                    'contenttype': 'text/csv',
                    'filename': '{}.csv'.format(self.lsid),
                },
                '_bccvlmetadata': bccvlmd,
                # FIXME: don't load files into ram
                '_files': {
                    'data.csv': {
                        'name': 'data.csv',
                        'data': open(csv).read()
                    },
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
            # TODO: consider deepcopy here (for now it's safe because all are normal dicts; no persistent dicts)
            '_bccvlmetadata': dict(IBCCVLMetadata(self.context)),
            '_files': {
                filename: {
                    # FIXME: there is some chaos here... do I really need name and filename?
                    'name': self.context.file.filename,
                    'filename': self.context.file.filename,
                    'contenttype': self.context.file.contentType,
                    # data is a readable file like object
                    # it may be an uncommitted blob file
                    'data': self.context.file.open('r')
                }
            }
        }
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
        self.bccvlmdkey = options.get('bccvlmd-key', '_bccvlmetadata').strip()

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
                path.encode(), None)
                #path.encode().lstrip('/'), None)

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


# TODO: maybe turn this into a RDF updater section.
@provider(ISectionBlueprint)
@implementer(ISection)
class FileMetadataToBCCVL(object):
    """Convert metedata extracted from files (_filemetadata) and store it
    in _bccvmd so that it can be applied to IBCCVLMetadata

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
        self.bccvlmdkey = options.get('bccvlmd-key', '_bccvlmetadata').strip()

    def __iter__(self):
        # exhaust previous iterator
        for item in self.previous:

            fileid = None
            if 'remoteUrl' in item:
                # TODO: assumse, that there is a _file entry to it which has
                #       the name for _filemetadata dictionary
                _files = item.get('_files', {}).get(item.get('remoteUrl'), {})
                fileid = item.get('remoteUrl')
                contenttype = _files.get('contenttype', 'application/octet-stream')
            elif 'file' in item:
                fileid = item.get('file', {}).get('file')
                contenttype = item.get('file', {}).get('contenttype')
            if not fileid:
                # there should be no other None key
                yield item
                continue

            # get metadata for file itself _filemetadata
            filemd = item.setdefault(self.filemetadatakey, {}).get(fileid, {})
            if not filemd:
                # no filemetadata (delete or leave untouched?)
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
                #path.encode().lstrip('/'), None)
                path.encode(), None)

            if content is None:
                yield item
                continue

            # get or create rdf graph
            # TODO: Ending up here means we have a file as main content
            #       let's set the format attribute to this mime type
            #       ? if there is none set yet?
            if contenttype and content.format != contenttype:
                content.format = contenttype

            # TODO: probably needs a different check for multi layer files in future
            # store metadata in self.bccvlmdkey
            bccvlmd = item.setdefault(self.bccvlmdkey, {})
            self._update_bccvl_metadata(bccvlmd, filemd)
            if content.format in ('application/zip', ):
                # TODO: we also have metadata about the file itself, like filesize
                # FIXME: here and in _extract_layer_metadata: filemetadata should probably be under key 'layers' and not 'files'
                #        for now I put them under files to get them extracted
                # multi layer metadata has archive filenames as keys in filemd (for main file)
                # if it is a multi layer file check layers (files)
                # go through all files in the dictionary and generate "layer/file" metadata
                for filename, layermd in filemd.items():
                    self._update_layer_metadata(bccvlmd, layermd['metadata'], filename)
            else:
                self._update_layer_metadata(bccvlmd, filemd, fileid)

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
            # check if 'species' is a set ... if it is the csv had multiple species names in it
            # issue a warning and pick a random species name (in case there is non set already)
            bccvlmd.setdefault('species', {})
            if not bccvlmd['species'].get('scientificName'):
                speciesmd = filemd['species']
                # TODO: currently the file metadata extractor creates a set of species names
                #       in case there are multiple species names in the csv file we should
                #       create multiple datasets (possibly grouped?) or suppert datasets for multiple species
                if isinstance(speciesmd, set):
                    speciesmd = next(iter(speciesmd))
                bccvlmd['species']['scientificname'] = speciesmd

    def _update_layer_metadata(self, bccvlmd, filemd, fileid):
        #  jsonmd: _bccvlmetadata
        layermd = {}
        # projection
        if 'srs' in filemd:
            layermd['srs'] = filemd['srs']
        # other global fileds:
        #    AREA_OR_POINT, PIXEL_SIZE, origin, projection, size, bounds

        # check band metadata
        bandmd =  filemd.get('band')
        if bandmd:
            # TODO: assumes there is only one band
            bandmd = bandmd[0]
            min_ = bandmd.get('min') or bandmd.get('STATISTICS_MINIMUM')
            max_ = bandmd.get('max') or bandmd.get('STATISTICS_MAXIMUM')
            mean_ = bandmd.get('mean') or bandmd.get('STATISTICS_MEAN')
            stddev_ = bandmd.get('stddev') or bandmd.get('STATISTICS_STDDEV')
            width, height = bandmd.get('size', (None, None))
            if min_:
                layermd['min'] = min_
            if max_:
                layermd['max'] = max_
            if mean_:
                layermd['mean'] = mean_
            if stddev_:
                layermd['stddev'] = stddev_
            if 'nodata' in bandmd:
                layermd['nodata'] = bandmd['nodata']
            if width and height:
                layermd['width'] = width
                layermd['height'] = height
            # check if we have more info in layer?
            rat = bandmd.get('rat')
            if rat:
                # FIXME: really a good way to store this?
                import ipdb; ipdb.set_trace()
                layermd['rat'] = json.dumps(rat)
            # other band metadata:
            #    'color interpretation', 'data type', 'description', 'index',
            #    'type': 'continuous'

            ##############################
            # Layer
            #    try to get a layer identifier from somewhere...
            #    from bccvlmetadata
            jsonmd = filemd.get('_bccvlmetadata', {})
            data_type = None
            fileinfo = jsonmd.get('files', {})
            fileinfo = fileinfo.get(fileid, {})
            if 'layer' in fileinfo:
                # TODO: check layer identifier?
                layermd['layer'] = fileinfo['layer']
                data_type = fileinfo.get('data_type')
            # check data_type (continuous, discrete)
            if not data_type:
                data_type = bandmd.get('type', jsonmd.get('data_type'))
            if data_type and data_type.lower() == 'categorical':
                layermd['datatype'] = 'categorical'
            else:
                layermd['datatype'] = 'continuous'
            # TODO: bbox: which units do we want bbox?
            #       lat/long?, whatever coordinates layer uses?
            # End Layer
            #############################
        if layermd:
            # TODO: check if filename really matches fileid? (or is this just item['_files'] id?)
            layermd['filename'] = fileid
            bccvlmd.setdefault('layers', {})[layermd.get('layer', fileid)] = layermd


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
