from Acquisition import aq_inner
from Products.Five.browser.pagetemplatefile import ViewPageTemplateFile
from plone.app.users.browser.personalpreferences import UserDataPanel
from plone.app.users.browser.personalpreferences import PasswordAccountPanel


class UserDataPanelView(UserDataPanel):
    """ Implementation of personalize form that uses formlib """
    # overriding it here to customise the template

    template = ViewPageTemplateFile('account-panel.pt')

    def getOAuthPrefsLink(self):
        context = aq_inner(self.context)

        template = None
        if self._checkPermission('Set own properties', context):
            template = '@@oauth-preferences'

        return template

class PasswordAccountPanelView(PasswordAccountPanel):
    """ Implementation of password reset form that uses formlib"""
    # overriding it here to customise the template

    template = ViewPageTemplateFile('account-panel.pt')

    def getOAuthPrefsLink(self):
        context = aq_inner(self.context)

        template = None
        if self._checkPermission('Set own properties', context):
            template = '@@oauth-preferences'

        return template

    
