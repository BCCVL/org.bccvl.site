from plone.directives import form
from zope import schema
from plone.dexterity.content import Container
from org.bccvl.site import vocabularies
from zope.interface import implementer
from z3c.form.browser.checkbox import CheckBoxFieldWidget
from Products.CMFCore.utils import getToolByName
from org.bccvl.site.interfaces import IExperiment

class ISDMExperiment(IExperiment):
    form.widget(functions=CheckBoxFieldWidget)
    functions = schema.List(
        title=u'Algorithm',
        value_type=schema.Choice(
            source=vocabularies.functions_source
        ),
        default=None,
        required=True,
    )

    species_occurrence_dataset = schema.Choice(
        title=u'Species Occurrence Datasets',
        source=vocabularies.species_presence_datasets_source,
        default=None,
        required=False,
    )

    species_absence_dataset = schema.Choice(
        title=u'Species Absence Datasets',
        source=vocabularies.species_absence_datasets_source,
        default=None,
        required=False,
    )

    environmental_layers = schema.Dict(
        title=u'Environmental Layers',
        key_type=schema.Choice(source=vocabularies.envirolayer_source),
        value_type=schema.Choice(source=vocabularies.environmental_datasets_source),
        required=False,
        )


class IProjectionExperiment(IExperiment):

    species_distribution_models = schema.Choice(
        title=u'Species Distribution Models',
        source=vocabularies.species_distributions_models_source,
        default=None,
        required=True,
    )

    years = schema.List(
        title=u'Projection Point: Years',
        value_type=schema.Choice(
            source=vocabularies.fc_years_source),
        default=None,
        required=True,
    )

    emission_scenarios = schema.List(
        title=u'Projection Point: Emission Scenarios',
        value_type=schema.Choice(
            source=vocabularies.emission_scenarios_source),
        default=None,
        required=True,
    )

    climate_models = schema.List(
        title=u'Projection Point: Climate Models',
        value_type=schema.Choice(
            source=vocabularies.global_climate_models_source),
        default=None,
        required=True,
    )

#


@implementer(ISDMExperiment)
class SDMExperiment(Container):
    pass


@implementer(IProjectionExperiment)
class ProjectionExperiment(Container):

    functions = ('org.bccvl.compute.predict.execute', )

    def projections(self):
        """compile points into list of datasets"""

    def future_climate_datasets(self):
        # TODO: use QueryApi?
        # TODO: ignore years for now
        pc = getToolByName(self, 'portal_catalog')
        brains = pc.searchResults(BCCEmissionsScenario=self.emission_scenarios,
                                  BCCGlobalClimateModel=self.climate_models)
        return [b.UID for b in brains]
