from plone.directives import form
from plone.namedfile.field import NamedBlobFile
from plone.dexterity.content import Item
from zope.interface import implementer
from org.bccvl.site import MessageFactory as _


class IDataset(form.Schema):

    # TODO: a primary field should not be required. possible bug in plone core
    form.primary('file')
    file = NamedBlobFile(
        title=_(u"File"),
        description=_(u"Data content"),
        required=True)


@implementer(IDataset)
class Dataset(Item):

    pass
