from eea.facetednavigation import EEAMessageFactory as _
from eea.facetednavigation.widgets.interfaces import ISchema, FacetedSchemata
from eea.facetednavigation.widgets.interfaces import DefaultSchemata as DS

from z3c.form import field
from zope import schema
from zope.schema.vocabulary import SimpleVocabulary, SimpleTerm


# Note: this is almost the same as in widgets.checkbox.interfaces
class IUserSelectSchema(ISchema):
    
    sortreversed = schema.Bool(
        title=_(u"Reverse options"),
        description=_(u"Sort options reversed"),
        required=False
    )    


class DefaultSchemata(DS):
    """ Schemata default
    """
    fields = field.Fields(IUserSelectSchema).select(
        u'title',
        u'index',
        #u'operator',
        #u'operator_visible',
        #u'vocabulary',
        #u'catalog',
        u'default'
    )


class DisplaySchemata(FacetedSchemata):
    """ Schemata display
    """
    label = u'display'
    fields = field.Fields(IUserSelectSchema).select(
        u'sortreversed',
)