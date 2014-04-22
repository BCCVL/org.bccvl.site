from Products.Five.browser import BrowserView
from Products.statusmessages.interfaces import IStatusMessage
from org.bccvl.site.interfaces import IJobTracker


class StartJobView(BrowserView):

    def __call__(self):
        # TODO: could also just submit current context (the experiment)
        #       with all infos accessible from it

        jt = IJobTracker(self.context)
        msgtype, msg = jt.start_job(self.request)
        if msgtype is not None:
            IStatusMessage(self.request).add(msg, type=msgtype)
        self.request.response.redirect(self.context.absolute_url())
