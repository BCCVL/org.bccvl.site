
from Products.GenericSetup.interfaces import IBody
from Products.GenericSetup.context import SnapshotImportContext
from eea.facetednavigation.layout.interfaces import IFacetedLayout
from plone import api
from plone.dexterity.content import Container
from zope.component import queryMultiAdapter
from zope.interface import implementer

from org.bccvl.site.faceted.interfaces import IFacetConfig, IFacetConfigTool, IFacetConfigUtility


@implementer(IFacetConfigTool)
class FacetConfigTool(Container):

    meta_type = 'FacetConfigTool'

    def __init__(self, *args, **kw):
        self.portal_type = 'org.bccvl.tool.facetconfigtool'
        super(FacetConfigTool, self).__init__(*args, **kw)

    pass


@implementer(IFacetConfigUtility)
class FacetConfigUtility(object):

    @property
    def context(self):
        return api.portal.get_tool('portal_facetconfig')

    def types(self, proxy=True, **kwargs):
        kwargs.setdefault('portal_type', 'org.bccvl.tool.facetconfig')
        kwargs.setdefault('review_state', '')
        brains = self.context.getFolderContents(contentFilter=kwargs)
        for brain in brains:
            if not proxy:
                brain = brain.getObject()
            if brain:
                yield brain


@implementer(IFacetConfig)
class FacetConfig(Container):

    pass

########## Events

def facet_config_added(obj, evt):
    """
    Enable facet navigation on newly created FacetConfig object.
    """
    context = obj
    portal_type = getattr(context, 'portal_type', None)
    if portal_type != 'org.bccvl.tool.facetconfig':
        return

    # subtyper = queryMultiAdapter((context, context.REQUEST),
    #     name=u'faceted_search_subtyper', default=queryMultiAdapter(
    #         (context, context.REQUEST), name=u'faceted_subtyper'))
    subtyper = queryMultiAdapter((context, context.REQUEST),
        name=u'faceted_subtyper')

    if subtyper:
        subtyper.enable()
        IFacetedLayout(obj).update_layout('faceted-popup-items')

    # Add default widgets
    widgets = queryMultiAdapter((obj, obj.REQUEST),
                                name=obj.id + '.xml')

    if not widgets:
        return

    xml = widgets()
    environ = SnapshotImportContext(obj, 'utf-8')
    importer = queryMultiAdapter((obj, environ), IBody)
    if not importer:
        return
    importer.body = xml
