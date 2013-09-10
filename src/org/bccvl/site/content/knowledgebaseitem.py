from plone.directives import form
from plone.app.textfield import RichTextField
from zope import schema
from plone.dexterity.content import Item
from org.bccvl.site import vocabularies
from zope.interface import implementer


class IKnowledgebaseItem(form.Schema):
    """Knowledge base item"""

    type = schema.Choice(
        title=u'Knowledgebase type',
        description=u'Knowledgebase entry related to type of field',
        required=True,
        default='Functional Response',
        values=('Functional Response', 'Climate Model', 'Species Distribution', 'Article'))

    related_information = RichTextField(
        title=u'Related information',
        input_format='text/html',
        required=False)


@implementer(IKnowledgebaseItem)
class KnowledgebaseItem(Item)

    pass
