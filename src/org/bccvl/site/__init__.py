from Products.CMFCore.utils import getToolByName
# from Products.CMFPlone.utils import _createObjectByType
from Products.membrane.interfaces import IUserAdder
from zope.interface import implements
from zope.component.hooks import getSite
from Acquisition import Explicit
from zope.i18nmessageid import MessageFactory
from AccessControl.SecurityManagement import getSecurityManager
from AccessControl.SecurityManagement import newSecurityManager
from AccessControl.SecurityManagement import setSecurityManager
from AccessControl.User import UnrestrictedUser as BaseUnrestrictedUser
from plone.dexterity.utils import createContent, addContentToContainer


MessageFactory = MessageFactory('org.bccvl.site')


class UnrestrictedUser(BaseUnrestrictedUser):
    """Unrestricted user that still has an id.
    """
    def getId(self):
        """Return the ID of the user.
        """
        return self.getUserName()


class UserAdder(Explicit):  # need Explicit Acquisition, because membrane assumes it to be persistent
    """
    UserAdder utility that knows how to add SimpleMembers.
    """
    implements(IUserAdder)

    def addUser(self, login, password):
        """
        Adds a SimpleMember object at the root of the Plone site.
        """
        # FIXME: the code here assumes, that dexterity.membrane options are set to
        #        uuid = false, email = false
        site = getSite()

        portal = getToolByName(site, 'portal_url').getPortalObject()
        # FIXME: create this folder if it is not there?
        directory = portal.get('directory')

        ## The current user is usually not allowed to create new user objects.
        ## temporarily change the security context to use a temporary
        ## user with manager role.
        old_sm = getSecurityManager()
        tmp_user = UnrestrictedUser(
            login,
            '', ['Manager'],
            ''
        )

        tmp_user = tmp_user.__of__(portal.acl_users)
        newSecurityManager(None, tmp_user)

        # check for current user here? get more info?
        # email, firstName, lastName
        newuser = createContent('org.bccvl.content.user', id=login, username=login)
        # first_name, last_name, homepage, bio, email
        # IMembraneUser, IProvidePasswords, IMember
        newuser = addContentToContainer(directory, newuser)
        # approve new user
        wf_tool = getToolByName(portal, 'portal_workflow')
        wf_tool.doActionFor(newuser, 'approve')

        ## Reset security manager
        setSecurityManager(old_sm)

        # Index with customer again
        newuser.reindexObject()
        return newuser

        # _createObjectByType('SimpleMember', portal, login, password=password,
        #                     userName=login)
