from Products.Five import BrowserView
from urllib import urlencode
import json
from zope.component import getUtility
from org.bccvl.site.browser.ws import IALAService
from Products.CMFCore.utils import getToolByName
from Products.statusmessages.interfaces import IStatusMessage
from org.bccvl.site import defaults


class DatasetsImportView(BrowserView):
    """
    render the dataset import template
    """

    def parseRequest(self):
        params = {'action': None}
        if 'search' in self.request:
            params['action'] = 'search'
        if 'import' in self.request:
            params['action'] = 'import'
        for name in ('searchOccurrence_query',
                     'searchOccurrence_source',
                     'lsid', 'taxon', 'common'):
            if name in self.request:
                params[name] = self.request.get(name)
        return params

    def searchResults(self):
        if self.params.get('action') != 'search':
            return

        ala = getUtility(IALAService)
        try:
            ret = ala.searchjson(q=self.params['searchOccurrence_query'],
                                 fq='rank:species')
            result = json.load(ret)
        except:
            # TODO yield result with error
            return

        if not 'searchResults' in result:
            return
        if not 'results' in result['searchResults']:
            return
        for item in result['searchResults']['results']:
            search_words = self.params['searchOccurrence_query'].lower().split();
            result = {
                'title': item['name'],
                'friendlyName': item['name'],
                'description': [],
                'actions': {},
                }
            if 'commonNameSingle' in item:
                result['title'] = '{} <i class="taxonomy">{}</i>'.format(
                    item['commonNameSingle'], result['title'])
                result['friendlyName'] = '{} {}'.format(
                    item['commonNameSingle'], result['friendlyName'])
            # and filter all searchwords
            resulttitle = result['title'].lower()
            if any(sw not in resulttitle for sw in search_words):
                continue
            # filter out results without occurrences
            if not item.get('occCount', 0) > 0:
                continue
            if item.get('rank'):
                result['description'].append('({})'.format(item['rank']))
            if item.get('occCount'):
                result['description'].append('{} occurrences from ALA'.format(
                    item['occCount']))
            result['description'] = ' '.join(result['description'])
            # prefer smallImage over thumbnail?
            if item.get('smallImageUrl'):
                result['thumbUrl'] = item['smallImageUrl']
            elif item.get('thumbnailUrl'):
                result['thumbUrl'] = item['thumbnailUrl']
            else:
                result['thumbUrl'] = ''
            # get actions
            if item.get('guid'):
                # TODO: uri path encode guid
                result['actions']['viz'] = 'http://bie.ala.org.au/species/' + item['guid']
                params = urlencode({
                    'lsid': item['guid'],
                    'taxon': item['name'],
                    'common': item.get('commonNameSingle'),
                    'import': 'Import'})
                # TODO: need a way to generate ajax url?
                # TODO: can I use view name/id here?
                result['actions']['alaimport'] = self.context.absolute_url() +  "/datasets_import_view?" +  params
            yield result

    def __call__(self):
        # FIXME: write test: create dataset in correct location and
        #        test permissions to 'dv' view
        # TODO: implement non js-search, and import here
        #       -> reuse DataMover api endpoint
        self.params = self.parseRequest()
        if self.params.get('action') == 'import':
            portal = getToolByName(self.context,
                                   'portal_url').getPortalObject()
            # TODO: @@dv or getMultiAdapter would enusre we get the view
            view = portal.restrictedTraverse(
                '/'.join((defaults.DATASETS_FOLDER_ID,
                         'dv', 'pullOccurrenceFromALA')))
            # create dataset and start import job
            ret = view(lsid=self.params['lsid'],
                       taxon=self.params['taxon'],
                       common=self.params.get('common'))
            # TODO: check ret for errors?
            # TODO: redirect to dataset or listing view?
            # everything went fine until here .. so let's redirect
            nexturl = portal[defaults.DATASETS_FOLDER_ID].absolute_url()
            self.request.response.redirect(nexturl)
            return
        return super(DatasetsImportView, self).__call__()

    # TODO: implement search: get list of data and feed template with it
    #       implement import: get selected lsid and title and do
    #                         what pullOccurrencesFromALA does
