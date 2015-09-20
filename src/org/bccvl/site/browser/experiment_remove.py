
from z3c.form import field, button, form
from z3c.form.widget import AfterWidgetUpdateEvent
from z3c.form.interfaces import DISPLAY_MODE
from zope.event import notify
from zope.lifecycleevent import modified
from org.bccvl.site.interfaces import IBCCVLMetadata
#from zope.browserpage.viewpagetemplatefile import Viewpagetemplatefile
from Products.Five.browser.pagetemplatefile import ViewPageTemplateFile
from Products.Five.browser import BrowserView
from Products.statusmessages.interfaces import IStatusMessage
from Acquisition import aq_inner
from Acquisition import aq_parent
from org.bccvl.site.interfaces import IJobTracker
from Products.CMFCore import permissions
from AccessControl import Unauthorized
from Products.CMFCore.utils import getToolByName
from zope.component import getMultiAdapter, getUtility
from org.bccvl.site import defaults


class ExperimentRemoveView(form.Form):
    """
    The remove view marks a dataset as 'removed' and deletes the associated blob. It is distinct from the built in delete
    view in that the dataset object is not actually deleted.
    """

    fields = field.Fields()
    enableCSRFProtection = True

    @button.buttonAndHandler(u'Remove')
    def handle_delete(self, action):
        title = self.context.Title()

        portal_membership = getToolByName(self.context, 'portal_membership')

        if not portal_membership.checkPermission(permissions.DeleteObjects, self.context):
            raise Unauthorized("You do not have permission to delete this object")

        experiment_tools = getMultiAdapter((self.context, self.request), name="experiment_tools")
        portal = getToolByName(self.context, 'portal_url').getPortalObject()
        excontainer = portal[defaults.EXPERIMENTS_FOLDER_ID]
        nexturl = excontainer.absolute_url()

        # this view should never come up if this is the case, so the check if merely a security / sanity check in
        # case someone guesses the delete url and tries to run it. In that case the view will just silently ignore the delete.
        if not experiment_tools.check_if_used():
            excontainer.manage_delObjects([self.context.getId()])
        self.request.response.redirect(nexturl)

    @button.buttonAndHandler(u'Cancel')
    def handle_cancel(self, action):
        portal = getToolByName(self.context, 'portal_url').getPortalObject()
        nexturl = portal[defaults.EXPERIMENTS_FOLDER_ID].absolute_url()
        self.request.response.redirect(nexturl)

    def render(self):
        if self.index:
            return self.index()
        return super(DatasetRemoveView, self).render()
