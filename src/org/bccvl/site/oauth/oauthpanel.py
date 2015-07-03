#
from Acquisition import aq_inner
from Products.CMFCore.utils import getToolByName
from Products.Five.browser import BrowserView
from plone import api
from plone.registry.interfaces import IRegistry
from zope.component import getUtility
from .interfaces import IOAuth1Settings, IOAuth2Settings
from Products.Five.browser.pagetemplatefile import ViewPageTemplateFile
from .oauth import OAuth1View, OAuth2View


class OAuthPreferencePanel(BrowserView):

    template = ViewPageTemplateFile('oauthpanel.pt')

    label = u"OAuth Preferences"
    description = u"BCCVL is allowed to access the following services."

    def getOAuthPrefsLink(self):
        context = aq_inner(self.context)

        template = None
        if self._checkPermission('Set own properties', context):
            template = '@@oauth-preferences'

        return template

    def _checkPermission(self, permission, context):
        mt = getToolByName(context, 'portal_membership')
        return mt.checkPermission(permission, context)

    def getPersonalInfoLink(self):
        context = aq_inner(self.context)

        template = None
        if self._checkPermission('Set own properties', context):
            template = '@@personal-information'

        return template

    def getPasswordLink(self):
        context = aq_inner(self.context)

        mt = getToolByName(context, 'portal_membership')
        member = mt.getAuthenticatedMember()

        template = None
        if member.canPasswordSet():
            template = '@@change-password'

        return template

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
