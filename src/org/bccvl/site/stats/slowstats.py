from collections import Counter
from operator import itemgetter
from datetime import datetime, timedelta
from Products.Five.browser import BrowserView
from plone import api
from Products.CMFCore.interfaces import ITypeInformation
from zope.component import getUtility
from org.bccvl.site.content.function import IFunction
from org.bccvl.site.job.interfaces import IJobUtility
from ..content.interfaces import (
    IExperiment,
    IDataset,
    IRemoteDataset,
)


class StatisticsView(BrowserView):

    def __call__(self):
        # TODO: shouldn't get experiment path via context... could be anything
        self.experiments_path = dict(query='/'.join(self.context.experiments.getPhysicalPath()))
        self.datasets_path = dict(query='/'.join(self.context.datasets.getPhysicalPath()))

        self.exp_types = {}
        for exp_type in ['org.bccvl.content.sdmexperiment',
                         'org.bccvl.content.projectionexperiment',
                         'org.bccvl.content.biodiverseexperiment',
                         'org.bccvl.content.ensemble',
                         'org.bccvl.content.speciestraitsexperiment',
                         'org.bccvl.content.speciestraitstemporalexperiment',
                         'org.bccvl.content.mmexperiment',
                         'org.bccvl.content.msdmexperiment',
                         ]:
            self.exp_types[exp_type] = getUtility(ITypeInformation, exp_type).Title()

        pc = api.portal.get_tool("portal_catalog")
        self.func_by_uuid = {}
        self.func_by_id = {}
        for func in pc.unrestrictedSearchResults(object_provides=IFunction.__identifier__):
            self.func_by_uuid[func.UID] = func.Title
            self.func_by_id[func.getId] = func.UID

        self._user_stats = None
        self._dataset_stats = None
        self._experiments_stats = None
        self._job_stats = None

        return super(StatisticsView, self).__call__()

    def gen_user_list(self):
        portal_membership = api.portal.get_tool('portal_membership')
        for userid in portal_membership.listMemberIds():
            yield portal_membership.getMemberById(userid)

    def get_user_stats(self):
        if self._user_stats:
            return self._user_stats
        users_count = 0
        users_active = 0
        institutions = Counter()

        # active is if logged in within the last 90 days
        furthest_login_time = datetime.now() - timedelta(days=90)
        portal_membership = api.portal.get_tool('portal_membership')
        for userid in portal_membership.listMemberIds():
            # load one user at a time to save memory
            users_count += 1
            member = portal_membership.getMemberById(userid)
            if member.getProperty('last_login_time').utcdatetime() > furthest_login_time:
                users_active += 1
            institutions[member.getProperty('email').split('@')[-1]] += 1

        # number of experiments run per user:
        user_experiments = Counter()
        pc = api.portal.get_tool('portal_catalog')
        for exp in pc.unrestrictedSearchResults(path=self.experiments_path,
                                                object_provides=IExperiment.__identifier__):
            user_experiments[exp.Creator] += 1
        self._user_stats = {
            'users': {
                'count': users_count,
                'active': users_active
            },
            'institutions': {
                'count': len(institutions),
                'domains': sorted(institutions.iteritems(), key=itemgetter(0))
            },
            'user_experiments': user_experiments
        }
        return self._user_stats

    def users_total(self):
        stats = self.get_user_stats()
        return stats['users']['count']

    def users_new(self):
        return 999999

    def users_experiments(self):
        stats = self.get_user_stats()
        return stats['user_experiments']

    def users_active(self):
        stats = self.get_user_stats()
        return stats['users']['active']

    def institutions(self):
        stats = self.get_user_stats()
        return stats['institutions']['domains']

    def institutions_total(self):
        stats = self.get_user_stats()
        return stats['institutions']['count']

    def get_dataset_stats(self):
        if self._dataset_stats:
            return self._dataset_stats

        ds_count = 0
        ds_added_remote = 0
        ds_added_local = 0
        ds_added_users = 0
        ds_added_failed = 0
        ds_generated = 0

        pc = api.portal.get_tool('portal_catalog')
        # stats for all datasets in datasets section
        for ds in pc.unrestrictedSearchResults(path=self.datasets_path,
                                               object_provides=IDataset.__identifier__,  #, IRemoteDataset.__identifier)
                                               job_state=('COMPLETED', 'QUEUED', 'RUNNING', 'FAILED')):
            ds_count += 1
            if ds.portal_type == 'org.bccvl.content.remotedataset':
                ds_added_remote += 1
            else:
                ds_added_local += 1
            # we should rather check ds._unrestrictedGetObject().getOwner().getUser().id ... and ideally any user that has a local role 'Owner' for this object.
            # but that get's very expensive
            if ds.Creator not in ('bccvl', 'admin'):
                ds_added_users += 1
            if ds.job_state == 'FAILED':
                ds_added_failed += 1
        # stats for all datasets in experiments section
        ds_generated = len(pc.unrestrictedSearchResults(path=self.experiments_path,
                                                        object_provides=IDataset.__identifier__))

        self._dataset_stats = {
            'datasets': {
                'count': ds_count,
                'generated': ds_generated,
                'added': {
                    'remote': ds_added_remote,
                    'local': ds_added_local,
                    'users': ds_added_users,
                    'failed': ds_added_failed
                }
            }
        }
        return self._dataset_stats

    def datasets(self):
        stats = self.get_dataset_stats()
        return stats['datasets']['count']

    def datasets_added(self):
        stats = self.get_dataset_stats()
        return stats['datasets']['added']['remote'] + stats['datasets']['added']['local']

    def datasets_added_remote(self):
        stats = self.get_dataset_stats()
        return stats['datasets']['added']['remote']

    def datasets_added_local(self):
        stats = self.get_dataset_stats()
        return stats['datasets']['added']['local']

    def datasets_added_users(self):
        stats = self.get_dataset_stats()
        return stats['datasets']['added']['users']

    def datasets_added_failed(self):
        stats = self.get_dataset_stats()
        return stats['datasets']['added']['failed']

    def datasets_generated(self):
        stats = self.get_dataset_stats()
        return stats['datasets']['generated']

    def get_experiments_stats(self):
        if self._experiments_stats:
            return self._experiments_stats
        exps_count = 0
        exps_count_pub = 0
        exps_types = Counter()
        runtime = {}
        algorithms = Counter()

        pc = api.portal.get_tool('portal_catalog')
        # stats for all datasets in datasets section
        for exp in pc.unrestrictedSearchResults(path=self.experiments_path,
                                                object_provides=IExperiment.__identifier__):
            exps_count += 1
            if exp.review_state == 'published':
                exps_count_pub += 1
            exps_types[exp.portal_type] += 1
            # collect runtime stats
            # portal_type seen first time
            if exp.portal_type not in runtime:
                runtime[exp.portal_type] = {
                    'runtime': 0,
                    'failed': 0,
                    'success': 0,
                    'count': 0
                }
            obj = exp._unrestrictedGetObject()
            if hasattr(obj, 'runtime'):
                runtime[exp.portal_type]['runtime'] += obj.runtime
                runtime[exp.portal_type]['count'] += 1
            if (exp.job_state in (None, 'COMPLETED', 'FINISHED')):
                runtime[exp.portal_type]['success'] += 1
            elif (exp.job_state in ('RUNNING',)):
                # ignore running experiments
                pass
            else:
                runtime[exp.portal_type]['failed'] += 1
            # collect per algorithm stats
            algouuids = []
            if hasattr(obj, 'functions'):
                algouuids = obj.functions
            if hasattr(obj, 'algorithm'):
                algouuids = [obj.algorithm]
            for algouuid in algouuids:
                if algouuid not in self.func_by_uuid:
                    # ignore unknown function uuids
                    continue
                algorithms[algouuid] += 1

        # calc runtime summaries
        for pt in runtime.keys():
            if runtime[pt]['count']:
                runtime[pt]['runtime'] /= runtime[pt]['count']
                runtime[pt]['runtime'] = "{:.1f}".format(runtime[pt]['runtime'])
            else:
                runtime[pt]['runtime'] = 'n/a'

        self._experiments_stats = {
            'count': exps_count,
            'count_pub': exps_count_pub,
            'types': exps_types.most_common(),
            'runtime': runtime,
            'algorithms': algorithms.most_common()
        }
        return self._experiments_stats

    def experiments_run(self):
        stats = self.get_experiments_stats()
        return stats['count']

    def experiments_published(self):
        stats = self.get_experiments_stats()
        return stats['count_pub']

    def experiment_types(self):
        stats = self.get_experiments_stats()
        return stats['types']

    def experiment_average_runtimes(self):
        stats = self.get_experiments_stats()
        return stats['runtime']

    def algorithm_types(self):
        stats = self.get_experiments_stats()
        return stats['algorithms']

    def get_job_stats(self):
        if self._job_stats:
            return self._job_stats
        jobtool = getUtility(IJobUtility)
        count = 0
        stats = {}

        for job in jobtool.query(type=self.exp_types.keys()):
            count += 1
            obj = jobtool.get_job_by_id(job.id)
            if obj is None or obj.state == 'RUNNING':
                continue

            success = obj.state in (None, 'COMPLETED', 'FINISHED')
            running = obj.state in ('RUNNING', )
            algouuid = self.func_by_id.get(obj.function, None)
            if not algouuid:
                # ignore unknown algorithm
                continue
            # algo seen first time
            if not stats.has_key(algouuid):
                stats[algouuid] = {
                    'runtime': 0.0,
                    'count': 0,
                    'mean': 0,
                    'success': 0,
                    'failed': 0,
                    'nodata_count': 0,
                    'nodata_success': 0,
                    'nodata_failed': 0
                }
            runtime = -1.0
            if hasattr(obj, 'rusage') and obj.rusage is not None:
                rusage = obj.rusage['rusage']
                if rusage.get('ru_utime') is None or rusage.get('ru_stime') is None:
                    runtime = -1.0
                else:
                    runtime = rusage['ru_utime'] + rusage['ru_stime']
            if runtime >= 0.0:
                stats[algouuid]['runtime'] += runtime
                stats[algouuid]['count'] += 1
                if success:
                    stats[algouuid]['success'] += 1
                elif running:
                    # ignore running jobs
                    pass
                else:
                    stats[algouuid]['failed'] += 1
            else:
                stats[algouuid]['nodata_count'] += 1
                if success:
                    stats[algouuid]['nodata_success'] += 1
                elif running:
                    # ignore running jobs
                    pass
                else:
                    stats[algouuid]['nodata_failed'] += 1
        # calc summaries
        for aid in stats.keys():
            if stats[aid]['count']:
                stats[aid]['mean'] = "{:.1f}".format(stats[aid]['runtime'] / stats[aid]['count'])
            else:
                stats[aid]['mean'] = 'n/a'
            stats[aid]['count'] += stats[aid]['nodata_count']
            stats[aid]['success'] += stats[aid]['nodata_success']
            stats[aid]['failed'] += stats[aid]['nodata_failed']
        self._job_stats = {
            'count': count,
            'average_runtimes': stats
        }
        return self._job_stats

    def algorithm_average_runtimes(self):
        stats = self.get_job_stats()
        return stats['average_runtimes']

    def jobs(self):
        # all experiment related jobs
        stats = self.get_job_stats()
        return stats['count']
