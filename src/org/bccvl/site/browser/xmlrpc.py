import json
import logging
import requests

from decorator import decorator
from Products.CMFCore.utils import getToolByName
from Products.Five.browser import BrowserView
from Products.statusmessages.interfaces import IStatusMessage
from plone import api
from plone.dexterity.utils import createContent, addContentToContainer
from plone.registry.interfaces import IRegistry
from zope import contenttype
from zope.component import getUtility
from zope.publisher.interfaces import NotFound, BadRequest

from org.bccvl.site import defaults
from org.bccvl.site.interfaces import (
    IBCCVLMetadata, IExperimentJobTracker, IDownloadInfo)
#from org.bccvl.site.stats.interfaces import IStatsUtility
from org.bccvl.site.swift.interfaces import ISwiftSettings
from org.bccvl.site.utils import decimal_encoder
from org.bccvl.site.content.interfaces import IMultiSpeciesDataset


LOG = logging.getLogger(__name__)

# self passed in as *args


@decorator  # well behaved decorator that preserves signature so that
# apply can inspect it
def returnwrapper(f, *args, **kw):
    # see http://code.google.com/p/mimeparse/
    # self.request.get['HTTP_ACCEPT']
    # self.request.get['CONTENT_TYPE']
    # self.request.get['method'']
    # ... decide on what type of call it is ... json?(POST),
    #     xmlrpc?(POST), url-call? (GET)

    # in case of post extract parameters and pass in?
    # jsonrpc:
    #    content-type: application/json-rpc (or application/json,
    #    application/jsonrequest) accept: application/json-rpc (or
    #    --""--)

    isxmlrpc = False
    view = args[0]
    try:
        ct = contenttype.parse.parse(view.request['CONTENT_TYPE'])
        if ct[0:2] == ('text', 'xml'):
            # we have xmlrpc
            isxmlrpc = True
    except Exception as e:
        # it's not valid xmlrpc
        # TODO: log this ?
        pass

    ret = f(*args, **kw)
    # return ACCEPT encoding here or IStreamIterator, that encodes
    # stuff on the fly could handle response encoding via
    # request.setBody ... would need to replace response instance of
    # request.response. (see ZPublisher.xmlprc.response, which wraps a
    # default Response)
    # FIXME: this is a bad workaround for - this method sholud be wrapped
    #        around tools and then be exposed as BrowserView ... ont as
    #        tool and BrowserView
    #        we call these wrapped functions internally, from templates and
    #        as ajax calls and xmlrpc calls, and expect different return
    #        encoding.
    #        ajax: json
    #        xmlrpc: xml, done by publisher
    #        everything else: python
    if not view.request['URL'].endswith(f.__name__):
        # not called directly, so return ret as is
        return ret

    # if we don't have xmlrpc we serialise to json
    if not isxmlrpc:
        ret = json.dumps(ret, default=decimal_encoder)
        view.request.response['CONTENT-TYPE'] = 'application/json'
    # FIXME: chaching headers should be more selective
    # prevent caching of ajax results... should be more selective here
    return ret


from ZPublisher.Iterators import IStreamIterator
from zope.interface import implementer


@implementer(IStreamIterator)
class UrlLibResponseIterator(object):

    def __init__(self, resp):
        self.resp = resp
        try:
            self.length = int(resp.headers.getheader('Content-Length'))
        except Exception:
            self.length = 0

    def __iter__(self):
        return self

    def next(self):
        data = self.resp.next()
        if not data:
            raise StopIteration
        return data

    def isError(self):
        return self.resp.code != 200

    def __len__(self):
        return self.length


