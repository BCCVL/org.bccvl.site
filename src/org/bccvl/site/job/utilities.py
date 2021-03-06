import uuid
from DateTime import DateTime
from plone import api
from plone.uuid.interfaces import IUUID
from zope.component import getUtility
from zope.event import notify
from zope.interface import implementer
from zope.lifecycleevent import ObjectCreatedEvent, ObjectAddedEvent
from org.bccvl.site.job.interfaces import IJob, IJobUtility, IJobTracker
from org.bccvl.site.job.job import Job


@implementer(IJobUtility)
class JobUtility(object):

    # TODO: CANCELED state?
    _states = ('PENDING', 'QUEUED', 'RUNNING', 'COMPLETED', 'FAILED', 'REMOVED')

    # TODO: memoize?
    def _catalog(self):
        return api.portal.get_tool('job_catalog')

    def _comparestate(self, state1, state2):
        """
        -1 if state1 < state2
        0  if state1 == state2
        1  if state1 > state2
        """
        if any(map(lambda x: x is None, [state1, state2])):
            if all(map(lambda x: x is None, [state1, state2])):
                return 0
            return -1 if state1 is None else 1

        # TODO: may raise ValueError if state not in list
        idx1 = self._states.index(state1)
        idx2 = self._states.index(state2)
        return cmp(idx1, idx2)

    def new_job(self, **kw):
        # FIXME: do we really need to locate it?
        job = Job()
        job.id = str(uuid.uuid1())
        job.state = 'PENDING'
        job.created = DateTime()
        job.userid = api.user.get_current().getId()

        for name in IJob.names():
            if name in kw:
                setattr(job, name, kw[name])

        notify(ObjectCreatedEvent(job))
        cat = self._catalog()
        cat.jobs[job.id] = job
        notify(ObjectAddedEvent(job, cat.jobs, job.id))
        return job

    def reindex_job(self, job):
        self._catalog().reindexObject(job, uid=job.id)

    def get_job_by_id(self, id):
        return self._catalog().jobs[id]

    def find_job_by_uuid(self, uuid):
        """
        return latest job for content object
        """
        brains = self._catalog().searchResults(content=uuid,
                                               sort_on='created',
                                               sort_order='reverse')
        if not brains:
            return None
        return brains[0].getObject()

    def set_progress(self, job, progress=None, message=None, rusage=None):
        """
        progress ... a short notice (maybe percent?, #step)
        message ... longer description of progress
        """
        # only set values if the have been passed in as params
        if progress != None:
            job.progress = progress
        if message != None:
            job.message = message
        if rusage != None:
            job.rusage = rusage
        # TODO: only reindex if there were changes
        self.reindex_job(job)

    def set_state(self, job, state):
        if self._comparestate(job.state, state) < 0:
            job.state = state
            self.reindex_job(job)

    def query(self, **kw):
        brains = self._catalog().searchResults(**kw)
        return brains




@implementer(IJobTracker)
class JobTracker(object):
    """
    Adapter to manage job state for context object
    """
    # job_info:
    #   - taskid ... unique id of task
    #   - name ... task name
    #   - state ... QUEUED, RUNNING, COMPLETED, FAILED
    #   - progress ... a dict with task specific progress
    #     - state ... short note of activity
    #     - message ... short descr of activity
    #     - .... could be more here; e.g. percent complete, steps, etc..

    def __init__(self, context):
        self.context = context
        self.job_tool = getUtility(IJobUtility)  # rather use get_tool as it depends on current portal anyway?

    def get_job(self):
        try:
            uuid = IUUID(self.context)
        except TypeError:
            return None
        return self.job_tool.find_job_by_uuid(uuid)

    @property
    def state(self):
        job = self.get_job()
        if job:
            return job.state
        return None

    @state.setter
    def state(self, state):
        # make sure we can only move forward in state
        job = self.get_job()
        if not job:
            return
        # TODO: do message update as well, may need to change comparison to <= 0 so that even if state does not change we can update the message
        self.job_tool.set_state(job, state)

    # FIXME: message vs. state vs. dict?
    def progress(self):
        job = self.get_job()
        if job:
            return {
                'progress': job.progress,
                'message': job.message
            }
        return None

    def set_progress(self, progress=None, message=None, rusage=None):
        """
        progress ... a short notice (maybe percent?, #step)
        message ... longer description of progress
        """
        job = self.get_job()
        if job:
            self.job_tool.set_progress(job, progress, message, rusage)

    def new_job(self, taskid, title, **kw):
        # FIXME: this is duplicate API ... should probably go away
        kw['taskid'] = taskid
        kw['title'] = title
        kw['content'] = IUUID(self.context)
        job = self.job_tool.new_job(**kw)
        self.job_tool.reindex_job(job)
        return job

    def start_job(self, request=None):
        # FIXME: this sholud not be part of this interface here, as it is usually very context dependent
        pass

    @property
    def states(self):
        pass
