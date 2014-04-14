from tempfile import mkdtemp
import os.path
import shutil
import time
from plone.app.async.interfaces import IAsyncService
from zope.component import getUtility
from zope.interface import provider
from org.bccvl.compute.utils import WorkEnvLocal
from org.bccvl.site.interfaces import IComputeMethod
from zc.async import local


def testjob(experiment, jobid, env):
    """
    An algorithm mack function, that generates some test result data.
    """
    # 1. create tempfolder for result files
    tmpdir = mkdtemp()
    env.tmpimport = tmpdir
    env.workdir = tmpdir
    env.jobid = jobid
    status = local.getLiveAnnotation('bccvl.status')
    try:
        # 2. create some result files
        for fname in ('testfile1.txt', ):
            f = open(os.path.join(tmpdir, fname), 'w')
            f.write(str(range(1, 10)))
            f.close()
            time.sleep(1)
        # 3. store results
        env.import_output(experiment, env, {})
        status['task'] = 'Completed'
        local.setLiveAnnotation('bccvl.status', status)
    except:
        status['task'] = 'Failed'
        local.setLiveAnnotation('bccvl.status', status)
        raise
    finally:
        # 4. clean up tmpdir
        shutil.rmtree(tmpdir)


@provider(IComputeMethod)
def testalgorithm(experiment, toolkit):
    # submit test_job into queue
    async = getUtility(IAsyncService)
    queues = async.getQueues()
    env = WorkEnvLocal('localhost')
    job = async.wrapJob((testjob, experiment, ('testalgorithm', env), {}))
    job.jobid = 'testalgorithm'
    job.quota_names = ('default', )
    job.annotations['bccvl.status'] = {
        'step': 0,
        'task': u'Queued'}
    queue = queues['']
    return queue.put(job)


def failingtestalgorithm(experiment, request):
    """
    An algorithm that always fails.
    """
    # 1. create tempfolder for result files
    # 2. create some error files
    pass
    #utils.store_results(experiment, tmpdir)
    # 3. clean up tmpdir
