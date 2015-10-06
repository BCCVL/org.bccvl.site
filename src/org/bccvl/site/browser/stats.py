from collections import Counter
import json
from operator import itemgetter
from datetime import datetime, timedelta
from Products.CMFCore.utils import getToolByName
from Products.Five.browser import BrowserView
from plone import api
from plone.app.uuid.utils import uuidToCatalogBrain
from plone.app.contenttypes.interfaces import IFolder
from org.bccvl.site.interfaces import IJobTracker
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
        for x in self._experiments:
            exp = x._unrestrictedGetObject()
            jt = IJobTracker(exp)
            success = jt.state in (None, 'COMPLETED')
            if not runtime.has_key(x.Type):
                runtime[x.Type] = {'runtime': 0, 'failed': 0, 'success': 0, 'count': 0}

            if hasattr(exp, 'runtime'):
                runtime[x.Type]['runtime'] += exp.runtime
                runtime[x.Type]['count'] += 1
            if success:
                runtime[x.Type]['success'] += 1
            else:
                runtime[x.Type]['failed'] += 1

        for i in runtime.keys():
            if runtime[i]['count']:
                runtime[i]['runtime'] /= runtime[i]['count']
                runtime[i]['runtime'] = "%.1f" %(runtime[i]['runtime'])
            else:
                runtime[i]['runtime'] = "n/a"
        return runtime

    def algorithm_average_runtimes(self):
        stats = {}

        for x in self._experiments:
            #if x.Type not in ['org.bccvl.content.sdmexperiment', 'org.bccvl.content.speciestraitsexperiment']:
            if x.Type not in ['SDM Experiment', 'Species Traits Modelling']:
                continue
            # Get the runtime each algorithm for each experiement type from the result file
            # An algorithm is mutually exclusive for SDM or Species Traits experiement.
            exp = x._unrestrictedGetObject()
            for v in exp.values():
                jt = IJobTracker(v)
                success = jt.state in (None, 'COMPLETED')

                algid = v.job_params.get('function') or v.job_params.get('algorithm')
                # Initialise statistic variables for each algorithm
                if not algid:
                    continue

                if not stats.has_key(algid):
                    stats[algid] = {'runtime' : 0.0, 'count' : 0, 'mean' : 0.0, 'success' : 0, 'failed' : 0}

                if not v.has_key('pstats.json'):
                    continue

                js = json.loads(v['pstats.json'].file.data)
                runtime = js['rusage'].get('ru_utime', -1.0) + js['rusage'].get('ru_stime', -1.0)
                if runtime >= 0.0:
                    stats[algid]['runtime'] += runtime
                    stats[algid]['count'] += 1
                    stats[algid]['mean'] = stats[algid]['runtime']/stats[algid]['count']
                    if success:
                        stats[algid]['success'] += 1
                    else:
                        stats[algid]['failed'] += 1
        for i in stats.keys():
            stats[i]['mean'] = "%.1f" %(stats[i]['mean'])
        return stats

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
