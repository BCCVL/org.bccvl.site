from zope.interface import Interface
from plone.app.textfield import RichText as RichTextField
from plone.autoform import directives
from plone.namedfile.field import NamedBlobFile
from plone.supermodel import model
from zope.schema import Choice, List, Dict, Bool, Int, TextLine, Text, Set, URI
from z3c.form.browser.radio import RadioFieldWidget
from org.bccvl.site import MessageFactory as _
# next import may cause circular import problems
# FIXME: remove form hints here and put them into special form schemata?
from org.bccvl.site.widgets.widgets import FunctionsFieldWidget
from org.bccvl.site.widgets.widgets import DatasetFieldWidget
from org.bccvl.site.widgets.widgets import DatasetDictFieldWidget
from org.bccvl.site.widgets.widgets import ExperimentSDMFieldWidget
from org.bccvl.site.widgets.widgets import ExperimentResultFieldWidget
from org.bccvl.site.widgets.widgets import FutureDatasetsFieldWidget
from org.bccvl.site.widgets.widgets import ExperimentResultProjectionFieldWidget


class IDataset(model.Schema):
    """Interface all datasets inherit from"""

    # TODO: need behavior to add metadata details?


class IBlobDataset(IDataset):

    # TODO: a primary field should not be required. possible bug in plone core
    model.primary('file')
    file = NamedBlobFile(
        title=_(u"File"),
        description=_(u"Data content"),
        required=True
    )


class IRemoteDataset(IDataset):
    """A dateset hosted externally"""

    remoteUrl = TextLine(
        title=_(u'Content location'),
        description=u'',
        required=True,
        default=u'http://',
    )


class IExperiment(Interface):
    """Base Experiment Class"""


class ISDMExperiment(IExperiment):

    directives.widget('functions', FunctionsFieldWidget)
    functions = List(
        title=u'Algorithm',
        value_type=Choice(vocabulary='sdm_functions_source'),
        default=None,
        required=True,
    )

    directives.widget('species_occurrence_dataset',
                DatasetFieldWidget,
                genre=['DataGenreSpeciesOccurrence'],
                errmsg=u"Please select at least 1 occurrence dataset.",
                vizclass=u'bccvl-occurrence-viz')
    species_occurrence_dataset = TextLine(
        title=u'Species Occurrence Datasets',
        default=None,
        required=True,
    )

    directives.widget('species_absence_dataset',
                DatasetFieldWidget,
                genre=['DataGenreSpeciesAbsence'],
                errmsg=u"Please select at least 1 emmission scenario.",
                vizclass=u'bccvl-absence-viz')
    species_absence_dataset = TextLine(
        title=u'Species Absence Datasets',
        default=None,
        required=False,
    )

    species_pseudo_absence_points = Bool(
        title=u"Use pseudo absence points instead of dataset.",
        description=u"Enable generation of random pseudo absence "
                    u"points across area defined in environmental data",
        default=False,
        required=False)

    species_number_pseudo_absence_points = Int(
        title=u"Number of points",
        description=u"The number of random pseudo absence points to generate",
        default=10000,
        required=False)

    directives.widget('environmental_datasets',
                DatasetDictFieldWidget,
                multiple='multiple',
                genre=['DataGenreCC', 'DataGenreE'],
                filters=['text', 'source', 'layer', 'resolution'],
                errmsg=u"Please select at least 1 layer.")
    environmental_datasets = Dict(
        title=u'Climate & Environmental Datasets',
        key_type=TextLine(),
        value_type=Set(value_type=TextLine()),
        required=True,
    )


