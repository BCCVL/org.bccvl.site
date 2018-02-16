from AccessControl import Unauthorized
from Products.CMFCore.utils import getToolByName
from Products.CMFCore import permissions
from Products.statusmessages.interfaces import IStatusMessage
from plone import api
from z3c.form import field, button, form
from zope.component import getMultiAdapter, getUtility

from org.bccvl.site import defaults
from org.bccvl.site.stats.interfaces import IStatsUtility


class ExperimentRemoveView(form.Form):
    """
    The remove view marks a dataset as 'removed' and deletes the associated blob. It is distinct from the built in delete
    view in that the dataset object is not actually deleted.
    """

    fields = field.Fields()
    enableCSRFProtection = True

    @button.buttonAndHandler(u'Remove')
    def handle_delete(self, action):
        #title = self.context.Title()

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
            # FIXME: this does not count removed datasets or jobs
            getUtility(IStatsUtility).count_experiment(
                user=api.user.get_current().getId(),
                portal_type=self.context.portal_type,
                state='REMOVED'
            )

        # leave a message for the user
        IStatusMessage(self.request).add(u"Experiment '{}' has been removed.".format(self.context.title))

        # In case this is an ajax request, we return a 204 redirect
        if self.request.get('ajax_load') == '1':
            self.request.response.redirect(nexturl, 204)
        else:
            # Browser form submit ... return 302
            self.request.response.redirect(nexturl)

    @button.buttonAndHandler(u'Cancel')
    def handle_cancel(self, action):
        portal = getToolByName(self.context, 'portal_url').getPortalObject()
        nexturl = portal[defaults.EXPERIMENTS_FOLDER_ID].absolute_url()
        self.request.response.redirect(nexturl)

    def render(self):
        if self.request.response.getStatus() in (204,):
            # short cut ajax redirect
            return u''

        if self.index:
            return self.index()
        return super(ExperimentRemoveView, self).render()
