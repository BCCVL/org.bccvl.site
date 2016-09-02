from collections import OrderedDict

from zope.schema.interfaces import IVocabularyFactory
from zope.schema.vocabulary import SimpleVocabulary, SimpleTerm, TreeVocabulary
from zope.interface import implementer, provider
from zope.component import getUtility
from plone.registry.interfaces import IRegistry
from Products.CMFCore.utils import getToolByName
from org.bccvl.site import defaults
from plone.app.contenttypes.interfaces import IFolder
# species occurrence datasets
from zope.site.hooks import getSite
from zope.interface import directlyProvides


class BCCVLSimpleVocabulary(SimpleVocabulary):
    """
    A SimpleVocabulary, that takes advantage of terms
    supplied as generators.
    """

    def __init__(self, terms, *interfaces):
        """Initialize the vocabulary given an iterable of terms.

        The vocabulary keeps a reference to the list of terms passed
        in; it should never be modified while the vocabulary is used.

        One or more interfaces may also be provided so that alternate
        widgets may be bound without subclassing.
        """
        self.by_value = {}
        self.by_token = {}
        self._terms = []
        for term in terms:
            if term.value in self.by_value:
                raise ValueError(
                    'term values must be unique: %s' % repr(term.value))
            if term.token in self.by_token:
                raise ValueError(
                    'term tokens must be unique: %s' % repr(term.token))
            self.by_value[term.value] = term
            self.by_token[term.token] = term
            self._terms.append(term)
        if interfaces:
            directlyProvides(self, *interfaces)

    @classmethod
    def fromItems(cls, items, *interfaces):
        """Construct a vocabulary from an iterable of (token, value) pairs.

        The order of the items is preserved as the order of the terms
        in the vocabulary.  Terms are created by calling the class
        method createTerm() with the pair (value, token).

        One or more interfaces may also be provided so that alternate
        widgets may be bound without subclassing.
        """
        terms = (cls.createTerm(value, token) for (token, value) in items)
        return cls(terms, *interfaces)

    @classmethod
    def fromValues(cls, values, *interfaces):
        """Construct a vocabulary from a simple iterable list.

        Values of the list become both the tokens and values of the
        terms in the vocabulary.  The order of the values is preserved
        as the order of the terms in the vocabulary.  Tokens are
        created by calling the class method createTerm() with the
        value as the only parameter.

        One or more interfaces may also be provided so that alternate
        widgets may be bound without subclassing.
        """
        terms = (cls.createTerm(value) for value in values)
        return cls(terms, *interfaces)


# TODO: optimize catalog vocabulary for lazy sliced access
class BrainsVocabulary(BCCVLSimpleVocabulary):
    # term.value ... UUID
    # term.token ... UUID
    # term.title ... Title
    # term.brain ... the brain

    # implements IVocaburaryTokenized

    @classmethod
    def createTerm(cls, brain, context):
        term = SimpleTerm(value=brain['UID'],
                          token=brain['UID'],
                          title=brain.Title)
        term.brain = brain
        return term

    @classmethod
    def fromBrains(cls, brains, context, *interfaces):
        terms = (cls.createTerm(brain, context) for brain in brains)
        return cls(terms, *interfaces)


# TODO: would be good to add some caching here?
#       memoize per request could be good enough or
#       watch for changes on whatever?
@implementer(IVocabularyFactory)
class CatalogVocabularyFactory(object):

    def __init__(self, name, query):
        self.__name__ = name
        self.query = query

    def __call__(self, context):
        try:
            catalog = getToolByName(context, 'portal_catalog')
        except AttributeError:
            catalog = getToolByName(getSite(), 'portal_catalog')
        brains = catalog.searchResults(**self.query)
        return BrainsVocabulary.fromBrains(brains, context)


# TODO: Need either two vocabs to separate sdm and traits scripts,
#       or a contextsourcebinder that filters the correct scrips
sdm_functions_source = CatalogVocabularyFactory(
    'sdm_functions_source',
    query={
        # TODO: could use a path restriction to toolkits folder
        # 'path': {
        #     'query': '/'.join([self.site_physical_path, defaults.FUNCTIONS_FOLDER_ID])
        # },
        'object_provides': 'org.bccvl.site.content.function.IFunction',
        # FIXME: find another way to separate SDM and traits "functions"
        'id': ['ann', 'bioclim', 'brt', 'circles', 'cta', 'convhull',
               'fda', 'gam', 'gbm', 'glm', 'geoDist', 'geoIDW',
               'maxent', 'mars', 'rf', 'sre', 'voronoiHull'],
        # 'mahal', 'domain'
        'sort_on': 'sortable_title',
    },
)


