from plone.directives import form
from zope.schema import Choice, List, Dict, Bool, Int
from plone.dexterity.content import Container
from org.bccvl.site import vocabularies
from zope.interface import implementer
from z3c.form.browser.checkbox import CheckBoxFieldWidget
from Products.CMFCore.utils import getToolByName
from org.bccvl.site.interfaces import IExperiment
from plone.directives import form
from gu.z3cform.rdf.interfaces import IGraph
from ordf.namespace import DC as DCTERMS


class ISDMExperiment(IExperiment):
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
        description=u"Enable generation of random pseudo absence points across area defined inenvironmental data",
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

    # TODO: instead of form hints ... maybe set widgetfactory in form updateWidgets?
    #       form hint affects all forms ... using updateWidgets would require to customise every form where we wanta custom widget
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


@implementer(ISDMExperiment)
class SDMExperiment(Container):
    pass


@implementer(IProjectionExperiment)
class ProjectionExperiment(Container):

    functions = ('org.bccvl.compute.predict.execute', )

    def future_climate_datasets(self):
        # TODO: use QueryApi?
        return find_projections(self, self.emission_scenarios, self.climate_models, self.years)


# TODO: turn this into some adapter lookup component-> maybe use z3c.form validation adapter lookup?
def find_projections(ctx, emission_scenarios, climate_models, years):
        """compile points into list of datasets"""
        pc = getToolByName(ctx, 'portal_catalog')
        result = []
        brains = pc.searchResults(BCCEmissionScenario=emission_scenarios,
                                  BCCGlobalClimateModel=climate_models)
        for brain in brains:
            graph = IGraph(brain.getObject())
            # TODO: do better date matching
            year = graph.value(graph.identifier, DCTERMS['temporal'])
            if year in years:
                # TODO: yield?
                result.append(brain)
        return result
