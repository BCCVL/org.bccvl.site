from Products.Five.browser import BrowserView
from org.bccvl.compute.bioclim import execute
from plone.app.uuid.utils import uuidToObject
from zope.component import getUtility
from plone.app.async.interfaces import IAsyncService
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
        import ipdb; ipdb.set_trace()

        async = getUtility(IAsyncService)
        #queue = async.getQueues()['']
        job = async.queueJob(execute, self.context, envfile, specfile)
        IStatusMessage(self.request).add(u'Job submitted {}'.format(job.status), type='info')
        self.request.response.redirect(self.context.absolute_url())
