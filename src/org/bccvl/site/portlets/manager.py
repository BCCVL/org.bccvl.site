from zope.interface import Interface
from zope.publisher.interfaces.browser import IBrowserView
from zope.publisher.interfaces.browser import IDefaultBrowserLayer
from zope.component import adapter, getMultiAdapter
from zope.security import checkPermission
from Acquisition import aq_inner
from plone.app.portlets.manager import PortletManagerRenderer
from Products.Five.browser.pagetemplatefile import ViewPageTemplateFile
from .interfaces import INewsPortletManager


@adapter(Interface, IDefaultBrowserLayer, IBrowserView, INewsPortletManager)
class BCCVLNewsPortletManagerRenderer(PortletManagerRenderer):

    template = ViewPageTemplateFile('bccvlnews_portletmanager.pt')

    def _context(self):
        return aq_inner(self.context)

    def base_url(self):
        """If context is a default-page, return URL of folder, else
        return URL of context.
        """
        return str(getMultiAdapter((self._context(), self.request, ), name=u'absolute_url'))

    def can_manage_portlets(self):
        # ftool = getToolByName(context, 'portal_factory', None)
        # if ftool and ftool.isTemporary(context) or \
        #     not ILocalPortletAssignable.providedBy(context):
        #     return False
        return checkPermission("plone.app.portlets.ManagePortlets", self._context())
