""" Checkbox tree widget

Limitations: supports two levels only
             works with ITreeVocabulary (nothing else)
             sort by count is broken. (needs to be done per tree level?)
"""
from plone.i18n.normalizer import urlnormalizer as normalizer

from zope.schema.interfaces import IVocabularyFactory
from zope.component import queryUtility

from BTrees.IIBTree import weightedIntersection, IISet
from Products.Archetypes.public import Schema
from Products.Archetypes.public import IntegerField
from Products.Archetypes.public import LinesField
from Products.Archetypes.public import BooleanField
from Products.Archetypes.public import StringField
from Products.Archetypes.public import IntegerWidget
from Products.Archetypes.public import LinesWidget
from Products.Archetypes.public import SelectionWidget
from Products.Archetypes.public import BooleanWidget
from Products.Archetypes.utils import DisplayList
from Products.CMFCore.utils import getToolByName

from eea.facetednavigation.dexterity_support import normalize as atdx_normalize
from eea.facetednavigation.interfaces import IFacetedCatalog
from eea.facetednavigation.widgets import ViewPageTemplateFile
from eea.faceted.vocabularies.utils import compare
from eea.facetednavigation.widgets.widget import CountableWidget
from eea.facetednavigation import EEAMessageFactory as _


EditSchema = Schema((
    StringField('index',
        schemata="default",
        required=True,
        vocabulary_factory='eea.faceted.vocabularies.CatalogIndexes',
        widget=SelectionWidget(
            label=_(u'Catalog index'),
            description=_(u'Catalog index to use for search'),
            i18n_domain="eea"
        )
    ),
    StringField('operator',
        schemata='default',
        required=True,
        vocabulary=DisplayList([('or', 'OR'), ('and', 'AND')]),
        default='or',
        widget=SelectionWidget(
            format='select',
            label=_(u'Default operator'),
            description=_(u'Search with AND/OR between elements'),
            i18n_domain="eea"
        )
    ),
    BooleanField('operator_visible',
        schemata='default',
        required=False,
        default=False,
        widget=BooleanWidget(
            label=_(u"Operator visible"),
            description=_(u"Let the end-user choose to search with "
                          "AND or OR between elements"),
        )
    ),
    StringField('vocabulary',
        schemata="default",
        # FIXME: provide vocab that returns only ITreeVocabularies
        vocabulary_factory='eea.faceted.vocabularies.PortalVocabularies',
        widget=SelectionWidget(
            label=_(u"Vocabulary"),
            description=_(u'Vocabulary to use to render widget items'),
        )
    ),
    # StringField('catalog',
    #     schemata="default",
    #     vocabulary_factory='eea.faceted.vocabularies.UseCatalog',
    #     widget=SelectionWidget(
    #         format='select',
    #         label=_(u'Catalog'),
    #         description=_(u"Get unique values from catalog "
    #                     u"as an alternative for vocabulary"),
    #     )
    # ),
    IntegerField('maxitems',
        schemata="display",
        default=0,
        widget=IntegerWidget(
            label=_(u"Maximum items"),
            description=_(u'Number of items visible in widget'),
        )
    ),
    BooleanField('sortreversed',
        schemata="display",
        widget=BooleanWidget(
            label=_(u"Reverse options"),
            description=_(u"Sort options reversed"),
        )
    ),
    LinesField('default',
        schemata="default",
        widget=LinesWidget(
            label=_(u'Default value'),
            description=_(u'Default items (one per line)'),
            i18n_domain="eea"
        )
    ),
))

