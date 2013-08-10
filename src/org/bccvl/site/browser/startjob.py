from Products.Five.browser import BrowserView
from org.bccvl.compute import bioclim,  brt
from plone.app.uuid.utils import uuidToObject
from zope.component import getUtility
from plone.app.async.interfaces import IAsyncService
from plone.app.async import service
from Products.statusmessages.interfaces import IStatusMessage


class StartJobView(BrowserView):

    def __call__(self):
        # TODO: could also just submit current context (the experiment)
        #       with all infos accessible from it
        func = uuidToObject(self.context.functions)

        async = getUtility(IAsyncService)
        # TODO: default queue quota is 1. either set it to a defined value (see: plone.app.asnc.subscriber)
        #       or create and oubmit job manually
        #job = async.queueJob(execute, self.context, envfile, specfile)
        jobinfo = None
        if func is None:
            IStatusMessage(self.request).add(u"Can't find function {}".format(self.context.functions), type='error')
        elif func.id == 'bioclim':
            jobinfo = (bioclim.execute, self.context, (), {})
        elif func.id == 'brt':
            jobinfo = (brt.execute, self.context, (), {})
        else:
            IStatusMessage(self.request).add(u'Unkown job function {}'.format(func.id), type = 'error')
        if jobinfo is not None:
            job = async.wrapJob(jobinfo)
            queue = async.getQueues()['']
            job = queue.put(job)
            # don't forget the plone.app.async notification callbacks
            job.addCallbacks(success=service.job_success_callback,
                            failure=service.job_failure_callback)

            IStatusMessage(self.request).add(u'Job submitted {}'.format(job.status), type='info')
        self.request.response.redirect(self.context.absolute_url())
