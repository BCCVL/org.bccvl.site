import itertools
from collections import Counter
from operator import itemgetter
from datetime import datetime, timedelta
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
        _experiments = _search(
            path=experiments_path,
            object_provides=IExperiment.__identifier__
        )
        self._experiments = [ x._unrestrictedGetObject() for x in _experiments ]

        self._experiments_pub = _search(
            path=experiments_path,
            object_provides=IExperiment.__identifier__,
            review_state='published',
        )

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
        self._institutions = Counter(e.split('@')[-1] for e in emails) 

        return super(StatisticsView, self).__call__()

    def users_total(self):
        return len(self._users)
    
    def users_new(self):
        return 999999
    
    def users_active(self):
        furthest_login_time = datetime.now() - timedelta(days=90)
        last_login_times = (x.getProperty('last_login_time').utcdatetime() for x in self._users)
        return len(
            [x for x in last_login_times if x > furthest_login_time]
        )

    def institutions(self):
        by_institution = itemgetter(0) # sort by key
        return sorted(self._institutions, key=by_institution)

    def institutions_total(self):
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
        experiments = Counter(
            x.__class__.__name__.replace('Experiment','') for x in self._experiments
        )
        by_count = itemgetter(1) # sort by value
        return sorted(experiments, key=by_count, reverse=True)
        
    def algorithm_types(self):
        algorithms = (x.algorithms for x in self._experiments if hasattr(x, 'algorithms'))
        functions = (x.functions for x in self._experiments if hasattr(x, 'functions'))
        flat_functions = (i for y in functions for i in y)
        algorithm_types= Counter(
            x.title for x in itertools.chain(algorithms, flat_functions)
        )
        by_count = itemgetter(1) # sort by value
        return sorted(algorithm_types.iteritems(), key=by_count, reverse=True)
        
    def jobs(self):
        return len(self._jobs)
