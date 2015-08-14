from collections import Counter
from operator import itemgetter
from datetime import datetime, timedelta
from Products.CMFCore.utils import getToolByName
from Products.Five.browser import BrowserView
from plone import api
from plone.app.uuid.utils import uuidToCatalogBrain
from plone.app.contenttypes.interfaces import IFolder
from ..content.interfaces import (
    IExperiment,
    IDataset,
    IRemoteDataset,
)

class StatisticsView(BrowserView):
    def __call__(self):
        _search = getToolByName(self.context, 'portal_catalog').unrestrictedSearchResults

        experiments_path = dict(query='/'.join(self.context.experiments.getPhysicalPath()))
        self._experiments = _search(
            path=experiments_path,
            object_provides=IExperiment.__identifier__
        )
        # self._experiments = [ x._unrestrictedGetObject() for x in _experiments ]

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

    def users_experiments(self):
        # returns a dict with user id's as key and number of experiments run
        return Counter(x.Creator for x in self._experiments)

    def users_active(self):
        furthest_login_time = datetime.now() - timedelta(days=90)
        last_login_times = (x.getProperty('last_login_time').utcdatetime() for x in self._users)
        return len(
            [x for x in last_login_times if x > furthest_login_time]
        )

    def institutions(self):
        by_institution = itemgetter(0) # sort by key
        return sorted(self._institutions.iteritems(), key=by_institution)

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

    def datasets_generated(self):
        return len(self._datasets_gen)

    def experiments_run(self):
        return len(self._experiments)

    def experiments_published(self):
        return len(self._experiments_pub)

    def experiment_types(self):
        experiments = Counter(x.Type for x in self._experiments)
        return experiments.most_common()

    def algorithm_types(self):
        func_obj_cache = {}

        def func_ids():
            for x in self._experiments:
                exp = x._unrestrictedGetObject()
                if hasattr(exp, 'functions'):
                    for funcid in exp.functions:
                        yield funcid
                if hasattr(exp, 'algorithm'):
                    yield exp.algorithm

        def get_func_obj(funcid):
            if funcid not in func_obj_cache:
                func_obj_cache[funcid] = uuidToCatalogBrain(funcid)
            return func_obj_cache[funcid]

        algorithm_types = Counter(get_func_obj(x).Title for x in func_ids())
        return algorithm_types.most_common()

    def jobs(self):
        return len(self._jobs)
