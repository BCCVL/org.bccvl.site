from plone.directives import form
from zope import schema
from plone.dexterity.content import Container
from org.bccvl.site import vocabularies
from org.bccvl.site.browser import parameter
from zope.interface import implementer
from z3c.form.browser.checkbox import CheckBoxFieldWidget


class IExperiment(form.Schema):
    """Base Experiment Class"""



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
        )


class IProjectionExperiment(IExperiment):
    species_distribution_models = schema.Choice(
        title=u'Species Distribution Models',
        source=vocabularies.species_distributions_models_source,
        default=None,
        required=False,
    )

#    years = schema.Choice(
#        title=u'Projection Point: Years',
#        source=vocabularies.projection_years_source,
#        default=None,
#        required=False,
#    )
#    
    emission_scenarios = schema.Choice(
        title=u'Projection Point: Emission Scenarios',
        source=vocabularies.projection_emission_scenarios_source,
        default=None,
        required=False,
    )
    
    climate_models = schema.Choice(
        title=u'Projection Point: Climate Models',
        source=vocabularies.projection_climate_models_source,
        default=None,
        required=False,
    )
    
#

@implementer(ISDMExperiment)
class SDMExperiment(Container):
    pass

@implementer(IProjectionExperiment)
class ProjectionExperiment(Container):

    def projections(self):
        """compile points into list of datasets"""

