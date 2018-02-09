from eea.facetednavigation import EEAMessageFactory as _
from eea.facetednavigation.widgets.interfaces import ISchema, FacetedSchemata
from eea.facetednavigation.widgets.interfaces import DefaultSchemata as DS

from z3c.form import field
from zope import schema
from zope.schema.vocabulary import SimpleVocabulary, SimpleTerm


# Note: this is almost the same as in widgets.checkbox.interfaces
class IPathSelectSchema(ISchema):

    index = schema.Choice(
        title=_(u"Catalog index"),
        description=_(u'Catalog index to be used'),
        vocabulary=u"eea.faceted.vocabularies.CatalogIndexes",
        #required=True,
    )

    root = schema.TextLine(
        title=_(u'Root folder'),
        description=_(u'Navigation js-tree starting point '
                      u'(relative to plone site. ex: SITE/data-and-maps)'),
        required=False
    )
    root._type = (unicode, str)    

    vocabulary = schema.Choice(
        title=_(u"Vocabulary"),
        description=_(u'Vocabulary to use to render widget items'),
        vocabulary=u'eea.faceted.vocabularies.PortalVocabularies',
        required=False
    )

    sortreversed = schema.Bool(
        title=_(u"Reverse options"),
        description=_(u"Sort options reversed"),
        required=False
    )


class DefaultSchemata(DS):
    """ Schemata default
    """
    fields = field.Fields(IPathSelectSchema).select(
        u'title',
        u'default',
        u'index',
        u'root',
        #u'depth',        
        u'vocabulary'
    )

class DisplaySchemata(FacetedSchemata):
    """ Schemata display
    """
    label = u'display'
    fields = field.Fields(IPathSelectSchema).select(
        #u'maxitems',
        u'sortreversed',
)