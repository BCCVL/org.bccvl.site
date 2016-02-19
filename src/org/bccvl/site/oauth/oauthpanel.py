#
from Products.CMFCore.utils import getToolByName
from Products.Five.browser.pagetemplatefile import ViewPageTemplateFile
from plone.app.users.browser.account import AccountPanelForm
from plone.registry.interfaces import IRegistry
from zope.component import getMultiAdapter
from zope.component import getUtility
from zope.schema.interfaces import IVocabularyFactory
from .interfaces import IOAuth1Settings, IOAuth2Settings
from .oauth import OAuth1View, OAuth2View


class OAuthPreferencePanel(AccountPanelForm):

    template = ViewPageTemplateFile('oauthpanel.pt')

    label = u"Linked Accounts"
    description = u"On this page you can manage authorisations for BCCVL to access external systems."
    enableCSRFProtection = True

    def prepareObjectTabs(self,
                          default_tab='view',
                          sort_first=['folderContents']):

        tabs = super(OAuthPreferencePanel, self).prepareObjectTabs(default_tab, sort_first)
        navigation_root_url = self.context.absolute_url()
        mt = getToolByName(self.context, 'portal_membership')

        def _check_allowed(context, request, name):
            """Check, if user has required permissions on view.
            """
            view = getMultiAdapter((context, request), name=name)
            allowed = True
            for perm in view.__ac_permissions__:
                allowed = allowed and mt.checkPermission(perm[0], context)
            return allowed

        # TODO: insert before id:user_data-change-password
        if _check_allowed(self.context, self.request, 'oauth-preferences'):
            tabs.append({
                'title': u'External Authorisations',
                'url': navigation_root_url + '/@@oauth-preferences',
                'selected': (self.__name__ == 'oauth-preferences'),
                'id': 'user_data-oauth-preferences',
            })
        return tabs

    def services(self):
        registry = getUtility(IRegistry)
        providers = getUtility(IVocabularyFactory, 'org.bccvl.site.oauth.providers')(self.context)
        for term in providers:
            coll = registry.collectionOfInterface(term.value)
            for pid, config in coll.items():
                if IOAuth1Settings.providedBy(config):
                    yield OAuth1View(self.context, self.request, config)
                elif IOAuth2Settings.providedBy(config):
                    yield OAuth2View(self.context, self.request, config)
                # TODO: error handling?
        # coll = registry.collectionOfInterface(IOAuth1Settings)
        # for provider, config in coll.items():
        #     yield OAuth1View(self.context, self.request, config)
        # coll = registry.collectionOfInterface(IOAuth2Settings)
        # for provider, config in coll.items():
        #     yield OAuth2View(self.context, self.request, config)
