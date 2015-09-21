from plone.supermodel import model
from zope.schema import TextLine,  Choice, Text, DottedName
from plone.dexterity.content import Item
from zope.interface import implementer
from org.bccvl.site import MessageFactory as _


class IFunction(model.Schema):

    experiment_type = Choice(
        title=_(u"Experiment Type"),
        description =_(u"The experiment type this toolkit can be used for."),
        required=False,
        vocabulary='experiment_type_source'
        )

    interpreter = Choice(
        title=_(u"Programming language"),
        description=_(u"The language the code is written in."),
        vocabulary="org.bccvl.site.programming_language_vocab",
        required=True,
        )

    script = Text(
        title=_(u"Script"),
        description=_(u"The code being executed"),
        required=True,
        )

    schema = Text(
        title=_(u"Schema"),
        description=_(u"A dexterity schema describing the input parameters for the algorithm"),
        required=True
        )

    output = Text(
        title=_(u"Output mapping"),
        description=_(u"defines how to import experiment outputs"),
        required=True
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
