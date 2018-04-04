import datetime

from BTrees.OOBTree import OOBTree
from persistent.dict import PersistentDict
from persistent import Persistent
from plone import api
from zope.annotation.interfaces import IAnnotations
from zope.interface import implementer

from org.bccvl.site.stats.interfaces import IStatsUtility


# Use custom classes to store a value that can only increase
class PCounter(Persistent):

    _val = 0

    @property
    def value(self):
        return self._val

    def inc(self, val=1):
        self._val += val

    def _p_resolveConflict(self, oldState, savedState, newState):
        """
        oldState   ... state of object in current transaction before changes
                       may be modified
        savedState ... state of object saved by other transaction
                       may be modified
        newState   ... new state of object in current transaction
                       don't modiy
        """
        oldState['_val'] = (
            # other new state
            savedState.get('_val', 0) +
            # + changes I made
            newState.get('_val', 0) -
            oldState.get('_val', 0)
        )
        return oldState


class BaseStats(Persistent):

    def __getitem__(self, key):
        if key in self._stats:
            return self._stats[key]
        raise KeyError(key)

    def get(self, key, default=None):
        try:
            return self._stats[key]
        except KeyError:
            return default

    def keys(self):
        return self._stats.keys()

    def items(self):
        return self._stats.items()

    def values(self):
        return self._stats.values()


class DatasetStats(BaseStats):
    # TODO: add top level keys .... by_source / by_portal_type ...
    #       makes it easier to aggregate counts
    #       alternative ... change 'datasets' key to dataset_types, dataset_sources
    # datasets:
    #    source:
    #      <source>: ... ala, gbif, aekos, upload, experiment
    #        CREATED:      ... overall count
    #        <state>       ... count by state
    #        <year>:
    #          <month>:
    #             CREATED: ... overall count by year/month
    #             <state>: ... count by state by year/month
    #    type:
    #      <portal_type>:
    #        CREATED:      ... overall count
    #        <state>:      ... count by state
    #        <year>:
    #          <month>:
    #             CREATED: ... over all count
    #             <state>: ... count by state by year/month

    def __init__(self):
        self._stats = PersistentDict({
            'source': PersistentDict(),
            'type': PersistentDict()
        })

    def inc(self, source, portal_type, state, date):
        # per source stats
        sstat = self._stats['source'].setdefault(source, PersistentDict())
        sstat.setdefault(state, PCounter()).inc()
        # years
        ystat = sstat.setdefault(date.year, PersistentDict())
        # months
        mstat = ystat.setdefault(date.month, PersistentDict())
        mstat.setdefault(state, PCounter()).inc()
        # per type stats
        pstat = self._stats['type'].setdefault(portal_type, PersistentDict())
        pstat.setdefault(state, PCounter()).inc()
        # years
        ystat = pstat.setdefault(date.year, PersistentDict())
        # months
        mstat = ystat.setdefault(date.month, PersistentDict())
        mstat.setdefault(state, PCounter()).inc()


class ExperimentStats(BaseStats):
    # experiments
    #    <portal_type>
    #        jobs:     ... overall number of jobs
    #        CREATED:
    #          count:  ... overall count
    #          runtime: ... should always be 0
    #        <state>
    #          count:  ... count per state
    #          runtime ... runtime per state
    #        <year>:
    #          <month>:
    #            jobs:      ... overall number of jobs within experiment
    #            CREATED:
    #              count:   ... overall count by year/month
    #              runtime: ... should always be 0
    #            <state>:
    #              count:   ... count yer state by year/month
    #              runtime: ... runtime per state by year/month

    def __init__(self):
        self._stats = PersistentDict()

    def inc(self, portal_type, runtime, state, date):
        # experiment type stats
        expstats = self._stats.setdefault(portal_type, PersistentDict())
        # per state stats
        statestats = expstats.setdefault(state, PersistentDict())
        statestats.setdefault('count', PCounter()).inc()
        statestats.setdefault('runtime', PCounter()).inc(runtime)
        # years
        ystat = expstats.setdefault(date.year, PersistentDict())
        # months
        mstat = ystat.setdefault(date.month, PersistentDict())
        # per state stats
        statestats = mstat.setdefault(state, PersistentDict())
        statestats.setdefault('count', PCounter()).inc()
        statestats.setdefault('runtime', PCounter()).inc(runtime)


