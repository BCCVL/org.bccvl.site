from org.bccvl.site.interfaces import IDownloadInfo, IBCCVLMetadata
from org.bccvl.site.content.interfaces import IDataset
from plone.uuid.interfaces import IUUID
from Products.CMFCore.utils import getToolByName
from Products.ZCatalog.interfaces import ICatalogBrain


# TODO: brains=True would be more useful for internal API?
def query(context=None, brains=False, **kw):
    """Query catalog for datasets.

    Queries the catalog with context as path (or navigation root if None),
    and returns a generator with dataset specific metadat about each indexed
    dataset.

    brains ... if True, this method returns the catalog brains directly.
               if False additional metadata about each item is generated
    """
    if context is None:
        # FIXME: lookup site root from nothing
        raise NotImplementedError()
    # assume we have a context
    query = kw
    query.update({
        'object_provides': IDataset.__identifier__,
        'path': '/'.join(context.getPhysicalPath()),
    })

    # TODO: should optimise this. e.g. return generator,
    pc = getToolByName(context, 'portal_catalog')
    for brain in pc.searchResults(query):
        if brains:
            yield brain
        else:
            yield getdsmetadata(brain)


# TODO: turn this into some adapter lookup component-> maybe use
# z3c.form validation adapter lookup?
def find_projections(ctx, emission_scenarios, climate_models, years, resolution=None):
        """Find Projection datasets for given criteria"""
        pc = getToolByName(ctx, 'portal_catalog')
        result = []
        params = {
            'BCCEmissionScenario': emission_scenarios,
            'BCCGlobalClimateModel': climate_models,
            'BCCDataGenre': 'DataGenreFC'
        }
        if resolution:
            params['BCCResolution'] = resolution
        brains = pc.searchResults(**params)
        for brain in brains:
            md = IBCCVLMetadata(brain.getObject())
            year = md.get('temporal', None)
            if year in years:
                # TODO: yield?
                result.append(brain)
        return result


def getdsmetadata(ds):
    # TODO: support brain, obj and uuid string (URI as well?)
    # extract info about files
    if ICatalogBrain.providedBy(ds):
        ds = ds.getObject()
        # TODO: try to use brains only here
        #    url: ds.getURL()
        #    id: ds.UID,
        #    description: ds.Description
    # start with metadata annotation
    md = {
        #'@context': { },
        '@id': IUUID(ds),
        '@type':  ds.portal_type,
        'url': ds.absolute_url(),
        'id': IUUID(ds),
        'description': ds.description,
    }
    md.update(IBCCVLMetadata(ds))
    dlinfo = IDownloadInfo(ds)
    md.update({
        'mimetype': dlinfo['contenttype'],
        'filename': dlinfo['filename'],
        'file': dlinfo['url'],
        'vizurl': dlinfo['alturl'][0]
    })
    return md


def get_vocab_label(vocab, resource):
    """Lookup up title for resource in vocabulary.

    In case resource is a Resource the function tries to find a label
    for resource.identifier, otherwise it assumes that resource is a
    URIRef.

    If there is no title in the vocabulary, it will return the value
    passed as resource converted to unicode

    """
    if resource is None:
        return resource
    if IResource.providedBy(resource):
        try:
            return unicode(vocab.getTerm(resource.identifier).title)
        except:
            return unicode(resource.identifier)
    else:
        try:
            return unicode(vocab.getTerm(resource).title)
        except:
            return unicode(resource)


