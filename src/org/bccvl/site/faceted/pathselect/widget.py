""" Select widget
"""
from Products.Archetypes.public import Schema
from Products.Archetypes.public import BooleanField
from Products.Archetypes.public import StringField
from Products.Archetypes.public import StringWidget
from Products.Archetypes.public import SelectionWidget
from Products.Archetypes.public import BooleanWidget
from Products.CMFCore.utils import getToolByName
from Products.CMFPlone.utils import safeToInt

from eea.facetednavigation.widgets import ViewPageTemplateFile
from eea.facetednavigation.widgets.widget import Widget as BaseWidget
from eea.facetednavigation import EEAMessageFactory as _

from plone.app.uuid.utils import uuidToCatalogBrain


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


class Widget(BaseWidget):
    """ Widget
    """
    # Widget properties
    widget_type = 'pathselect'
    widget_label = _('Path Select')
    view_js = '++resource++org.bccvl.site.faceted.pathselect.view.js'
    edit_js = '++resource++org.bccvl.site.faceted.pathselect.edit.js'
    view_css = '++resource++org.bccvl.site.faceted.pathselect.view.css'

    index = ViewPageTemplateFile('widget.pt')
    edit_schema = BaseWidget.edit_schema.copy() + EditSchema

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
