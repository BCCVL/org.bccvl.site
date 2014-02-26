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
from dexterity.membrane.behavior.membraneuser import IProvidePasswords

import org.bccvl.site.patch

MessageFactory = MessageFactory('org.bccvl.site')


class UnrestrictedUser(BaseUnrestrictedUser):
    """Unrestricted user that still has an id.
    """
    def getId(self):
        """Return the ID of the user.
        """
        return self.getUserName()


class UserAdder(Explicit):
    # need Explicit Acquisition, because membrane assumes it to be persistent
    """
    UserAdder utility that knows how to add SimpleMembers.
    """
    implements(IUserAdder)

    def addUser(self, login, password):
        """
        Adds a SimpleMember object at the root of the Plone site.
        """
        # FIXME: the code here assumes, that dexterity.membrane
        #        options are set to uuid = false, email = false
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
        newuser = createContent('org.bccvl.content.user',
                                id=login, username=login)
        # set password in case the user has been created manually
        # FIXME: don't set password for aaf user ... and check if
        #        login with empty pw is possible
        pvprop = IProvidePasswords(newuser, None)
        if pvprop:
            pvprop.password = password
        # first_name, last_name, homepage, bio, email

        # FIXME: in case we have use email address as username
        #       activated, we'll have to set it before adding the
        #       object to the container'
        #       add user controlpanel optionally supplys full user
        #       name
        #       membrane also determines user id at this stage. (uuid
        #       or id->username->email?)
        #       workaround: supply email instead of username in
        #       username field

        # IMembraneUser, IProvidePasswords, IMember
        newuser = addContentToContainer(directory, newuser)
        # approve new user

        try:
            # TODO: this auto activation should be outside of UserAdder
            # the user adder is called for self registration as well,
            # we reset the security manager to current user and try to
            # auto activate. in case it fails, the user didn't have
            # permission to do so and has to wait for an approver
            wf_tool = getToolByName(portal, 'portal_workflow')
            wf_tool.doActionFor(newuser, 'approve')

            # Index with again because of changed workflow state
            newuser.reindexObject()
        except:
            # TODO: not nice to eat all exceptions
            pass

        ## Reset security manager
        setSecurityManager(old_sm)
        # FIXME: should happen before workflow transition
        #        we want to auto approve AAF logins. but not self
        #        registration?
        #        AAF needs higher privileges than self registration

        return newuser
