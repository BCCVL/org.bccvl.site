from plone.directives import form
from zope import schema
from plone.dexterity.content import Container
from org.bccvl.site import vocabularies
from zope.interface import implementer


class IExperiment(form.Schema):
    """Base Experiment Class"""

#    experiment_type = schema.Choice(
#        title=u'Experiment Type',
#        vocabulary=vocabularies.experiments_vocabulary,
#        default=None,
#    )

    functions = schema.Choice(
        title=u'Algorithm',
        source=vocabularies.functions_source,
        default=None,
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

    environmental_dataset = schema.Choice(
        title=u'Environmental Datasets',
        source=vocabularies.environmental_datasets_source,
        default=None,
        required=False,
    )

    climate_dataset = schema.Choice(
        title=u'Climate Datasets',
        source=vocabularies.future_climate_datasets_source,
        default=None,
        required=False,
    )

# TODO: validate input choices against function selected

@implementer(IExperiment)
class Experiment(Container):
    pass
