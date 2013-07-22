from Products.Five.browser import BrowserView
from org.bccvl.compute.bioclim import execute
from plone.app.uuid.utils import uuidToObject
from zope.component import getUtility
from plone.app.async.interfaces import IAsyncService
from plone.app.async import service
from Products.statusmessages.interfaces import IStatusMessage


class StartJobView(BrowserView):

    def __call__(self):
        # TODO: could also just submit current context (the experiment)
        #       with all infos accessible from it
        #func = uuidToObject(self.context.functions)
        spec = uuidToObject(self.context.species_occurrence_dataset)
        env = uuidToObject(self.context.environmental_dataset)
        specfile = spec.get('occur.csv')
        envfile = env.get('current_asc.zip')

        async = getUtility(IAsyncService)
        # TODO: default queue quota is 1. either set it to a defined value (see: plone.app.asnc.subscriber)
        #       or create and oubmit job manually
        #job = async.queueJob(execute, self.context, envfile, specfile)
        jobinfo = (execute, self.context, (envfile, specfile), {})
        job = async.wrapJob(jobinfo)
        queue = async.getQueues()['']
        job = queue.put(job)
        # don't forget the plone.app.async notification callbacks
        job.addCallbacks(success=service.job_success_callback,
                         failure=service.job_failure_callback)

        IStatusMessage(self.request).add(u'Job submitted {}'.format(job.status), type='info')
        self.request.response.redirect(self.context.absolute_url())
