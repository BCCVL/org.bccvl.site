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
