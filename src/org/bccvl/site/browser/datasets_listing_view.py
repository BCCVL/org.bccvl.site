from Products.Five import BrowserView
from plone.app.content.browser.interfaces import IFolderContentsView
from zope.interface import implementer
from plone.app.uuid.utils import uuidToObject
from org.bccvl.site.content.interfaces import IDataset
from Products.CMFCore.utils import getToolByName
from zope.security import checkPermission
from zope.component import getMultiAdapter


def get_title_from_uuid(uuid):
    obj = uuidToObject(uuid)
    if obj:
        return obj.title
    return None


# FIXME: this view needs to exist for default browser layer as well
#        otherwise diazo.off won't find the page if set up.
#        -> how would unthemed markup look like?
#        -> theme would only have updated template.
@implementer(IFolderContentsView)
class DatasetsListingView(BrowserView):

    def contentFilter(self):
        # the default folder_contents template/macro could take this filter
        # from the request as well...
        # TODO: maybe we can simply parse the request here to change
        #       sort_order, or do batching?
        return {
            'path': {
                'query': '/'.join(self.context.getPhysicalPath()),
                'depth': -1
            },
            'sort_on': 'modified',
            'sort_order': 'descending',
            'object_provides': IDataset.__identifier__,
        }

    def local_roles_action(self, itemobj):
        context_state = getMultiAdapter((itemobj, self.request),
                                        name=u'plone_context_state')
        for action in context_state.actions().get('object'):
            if action.get('id') == 'local_roles':
                return action
        return {}

    def get_transition(self, itemob):
        #return checkPermission('cmf.RequestReview', self.context)
        wftool = getToolByName(itemob, 'portal_workflow')
        wfid = wftool.getChainFor(itemob)[0]
        wf = wftool.getWorkflowById(wfid)
        # check whether user can invoke transition
        # TODO: expects simple publication workflow publish/retract
        for transition in ('publish', 'retract'):
            if wf.isActionSupported(itemob, transition):
                return transition

    def download_url(self):
        pass

    def can_modify(self, itemob):
        return checkPermission('cmf.ModifyPortalContent', itemob)
