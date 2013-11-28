from plone.directives import form
from zope import schema
from plone.dexterity.content import Item
from zope.interface import implementer
from org.bccvl.site import MessageFactory as _


class IFunction(form.Schema):

#    compute_function = schema.TextLine(
#        title=_(u'Compute Function'),
#        description=_(u"Full dotted name of a python module implementing IComputeFunction"),
#        required=True)
    method = schema.TextLine(
        title=_(u'Method'),
        description=_(u"Full dotted name of a python function implementing this algorithm"),
        required=True)

    schema = schema.Text(
        title=_(u"Schema"),
        description=_(u"A dexterity schema describing the input parameters for the algorithm"),
        required=True)

# TODO: add validators:
#    e.g. restrict the set of available methods; maybe setuptools entry points from a vocabulary
#
#    other option:
#       let method provide specific interface ... register via name as utility
#       this way only system wide supplied code can be used
 
@implementer(IFunction)
class Function(Item):

    pass
