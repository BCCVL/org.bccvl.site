from plone.indexer.decorator import indexer
from plone.indexer.interfaces import IIndexer
from zope.interface import implementer
from zope.component import getUtility
from zope.schema.interfaces import IVocabularyFactory
from Products.CMFPlone.utils import safe_unicode
from org.bccvl.site.content.interfaces import IDataset
from org.bccvl.site.content.interfaces import IExperiment
from org.bccvl.site.content.interfaces import IBlobDataset
from org.bccvl.site.content.interfaces import IRemoteDataset
from org.bccvl.site.content.interfaces import IProjectionExperiment, IEnsembleExperiment, IBiodiverseExperiment
from org.bccvl.site.behavior.collection import ICollection
from org.bccvl.site.interfaces import IBCCVLMetadata, IExperimentJobTracker
from org.bccvl.site.job.interfaces import IJobTracker


@indexer(IDataset)
def dataset_BCCDataGenre(obj, **kw):
    return IBCCVLMetadata(obj).get('genre')


@indexer(IDataset)
def dataset_BCCEmissionScenario(obj, **kw):
    return IBCCVLMetadata(obj).get('emsc')


@indexer(IDataset)
def dataset_BCCGlobalClimateModel(obj, **kw):
    return IBCCVLMetadata(obj).get('gcm')


@indexer(IDataset)
def BCCDatasetResolution(obj, **kw):
    return IBCCVLMetadata(obj).get('resolution')


@indexer(IExperiment)
def BCCExperimentResolution(obj, **kw):
    return IBCCVLMetadata(obj).get('resolution')


@indexer(IDataset)
def DatasetSearchableText(obj, **kw):
    md = IBCCVLMetadata(obj)
    entries = [
        safe_unicode(obj.id),
        safe_unicode(obj.title) or u"",
        safe_unicode(obj.description) or u""
    ]
    if 'layers' in md:
        layer_vocab = getUtility(IVocabularyFactory, 'layer_source')(obj)
        for key in md['layers']:
            if key not in layer_vocab:
                continue
            entries.append(
                safe_unicode(layer_vocab.getTerm(key).title) or u""
            )
    if 'species' in md:
        entries.extend((
            safe_unicode(md.get('species', {}).get('scientificName')) or u"",
            safe_unicode(md.get('species', {}).get('vernacularName')) or u"",
        ))
    if md.get('genre') == "DataGenreFC":
        # year, gcm, emsc
        emsc_vocab = getUtility(IVocabularyFactory, 'emsc_source')(obj)
        gcm_vocab = getUtility(IVocabularyFactory, 'gcm_source')(obj)
        year = unicode(md.get('year', u''))
        month = unicode(md.get('month', u''))
        if md['emsc'] in emsc_vocab:
            entries.append(
                safe_unicode(emsc_vocab.getTerm(md['emsc']).title) or u""
            )
        if md['gcm'] in gcm_vocab:
            entries.append(
                safe_unicode(gcm_vocab.getTerm(md['gcm']).title) or u""
            )
        entries.append(year)
        entries.append(month)
    elif md.get('genre') == "DataGenreCC":
        entries.append(u"current")
    return u" ".join(entries)


@indexer(IDataset)
def dataset_environmental_layer(obj, **kw):
    md = IBCCVLMetadata(obj)
    # if we have 'layers_used' index it
    if 'layers_used' in md:
        return md['layers_used']
    # otherwise index list of layers provided by dataset
    return md.get('layers', None)


@indexer(IExperiment)
def experiment_reference_indexer(object, **kw):
    # TODO: Add Ensemble -> SDM, Proj, Biodiv, Biodiverse -> SDM, Proj
    if IProjectionExperiment.providedBy(object):
        return object.species_distribution_models.keys()
    elif IEnsembleExperiment.providedBy(object):
        return object.datasets.keys()
    elif IBiodiverseExperiment.providedBy(object):
        return object.projection.keys()
    else:
        pass


@implementer(IIndexer)
class JobStateIndexer(object):

    def __init__(self, context, catalog):
        self.context = context
        self.catalog = catalog

    def __call__(self, **kw):
        jt = IJobTracker(self.context)
        # TODO: if state is empty check if there is a downloadable file
        #       Yes: COMPLETED
        #       No: FAILED
        try:
            state = jt.state
        except TypeError:
            return None
        if not state:
            if IBlobDataset.providedBy(self.context):
                # we have no state, may happen for imported datasets,
                # let's check if we have a file
                if self.context.file is not None:
                    state = 'COMPLETED'
                else:
                    state = 'FAILED'
            elif IRemoteDataset.providedBy(self.context):
                if self.context.remoteUrl:
                    state = 'COMPLETED'
                else:
                    state = 'FAILED'
        return state


@implementer(IIndexer)
class ExperimentJobStateIndexer(object):

    def __init__(self, context, catalog):
        self.context = context
        self.catalog = catalog

    def __call__(self, **kw):
        jt = IExperimentJobTracker(self.context)
        # TODO: if state is empty check if there is a downloadable file
        #       Yes: COMPLETED
        #       No: FAILED
        return jt.state


@indexer(IDataset)
def scientific_category(obj, **kw):
    md = IBCCVLMetadata(obj)
    vocab = getUtility(IVocabularyFactory, 'scientific_category_source')(obj)
    path = set()
    for cat in md.get('categories', ()):
        path.update(vocab.getTermPath(cat))
    if path:
        return tuple(path)
    return None


@indexer(ICollection)
def scientific_category_collection(obj, **kw):
    return obj.categories or None


@indexer(IDataset)
def year(obj, **kw):
    # FIXME: this indexer is meant for future projection only ....
    # - make sure we don't index any other datasets. i.e. environmental and current datasets, which may have a date attached to it, but it is meaningless for future projections
    md = IBCCVLMetadata(obj)
    year = md.get('year', None)
    if year:
        year = str(year)
    return year


@indexer(IDataset)
def month(obj, **kw):
    # FIXME: see year indexer above
    md = IBCCVLMetadata(obj)
    return md.get('month', None)

@indexer(IDataset)
def domain_type(obj, **kw):
    return obj.subject

@indexer(IDataset)
def headers(obj, **kw):
    md = IBCCVLMetadata(obj)
    return md.get('headers', None)