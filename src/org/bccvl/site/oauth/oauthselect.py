from Products.Five.browser import BrowserView
from Products.Five.browser.pagetemplatefile import ViewPageTemplateFile
from plone.registry.interfaces import IRegistry
from zope.component import getUtility
from .interfaces import IOAuth1Settings, IOAuth2Settings
from .oauth import OAuth1View, OAuth2View


class OAuthSelectModal(BrowserView):

    template = ViewPageTemplateFile('oauthselect.pt')

    def services(self):
        registry = getUtility(IRegistry)
        coll = registry.collectionOfInterface(IOAuth1Settings)
        for provider, config in coll.items():
            yield OAuth1View(self.context, self.request, config)
        coll = registry.collectionOfInterface(IOAuth2Settings)
        for provider, config in coll.items():
            yield OAuth2View(self.context, self.request, config)

    def __call__(self):
        return self.template()
