from plone.directives import form
from plone.namedfile.field import NamedBlobFile
from plone.dexterity.content import Item
from zope.interface import implementer
from org.bccvl.site import MessageFactory as _


class IDataset(form.Schema):

    file = NamedBlobFile(
        title=_(u"File"),
        description=_(u"Data content"),
        required=True)


@implementer(IDataset)
class Dataset(Item):

    pass
