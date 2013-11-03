
# this should be sent upstream to z3c.form.converter:
#   in case the siglecheckbox-empty-marker is not present in the request,
#   the widget extracts NO_VALUE and passes this on to this converter.toFieldValue
#   which expects the value to be a list.
#   other option would be to make NO_VALUE evaluate to False. bool(NO_VALUE)
#-> possibly related to custom singlechockboxwidget in plone.z3cform? (which renders a radio as workaround?)
#-> empt-marker no longer needed on checkbox

from plone.app.dexterity.behaviors.exclfromnav import IExcludeFromNavigation

IExcludeFromNavigation['exclude_from_nav'].required = False
