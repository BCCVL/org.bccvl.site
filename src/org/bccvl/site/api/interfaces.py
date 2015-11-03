from zope.interface import Interface


class IAPIService(Interface):
    """
    Marker interface for API Services
    """


class IDMService(Interface):
    """
    Dataset service
    """


class IJobService(Interface):
    """
    Job service
    """


class IExperimentService(Interface):
    """
    Experiment service
    """


class ISiteService(Interface):
    """
    Site information service
    """
