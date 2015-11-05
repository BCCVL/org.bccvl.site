from zope.interface import Interface


class IAPIService(Interface):
    """
    Marker interface for API Services
    """

    def schema():
        """Return json schema for this API endpoint.
        """

    def __call__():
        """Return json descrition for this API endpoint.
        """


class IDMService(Interface):
    """
    Dataset service
    """

    def metadata(uuid):
        """Return all metadata about dataset identified by uuid.
        """


class IJobService(Interface):
    """Job service
    """

    def state(jobid=None, uuid=None):
        """Return job state for given job id or latest job related to content
        object identified by uuid.

        """

    def get(**kw):
        """Get json description for job identified by keyword parameters.
        """


class IExperimentService(Interface):
    """
    Experiment service
    """

    def demosdm(lsid):
        """Run a demosdm experiment for given lsdi.

        Return a dictionary with keys 'state', 'result' and 'jobid'
        """


class ISiteService(Interface):
    """
    Site information service
    """
