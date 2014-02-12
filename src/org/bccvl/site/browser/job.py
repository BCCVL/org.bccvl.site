from Products.Five.browser import BrowserView
from Products.statusmessages.interfaces import IStatusMessage
from org.bccvl.site.interfaces import IJobTracker
from zope.interface import implementer
from plone.directives import form
from zope.schema import TextLine


class StartJobView(BrowserView):

    def __call__(self):
        # TODO: could also just submit current context (the experiment)
        #       with all infos accessible from it

        jt = IJobTracker(self.context)
        msgtype, msg = jt.start_job(self.request)
        if msgtype is not None:
            IStatusMessage(self.request).add(msg, type=msgtype)
        self.request.response.redirect(self.context.absolute_url())


class IJobStatus(form.Schema):

    status = TextLine(title=u'Current Job Status',
                      required=False,
                      readonly=True)

    #apply = button.Button(title=u'Apply')


@implementer(IJobStatus)
class JobStatus(object):
    # implement additional fields for form schema

    def __init__(self, context):
        self.context = context

    @property
    def status(self):
        return IJobTracker(self.context).status()