traits_functions_source = CatalogVocabularyFactory(
    'traits_functions_source',
    query={
        # TODO: could use a path restriction to toolkits folder
        # 'path': {
        #     'query': '/'.join([self.site_physical_path, defaults.FUNCTIONS_FOLDER_ID])
        # },
        'object_provides': 'org.bccvl.site.content.function.IFunction',
        # FIXME: find another way to separate SDM and traits "functions"
        'id': ['lm', 'speciestrait_glm', 'speciestrait_gam', 'gamlss',
               'aov', 'manova'],
        'sort_on': 'sortable_title',
    },
)


# A vocabulary to assign functions (toolkits) to experiment types
experiment_type_vocabulary = SimpleVocabulary([
    SimpleTerm("org.bccvl.content.sdmexperiment", "org.bccvl.content.sdmexperiment",
               u"Species Distribution Modelling Experiment"),
    SimpleTerm("org.bccvl.content.projectionexperiment",
               "org.bccvl.content.projectionexperiment", u"Climate Change Experiment"),
    SimpleTerm("org.bccvl.content.biodiverseexperiment",
               "org.bccvl.content.biodiverseexperiment", u"Biodiverse Experiment"),
    SimpleTerm("org.bccvl.content.speciestraitsexperiment",
               "org.bccvl.content.speciestraitsexperiment", u"Species Trait Modelling Experiment"),
    SimpleTerm("org.bccvl.content.ensemble",
               "org.bccvl.content.ensemble", u"Ensemble Analysis"),
    SimpleTerm(None, "None", u"Unknown")
])


@provider(IVocabularyFactory)
def experiment_type_source(context):
    return experiment_type_vocabulary


@implementer(IVocabularyFactory)
class RegistryVocabularyFactory(object):

    def __init__(self, name):
        self.__name__ = name

    def _term_generator(self, reg):
        for record in reg[self.__name__]:
            term = SimpleTerm(value=record['value'],
                              token=record['value'],
                              title=record['title'])
            # attach additional attributes to term:
            for key in record.keys():
                if not hasattr(term, key):
                    if not hasattr(term, 'data'):
                        term.data = {}
                    term.data[key] = record[key]
            yield term

    def __call__(self, context):
        reg = getUtility(IRegistry)
        return BCCVLSimpleVocabulary(self._term_generator(reg))


layer_source = RegistryVocabularyFactory(
    'org.bccvl.layers')


resolution_source = RegistryVocabularyFactory(
    'org.bccvl.resolution')


crs_source = RegistryVocabularyFactory(
    'org.bccvl.crs')