class Widget(CountableWidget):
    """ Widget
    """
    # Widget properties
    widget_type = 'checkboxtree'
    widget_label = _('Checkboxes Tree')
    view_js = '++resource++org.bccvl.site.faceted.checkboxtree.view.js'
    edit_js = '++resource++org.bccvl.site.faceted.checkboxtree.edit.js'
    view_css = '++resource++org.bccvl.site.faceted.checkboxtree.view.css'
    edit_css = '++resource++org.bccvl.site.faceted.checkboxtree.edit.css'

    index = ViewPageTemplateFile('widget.pt')
    edit_schema = CountableWidget.edit_schema.copy() + EditSchema

    @property
    def css_class(self):
        """ Widget specific css class
        """
        css_type = self.widget_type
        css_title = normalizer.normalize(self.data.title)
        return ('faceted-checkboxtree-widget '
                'faceted-{0}-widget section-{1}').format(css_type, css_title)

    @property
    def default(self):
        """ Get default values
        """
        default = super(Widget, self).default
        if not default:
            return []

        if isinstance(default, (str, unicode)):
            default = [default, ]
        return default

    def selected(self, key):
        """ Return True if key in self.default
        """
        default = self.default
        if not default:
            return False
        for item in default:
            if compare(key, item) == 0:
                return True
        return False

    @property
    def operator_visible(self):
        """ Is operator visible for anonymous users
        """
        return self.data.get('operator_visible', False)

    @property
    def operator(self):
        """ Get the default query operator
        """
        return self.data.get('operator', 'and')

    def query(self, form):
        """ Get value from form and return a catalog dict query
        """
        query = {}
        index = self.data.get('index', '')
        index = index.encode('utf-8', 'replace')

        if not self.operator_visible:
            operator = self.operator
        else:
            operator = form.get(self.data.getId() + '-operator', self.operator)

        operator = operator.encode('utf-8', 'replace')

        if not index:
            return query

        if self.hidden:
            value = self.default
        else:
            value = form.get(self.data.getId(), '')

        value = atdx_normalize(value)

        if not value:
            return query

        catalog = getToolByName(self.context, 'portal_catalog')
        if index in catalog.Indexes:
            if catalog.Indexes[index].meta_type == 'BooleanIndex':
                if value == 'False':
                    value = False
                elif value == 'True':
                    value = True

        query[index] = {'query': value, 'operator': operator}
        return query

    def vocabulary(self, **kwargs):
        voc_id = self.data.get('vocabulary', None)
        if not voc_id:
            return []
        voc = queryUtility(IVocabularyFactory, voc_id, None)
        if not voc:
            return []
        return voc(self.context)

    def count(self, brains, sequence=None):
        """ Intersect results
        """
        res = {}
        # by checking for facet_counts we assume this is a SolrResponse
        # from collective.solr
        if hasattr(brains, 'facet_counts'):
            facet_fields = brains.facet_counts.get('facet_fields')
            if facet_fields:
                index_id = self.data.get('index')
                facet_field = facet_fields.get(index_id, {})
                for value, num in facet_field.items():
                    normalized_value = atdx_normalize(value)
                    if isinstance(value, unicode):
                        res[value] = num
                    elif isinstance(normalized_value, unicode):
                        res[normalized_value] = num
                    else:
                        unicode_value = value.decode('utf-8')
                    res[unicode_value] = num
            else:
                # no facet counts were returned. we exit anyway because
                # zcatalog methods throw an error on solr responses
                return res
            res[""] = res['all'] = len(brains)
            return res
        else:
            # this is handled by the zcatalog. see below
            pass

        if not sequence:
            vocab = self.vocabulary()
            sequence = [key.value for key in vocab] + [subkey.value for key in vocab for subkey in vocab.get(key,())]

        if not sequence:
            return res

        index_id = self.data.get('index')
        if not index_id:
            return res

        ctool = getToolByName(self.context, 'portal_catalog')
        index = ctool._catalog.getIndex(index_id)
        ctool = queryUtility(IFacetedCatalog)
        if not ctool:
            return res

        brains = IISet(brain.getRID() for brain in brains)
        res[""] = res['all'] = len(brains)
        for value in sequence:
            if not value:
                res[value] = len(brains)
                continue
            normalized_value = atdx_normalize(value)
            rset = ctool.apply_index(self.context, index, normalized_value)[0]
            rset = IISet(rset)
            rset = weightedIntersection(brains, rset)[1]
            if isinstance(value, unicode):
                res[value] = len(rset)
            elif isinstance(normalized_value, unicode):
                res[normalized_value] = len(rset)
            else:
                unicode_value = value.decode('utf-8')
                res[unicode_value] = len(rset)
        return res
