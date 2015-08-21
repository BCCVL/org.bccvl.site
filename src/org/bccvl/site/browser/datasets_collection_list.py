from urllib import urlencode

from Products.Five import BrowserView

from eea.facetednavigation.interfaces import ICriteria
from plone.app.uuid.utils import uuidToCatalogBrain


class DatasetsCollectionListView(BrowserView):

    def __init__(self, context, request):
        super(DatasetsCollectionListView, self).__init__(context, request)
        self.datasets_url = self.context.absolute_url()
        self.criteria = ICriteria(self.context, {})
        self.defaults = {}
        self.criterion = None
        for criterion in self.criteria.values():
            if criterion.widget == 'pathselect':
                self.criterion = criterion
            if criterion.widget == 'sorting':
                default = criterion.default
                if not default:
                    continue
                if '(reverse)' in default:
                    default = default.replace('(reverse)', '', 1)
                    self.defaults['reversed'] = True
                self.defaults[criterion.getId()] = default

    def get_browse_link(self, uuid):
        # return link into datasets facetedview to filter given collection
        collection = uuidToCatalogBrain(uuid)
        if not collection:
            return self.datasets_url
        params = dict(self.defaults)
        if self.criterion:
            params[self.criterion.getId()] = collection.UID
            return "{}#{}".format(self.datasets_url, urlencode(params))
        # fallback to original datasets_listing_view
        groupid = collection.getObject().__parent__.getId()
        params['datasets.filter.source:list'] = '{}-{}'.format(self.datesets_url, groupid, collection.getId)
        return "{}/?{}" . format(self.datasets_url, urlencode(params))
