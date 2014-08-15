from zope.interface import implementer
from zope.publisher.interfaces import NotFound
from zope.component import getUtility, queryUtility
from zope.schema.interfaces import IVocabularyFactory
from Products.Five.browser import BrowserView
from plone.app.uuid.utils import uuidToObject, uuidToCatalogBrain
from gu.z3cform.rdf.interfaces import IORDF, IGraph, IResource
from org.bccvl.site.api.interfaces import IAPIPublisher
from org.bccvl.site.interfaces import IDownloadInfo
from org.bccvl.site.namespace import BCCPROP, BCCVOCAB, DWC, BIOCLIM, NFO, GML
from org.bccvl.site.content.interfaces import IDataset
from plone.uuid.interfaces import IUUID
from rdflib.resource import Resource
from Products.CMFCore.utils import getToolByName
from ordf.namespace import DC as DCTERMS
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
def find_projections(ctx, emission_scenarios, climate_models, years):
        """Find Projection datasets for given criteria"""
        pc = getToolByName(ctx, 'portal_catalog')
        result = []
        brains = pc.searchResults(BCCEmissionScenario=emission_scenarios,
                                  BCCGlobalClimateModel=climate_models,
                                  BCCDataGenre=BCCVOCAB['DataGenreFC'])
        for brain in brains:
            graph = IGraph(brain.getObject())
            # TODO: do better date matching
            year = graph.value(graph.identifier, DCTERMS['temporal'])
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
    md = {
        'url': ds.absolute_url(),
        'id': IUUID(ds),
        'description': ds.description,
        'mimetype': None,
        'filename': None,
        'file': None,
    }
    md.update(getbiolayermetadata(ds))
    md.update(getspeciesmetadata(ds))
    info = IDownloadInfo(ds)
    md.update({
        'mimetype': info['contenttype'],
        'filename': info['filename'],
        'file': info['url'],
        'vizurl': info['alturl'][0]
    })
    return md


def get_vocab_label(vocab, resource):
    if resource is None:
        return resource
    try:
        return unicode(vocab.getTerm(resource.identifier).title)
    except:
        return unicode(resource.identifier)


# TODO: this gets called to often... cache? optimise?
def getbiolayermetadata(ds):
    # TODO: use a sparql query to get all infos in one go...
    #       could get layer friendly names as well
    # FIXME: this here is slow compared to the query version below
    # FIXME: layers should only be added if we have multiple layers
    ret = {'layers': {}}
    handler = getUtility(IORDF).getHandler()
    biovocab = getUtility(IVocabularyFactory,
                          name='org.bccvl.site.BioclimVocabulary')(ds)
    crsvocab = getUtility(IVocabularyFactory,
                          name='org.bccvl.site.CRSVocabulary')(ds)
    resvocab = getUtility(IVocabularyFactory,
                          name='org.bccvl.site.ResolutionVocabulary')(ds)
    dstypevocab = getUtility(IVocabularyFactory,
                             name='org.bccvl.site.DatasetTypeVocabulary')(ds)
    r = IResource(ds, None)
    if r is None:
        return ret
    for ref in r.objects(BCCPROP['hasArchiveItem']):
        # TODO: is this a good test for empty resource?
        obj = next(ref.objects(), None)
        if obj is None:
            ref = Resource(handler.get(ref.identifier), ref.identifier)
        bvar = ref.value(BIOCLIM['bioclimVariable'])
        if bvar:
            # FIXME: if vocabulary and data are committed in same transaction,
            #        the vocab is still empty at that time because it queries
            #        the triple store directly. As this should only happen with
            #        new content, it's not that critical
            ret['layers'][bvar.identifier] = {
                'filename': unicode(ref.value(NFO['fileName'])),
                'label': get_vocab_label(biovocab, bvar),
                'min': ref.value(BCCPROP['min'], None),
                'max': ref.value(BCCPROP['max'], None),
                'width': ref.value(BCCPROP['width'], None),
                'height': ref.value(BCCPROP['height'], None),
                'crs': get_vocab_label(crsvocab,
                                       r.value(GML['srsName'], None)),
                'datatype': get_vocab_label(dstypevocab,
                                            r.value(BCCPROP['datatype'], None))
            }
    # check for metadat for file itself:
    ret.update({
        'min': r.value(BCCPROP['min'], None),
        'max': r.value(BCCPROP['max'], None),
        'width': r.value(BCCPROP['width'], None),
        'height': r.value(BCCPROP['height'], None),
        'resolution': get_vocab_label(resvocab, r.value(BCCPROP['resolution'], None)),
        'crs': get_vocab_label(crsvocab, r.value(GML['srsName'], None)),
        'temporal': unicode(r.value(DCTERMS['temporal'], None)), # FIXME: parse it
        'emsc': unicode(r.value(BCCPROP['emissionsscenario'], None)), # FIXME: title
        'gcm': unicode(r.value(BCCPROP['gcm'], None)), # FIXME: title
        'datatype': get_vocab_label(dstypevocab,
                                    r.value(BCCPROP['datatype'], None))
    })
    # do we have layer metadata directly on the object? (no archive items)
    bvar = r.value(BIOCLIM['bioclimVariable'])
    if bvar:
        # FIXME: checking for bioclimVariable is not a good test
        #        some files wolud have multiple layers as metadat... (like R SDM data files)
        try:
            label = unicode(biovocab.getTerm(bvar.identifier).title)
        except:
            label = bvar.identifier
        ret.update({
            'label': label,
            'layer': bvar.identifier
        })

    return ret


