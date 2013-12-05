from plone.directives import form
from zope import schema
from plone.dexterity.content import Container
from org.bccvl.site import vocabularies
from org.bccvl.site.browser import parameter
from zope.interface import implementer
from z3c.form.browser.checkbox import CheckBoxFieldWidget


class IExperiment(form.Schema):
    """Base Experiment Class"""

#    experiment_type = schema.Choice(
#        title=u'Experiment Type',
#        vocabulary=vocabularies.experiments_vocabulary,
#        default=None,
#    )

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


@implementer(IExperiment)
class Experiment(Container):
    pass
