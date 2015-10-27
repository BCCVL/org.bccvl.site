from zope.interface import Attribute, Interface, implementer

# FIXME: move all job related interfaces in here

# IJobTracker
# IJobCatalog
# IJobWhatever


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
