from zope.interface import Interface
from plone.directives import form

class IJobTracker(Interface):

    def start_job(request):
        """
        start this job
        """

    def get_job():
        """
        return the job instance
        """


class IExperiment(form.Schema):
    """Base Experiment Class"""