def getspeciesmetadata(ds):
    res = IResource(ds, None)
    ret = {
        'scientificname': None,
        'commonname': None,
        'taxonid': None,
        'rows': None
    }
        # bccprop: datagenre ->  bccvocab: DataGenreSO
        # bccprop: specieslayer -> bccvocab: SpeciesLayerP, SpeciesLayerX
    if res is None:
        return ret
    for key, prop in (('rows', BCCPROP['rows']),
                      ('scientificname', DWC['scientificName']),
                      ('taxonid', DWC['taxonID']),
                      ('commonname', DWC['vernacularName'])):
        val = res.value(prop)
        if val:
            ret[key] = unicode(val)
    return ret


# TODO: update this method to new interface
# def getbiolayermetadata_query(ds):
#     # TODO: use a sparql query to get all infos in one go...
#     #       could get layer friendly names as well
#     # FIXME: this here does not respect uncomitted changes
#     query = """PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
# PREFIX ns: <http://www.bccvl.org.au/individual/>
# PREFIX cvocab: <http://namespaces.griffith.edu.au/collection_vocab#>
# PREFIX bccprop: <http://namespaces.bccvl.org.au/prop#>
# PREFIX bioclim: <http://namespaces.bccvl.org.au/bioclim#>
# PREFIX nfo: <http://www.semanticdesktop.org/ontologies/2007/03/22/nfo#>


# SELECT ?bvar ?blabel ?fnam WHERE {{
#   Graph ?g {{
#   <{subject}> a cvocab:Dataset .
#   <{subject}> bccprop:hasArchiveItem ?ar .
#   }}
#   Graph ?a {{
#     ?ar bioclim:bioclimVariable ?bvar .
#     ?ar nfo:fileName ?fnam .
#   }}
#   Graph ?b {{
#     ?bvar rdfs:label ?blabel .
#   }}
# }}"""
#     # FIXME: need to clean up getContentUri function
#     uri = getUtility(IORDF).getContentUri(ds)
#     q = query.format(subject=uri)
#     ret = {}
#     handler = getUtility(IORDF).getHandler()
#     for row in handler.query(q):
#         ret[row['bvar']] = {'label': unicode(row['blabel']),
#                             'filename': unicode(row['fnam'])}
#     return ret


############# ++api++<name>/ experiment
######## maybe useful with inspection? e.g. json-ld schema, json-hyperschema?
######## json-api ?


# def getMetadata(datasetid):
#     ds = uuidToObject(datasetid)
#     if ds is None:
#         # TODO: raise Exception?
#         return None
#     return getdsmetadata(ds)


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
