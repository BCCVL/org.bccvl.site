from zope.interface import Attribute, Interface, implementer

# FIXME: move all job related interfaces in here

# IJobTracker
# IJobCatalog
# IJobWhatever


class IJob(Interface):

    id = Attribute(u'job identifier')
    created = Attribute(u'job creation timestamp')
    userid = Attribute(u'who started this job?')
    message = Attribute(u'last state change message .. or error')
    state = Attribute(u'state')
    title = Attribute(u'job title')
    progress = Attribute(u'progress message')
    taskid = Attribute(u'underlying task id (celery task)')
    content = Attribute(u'related content object')
    lsid = Attribute(u'species lsid (good for demosdm)')
    toolkit = Attribute(u'function uuid')
    function = Attribute(u'function id')
    type = Attribute(u'type of job ... ?? maybe experiment portal_type?')
    rusage = Attribute(u'process statistics for the job')


class IJobUtility(Interface):
    """
    A global utility that provides an API to work with Jobs.
    """

    def new_job(self):
        """
        Create new job object and store it in job store.

        New Job object will be in state PENDING, and has a UUID assigned.
        """

    def reindex_job(self, job):
        """
        Update index for given job object.
        """


class IJobCatalog(Interface):
    """
    Interface for catalog to index job objects.
    """


class IJobTracker(Interface):
    """
    Interface to deal with jobs that are associated with content.
    """

    def get_job(self):
        """
        Get Job object for this content object.
        """

    state = Attribute("State for this Job")
