
import unittest

from plone import api
from plone.app.testing import setRoles
from plone.app.testing import TEST_USER_ID

from plone.uuid.interfaces import IUUID
from zope.component import getUtility

from org.bccvl.site.job.interfaces import IJobUtility, IJobTracker
from org.bccvl.site.testing import BCCVL_INTEGRATION_TESTING


class JobSetupTest(unittest.TestCase):

    layer = BCCVL_INTEGRATION_TESTING

    def test_job_catalog_setup(self):
        portal = self.layer['portal']

        self.assertTrue('job_catalog' in portal)

        jc = api.portal.get_tool('job_catalog')
        self.assertEqual(jc.meta_type, 'JobCatalog')
        # TODO: test indices and columns

        self.assertEqual(set(jc.indexes()), set(['userid', 'state', 'content', 'created',
                                                 'function', 'type', 'lsid']))
        self.assertEqual(set(jc.schema()), set(['id', 'state', 'content']))


class JobTest(unittest.TestCase):

    layer = BCCVL_INTEGRATION_TESTING

    def setUp(self):
        # create dummy content
        portal = self.layer['portal']
        setRoles(portal, TEST_USER_ID, ['Manager'])
        portal.invokeFactory('Document', 'd1')
        setRoles(portal, TEST_USER_ID, ['Member'])
        return portal['d1']

    def _create_new_job(self):
        job_tool = getUtility(IJobUtility)
        job = job_tool.new_job()
        return job

    def test_job_state_change(self):
        portal = self.layer['portal']
        job = self._create_new_job()
        content = portal['d1']
        job.content = IUUID(content)
        self.assertEqual(job.state, 'PENDING')
        job_tool = getUtility(IJobUtility)
        job_tool.reindex_job(job)
        # get job tracker for content
        jt = IJobTracker(content)
        # check if we get the same job
        self.assertEqual(job, jt.get_job())
        # progress state
        jt.state = 'COMPLETED'
        self.assertEqual(job.state, 'COMPLETED')
        # but we can't move back
        jt.state = 'RUNNING'
        self.assertEqual(job.state, 'COMPLETED')
