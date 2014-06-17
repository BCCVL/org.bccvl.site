from plone.dexterity.content import Item
from zope.interface import implementer
from plone.app.contenttypes.interfaces import ILink
from org.bccvl.site.content.interfaces import IRemoteDataset


@implementer(IRemoteDataset, ILink)
class RemoteDataset(Item):

    pass
