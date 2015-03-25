from Products.Five.browser import BrowserView
from Products.CMFCore.utils import getToolByName
from org.bccvl.site.interfaces import IJobTracker
from org.bccvl.site.content.interfaces import IDataset,  IExperiment
from org.bccvl.site import defaults


class DashboardView(BrowserView):

    def __call__(self):
        self.pc = getToolByName(self.context, 'portal_catalog')
        self.portal = self.pc.__parent__
        return super(DashboardView, self).__call__()

    def num_datasets(self):
        return len(self.pc.searchResults(
            path='/'.join(self.portal.datasets.getPhysicalPath()),
            job_state=("COMPLETED", "QUEUED", "RUNNING"),            
            object_provides=IDataset.__identifier__))

    def num_experiments(self):
        return len(self.pc.searchResults(
            path='/'.join(self.portal.experiments.getPhysicalPath()),
            object_provides=IExperiment.__identifier__))

    def newest_datasets(self):
        return self.pc.searchResults(
            path='/'.join(self.portal[defaults.DATASETS_FOLDER_ID].getPhysicalPath()),
            object_provides=IDataset.__identifier__,
            job_state=("COMPLETED", "QUEUED", "RUNNING"),            
            sort_on='modified',
            sort_order='descending',
        )[:3]

    def newest_experiments(self):
        return self.pc.searchResults(
            path='/'.join(self.portal[defaults.EXPERIMENTS_FOLDER_ID].getPhysicalPath()),
            object_provides=IExperiment.__identifier__,
            sort_on='modified',
            sort_order='descending',
            sort_limit=3
        )[:3]

    def get_state_css(self, brain):
        css_map = {
            None: 'success',
            'COMPLETED': 'success',
            'FAILED': 'error',
            'REMOVED': 'removed'
        }
        # check job_state and return either success, error or block
        job_state = IJobTracker(brain.getObject()).state
        return css_map.get(job_state, 'info')
