from Products.Five.browser import BrowserView
from Products.statusmessages.interfaces import IStatusMessage
from org.bccvl.site.job.interfaces import IJobTracker
from org.bccvl.tasks.plone import submit_experiment
from org.bccvl.tasks.plone.utils import after_commit_task, create_task_context


# FIXME: either update to new way of background submission (maybe an internal API would be good here, which will be used for this view and all other places)
#        or remove this view entirely
class StartJobView(BrowserView):

    def __call__(self):
        jt = IJobTracker(self.context)  # get submission job tracker
        if jt.state not in (None, 'COMPLETED', 'FAILED', 'REMOVED'):
            IStatusMessage(self.request).add('Submit in progress', type='error')
        # FIXME: do something about submitting twice?
        else:
        #if True:
            # start a new job
            context = create_task_context(self.context)
            context['experiment'] = {
                'title': self.context.title,
                'url': self.context.absolute_url()
            }
            after_commit_task(submit_experiment, context=context)
            job = jt.new_job('TODO: generate id',
                             'generate taskname: submit_experiment')
            job.type = self.context.portal_type
            jt.state = 'PENDING'
            jt.set_progress('PENDING',
                            u'submit experiment pending ')
            IStatusMessage(self.request).add('Job submitted {0}'.format(self.context.title), type='info')
        self.request.response.redirect(self.context.absolute_url())
