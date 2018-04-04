from persistent import Persistent
from zope.interface import implementer
from .interfaces import IJob


@implementer(IJob)
class Job(Persistent):

    def __init__(self):
        self.id = None  # job identifier
        self.created = None  # job creation timestamp
        self.userid = None  # who started this job?
        self.message = None  # last state change message .. or error
        self.state = None  # state
        self.title = None  # job title
        self.progress = None  # progress message
        self.taskid = None  # underlying task id (celery task)
        self.content = None  # related content object
        self.lsid = None  # species lsid (good for demosdm)
        self.toolkit = None  # function uuid
        self.function = None  # function id
        self.type = None  # type of job ... ?? maybe experiment portal_type?
        self.rusage = None # process statistics for the job
