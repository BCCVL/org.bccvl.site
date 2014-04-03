from plone.directives import form
from zope.schema import TextLine,  Choice, Text, DottedName
from plone.dexterity.content import Item
from zope.interface import implementer
from org.bccvl.site import MessageFactory as _


class IFunction(form.Schema):

    method = TextLine(
        title=_(u'Method'),
        description=_(u"Full dotted name of a python function implementing this algorithm"),
        required=True)

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

    interface = DottedName(
        title=_(u'Interface'),
        description=_(u"full package name to interface"),
        required=True
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