# # TODO: this gets called to often... cache? optimise?
# def getbiolayermetadata(ds):
#     # TODO: use a sparql query to get all infos in one go...
#     #       could get layer friendly names as well
#     # FIXME: this here is slow compared to the query version below
#     # FIXME: layers should only be added if we have multiple layers
#     ret = {'layers': []}
#     biovocab = getUtility(IVocabularyFactory,
#                           name='org.bccvl.site.BioclimVocabulary')(ds)
#     crsvocab = getUtility(IVocabularyFactory,
#                           name='org.bccvl.site.CRSVocabulary')(ds)
#     resvocab = getUtility(IVocabularyFactory,
#                           name='org.bccvl.site.ResolutionVocabulary')(ds)
#     dstypevocab = getUtility(IVocabularyFactory,
#                              name='org.bccvl.site.DatasetTypeVocabulary')(ds)
#     md = IBCCVLMetadata(ds, None)
#     if not md:
#         return ret
#     ret['@id'] = IUUID(ds)
#     for ref in md.get('archiveItems', []):
#         bvar = ref.get(BIOCLIM['bioclimVariable'])
#         if bvar:
#             # FIXME: if vocabulary and data are committed in same transaction,
#             #        the vocab is still empty at that time because it queries
#             #        the triple store directly. As this should only happen with
#             #        new content, it's not that critical
#             ret['layers'].append({
#                 'layer': bvar, # {'@id', 'label'}
#                 'filename': ref.get(NFO['fileName']),
#                 'label': get_vocab_label(biovocab, bvar),
#                 'min': ref.get(BCCPROP['min'], None),
#                 'max': ref.get(BCCPROP['max'], None),
#                 'width': ref.get(BCCPROP['width'], None),
#                 'height': ref.get(BCCPROP['height'], None),
#                 'crs': get_vocab_label(crsvocab,
#                                        ref.get(GML['srsName'], None)),
#                 'datatype': get_vocab_label(dstypevocab,
#                                             ref.get(BCCPROP['datatype'], None))
#             })
#     # check for metadat for file itself:
#     ret.update({
#         'resolution': get_vocab_label(resvocab, md.get(BCCPROP['resolution'])),
#         'temporal': md.get(DCTERMS['temporal']),  # FIXME: parse it
#         'emsc': md.get(BCCPROP['emissionsscenario']),  # FIXME: title
#         'gcm': md.get(BCCPROP['gcm']),  # FIXME: title
#     })
#     # do we have layer metadata directly on the object? (no archive items)
#     bvar = md.get('layer')
#     if bvar:
#         # FIXME: checking for bioclimVariable is not a good test
#         #        some files wolud have multiple layers as metadat... (like R SDM data files)
#         try:
#             label = unicode(biovocab.getTerm(bvar).title)
#         except:
#             label = bvar
#         ret['layers'].append({
#             'label': label,
#             'layer': bvar,
#             'min': md.get(BCCPROP['min']),
#             'max': md.get(BCCPROP['max']),
#             'width': md.get(BCCPROP['width']),
#             'height': md.get(BCCPROP['height']),
#             'crs': get_vocab_label(crsvocab, md.get(GML['srsName'])),
#             'datatype': get_vocab_label(dstypevocab,
#                                         md.get(BCCPROP['datatype']))
#         })

#     return ret


# def getspeciesmetadata(ds):
#     md = IBCCVLMetadata(ds, None)
#     ret = {
#         'scientificname': None,
#         'commonname': None,
#         'taxonid': None,
#         'rows': None
#     }
#         # bccprop: datagenre ->  bccvocab: DataGenreSpeciesOccurrence
#     if not md:
#         return ret
#     for key, prop in (('rows', BCCPROP['rows']),
#                       ('scientificname', DWC['scientificName']),
#                       ('taxonid', DWC['taxonID']),
#                       ('commonname', DWC['vernacularName'])):
#         val = md.get(prop)
#         if val:
#             ret[key] = unicode(val)
#     return ret


############# ++api++<name>/ experiment
######## maybe useful with inspection? e.g. json-ld schema, json-hyperschema?
######## json-api ?

# from zope.interface import Interface
# class IDmApi(Interface):

#     def getMetadata(datasetid):
#         """get metadata about given dataset uuid"""


# @implementer(IAPIPublisher, IDmApi)
# class DmApiPublisher(BrowserView):

#     allow_access_to_unprotected_subobjects = False

#     # TODO: provide IPublishTravers?
#     #       if net provided here an adapter will be looked for self
#     #       fallback to DefaultPublishTraverse
#     #       1st check: hasattr
#     #       2nd check: view: (object, request), Interface, name=
#     #       3rd check: getattr
#     #       4th check: try dict access

#     def getMetadata(self, datasetid):
#         """Need a docstring to get this "attribute" published.
#         """
#         import ipdb; ipdb.set_trace()
#         ds = getMetadata(datasetid)
#         if ds is None:
#             raise NotFound(self.context, datasetid, self.request)
#         return ds

#     # BrowserPublisher
#     # def browserefault(self, request): self, ()

#     # IPubilshTravers
#     def publishTraverse(self, name):
#         import ipdb; ipdb.set_trace()
#         return super(DmApiPublisher, self).publishTraverse(name)

#     # IBrowserPage,
#     # def __call__(...)
#     def __call__(self, *args, **kw):
#         import ipdb; ipdb.set_trace()
#         return self.getMetadata(*args, **kw)
