from collections import Counter
import json
from operator import itemgetter
from datetime import datetime, timedelta
from Products.CMFCore.utils import getToolByName
from Products.Five.browser import BrowserView
from plone import api
from plone.app.uuid.utils import uuidToCatalogBrain
from plone.app.contenttypes.interfaces import IFolder
from Products.CMFCore.interfaces import ITypeInformation
from zope.component import getUtility
from org.bccvl.site.job.interfaces import IJobTracker
from org.bccvl.site.interfaces import IExperimentJobTracker
from org.bccvl.site.job.interfaces import IJobUtility
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

        EXP_TYPES = ['org.bccvl.content.sdmexperiment',
                     'org.bccvl.content.projectionexperiment',
                     'org.bccvl.content.biodiverseexperiment',
                     'org.bccvl.content.ensemble',
                     'org.bccvl.content.speciestraitsexperiment'
                     ]
        self._jobtool = getUtility(IJobUtility)
        self._jobs = self._jobtool.query(type=EXP_TYPES)

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
        by_institution = itemgetter(0)  # sort by key
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
            [x for x in owners if x.getUserName() not in ('admin', 'bccvl',)]
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
        experiments = Counter(x.portal_type for x in self._experiments)
        return experiments.most_common()

    def experiment_type_title(self, portal_type):
        return getUtility(ITypeInformation, portal_type).Title()

    def experiment_average_runtimes(self):
        runtime = {}
        for x in self._experiments:
            exp = x._unrestrictedGetObject()
            jt = IExperimentJobTracker(exp)
            success = jt.state in (None, 'COMPLETED')
            if not runtime.has_key(x.portal_type):
                runtime[x.portal_type] = {'runtime': 0, 'failed': 0, 'success': 0, 'count': 0,
                                          'title': self.experiment_type_title(x.portal_type)}

            if hasattr(exp, 'runtime'):
                runtime[x.portal_type]['runtime'] += exp.runtime
                runtime[x.portal_type]['count'] += 1
            if success:
                runtime[x.portal_type]['success'] += 1
            else:
                runtime[x.portal_type]['failed'] += 1

        for i in runtime.keys():
            if runtime[i]['count']:
                runtime[i]['runtime'] /= runtime[i]['count']
                runtime[i]['runtime'] = "%.1f" % (runtime[i]['runtime'])
            else:
                runtime[i]['runtime'] = "n/a"
        return runtime

    def algorithm_average_runtimes(self):
        stats = {}

        for x in self._jobs:
            job = self._jobtool.get_job_by_id(x.id)

            if job is None or job.state == 'RUNNING' or job.type not in ['org.bccvl.content.sdmexperiment', 'org.bccvl.content.speciestraitsexperiment']:
                continue
            # Get the runtime each algorithm for each experiement type.
            # An algorithm is mutually exclusive for SDM or Species Traits experiement.
            success = job.state in (None, 'COMPLETED')
            algid = job.function

            # Initialise statistic variables for each algorithm
            if not algid:
                continue

            if not stats.has_key(algid):
                stats[algid] = {'runtime': 0.0, 'count': 0, 'mean': 0.0, 'success': 0,
                                'failed': 0, 'nodata_count': 0, 'nodata_success': 0, 'nodata_failed': 0}

            runtime = -1.0
            if hasattr(job, 'rusage') and job.rusage is not None:
                runtime = job.rusage['rusage'].get('ru_utime', -1.0) + job.rusage['rusage'].get('ru_stime', -1.0)
            if runtime >= 0.0:
                stats[algid]['runtime'] += runtime
                stats[algid]['count'] += 1
                if success:
                    stats[algid]['success'] += 1
                else:
                    stats[algid]['failed'] += 1
            else:
                stats[algid]['nodata_count'] += 1
                if success:
                    stats[algid]['nodata_success'] += 1
                else:
                    stats[algid]['nodata_failed'] += 1

        for i in stats.keys():
            stats[i]['mean'] = "%.1f" % (stats[i]['runtime'] / stats[i]['count'])
            stats[i]['count'] += stats[i]['nodata_count']
            stats[i]['success'] += stats[i]['nodata_success']
            stats[i]['failed'] += stats[i]['nodata_failed']
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
        # FIXME: this counts experiment objects... the number of result objects per algorithm
        #        may be different (esp. if experiment has been saved but not started or has
        #        been re-run multiple times)
        # FIXME: we ignore removed func objects here... they should probably still show up somehow?
        func_obs = (self.get_func_obj(x) for x in func_ids())
        algorithm_types = Counter(func_ob.getId for func_ob in func_obs if func_ob)
        return algorithm_types.most_common()

    def get_func_obj(self, uuid=None, funcid=None):
        if (funcid is None or funcid in self.func_obj_cache) and uuid is not None:
            brain = uuidToCatalogBrain(uuid)
            if brain is None:
                return None
            self.func_obj_cache[brain.getId] = brain
            return self.func_obj_cache[brain.getId]
        return self.func_obj_cache[funcid]

    def jobs(self):
        return len(self._jobs)