class DataMover(BrowserView):

    @returnwrapper
    def pullOccurrenceFromALA(self, lsid, taxon, dataSrc='ala', common=None):
        # TODO: check permisions?
        # 1. create new dataset with taxon, lsid and common name set
        portal = getToolByName(self.context, 'portal_url').getPortalObject()

        if dataSrc == 'ala':
            dscontainer = portal[defaults.DATASETS_FOLDER_ID][
                defaults.DATASETS_SPECIES_FOLDER_ID]['ala']
        elif dataSrc == 'gbif':
            dscontainer = portal[defaults.DATASETS_FOLDER_ID][
                defaults.DATASETS_SPECIES_FOLDER_ID]['gbif']
        elif dataSrc == 'aekos':
            dscontainer = portal[defaults.DATASETS_FOLDER_ID][
                defaults.DATASETS_SPECIES_FOLDER_ID]['aekos']
        elif dataSrc == 'obis':
            dscontainer = portal[defaults.DATASETS_FOLDER_ID][
                defaults.DATASETS_SPECIES_FOLDER_ID]['obis']
        else:
            raise BadRequest('Invalid data source {0}'.format(dataSrc))

        title = [taxon]
        if common:
            title.append(u"({})".format(common))

        # determine dataset type
        # 1. test if it is a multi species import
        species = set()
        if dataSrc == 'ala':
            params = [{
                'query': 'taxon_concept_lsid:{}'.format(lsid),
                'url': 'https://biocache-ws.ala.org.au/ws'
            }]
            for query in params:
                biocache_url = '{}/occurrences/search'.format(query['url'])
                query = {
                    'q': query['query'],
                    'pageSize': 0,
                    'limit': 2,
                    'facets': 'species_guid',
                    'fq': 'species_guid:*'    # skip results without species guid
                }
                res = requests.get(biocache_url, params=query)
                res = res.json()
                if res.get('facetResults'):  # do we have some results at all?
                    for guid in res['facetResults'][0]['fieldResult']:
                        species.add(guid['label'])
        elif dataSrc == 'gbif':
            genusChildren_url = 'https://api.gbif.org/v1/species/{}/children?offset=0&limit=40'.format(lsid)
            res = requests.get(genusChildren_url)
            res = res.json()
            if res.get('results'):
                for sp in res.get('results'):
                    if sp.get('speciesKey'):
                        species.add(sp['speciesKey'])
        elif dataSrc == 'obis':
            genusChildren_url = 'https://backend.iobis.org/children/{}'.format(lsid)
            res = requests.get(genusChildren_url)
            res = res.json()
            for sp in res:
                if sp.get('rank_name', '') != 'Species':
                    continue
                if sp.get('valid_id'):
                    species.add(sp['valid_id'])

        if len(species) > 1:
            portal_type = 'org.bccvl.content.multispeciesdataset'
        else:
            swiftsettings = getUtility(IRegistry).forInterface(ISwiftSettings)
            if swiftsettings.storage_url:
                portal_type = 'org.bccvl.content.remotedataset'
            else:
                portal_type = 'org.bccvl.content.dataset'

        # TODO: make sure we get a better content id that dataset-x
        title = u' '.join(title)
        ds = createContent(portal_type, title=title)
        ds.dataSource = dataSrc  # Either ALA or GBIF as source
        # TODO: add number of occurences to description
        ds.description = u' '.join(
            (title, u'imported from', unicode(dataSrc.upper()))
        )
        ds = addContentToContainer(dscontainer, ds)
        md = IBCCVLMetadata(ds)
        # TODO: provenance ... import url?
        # FIXME: verify input parameters before adding to graph
        if IMultiSpeciesDataset.providedBy(ds):
            md['genre'] = 'DataGenreSpeciesCollection'
            md['categories'] = ['multispecies']
        else:
            md['genre'] = 'DataGenreSpeciesOccurrence'
            md['categories'] = ['occurrence']
        md['species'] = {
            'scientificName': taxon,
            'taxonID': lsid,
        }
        if common:
            md['species']['vernacularName'] = common
        IStatusMessage(self.request).add('New Dataset created',
                                         type='info')

        # 2. create and push alaimport job for dataset
        # TODO: make this named adapter
        jt = IExperimentJobTracker(ds)
        status, message = jt.start_job()
        # reindex object to make sure everything is up to date
        ds.reindexObject()
        # Job submission state notifier
        IStatusMessage(self.request).add(message, type=status)

        return (status, message)


class ExportResult(BrowserView):
    # TODO: should be post only? see plone.security for

    # parameters needed:
    #   ... serviceid ... service to export to

    # FIXME: should probably be a post only request?
    @returnwrapper
    def export_result(self, serviceid):
        # self.context should be a result
        if not hasattr(self.context, 'job_params'):
            raise NotFound(self.context, self.context.title, self.request)
        # TODO: validate serviceid

        # start export job
        context_path = '/'.join(self.context.getPhysicalPath())
        member = api.user.get_current()

        # collect list of files to export:
        urllist = []
        for content in self.context.values():
            if content.portal_type not in ('org.bccvl.content.dataset', 'org.bccvl.content.remotedataset'):
                # skip non datasets
                continue
            dlinfo = IDownloadInfo(content)
            urllist.append(dlinfo['url'])
        # add mets.xml
        urllist.append('{}/mets.xml'.format(self.context.absolute_url()))
        # add prov.ttl
        urllist.append('{}/prov.ttl'.format(self.context.absolute_url()))
        # add experiment metadata
        urllist.append('{}/expmetadata.txt'.format(self.context.absolute_url()))

        from org.bccvl.tasks.celery import app
        from org.bccvl.tasks.plone import after_commit_task
        # FIXME: Do mapping from serviceid to service type? based on interface
        #        background task will need serviceid and type, but it may resolve
        #        servicetype via API with serviceid
        export_task = app.signature(
            "org.bccvl.tasks.export_services.export_result",
            kwargs={
                'siteurl': api.portal.get().absolute_url(),
                'fileurls': urllist,
                'serviceid': serviceid,
                'context': {
                    'context': context_path,
                    'user': {
                        'id': member.getUserName(),
                        'email': member.getProperty('email'),
                        'fullname': member.getProperty('fullname')
                    }
                }
            },
            immutable=True)

        # queue job submission
        after_commit_task(export_task)

        # self.new_job('TODO: generate id', 'generate taskname: export_result')
        # self.set_progress('PENDING', u'Result export pending')

        status = 'info'
        message = u'Export request for "{}" succesfully submitted! Please check the service and any associated email accounts to confirm the data\'s availability'.format(
            self.context.title)

        IStatusMessage(self.request).add(message, type=status)
        nexturl = self.request.get('HTTP-REFERER')
        if not nexturl:
            # this method should only be called on a result folder
            # we should be able to safely redirect back to the pacent
            # experiment
            nexturl = self.context.__parent__.absolute_url()
        self.request.response.redirect(nexturl, 307)
        return (status, message)
