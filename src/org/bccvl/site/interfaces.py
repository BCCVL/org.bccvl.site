from zope.interface import Interface


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