gcm_vocabulary = SimpleVocabulary([
    SimpleTerm("cccma-cgcm31", "cccma-cgcm31",
               "Coupled Global Climate Model (CGCM3)"),
    SimpleTerm("ccsr-miroc32hi", "ccsr-miroc32hi", "MIROC3.2 (hires)"),
    SimpleTerm("ccsr-miroc32med", "ccsr-miroc32med", "MIROC3.2 (medres)"),
    SimpleTerm("cnrm-cm3", "cnrm-cm3", "CNRM-CM3"),
    SimpleTerm("csiro-mk30", "csiro-mk30", "CSIRO Mark 3.0"),
    SimpleTerm("gfdl-cm20", "gfdl-cm20", "CM2.0 - AOGCM"),
    SimpleTerm("gfdl-cm21", "gfdl-cm21", "CM2.1 - AOGCM"),
    SimpleTerm("giss-modeleh", "giss-modeleh", "GISS-EH"),
    SimpleTerm("giss-modeler", "giss-modeler", "GISS-ER"),
    SimpleTerm("iap-fgoals10g", "iap-fgoals10g", "FGOALS1.0_g"),
    SimpleTerm("inm-cm30", "inm-cm30", "INMCM3.0"),
    SimpleTerm("ipsl-cm4", "ipsl-cm4", "IPSL-CM4"),
    SimpleTerm("mpi-echam5", "mpi-echam5", "ECHAM5/MPI-OM"),
    SimpleTerm("mri-cgcm232a", "mri-cgcm232a", "MRI-CGCM2.3.2"),
    SimpleTerm("ncar-ccsm30", "ncar-ccsm30",
               "Community Climate System Model, version 3.0 (CCSM3)"),
    SimpleTerm("ncar-pcm1", "ncar-pcm1", "Parallel Climate Model (PCM)"),
    SimpleTerm("ukmo-hadcm3", "ukmo-hadcm3", "HadCM3"),
    SimpleTerm("ukmo-hadgem1", "ukmo-hadgem1",
               "Hadley Centre Global Environmental Model, version 1 (HadGEM1)"),
    SimpleTerm("access1-0", "access1-0", "ACCESS1.0"),
    SimpleTerm("bcc-csm1-1", "bcc-csm1-1",
               "Beijing Climate Center Climate System Model (BCC_CSM1.1)"),
    SimpleTerm("ncar-ccsm40", "ncar-ccsm40",
               "Community Climate System Model, version 4.0 (CCSM4)"),
    SimpleTerm("cesm1-cam5-1-fv2", "cesm1-cam5-1-fv2",
               "Community Atmosphere Model, version 5.1 (CAM-5.1)"),
    SimpleTerm("cnrm-cm5", "cnrm-cm5", "CNRM-CM5"),
    SimpleTerm("gfdl-cm3", "gfdl-cm3", "CM3 - AOGCM"),
    SimpleTerm("gfdl-esm2g", "gfdl-esm2g",
               "GFDL Earth System Model, version 2.1 (ESM2G)"),
    SimpleTerm("giss-e2-r", "giss-e2-r",
               "ModelE/Russell 2x2.5xL40 (GISS-E2-R)"),
    SimpleTerm("hadgem2-a0", "hadgem2-a0",
               "Hadley Global Environment Model 2 - Atmosphere (HadGEM2-A)"),
    SimpleTerm("hadgem2-cc", "hadgem2-cc",
               "Hadley Global Environment Model 2 - Carbon Cycle (HadGEM2-CC)"),
    SimpleTerm("hadgem2-es", "hadgem2-es",
               "Hadley Global Environment Model 2 - Earth System (HadGEM2-ES)"),
    SimpleTerm("inmcm4", "inmcm4", "INMCM4.0"),
    SimpleTerm("ipsl-cm5a-lr", "ipsl-cm5a-lr", "IPSL-CM5A (lores)"),
    SimpleTerm("miroc-esm-chem", "miroc-esm-chem", "MIROC-ESM-CHEM"),
    SimpleTerm("miroc-esm", "miroc-esm", "MIROC-ESM"),
    SimpleTerm("miroc5", "miroc5", "MIROC5"),
    SimpleTerm("mpi-esm-lr", "mpi-esm-lr",
               "Max Planck Institute for Meteorology Earth System Model (lores) (MPI-ESM-LR)"),
    SimpleTerm("mri-cgcm3", "mri-cgcm3",
               "Meteorological Research Institute Global Climate Model, version 3.0 (MRI-CGMC3)"),
    SimpleTerm("noresm1-m", "noresm1-m",
               "Norwegian Earth System Model (NorESM1-M)"),
    SimpleTerm("gcm-mean-5", "gcm-mean-5",
               "Mean of 5 GCM's: ECHAM5, GFDL-CM2.0, GFDL-CM2.1, MICRO3.2_MEDRES & UKMO-HadCM"),
])


@provider(IVocabularyFactory)
def gcm_source(context):
    return gcm_vocabulary


emsc_vocabulary = SimpleVocabulary([
    SimpleTerm("RCP3PD", "RCP3PD", "RCP3PD"),
    SimpleTerm("RCP45", "RCP45", "RCP45"),
    SimpleTerm("RCP6", "RCP6", "RCP6"),
    SimpleTerm("RCP85", "RCP85", "RCP85"),
    SimpleTerm("SRESA1B", "SRESA1B", "SRESA1B"),
    SimpleTerm("SRESA1FI", "SRESA1FI", "SRESA1FI"),
    SimpleTerm("SRESA2", "SRESA2", "SRESA2"),
    SimpleTerm("SRESB1", "SRESB1", "SRESB1"),
    SimpleTerm("SRESB2", "SRESB2", "SRESB2"),
])


@provider(IVocabularyFactory)
def emsc_source(context):
    return emsc_vocabulary


datatype_vocabulary = SimpleVocabulary([
    SimpleTerm("continuous", "continuous", "continuous"),
    SimpleTerm("discrete", "discrete", "discrete")
])


