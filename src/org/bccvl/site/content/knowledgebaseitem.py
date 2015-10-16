from plone.app.textfield import RichText
from plone.supermodel import model
from zope import schema
from plone.dexterity.content import Item
from zope.interface import implementer


class IKnowledgebaseItem(model.Schema):
    """Knowledge base item"""

    type = schema.Choice(
        title=u'Knowledgebase type',
        description=u'Knowledgebase entry related to type of field',
        required=True,
        default='Functional Response',
        values=('Functional Response', 'Climate Model', 'Species Distribution', 'Article'))

    related_information = RichText(
        title=u'Related information',
        default_mime_type='text/html',
        required=False)


@implementer(IKnowledgebaseItem)
class KnowledgebaseItem(Item):

    pass
