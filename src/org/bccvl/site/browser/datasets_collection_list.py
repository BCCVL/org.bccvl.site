from Products.Five import BrowserView

from eea.facetednavigation.interfaces import ICriteria
from plone.app.uuid.utils import uuidToCatalogBrain


class DatasetsCollectionListView(BrowserView):

    def __init__(self, context, request):
        super(DatasetsCollectionListView, self).__init__(context, request)
        self.datasets_url = self.context.absolute_url()
        self.criteria = ICriteria(self.context, {})
        for criterion in self.criteria.values():
            if criterion.widget == 'pathselect':
                self.criterion = criterion
                return
        self.criterion = None

    def get_browse_link(self, uuid):
        # return link into datasets facetedview to filter given collection
        collection = uuidToCatalogBrain(uuid)
        if not collection:
            return self.datasets_url
        if self.criterion:
            return "{}#{}={}".format(self.datasets_url, self.criterion.getId(), collection.UID)
        # fallback to original datasets_listing_view
        groupid = collection.getObject().__parent__.getId()
        return "{}/?datasets.filter.source%3Alist={}-{}".format(self.datests_url, groupid, collection.getId)
