from zope.interface import Interface
from zope.schema import Text


class IDownloadInfo(Interface):
    """Return a dictionary with infos to download a file.

    The dictionary has the following keys:

    filename ... the naem of the file
    url      ... the url to fetch it from
    """

class IExperimentJobTracker(Interface):
    """
    helper to work with experiment jobs
    """

class IComputeMethod(Interface):

    def __call__(result, toolkit, priority):
        """
        execute a compute method
        """


class IBCCVLMetadata(Interface):
    """
    Interface to access BCCVL specific metadata.
    """
    # FIXME: add IDict or IMapping as base interface?


class IProvenanceData(Interface):
    """
    Interface to access Provenance specific metadata.
    """

    data = Text()

class IExperimentMetadata(Interface):
    """
    Interface to access experiment metadata
    """

    data = Text()

class IExperimentParameter(Interface):
    """
    Interface to access experiment parameters
    """

    data = Text()