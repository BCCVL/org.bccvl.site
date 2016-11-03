from plone.supermodel import model
from plone.autoform import directives
from zope.schema import TextLine,  Choice, Text, DottedName
from plone.dexterity.content import Item
from zope.interface import implementer
from org.bccvl.site import MessageFactory as _


class IFunction(model.Schema):

    experiment_type = Choice(
        title=_(u"Experiment Type"),
        description=_(u"The experiment type this toolkit can be used for."),
        required=False,
        default=None,
        vocabulary='experiment_type_source'
    )

    interpreter = Choice(
        title=_(u"Programming language"),
        description=_(u"The language the code is written in."),
        vocabulary="org.bccvl.site.programming_language_vocab",
        required=True,
    )

    directives.widget('script',
                      rows=40)
    script = Text(
        title=_(u"Script"),
        description=_(u"The code being executed"),
        required=True,
    )

    directives.widget('schema',
                      rows=40)
    schema = Text(
        title=_(u"Schema"),
        description=_(
            u"A dexterity schema describing the input parameters for the algorithm"),
        required=True
    )

    directives.widget('output',
                      rows=40)
    output = Text(
        title=_(u"Output mapping"),
        description=_(u"defines how to import experiment outputs"),
        required=True
    )

    algorithm_category = Choice(
        title=_(u"Algorithm Category"),
        description=_(u"The category an algorithm belongs to"),
        vocabulary="org.bccvl.site.algorithm_category_vocab",
        required=False,
    )

# TODO: add validators:
#    e.g. restrict the set of available methods; maybe setuptools
#    entry points from a vocabulary
#
#    other option:
#       let method provide specific interface ... register via name as utility
#       this way only system wide supplied code can be used


@implementer(IFunction)
class Function(Item):

    pass
