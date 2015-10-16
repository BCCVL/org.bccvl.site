from persistent import Persistent
from zope.location.location import Location


class Job(Persistent):

    def __init__(self):
        self.id = None
        self.userid = None
        self.message = None
        self.state = None
        self.title = None
        self.progress = None
        self.taskid = None
