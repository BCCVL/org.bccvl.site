
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

class ExperimentRemoveView(form.Form):
    """ 
    The remove view marks a dataset as 'removed' and deletes the associated blob. It is distinct from the built in delete
    view in that the dataset object is not actually deleted.
    """

    fields = field.Fields()
    template = ViewPageTemplateFile('experiment_remove.pt')
    enableCSRFProtection = True

    @button.buttonAndHandler(u'Remove')
    def handle_delete(self, action):
        title = self.context.Title()
        parent = aq_parent(aq_inner(self.context))
        ## removed file working on frontend Javascript
        # if hasattr(self.context, "file"):
        #     self.context.file = None
        # jt = IJobTracker(self.context)
        # jt.state = 'REMOVED'
        # self.context.reindexObject()
        #####
        IStatusMessage(self.request).add(u'{0[title]} has been removed.'.format({u'title': title}))
        self.request.response.redirect(aq_parent(parent).absolute_url())

    @button.buttonAndHandler(u'Cancel')
    def handle_cancel(self, action):
        self.request.response.redirect(self.context.absolute_url())