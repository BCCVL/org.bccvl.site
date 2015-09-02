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
        self.func_obj_cache = {}
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
        
    def experiment_average_runtimes(self):
        runtime = {}
        count = {}
        for x in self._experiments:
            exp = x._unrestrictedGetObject()
            if not hasattr(exp, 'runtime'):
                continue
            if runtime.has_key(x.Type):
                runtime[x.Type] += exp.runtime
                count[x.Type] += 1
            else:
                runtime[x.Type] = exp.runtime
                count[x.Type] = 1
        for tp in runtime.keys():
            runtime[tp] /= count[tp]
            runtime[tp] = "%.1f seconds" %(runtime[tp])
        return runtime                 

    def algorithm_average_runtimes(self):
        runtime_sum = {}
        count = {}
        runtime_mean = {}
        for x in self._experiments:                
            #if x.Type not in ['org.bccvl.content.sdmexperiment', 'org.bccvl.content.speciestraitsexperiment']:
            if x.Type not in ['SDM Experiment', 'Species Traits Modelling']:
                continue
            # Get the runtime each algorithm for each experiement type from the result file
            # An algorithm is mutually exclusive for SDM or Species Traits experiement.
            exp = x._unrestrictedGetObject()
            for r in exp.values():                
                import json
                algid = r.job_params.get('function') or r.job_params.get('algorithm')
                # Initialise statistic variables for each algorithm
                if algid:
                    runtime_sum[algid] = 0.0
                    count[algid] = 0
                    runtime_mean[algid] = 0.0
                else:
                    continue                    
                if not r.has_key('pstats.json'):
                    continue
                js = json.loads(r['pstats.json'].file.data)
                runtime = js['rusage'].get('ru_utime', -1.0) + js['rusage'].get('ru_stime', -1.0)
                if runtime >= 0.0:
                    runtime_sum[algid] += runtime
                    count[algid] += 1
                    runtime_mean[algid] = runtime_sum[algid]/count[algid]
                    
        for i in runtime_mean.keys():
            runtime_mean[i] = "%.1f seconds" %(runtime_mean[i])
        return runtime_mean

    def algorithm_types(self):
        def func_ids():
            for x in self._experiments:
                exp = x._unrestrictedGetObject()
                if hasattr(exp, 'functions'):
                    for funcid in exp.functions:
                        yield funcid
                if hasattr(exp, 'algorithm'):
                    yield exp.algorithm
        
        algorithm_types = Counter(self.get_func_obj(x).getId for x in func_ids())
        return algorithm_types.most_common()

    def get_func_obj(self, uuid=None, funcid=None):
        if (funcid is None or funcid in self.func_obj_cache) and uuid is not None:
            brain = uuidToCatalogBrain(uuid)
            self.func_obj_cache[brain.getId] = brain
            return self.func_obj_cache[brain.getId]
        return self.func_obj_cache[funcid]

    def jobs(self):
        return len(self._jobs)
