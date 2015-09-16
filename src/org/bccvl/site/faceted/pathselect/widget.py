""" Select widget
"""
from BTrees.IIBTree import weightedIntersection, IISet

from Products.Archetypes.public import Schema
from Products.Archetypes.public import BooleanField
from Products.Archetypes.public import StringField
from Products.Archetypes.public import StringWidget
from Products.Archetypes.public import SelectionWidget
from Products.Archetypes.public import BooleanWidget
from Products.CMFCore.utils import getToolByName
from Products.CMFPlone.utils import safeToInt

from eea.facetednavigation.interfaces import IFacetedCatalog
from eea.facetednavigation.widgets import ViewPageTemplateFile
from eea.facetednavigation.widgets.widget import CountableWidget
from eea.facetednavigation import EEAMessageFactory as _

from plone.app.uuid.utils import uuidToCatalogBrain
from zope.component import queryUtility



EditSchema = Schema((
    StringField('index',
        schemata="default",
        required=True,
        vocabulary_factory='eea.faceted.vocabularies.PathCatalogIndexes',
        widget=SelectionWidget(
            format='select',
            label=_(u'Catalog index'),
            description=_(u'Catalog index to use for search'),
            i18n_domain="eea"
        )
    ),
    StringField('root',
        schemata="default",
        widget=StringWidget(
            size=25,
            label=_(u'Root folder'),
            description=_(u'Full path to default container relative site root'
                          u'Will be used if All is selected.'),
            i18n_domain="eea"
        )
    ),
    StringField('vocabulary',
        schemata="default",
        vocabulary_factory='eea.faceted.vocabularies.PortalVocabularies',
        widget=SelectionWidget(
            label=_(u"Vocabulary"),
            description=_(u'Vocabulary to use to render widget items.'),
        )
    ),
    BooleanField('sortreversed',
        schemata="display",
        widget=BooleanWidget(
            label=_(u"Reverse options"),
            description=_(u"Sort options reversed"),
        )
    ),
))


class Widget(CountableWidget):
    """ Widget
    """
    # Widget properties
    widget_type = 'pathselect'
    widget_label = _('Path Select')
    view_js = '++resource++org.bccvl.site.faceted.pathselect.view.js'
    edit_js = '++resource++org.bccvl.site.faceted.pathselect.edit.js'
    view_css = '++resource++org.bccvl.site.faceted.pathselect.view.css'
    edit_css = '++resource++org.bccvl.site.faceted.pathselect.edit.css'

    index = ViewPageTemplateFile('widget.pt')
    edit_schema = CountableWidget.edit_schema.copy() + EditSchema

    # TODO: we could add index and field 'part_of' to associate datasets with collections (similar to related_items? maybe eea.relations would be an option?)

    def query(self, form):
        """ Get value from form and return a catalog dict query
        """
        query = {}
        index = self.data.get('index', '')
        index = index.encode('utf-8', 'replace')
        if not index:
            return query

        value = form.get(self.data.getId(), '')
        if value:
            value = uuidToCatalogBrain(value)
            if value:
                value = value.getPath()

        if not value:
            portal_url = getToolByName(self.context, 'portal_url')
            root = self.data.get('root', '')
            if root.startswith('/'):
                root = root[1:]
            value = '/'.join([portal_url.getPortalPath(), root])

        if not value:
            return query

        depth = safeToInt(self.data.get('depth', -1))
        query[index] = {"query": value, 'level': depth}

        return query

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
                    if isinstance(value, unicode):
                        res[value] = num
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
            sequence = [key for key, value in self.vocabulary()]

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
            item = uuidToCatalogBrain(value)
            if not item:
                res[value] = len(brains)
                continue
            rset = ctool.apply_index(self.context, index, item.getPath())[0]
            rset = IISet(rset)
            rset = weightedIntersection(brains, rset)[1]
            if isinstance(value, unicode):
                res[value] = len(rset)
            else:
                unicode_value = value.decode('utf-8')
                res[unicode_value] = len(rset)
        return res
