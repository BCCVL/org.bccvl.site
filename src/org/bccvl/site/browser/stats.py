from collections import Counter
from Products.CMFCore.utils import getToolByName
from Products.Five.browser import BrowserView
from plone import api
from plone.app.contenttypes.interfaces import IFolder
from ..content.interfaces import (
    IExperiment, 
    IDataset,
    IRemoteDataset,
)

def _count_classes(result_seq):
    objects = (x._unrestrictedGetObject() for x in result_seq)
    return Counter(
        o.__class__.__name__ for o in objects
    )

class StatisticsView(BrowserView):
    def __call__(self):
        _search = getToolByName(self.context, 'portal_catalog').unrestrictedSearchResults
        
        experiments_path = dict(query='/'.join(self.context.experiments.getPhysicalPath()))
        self._experiments = _search(
            path=experiments_path,
            object_provides=IExperiment.__identifier__
        )
        self._experiments_pub = _search(
            path=experiments_path,
            object_provides=IExperiment.__identifier__,
            review_state='published',
        )

        # XXX: loop through experiments & use the physical path of each to ensure
        # only folders in experiments are included?
        self._jobs = _search(
            path=experiments_path,
            object_provides=IFolder.__identifier__,
        )

        datasets_path = dict(query='/'.join(self.context.datasets.getPhysicalPath()))
        self._datasets_added = _search(
            path=datasets_path,
            object_provides=IDataset.__identifier__,
            job_state=('COMPLETED', 'QUEUED', 'RUNNING'),
        )
        self._datasets_added_remote = _search(
            path=datasets_path,
            object_provides=IRemoteDataset.__identifier__,
            job_state=('COMPLETED', 'QUEUED', 'RUNNING'),
        )
        self._datasets_added_failed = _search(
            path=datasets_path,
            object_provides=IDataset.__identifier__,
            job_state='FAILED',
        ) 

        self._datasets_gen = _search(
            path=experiments_path,
            object_provides=IDataset.__identifier__,
        )

        self._users = api.user.get_users()
        emails = (u.getProperty('email') for u in self._users)
        domains = set(e.split('@')[-1] for e in emails)
        self._institutions = list(domains)

        return super(StatisticsView, self).__call__()

    def users(self):
        return len(self._users)
    
    def institutions(self):
        return len(self._institutions)
    
    def datasets(self):
        return self.datasets_added() + self.datasets_generated()

    def datasets_added(self):
        return len(self._datasets_added)

    def datasets_added_remote(self):
        return len(self._datasets_added_remote)

    def datasets_added_local(self):
        return self.datasets_added() - self.datasets_added_remote()

    def datasets_added_users(self):
        datasets = (x._unrestrictedGetObject() for x in self._datasets_added)
        owners = (x.getOwner() for x in datasets)
        return len(
            [ x for x in owners if x.getUserName() not in ('admin', 'bccvl',) ]
        )

    def datasets_added_failed(self):
        return len(self._datasets_added_failed)
    
    def datasets_added_types(self):
        return _count_classes(self._datasets_added).iteritems()

    def datasets_generated(self):
        return len(self._datasets_gen)
    
    def experiments_run(self):
        return len(self._experiments)
    
    def experiments_published(self):
        return len(self._experiments_pub)
    
    def experiment_types(self):
        return _count_classes(self._experiments).iteritems()
        
    def jobs(self):
        return len(self._jobs)
