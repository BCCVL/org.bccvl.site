from zope.interface import Interface
from plone.directives import form
from plone.namedfile.field import NamedBlobFile
from zope.schema import Choice, List, Dict, Bool, Int, Decimal
from org.bccvl.site import vocabularies
from z3c.form.browser.checkbox import CheckBoxFieldWidget
from org.bccvl.site import MessageFactory as _


class IDataset(form.Schema):

    # TODO: a primary field should not be required. possible bug in plone core
    form.primary('file')
    file = NamedBlobFile(
        title=_(u"File"),
        description=_(u"Data content"),
        required=True)

        # fixed fields
        # RDFURIChoiceField(
        #     __name__='format',
        #     prop=BCCPROP['format'],
        #     required=False,
        #     title=u'Format',
        #     vocabulary=u'http://namespaces.zope.org/z3c/form#DataSetFormatVocabulary')


        # layer
        # RDFURIChoiceField(
        #     __name__='datatype',
        #     prop=BCCPROP['datatype'],
        #     required=False,
        #     title=u'Type of Dataset',
        #     vocabulary=u'http://namespaces.zope.org/z3c/form#DataSetTypeVocabulary'),
        # # not needed?
        # RDFLiteralLineField(
        #     __name__='formato',
        #     prop=DCTERMS['format'],
        #     required=False,
        #     title=u'Data format (other)'),


class IExperiment(Interface):
    """Base Experiment Class"""


class ISDMExperiment(IExperiment):

    resolution = Choice(
        title=u'Spatial scale',
        default=None,
        vocabulary='org.bccvl.site.ResolutionVocabulary',
        required=True,
        )

    form.widget(functions=CheckBoxFieldWidget)
    functions = List(
        title=u'Algorithm',
        value_type=Choice(source=vocabularies.functions_source),
        default=None,
        required=True,
    )

    species_occurrence_dataset = Choice(
        title=u'Species Occurrence Datasets',
        source=vocabularies.species_presence_datasets_source,
        default=None,
        required=False,
    )

    species_absence_dataset = Choice(
        title=u'Species Absence Datasets',
        source=vocabularies.species_absence_datasets_source,
        default=None,
        required=False,
    )

    species_pseudo_absence_points = Bool(
        title=u"Pseudo absence points",
        description=u"Enable generation of random pseudo absence "
                    u"points across area defined inenvironmental data",
        default=False,
        required=False)

    species_number_pseudo_absence_points = Int(
        title=u"Number of pseudo absence points",
        description=u"The number of random pseudo absence points to generate",
        default=10000,
        required=False)

    # TODO: need a better field here to support dynamic vocabularies for
    #       values based on selected key
    #       -> needs specialised widget as well
    form.widget(environmental_datasets='org.bccvl.site.browser.widgets.DatasetsFieldWidget')
    environmental_datasets = Dict(
        title=u'Environmental Datasets',
        key_type=Choice(source=vocabularies.environmental_datasets_source),
        value_type=List(Choice(source=vocabularies.envirolayer_source),
                        unique=False),
        required=True,
        )


class IProjectionExperiment(IExperiment):

    form.widget(species_distribution_models=
                'org.bccvl.site.browser.widgets.DatasetsRadioFieldWidget')
    species_distribution_models = Choice(
        title=u'Species Distribution Models',
        source=vocabularies.species_distributions_models_source,
        default=None,
        required=True,
    )

    # TODO: instead of form hints ... maybe set widgetfactory in form
    #       updateWidgets?  form hint affects all forms ... using
    #       updateWidgets would require to customise every form where
    #       we wanta custom widget
    form.widget(years=
                'org.bccvl.site.browser.widgets.SequenceCheckboxFieldWidget')
    years = List(
        title=u'Projection Point: Years',
        value_type=Choice(source=vocabularies.fc_years_source),
        default=None,
        required=True,
    )

    form.widget(emission_scenarios=
                'org.bccvl.site.browser.widgets.SequenceCheckboxFieldWidget')
    emission_scenarios = List(
        title=u'Projection Point: Emission Scenarios',
        value_type=Choice(source=vocabularies.emission_scenarios_source),
        default=None,
        required=True,
    )

    form.widget(climate_models=
                'org.bccvl.site.browser.widgets.SequenceCheckboxFieldWidget')
    climate_models = List(
        title=u'Projection Point: Climate Models',
        value_type=Choice(source=vocabularies.global_climate_models_source),
        default=None,
        required=True,
    )


class IBiodiverseExperiment(IExperiment):

    # options: use dicts or other things here
    #          number of items in both lists must match
    form.widget(datasets='org.bccvl.site.browser.widgets.SequenceCheckboxFieldWidget')
    datasets = List(
        title=u'Species layer',
        value_type=Choice(source=vocabularies.species_projection_datasets_source),
        default=None,
        required=True,
        )

    thresholds = List(
        title=u'Threshold values',
        value_type=Decimal(),
        default=None,
        required=True,
        )

    # ->  interface,  content class? , profile,  add / edit / display / result view
    # ->  perl script ... exec env
    # =>  species metadata filenaming