class IProjectionExperiment(IExperiment):

    # TODO: ignore context here? don't really need to store this?
    directives.widget('species_distribution_models',
                ExperimentSDMFieldWidget,
                experiment_type=[ISDMExperiment.__identifier__],
                errmsg=u"Please select at least 1 Species Distribution Model")
    species_distribution_models = Dict(
        title=u'Species Distribution Models',
        key_type=TextLine(),
        value_type=List(value_type=TextLine(), required=True),
        default=None,
        required=True,
    )

    directives.widget('future_climate_datasets',
                FutureDatasetsFieldWidget,
                genre=['DataGenreFC'],
                errmsg=u"Please select at least 1 future climate dataset.",
                vizclass=u'bccvl-absence-viz')
    future_climate_datasets = List(
        title=u'Future Climate Data',
        value_type=TextLine(),
        default=None,
        required=True
    )


class IBiodiverseExperiment(IExperiment):

    # - Opt1 ... select experiments and pick datasets from experiment (like experimend sdm model select)
    # - Opt2 ... I think it's better to select datasets and show them grouped by grouping criteria for biodiverse. May make searching easier as well?
    # - Opt3 ... set criteria for grouping on page, and make search interface for specise only...
    #            restricts to single biodiverse experiment?.
    # - Opt4 ... make different interfaces .... optimised for different interests

    # Key is the dataset uuid and value a threstold to apply
    directives.widget('projection',
                ExperimentResultProjectionFieldWidget,
                experiment_type=[ISDMExperiment.__identifier__,
                                 IProjectionExperiment.__identifier__],
                errmsg=u"Please select at least 1 dataset.")
    projection = Dict(
        title=u'Projection Datasets',
        key_type=TextLine(),
        value_type=Dict(
            key_type=TextLine(),
            value_type=Dict()
        ),
        required=True,
    )

    cluster_size = Choice(
        title=u'Biodiverse cell size',
        description=u'x/y cell size in meter',
        default=5000,
        required=True,
        values=(5000, 10000, 20000, 50000),
    )

    # ->  interface,  content class? , profile,  add / edit / display / result view
    # ->  perl script ... exec env
    # =>  species metadata filenaming


class ISpeciesTraitsExperiment(IExperiment):

    directives.widget(algorithm=RadioFieldWidget)
    algorithm = Choice(
        title=u'Algorithm',
        vocabulary='traits_functions_source',
        required=True,
        default=None,
    )

    formula = Text(
        title=u'Formula',
        description=u'Please see <a href="http://stat.ethz.ch/R-manual/R-devel/library/stats/html/lm.htm">R:Fitting Linear Models</a> for details.',
        required=True,
        default=None,
    )

    directives.widget('data_table',
        DatasetFieldWidget,
        genre=['DataGenreTraits'],
        errmsg=u"Please select 1 species traits dataset.",
        vizclass=u'bccvl-auto-viz')
    data_table = TextLine(
        title=u'Species Traits Datasets',
        default=None,
        required=True,
    )


# TODO: use interfaces or portal_type?
from zope.schema.vocabulary import SimpleVocabulary, SimpleTerm
EXPERIMENT_TYPE_VOCAB = SimpleVocabulary(
    (SimpleTerm(ISDMExperiment.__identifier__, ISDMExperiment.__identifier__, u'SDM Experiment'),
     SimpleTerm(IProjectionExperiment.__identifier__, IProjectionExperiment.__identifier__, u'Climate Change Experiment'),
     SimpleTerm(IBiodiverseExperiment.__identifier__, IBiodiverseExperiment.__identifier__,  u'Biodiverse Experiment'))
)


class IEnsembleExperiment(IExperiment):

    experiment_type = Choice(
        title=u"Select Experiment Type",
        vocabulary = EXPERIMENT_TYPE_VOCAB,
        default=ISDMExperiment.__identifier__,
        required=True
    )

    directives.widget('datasets',
                ExperimentResultFieldWidget,
                errmsg=u"Please select at least 1 Experiment Result")
    datasets = Dict(
        title=u'Result Datasets',
        key_type=TextLine(),
        value_type=List(value_type=TextLine(), required=True),
        default=None,
        required=True
    )