@provider(IVocabularyFactory)
def datatype_source(context):
    return datatype_vocabulary

programming_language_vocab = SimpleVocabulary([
    SimpleTerm("R", "R", u'R'),
    SimpleTerm("Perl", "Perl", u'Perl'),
    # SimpleTerm("Python", "Python", u'Python'),
])


# TODO: maybe a tree vocabulary would be nice here?
@provider(IVocabularyFactory)
def programming_language_vocab_factory(context):
    return programming_language_vocab


def createTerm(value, token, title, data):
    term = SimpleTerm(value, token, title)
    term.data = data
    return term

category_desc = {'profile': u"These models only use occurrence data, and are based on the characterization of the environmental conditions of locations associated with species presence.",
                 'machineLearning': u"These models typically use one part of the dataset to 'learn' and describe the dataset (training) and the other part to to assess the accuracy of the model.",
                 'statistical': u"These models estimate the parameters of the predictors, and construct a function that best describes the effect of environmental variables on species occurrence. The suitability of a particular model is often defined by specific model assumptions.",
                 'geographic': u"These models use the geographic location of known occurrences of a species to predict the likelihood of presence in other locations, and do not rely on the values of environmental variables."
                 }

algorithm_category_vocab = SimpleVocabulary([
    createTerm("profile", "profile", u'Profile Models', {
               'description': category_desc['profile']}),
    createTerm("machineLearning", "machineLearning", u'Machine Learning Models', {
               'description': category_desc['machineLearning']}),
    createTerm("statistical", "statistical", u'Statistical Models',
               {'description': category_desc['statistical']}),
    createTerm("geographic", "geographic", u'Geographic Models',
               {'description': category_desc['geographic']}),
])

# TODO: maybe a tree vocabulary would be nice here?


@provider(IVocabularyFactory)
def algorithm_category_vocab_factory(context):
    return algorithm_category_vocab

genre_vocabulary = SimpleVocabulary([
    SimpleTerm("DataGenreSpeciesOccurrence",
               "DataGenreSpeciesOccurrence", "Species Occurrence"),
    SimpleTerm("DataGenreSpeciesAbsence",
               "DataGenreSpeciesAbsence", "Species Absence"),
    SimpleTerm("DataGenreSpeciesAbundance",
               "DataGenreSpeciesAbundance", "Species Abundance"),
    SimpleTerm("DataGenreSpeciesCollection",
               "DataGenreSpeciesCollection", "Species Occurrence Collection"),
    SimpleTerm("DataGenreTraits", "DataGenreTraits", "Species Traits"),
    SimpleTerm("DataGenreCC", "DataGenreCC", "Current Climate"),
    SimpleTerm("DataGenreFC", "DataGenreFC", "Future Climate"),
    SimpleTerm("DataGenreE", "DataGenreE", "Environmental"),
    SimpleTerm("DataGenreSDMEval", "DataGenreSDMEval",
               "Species Distribution Model Evaluation"),
    SimpleTerm("DataGenreSDMModel", "DataGenreSDMModel",
               "Species Distribution Model"),
    SimpleTerm("DataGenreClampingMask",
               "DataGenreClampingMask", "Clamping Mask"),
    SimpleTerm("DataGenreSTModel", "DataGenreSTModel", "Species Traits Model"),
    SimpleTerm("DataGenreSTResult", "DataGenreSTResult",
               "Species Traits Result"),
    SimpleTerm("DataGenreFP", "DataGenreFP", "Future Projection"),
    SimpleTerm("DataGenreCP", "DataGenreCP", "Current Projection"),
    SimpleTerm("DataGenreLog", "DataGenreLog", "Output log file"),
    SimpleTerm("DataGenreBinaryImage",
               "DataGenreBinaryImage", "Binary input image"),
    SimpleTerm("DataGenreENDW_CWE", "DataGenreENDW_CWE",
               "Endemism whole - Corrected Weighted Endemism"),
    SimpleTerm("DataGenreENDW_WE", "DataGenreENDW_WE",
               "Endemism whole- Weighted Endemism"),
    SimpleTerm("DataGenreENDW_RICHNESS", "DataGenreENDW_RICHNESS",
               "Endemism whole - Richness used in ENDW_CWE"),
    SimpleTerm("DataGenreENDW_SINGLE", "DataGenreENDW_SINGLE",
               "Endemism whole - Unweighted by the number of neighbours"),
    SimpleTerm("DataGenreREDUNDANCY_SET1", "DataGenreREDUNDANCY_SET1",
               "Redundancy - neighbour set 1"),
    SimpleTerm("DataGenreREDUNDANCY_SET2", "DataGenreREDUNDANCY_SET2",
               "Redundancy - neighbour set 2"),
    SimpleTerm("DataGenreREDUNDANCY_ALL", "DataGenreREDUNDANCY_ALL",
               "Redundancy - both neighbour sets"),
    SimpleTerm("DataGenreRAREW_CWE", "DataGenreRAREW_CWE",
               "Rarity whole - Corrected weighted rarity"),
    SimpleTerm("DataGenreRAREW_RICHNESS", "DataGenreRAREW_RICHNESS",
               "Rarity whole - Richness used in RAREW_CWE"),
    SimpleTerm("DataGenreRAREW_WE", "DataGenreRAREW_WE",
               "Rarity whole - weighted rarity"),
    SimpleTerm("DataGenreBiodiverseModel",
               "DataGenreBiodiverseModel", "Biodiverse output"),
    SimpleTerm("DataGenreBiodiverseOutput",
               "DataGenreBiodiverseOutput", "Biodiverse analysis output"),
    SimpleTerm("DataGenreEnsembleResult",
               "DataGenreEnsembleResult", "Ensembling output"),
    SimpleTerm("JobScript", "JobScript", "Job script"),
])