class JobStats(BaseStats):
    # jobs:
    #    <job_type>:    ... the algorithm id (or content type)
    #      CREATED:
    #        count:     ... over all count
    #        runtime:   ... should always be 0
    #      <state>:
    #        count:     ... count per state
    #        runtime:   ... over all runtime per state
    #      <year>:
    #        <month>:
    #          CREATED:
    #            count:
    #            runtime: ... always 0
    #          <state>:
    #            count:
    #            runtime:

    def __init__(self):
        self._stats = PersistentDict()

    def inc(self, function, portal_type, runtime, state, date):
        # count jobs per type
        if portal_type:
            jobstats = self._stats.setdefault(portal_type, PersistentDict())
            statestats = jobstats.setdefault(state, PersistentDict())
            statestats.setdefault('count', PCounter()).inc()
            statestats.setdefault('runtime', PCounter()).inc(runtime)
            # years/months
            ystats = jobstats.setdefault(date.year, PersistentDict())
            mstats = ystats.setdefault(date.month, PersistentDict())
            statestats = mstats.setdefault(state, PersistentDict())
            statestats.setdefault('count', PCounter()).inc()
            statestats.setdefault('runtime', PCounter()).inc(runtime)
        if function:
            # count jobs per function
            jobstats = self._stats.setdefault(function, PersistentDict())
            statestats = jobstats.setdefault(state, PersistentDict())
            statestats.setdefault('count', PCounter()).inc()
            statestats.setdefault('runtime', PCounter()).inc(runtime)
            # years/months
            ystats = jobstats.setdefault(date.year, PersistentDict())
            mstats = ystats.setdefault(date.month, PersistentDict())
            statestats = mstats.setdefault(state, PersistentDict())
            statestats.setdefault('count', PCounter()).inc()
            statestats.setdefault('runtime', PCounter()).inc(runtime)


def init_stats():
    """Setup stats storage.

    A simple OOBTree
    """
    portal = api.portal.get()
    annotations = IAnnotations(portal)
    annotations.pop('org.bccvl.site.stats', None)
    if 'org.bccvl.site.stats' not in annotations:
        stats = PersistentDict()
        # per user stats
        stats['users'] = OOBTree()
        stats['datasets'] = DatasetStats()
        stats['experiments'] = ExperimentStats()
        stats['jobs'] = JobStats()
        annotations['org.bccvl.site.stats'] = stats


@implementer(IStatsUtility)
class StatsUtility(object):

    # TODO: maybe add decorator to cache annotations per request
    #       don't cache longer, as the utility instance will be cached by
    #       zope component engine.
    @property
    def stats(self):
        portal = api.portal.get()
        return IAnnotations(portal)['org.bccvl.site.stats']

    def count_dataset(self, source, portal_type, state=None, date=None):
        if state not in (None, 'COMPLETED', 'FAILED', 'REMOVED'):
            return
        if state is None:
            state = 'CREATED'
        if date is None:
            date = datetime.date.today()
        dsstats = self.stats['datasets']
        dsstats.inc(source, portal_type, state, date)

    def count_experiment(self, user, portal_type,
                         runtime=0, jobs=0, state=None, date=None):
        if state not in (None, 'COMPLETED', 'FINISHED', 'FAILED', 'REMOVED'):
            return
        if state is None:
            state = 'CREATED'
        if date is None:
            date = datetime.date.today()
        # exp stats
        expstats = self.stats['experiments']
        expstats.inc(portal_type, runtime, state, date)
        if jobs:
            expstats.inc_jobs(portal_type, jobs, date)
        # user stats
        ustats = self.stats['users']
        if user not in ustats:
            ustats[user] = ExperimentStats()
        ustats[user].inc(portal_type, runtime, state, date)
        if jobs:
            ustats[user].inc_jobs(portal_type, jobs, date)

    def count_job(self, function, portal_type,
                  runtime=0, state=None, date=None):
        if state not in (None, 'COMPLETED', 'FAILED'):
            return
        if state is None:
            state = 'CREATED'
        if date is None:
            date = datetime.date.today()
        jobstats = self.stats['jobs']
        jobstats.inc(function, portal_type, runtime, state, date)
