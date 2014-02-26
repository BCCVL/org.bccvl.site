import logging
from zope import schema
from zope.interface import implementer
from zope.component import adapter
from dexterity.membrane.content.member import IMember
from dexterity.membrane.behavior.membraneuser import INameFromFullName
from dexterity.membrane.behavior.membraneuser import MembraneUser
from Products.membrane.interfaces import IMembraneUserProperties
from Products.PlonePAS.sheet import MutablePropertySheet

LOG = logging.getLogger(__name__)


class IBCCVLUser(IMember):

    username = schema.TextLine(
        # String with validation in place looking for @, required.
        # Note that a person's email address will be their username.
        #title=_(u"E-mail Address"),
        title=u"Username",
        required=True,
        )

    full_name = schema.TextLine(
        title=u"Full name",
        required=False,
        )


#class Bccvluser(Item):
@adapter(IBCCVLUser)
@implementer(INameFromFullName)
class NameFromFullName(object):

    def __init__(self, context):
        self.context = context

    @property
    def title(self):
        # TODO: fallback to user id?
        self.context.full_name


@adapter(IBCCVLUser)
@implementer(IMembraneUserProperties)
class BCCVLUserProperties(MembraneUser):

    # map plone user properties to bccvl user properties
    property_map = dict(
        email='email',
        home_page='homepage',
        description='bio',
        fullname='full_name'
        )

    @property
    def fullname(self):
        if not hasattr(self.context, 'full_name'):
            return u''
        return self.context.full_name

    def getPropertiesForUser(self, user, request=None):
        """Get properties for this user.

        Find the fields of the user schema that make sense as a user
        property in @@personal-information.

        Note: this method gets called a crazy amount of times...

        Also, it looks like we can ignore the user argument and just
        check self.context.
        """
        properties = dict(
            fullname=self.fullname,
            )
        for prop_name, field_name in self.property_map.items():
            value = getattr(self.context, field_name, None)
            if value is None:
                # Would give an error like this:
                # ValueError: Property home_page: unknown type
                value = u''
            properties[prop_name] = value
        return MutablePropertySheet(self.context.getId(),
                                    **properties)

    def setPropertiesForUser(self, user, propertysheet):
        """
        Set modified properties on the user persistently.

        Should raise a ValueError if the property or property value is
        invalid.  We choose to ignore it and just handpick the ones we
        like.

        For example, fullname cannot be handled as we don't know how
        to split that into first, middle and last name.
        """
        # import ipdb; ipdb.set_trace()
        properties = dict(propertysheet.propertyItems())
        for prop_name, field_name in self.property_map.items():
            value = properties.get(prop_name, '').strip()
            LOG.info("Setting field %s: %r", field_name, value)
            setattr(self.context, field_name, value)
            # oldval = getattr(self.context, field_name, None)
            # if oldval != value:
            #     LOG.info("Setting field %s: %r", field_name, value)
            #     setattr(self.context, field_name, value)

    def deleteUser(self, user_id):
        """
        Remove properties stored for a user

        Note that membrane itself does not do anything here.  This
        indeed seems unneeded, as the properties are stored on the
        content item, so they get removed anyway without needing
        special handling.
        """
        pass
