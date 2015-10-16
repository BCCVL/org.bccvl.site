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

from eea.facetednavigation.dexterity_support import normalize as atdx_normalize
from eea.facetednavigation.interfaces import IFacetedCatalog
from eea.facetednavigation.widgets import ViewPageTemplateFile
from eea.facetednavigation.widgets.widget import CountableWidget
from eea.facetednavigation import EEAMessageFactory as _

from zope.component import getMultiAdapter, queryUtility


EditSchema = Schema((
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
    widget_type = 'userselect'
    widget_label = _('User Select')
    view_js = '++resource++org.bccvl.site.faceted.userselect.view.js'
    edit_js = '++resource++org.bccvl.site.faceted.userselect.edit.js'
    view_css = '++resource++org.bccvl.site.faceted.userselect.view.css'

    index = ViewPageTemplateFile('widget.pt')
    edit_schema = CountableWidget.edit_schema.copy() + EditSchema

    def __init__(self, context, request, data=None):
        super(Widget, self).__init__(context, request, data)
        self.data.index = 'Creator'
        self.data.default = 'all'

    def vocabulary(self):
        return (('user', u'User'),
                ('admin', u'BCCVL'),
                ('shared', u'Shared'))

    def _get_query(self, value):
        portal_state = getMultiAdapter(
            (self.context, self.request), name="plone_portal_state")
        member = portal_state.member()
        if value == 'user':
            return {'Creator': member.getId()}
        elif value == 'admin':
            return {'Creator': 'BCCVL'}
        elif value == 'shared':
            pc = getToolByName(self.context, 'portal_catalog')
            vals = filter(lambda x: x not in ('BCCVL', member.getId()),
                          pc.uniqueValuesFor('Creator'))
            return {'Creator': vals}
        return {}

    def query(self, form):
        """ Get value from form and return a catalog dict query
        """
        index = self.data.get('index', '')
        index = index.encode('utf-8', 'replace')
        if not index:
            return {}
        value = form.get(self.data.getId(), 'all')
        return self._get_query(value)

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
            if not value:
                res[value] = len(brains)
                continue
            normalized_value = atdx_normalize(value)
            query = self._get_query(normalized_value)
            rset = ctool.apply_index(self.context, index, query[index_id])[0]
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
