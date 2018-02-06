from eea.facetednavigation import EEAMessageFactory as _
from eea.facetednavigation.widgets.interfaces import ISchema, FacetedSchemata
from eea.facetednavigation.widgets.interfaces import DefaultSchemata as DS

from z3c.form import field
from zope import schema
from zope.schema.vocabulary import SimpleVocabulary, SimpleTerm


# Note: this is almost the same as in widgets.checkbox.interfaces
class ICheckboxTreeSchema(ISchema):
    
    # index = schema.Choice(
    #     title=_(u"Catalog index"),
    #     description=_(u'Catalog index to be used'),
    #     vocabulary=u"eea.faceted.vocabularies.CatalogIndexes",
    #     #required=True,
    # )
    
    default = schema.List(
        title=_(u'Default value'),
        description=_(u'Default items (one per line)'),
        required=False,
        unique=True,
        value_type=schema.TextLine(title=u'Item'),
    )
    
    operator = schema.Choice(
        title=_(u'Default operator'),
        description=_(u'Search with AND/OR between elements'),
        vocabulary=SimpleVocabulary([
            SimpleTerm(u'or', u'or', u'OR'),
            SimpleTerm(u'and', u'and', u'AND')
        ]),
        default=u'or',
        # required=True
    )
    
    operator_visible = schema.Bool(
        title=_(u"Operator visible"),
        description=_(u"Let the end-user choose to search with "
                      u"AND or OR between elements"),
        required=False,
        default=False
    )    

    vocabulary = schema.Choice(
        title=_(u"Vocabulary"),
        description=_(u'Vocabulary to use to render widget items'),
        # FIXME: provide vocab that returns only ITreeVocabularies
        vocabulary=u'eea.faceted.vocabularies.PortalVocabularies',
        required=False
    )

    # catalog = schema.Choice(
    #     title=_(u'Catalog'),
    #     description=_(u"Get unique values from catalog "
    #                   u"as an alternative for vocabulary"),
    #     vocabulary=u'eea.faceted.vocabularies.UseCatalog',
    #     required=False
    # )
    
    maxitems = schema.Int(
        title=_(u"Maximum items"),
        description=_(u'Number of items visible in widget'),
        default=0,
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
    fields = field.Fields(ICheckboxTreeSchema).select(
        u'title',
        u'index',
        u'operator',
        u'operator_visible',
        u'vocabulary',
        #u'catalog',
        u'default'
    )

class DisplaySchemata(FacetedSchemata):
    """ Schemata display
    """
    label = u'display'
    fields = field.Fields(ICheckboxTreeSchema).select(
        u'maxitems',
        u'sortreversed',
)