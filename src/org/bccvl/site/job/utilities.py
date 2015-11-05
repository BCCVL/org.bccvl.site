import uuid
from DateTime import DateTime
from plone import api
from plone.uuid.interfaces import IUUID
from zope.component import getUtility
from zope.interface import implementer
from org.bccvl.site.job.interfaces import IJobUtility, IJobTracker
from org.bccvl.site.job.job import Job


@implementer(IJobUtility)
class JobUtility(object):

    # TODO: memoize?
    def _catalog(self):
        return api.portal.get_tool('job_catalog')

    def new_job(self):
        # FIXME: do we really need to locate it?
        job = Job()
        job.id = str(uuid.uuid1())
        job.state = 'PENDING'
        job.created = DateTime()
        job.userid = api.user.get_current().getId()
        cat = self._catalog()
        cat.jobs[job.id] = job
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

    def query(self, **kw):
        brains = self._catalog().searchResults(**kw)




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

    # TODO: CANCELED state?
    _states = ('PENDING', 'QUEUED', 'RUNNING', 'COMPLETED', 'FAILED', 'REMOVED')

    def __init__(self, context):
        self.context = context
        self.job_tool = getUtility(IJobUtility)  # rather use get_tool as it depends on current portal anyway?

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
        if self._comparestate(job.state, state) < 0:
            job.state = state
            self.job_tool.reindex_job(job)

    # FIXME: message vs. state vs. dict?
    def progress(self):
        job = self.get_job()
        if job:
            return {
                'progress': job.progress,
                'message': job.message
            }
        return None

    def set_progress(self, progress=None, message=None):
        """
        progress ... a short notice (maybe percent?, #step)
        message ... longer description of progress
        """
        job = self.get_job()
        if job:
            job.progress = progress
            job.message = message
            self.job_tool.reindex_job(job)

    def new_job(self, taskid, title):
        # FIXME: this is duplicate API ... should probably go away
        job = self.job_tool.new_job()
        job.content = IUUID(self.context)
        job.taskid = taskid
        job.title = title
        self.job_tool.reindex_job(job)
        return job

    def start_job(self, request=None):
        # FIXME: this sholud not be part of this interface here, as it is usually very context dependent
        pass

    @property
    def states(self):
        pass
