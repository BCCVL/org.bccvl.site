from Products.Five.browser import BrowserView
from Products.Five.browser.pagetemplatefile import ViewPageTemplateFile
from plone.registry.interfaces import IRegistry
from zope.component import getUtility
from zope.schema.interfaces import IVocabularyFactory
from .interfaces import IOAuth1Settings, IOAuth2Settings
from .oauth import OAuth1View, OAuth2View


class OAuthSelectModal(BrowserView):

    template = ViewPageTemplateFile('oauthselect.pt')

    def services(self):
        registry = getUtility(IRegistry)
        providers = getUtility(IVocabularyFactory, 'org.bccvl.site.oauth.providers')(self.context)
        for term in providers:
            coll = registry.collectionOfInterface(term.value)
            for pid, config in coll.items():
                if IOAuth1Settings.providedBy(config):
                    view = OAuth1View(self.context, self.request, config)
                elif IOAuth2Settings.providedBy(config):
                    view = OAuth2View(self.context, self.request, config)
                else:
                    continue
                if view.hasToken():
                    yield view

    def __call__(self):
        return self.template()
