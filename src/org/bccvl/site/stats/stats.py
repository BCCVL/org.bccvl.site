from collections import Counter
from operator import itemgetter
from datetime import datetime, timedelta
from Products.Five.browser import BrowserView
from plone import api
from Products.CMFCore.interfaces import ITypeInformation
from zope.component import getUtility
from org.bccvl.site.content.function import IFunction
from org.bccvl.site.job.interfaces import IJobUtility
from org.bccvl.site.stats.interfaces import IStatsUtility
from ..content.interfaces import (
    IExperiment,
    IDataset,
    IRemoteDataset,
)


def dict_get(d, keys, default):
    val = d
    for key in keys:
        val = val.get(key)
        if val is None:
            return default
    if hasattr(val, 'value'):
        return val.value
    return val


import json
from persistent import Persistent
from persistent.dict import PersistentDict

class MyJSONEncoder(json.JSONEncoder):

    def default(self, obj):
        # in stats we only have sub classes of Persistent, PersistentDict
        # and PCounters. (PCounters are Persistent as well)
        if hasattr(obj, 'value'):
            return obj.value
        if isinstance(obj, (Persistent, PersistentDict)):
            return dict(obj)
        # raise TypeError
        return super(MyJSONEncoder, self).default(obj)


class StatsJSONView(BrowserView):

    def __call__(self):
        stats = getUtility(IStatsUtility).stats
        self.request.response.setHeader('Content-Type', 'application/json')
        return json.dumps(stats, cls=MyJSONEncoder, indent=4)


class StatisticsView(BrowserView):

    # cache
    _user_stats = None
    _dataset_stats = None
    _experiment_stats = None
    _job_stats = None

    def __call__(self):
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

        self.stats = getUtility(IStatsUtility).stats
        return super(StatisticsView, self).__call__()

    def gen_user_list(self):
        portal_membership = api.portal.get_tool('portal_membership')
        for userid in portal_membership.listMemberIds():
            yield portal_membership.getMemberById(userid)

    def user_stats(self):
        if self._user_stats:
            return self._user_stats
        users_count = 0
        users_active = 0
        institutions = Counter()
        user_experiments = {}

        # active is if logged in within the last 90 days
        furthest_login_time = datetime.now() - timedelta(days=90)
        for member in self.gen_user_list():
            users_count += 1
            if member.getProperty('last_login_time').utcdatetime() > furthest_login_time:
                users_active += 1
            institutions[member.getProperty('email').split('@')[-1]] += 1
            # aggregate created experiments per user
            user_exp_stats = dict_get(
                self.stats,
                ['users', member.getId()],
                {}
            )
            user_experiments[member.getId()] = sum(
                dict_get(x, ['CREATED', 'count'], 0)
                for x in user_exp_stats.values()
            )

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

    def dataset_stats(self):
        if self._dataset_stats:
            return self._dataset_stats

        dsstats = self.stats['datasets']
        self._dataset_stats = {
            # TODO:  is count being used at all?
            'count': (
                sum(
                    dict_get(dsstats, ['type', portal_type, 'CREATED'], 0)
                    for portal_type in (
                        'org.bccvl.content.dataset',
                        'org.bccvl.content.remotedataset',
                        'org.bccvl.content.multispeciesdataset'
                    )
                )
            ),
            'generated': (
                dict_get(dsstats, ['source', 'experiment', 'CREATED'], 0)
            ),
            'added': {
                # FIXME: remote / local counts everyting (including experiment results)
                'remote': dict_get(dsstats, ['type', 'org.bccvl.content.remotedataset', 'CREATED'], 0),
                'local': (
                    dict_get(dsstats, ['type', 'org.bccvl.content.dataset', 'CREATED'], 0) +
                    dict_get(dsstats, ['type', 'org.bccvl.content.multispeciesdataset', 'CREATED'], 0)
                ),
                'users': sum(
                    dict_get(dsstats, ['source', key, 'CREATED'], 0)
                    for key in ('ala', 'gbif', 'aekos', 'upload')
                ),
                # 'failed': sum(
                #     dsstats['org.bccvl.content.remotedataset']['FAILED'],
                #     dsstats['org.bccvl.content.dataset']['FAILED']
                # )
            }
        }
        return self._dataset_stats

    def experiment_stats(self):
        if self._experiment_stats:
            return self._experiment_stats

        expstats = self.stats['experiments']

        exp_types = Counter()
        runtimes = {}
        for portal_type in expstats.keys():
            count = (dict_get(expstats, [portal_type, 'COMPLETED', 'count'], 0) +
                     dict_get(expstats, [portal_type, 'FINISHED', 'count'], 0))
            runtime = (dict_get(expstats, [portal_type, 'COMPLETED', 'runtime'], 0) +
                       dict_get(expstats, [portal_type, 'FINISHED', 'runtime'], 0))
            failed = dict_get(expstats, [portal_type, 'FAILED', 'count'], 0)

            exp_types[portal_type] = dict_get(expstats, [portal_type, 'CREATED', 'count'], 0)
            if count == 0:
                runtime = u'n/a'
            else:
                runtime = u'{:.1f}'.format(runtime / count)
            runtimes[portal_type] = {
                'runtime': runtime,
                'failed': failed,
                'success': count,
                'count': dict_get(expstats, [portal_type, 'CREATED', 'count'], 0)
            }

        self._experiment_stats = {
            'count': sum(
                dict_get(x, ['CREATED', 'count'], 0) for x in expstats.values()
            ),
            'types': exp_types.most_common(),
            'runtime': runtimes
        }
        return self._experiment_stats

    def job_stats(self):
        if self._job_stats:
            return self._job_stats

        jobstats = self.stats['jobs']
        stats = {}
        count_all = 0

        for function, jstats in jobstats.items():
            algouuid = self.func_by_id.get(function, None)
            if not algouuid:
                # ignore unknown algorithms
                continue
            runtime = (dict_get(jstats, ['COMPLETED', 'runtime'], 0) +
                       dict_get(jstats, ['FINISHED', 'runtime'], 0))
            count = (dict_get(jstats, ['COMPLETED', 'count'], 0) +
                     dict_get(jstats, ['FINISHED', 'count'], 0))
            if count == 0:
                mean_runtime = 'n/a'
            else:
                mean_runtime = '{:.1f}'.format(runtime / count)
            stats[algouuid] = {
                'runtime': (dict_get(jstats, ['COMPLETED', 'runtime'], 0) +
                            dict_get(jstats, ['FINISHED', 'runtime'], 0)),
                'count': dict_get(jstats, ['CREATED', 'count'], 0),
                'mean': mean_runtime,
                'success': (dict_get(jstats, ['COMPLETED', 'count'], 0) +
                            dict_get(jstats, ['FINISHED', 'count'], 0)),
                'failed': dict_get(jstats, ['FAILED', 'count'], 0),
                # 'nodata_count': 0,
                # 'nodata_success': 0,
                # 'nodata_failed': 0
            }
            count_all += dict_get(jstats, ['CREATED', 'count'], 0)

        self._job_stats = {
            'count': count_all,
            'average_runtimes': stats
        }
        return self._job_stats
