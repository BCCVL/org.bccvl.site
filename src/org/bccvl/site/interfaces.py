from zope.interface import Interface


class IDownloadInfo(Interface):
    """Return a dictionary with infos to download a file.

    The dictionary has the following keys:

    filename ... the naem of the file
    url      ... the url to fetch it from
    alturl   ... a tuple of alternative urls
    """


class IJobTracker(Interface):

    def start_job(request):
        """
        start this job
        """

    def get_job():
        """
        return the job instance
        """


class IComputeMethod(Interface):

    def __call__(result, toolkit):
        """
        execute a compute method
        """
