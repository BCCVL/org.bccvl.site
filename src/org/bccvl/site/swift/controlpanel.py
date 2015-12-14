from plone.app.registry.browser.controlpanel import RegistryEditForm
from plone.app.registry.browser.controlpanel import ControlPanelFormWrapper
from plone.z3cform import layout
from org.bccvl.site.swift.interfaces import ISwiftSettings


class SwiftSettingsEditForm(RegistryEditForm):

    schema = ISwiftSettings
    label = u"Swift settings"

    # TODO: use this to bring in os.environ settings into form?
    # def updateFields(self):
    #     super(SwiftSettingsEditForm, self).updateFields()

    # TODO: what's the logic between storing values in registry and using
    #       environment variables?
    #       how to update / reset / choose / delete ?


SwiftSettingsView = layout.wrap_form(SwiftSettingsEditForm, ControlPanelFormWrapper)
