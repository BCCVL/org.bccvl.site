from zope import schema
from dexterity.membrane.content.member import IMember
#from plone.dexterity.content import Item

class IBCCVLUser(IMember):

    username = schema.TextLine(
        # String with validation in place looking for @, required.
        # Note that a person's email address will be their username.
        #title=_(u"E-mail Address"),
        title=u"Username",
        required=True,
        )


#class Bccvluser(Item):