@provider(IVocabularyFactory)
def genre_source(context):
    return genre_vocabulary


job_state_vocabulary = SimpleVocabulary([
    SimpleTerm('PENDING', 'PENDING', u'Pending'),
    SimpleTerm('QUEUED', 'QUEUED', u'Queued'),
    SimpleTerm('RUNNING', 'RUNNING', u'Running'),
    SimpleTerm('COMPLETED', 'COMPLETED', u'Completed'),
    SimpleTerm('FAILED', 'FAILED', u'Failed'),
    SimpleTerm('REMOVED', 'REMOVED', u'Removed')
])


@provider(IVocabularyFactory)
def job_state_source(context):
    return job_state_vocabulary


scientific_category_vocabulary = TreeVocabulary(OrderedDict([
    (SimpleTerm('biological', 'biological', u'Biological'), OrderedDict([
        (SimpleTerm('occurrence', 'occurrence', u'Occurrence'), {}),
        (SimpleTerm('absence', 'absence', u'Absence'), {}),
        (SimpleTerm('abundance', 'abundance', u'Abundance'), {}),
        (SimpleTerm('traits', 'traits', u'Traits'), {}),
    ])),
    (SimpleTerm('climate', 'climate', u'Climate'), OrderedDict([
        (SimpleTerm('current', 'current', u'Current'), {}),
        (SimpleTerm('future', 'future', u'Future'), {}),
    ])),
    (SimpleTerm('environmental', 'environmental', u'Environmental'), OrderedDict([
        (SimpleTerm('topography', 'topography', u'Topography'), {}),
        (SimpleTerm('hydrology', 'hydrology', u'Hydrology'), {}),
        (SimpleTerm('substrate', 'substrate', u'Substrate'), {}),
        (SimpleTerm('vegetation', 'vegetation', u'Vegetation'), {}),
        (SimpleTerm('landcover', 'landcover', u'Land Cover'), {}),
        (SimpleTerm('landuse', 'landuse', u'Land Use'), {}),
    ]))
]))


@provider(IVocabularyFactory)
def scientific_category_source(context):
    return scientific_category_vocabulary

summary_dataset_vocabulary = SimpleVocabulary([
    SimpleTerm("Summary datasets", "Summarydatasets", u'Summary datasets'),
])

@provider(IVocabularyFactory)
def summary_dataset_source(context):
    return summary_dataset_vocabulary

@provider(IVocabularyFactory)
def data_collections_source(context):
    portal_url = getToolByName(context, 'portal_url')
    catalog = getToolByName(context, 'portal_catalog')
    vocab = getUtility(IVocabularyFactory,
                       'scientific_category_source')(context)
    coll_query = {
        'portal_type': 'org.bccvl.content.collection',
        'path': '/'.join([portal_url.getPortalPath(), defaults.DATASETS_FOLDER_ID]),
    }

    def generate_collections():
        for term in vocab:
            coll_query['BCCCategory'] = term.value
            for brain in catalog.searchResults(**coll_query):
                yield brain
    return BrainsVocabulary.fromBrains(generate_collections(), context)
