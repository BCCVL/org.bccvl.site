from zope.interface import Interface


class IStatsUtility(Interface):

    def count_dataset(source, portal_type, state=None, date=None):
        """Count dataset stats
        source      ... ala, gbif, aekos, upload, experiment
        portal_type ... type of dataset
        state       ... count per state ('COMPLETED', 'FAILED', 'REMOVED')
                        None means, created
                        anything else counts a dataset related job
                        if a dataset job fails, but succeeds when retried,
                        he failed counter won't be decremented
        date        ... date of event, we only collect per year/month
        """

    def count_experiment(user, portal_type,
                         runtime=0, jobs=0, state=None, date=None):
        """Count experiment stats
        user        ... user id
        portal_type ... type of experiment
        runtime     ... overall runtime of experiment
        jobs        ... number of jobs in experiment
        state       ... count per state ('COMPLETED', 'FINISHED', FAILED', 'REMOVED')
                        None means, created
        date        ... date of event, we only collect per year/month
        """

    def count_job(self, function, portal_type,
                  runtime=0, state=None, date=None):
        """Count Job stats
        function    ... algorithm/func id
        portal_type ... job/portal type
        runtime     ... overall runtime of job
        state       ... count per state ('COMPLETED', 'FAILED')
                        None means, created
        date        ... date of event, we only collect per year/month
        """
