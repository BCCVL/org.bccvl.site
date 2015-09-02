from Products.Five.browser import BrowserView
from Products.CMFCore.utils import getToolByName
from Products.CMFCore.WorkflowCore import WorkflowException
from zope import contenttype
#from zope.publisher.browser import BrowserView as Z3BrowserView
#from zope.publisher.browser import BrowserPage as Z3BrowserPage  # + publishTraverse
#from zope.publisher.interfaces import IPublishTraverse
from zope.publisher.interfaces import NotFound
#from functools import wraps
from decorator import decorator
from plone.app.uuid.utils import uuidToCatalogBrain
from plone import api
from org.bccvl.site.interfaces import IJobTracker, IBCCVLMetadata
from org.bccvl.site.content.interfaces import IProjectionExperiment
from org.bccvl.site.content.interfaces import ISDMExperiment
from org.bccvl.site.content.interfaces import IBiodiverseExperiment
from org.bccvl.site.content.dataset import IDataset
from org.bccvl.site import defaults
import logging
from zope.component import getUtility, queryUtility
from zope.schema.vocabulary import getVocabularyRegistry
from zope.schema.interfaces import IContextSourceBinder
import json
from Products.statusmessages.interfaces import IStatusMessage
from org.bccvl.site.browser.ws import IDataMover, IALAService
from plone.dexterity.utils import createContentInContainer
from org.bccvl.site.api import dataset
from org.bccvl.site.utils import DecimalJSONEncoder


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
    # FIXME: this is a bad workaround for - this method sholud be wrapped around tools and then be exposed as BrowserView ... ont as tool and BrowserView
    #        we call these wrapped functions internally, from templates and
    #        as ajax calls and xmlrpc calls, and expect different return encoding.
    #        ajax: json
    #        xmlrpc: xml, done by publisher
    #        everything else: python
    if not view.request['URL'].endswith(f.__name__):
        # not called directly, so return ret as is
        return ret

    # if we don't have xmlrpc we serialise to json
    if not isxmlrpc:
        ret = DecimalJSONEncoder().encode(ret)
        view.request.response['CONTENT-TYPE'] = 'application/json'
    # FIXME: chaching headers should be more selective
    # prevent caching of ajax results... should be more selective here
    return ret


class DataSetManager(BrowserView):
    # DS Manager API on Site Root

    @returnwrapper
    # TODO: this method can be removed and use query(UID='') instead
    def metadata(self, datasetid):
        query = {'UID': datasetid}
        ds = dataset.query(self.context, **query)
        if ds:
            # we have a generator, let's pick the first result
            # metadata is extracted by query
            ds = next(ds, None)
        if ds is None:
            raise NotFound(self.context,  datasetid,  self.request)
        return ds

    # TODO: backwards compatible name
    @returnwrapper
    def getMetadata(self, datasetid):
        return self.metadata(datasetid)

    @returnwrapper
    def getRAT(self, datasetid, layer=None):
        query = {'UID': datasetid}
        dsbrain = dataset.query(self.context, brains=True, **query)
        if dsbrain:
            # get first brain from list
            dsbrain = next(dsbrain, None)
        if not dsbrain:
            raise NotFound(self.context, datasetid, self.request)
        md = IBCCVLMetadata(dsbrain.getObject())
        rat = md.get('layers', {}).get(layer, {}).get('rat')
        # if we have a rat, let's try and parse it
        if rat:
            try:
                rat = json.loads(unicode(rat))
            except Exception as e:
                LOG.warning("Couldn't decode Raster Attribute Table from metadata. %s: %s", self.context, repr(e))
                rat = None
        return rat

    @returnwrapper
    def query(self):
        # TODO: remove some parameters from request?
        #       e.g only matching with catalog indices
        #           only certain indices
        #       remove batching and internal parameters like brains
        query = self.request.form
        # TODO: should optimise this. e.g. return generator,
        objs = []
        for item in dataset.query(self.context, **query):
            objs.append(item)
        return objs

    @returnwrapper
    # TODO: need a replacement for this. it's a convenience function for UI
    def queryDataset(self, genre=None, layers=None):
        params = {'object_provides': IDataset.__identifier__}
        if genre:
            if not isinstance(genre, (tuple, list)):
                genre = (genre, )
            params['BCCDataGenre'] = {'query': genre,
                                      'operator': 'or'}
        if layers:
            if not isinstance(layers, (tuple, list)):
                layers = (layers, )
            params['BCCEnviroLayer'] = {'query': layers,
                                        'operator': 'and'}
        result = []
        for brain in dataset.query(self.context, True, **params):
            result.append({'uuid': brain.UID,
                           'title': brain.Title})
        return result

    # TODO: this is rather experiment API
    @returnwrapper
    def getSDMDatasets(self):
        # get all SDM current projection datasets
        pc = getToolByName(self.context, 'portal_catalog')
        sdmbrains = pc.searchResults(
            object_provides=ISDMExperiment.__identifier__,
            sort_on='sortable_title')  # date?
        sdms = []
        for sdmbrain in sdmbrains:
            # TODO: this loop over loop is inefficient
            # TODO: this pattern is all the same across, get XXXDatasets
            datasets = []
            for dsbrain in pc.searchResults(
                    path=sdmbrain.getPath(),
                    BCCDataGenre='DataGenreCP'):
                # get required metadata about dataset
                datasets.append({
                    #"files": [raster file names],
                    "title": dsbrain.Title,
                    "uuid": dsbrain.UID,
                    "url": dsbrain.getURL(),
                    #"year", "gcm", "msc", "species"
                })
            sdms.append({
                #"species": [],
                #"years": [],
                "name": sdmbrain.Title,
                "uuid": sdmbrain.UID,
                "url": sdmbrain.getURL(),
                "result": datasets
            })
        return {'sdms': sdms}

    # TODO: this is rather experiment API
    @returnwrapper
    def getBiodiverseDatasets(self):
        # TODO: there must be a way to do this with lfewer queries
        pc = getToolByName(self.context, 'portal_catalog')
        biodiversebrains = pc.searchResults(
            object_provides=IBiodiverseExperiment.__identifier__,
            sort_on='sortable_title')  # date?
        biodiverses = []
        for biodiversebrain in biodiversebrains:
            # search for datasets with this experiment
            datasets = []
            # TODO: query for data genre class?
            for dsbrain in pc.searchResults(
                    path=biodiversebrain.getPath(),
                    BCCDataGenre=('DataGenreENDW_CWE',
                                  'DataGenreENDW_WE',
                                  'DataGenreENDW_RICHNESS',
                                  'DataGenreENDW_SINGLE',
                                  'DataGenreREDUNDANCY_SET1',
                                  'DataGenreREDUNDANCY_SET2',
                                  'DataGenreREDUNDANCY_ALL')):
                # get required metadata about dataset
                datasets.append({
                    "title": dsbrain.Title,
                    "uuid": dsbrain.UID,
                    "url": dsbrain.getURL(),
                })
            biodiverses.append({
                "name": biodiversebrain.Title,
                "uuid": biodiversebrain.UID,
                "url": biodiversebrain.getURL(),
                "result": datasets
            })
        return {'biodiverses': biodiverses}

    # TODO: This method is very specific to UI in use,...
    #       maybe move to UI specific part?
    @returnwrapper
    def getProjectionDatasets(self):
        pc = getToolByName(self.context, 'portal_catalog')
        # to make it easire to produce required structure do separate queries
        # 1st query for all projection experiments
        projbrains = pc.searchResults(
            object_provides=(IProjectionExperiment.__identifier__, ISDMExperiment.__identifier__),
            sort_on='sortable_title')  # date?
        # the list to collect results
        projections = []
        for projbrain in projbrains:
            # get all result datasets from experiment and build list
            datasets = []
            agg_species = set()
            agg_years = set()
            for dsbrain in pc.searchResults(
                    path=projbrain.getPath(),
                    BCCDataGenre=('DataGenreFP', 'DataGenreCP')):
                # get year, gcm, emsc, species, filename/title, fileuuid
                # TODO: Result is one file per species ... should this be a dict by species or year as well?
                ds = dsbrain.getObject()
                md = IBCCVLMetadata(ds)
                # parse year
                year = md.get('year', None)
                month = md.get('month', None)
                species = md.get('species', {}).get('scientificName')
                dsinfo = {
                    # passible fields on brain:
                    #   Description, BCCResolution
                    #   ds.file.contentType
                    # TODO: restructure ... tile, filename no list
                    "title":  dsbrain.Title,
                    "uuid": dsbrain.UID,
                    "files": [ds.file.filename],  # filenames
                    "year": year,  # int or string?
                    "month": month,
                    "gcm": md.get('gcm'),  # URI? title? both?-> ui can fetch vocab to get titles
                    "emsc": md.get('emsc'),
                    "species": species,
                    "resolution": dsbrain.BCCResolution,
                }
                # add info about sdm
                if 'DataGenreCP' in dsbrain.BCCDataGenre:
                    sdmresult = ds.__parent__
                    # sdm = .... it's the model as sibling to this current projection ds
                    sdm = ds  # FIXME: wrong object here
                    dsinfo['type'] = u"Current"
                else:
                    sdmuuid = ds.__parent__.job_params['species_distribution_models']
                    sdm = uuidToCatalogBrain(sdmuuid).getObject()
                    sdmresult = sdm.__parent__
                    dsinfo['type'] = u"Future"
                sdmexp = sdmresult.__parent__
                dsinfo['sdm'] = {
                    'title': sdmexp.title,
                    'algorithm': sdmresult.job_params['function'],
                    'url': sdm.absolute_url()
                }
                datasets.append(dsinfo)
                agg_species.add(species)
                agg_years.add(year)
            # TODO: could also aggregate all data on projections result:
            #       e.g. list all years, grms, emsc, aggregated from datasets
            projections.append({
                "name": projbrain.Title,  # TODO: rename to title
                "uuid":  projbrain.UID,   # TODO: rename to uuid
                "species":  tuple(agg_species),
                "years": tuple(agg_years),
                "result": datasets
            })
        # wrap in projections neccesarry?
        return {'projections': projections}

    # TODO: this is generic api ....
    @returnwrapper
    def getVocabulary(self, name):
        # TODO: check if there are vocabularies that need to be protected
        vocab = ()
        try:
            # TODO: getUtility(IVocabularyFactory???)
            vr = getVocabularyRegistry()
            vocab = vr.get(self.context, name)
        except:
            # eat all exceptions
            pass
        if not vocab:
            # try IContextSourceBinder
            vocab = queryUtility(IContextSourceBinder, name=name)
            if vocab is None:
                return []
            vocab = vocab(self.context)
        result = []
        for term in vocab:
            data = {'token': term.token,
                    'title': term.title}
            if hasattr(term, 'data'):
                data.update(term.data)
            result.append(data)
        return result

    @returnwrapper
    def getThresholds(self, datasets, thresholds=None):
        # datasets: a future projection dataset as a result of projectien experiment
        # thresholds: list of names to retrieve or all
        return dataset.getThresholds(datasets, thresholds)


class DataSetAPI(BrowserView):
    # DS Manager API on Dataset

    @returnwrapper
    def getMetadata(self):
        return dataset.getdsmetadata(self.context)

    @returnwrapper
    def share(self):
        # TODO: status message and redirect are not useful for ajax
        msg = u"Status changed"
        msg_type = 'info'
        try:
            wtool = getToolByName(self.context, 'portal_workflow')
            wtool.doActionFor(self.context,  'publish')
        except WorkflowException as e:
            msg = u"Status change failed"
            msg_type = 'error'
        IStatusMessage(self.request).add(msg, type=msg_type)
        next = self.request['HTTP_REFERER']
        if not next or next == self.request['URL']:
            next = self.context.absolute_url()
        self.request.response.redirect(next)

    @returnwrapper
    def unshare(self):
        # TODO: status message and redirect are not useful for ajax
        msg = u"Status changed"
        msg_type = 'info'
        try:
            wtool = getToolByName(self.context, 'portal_workflow')
            wtool.doActionFor(self.context,  'retract')
        except WorkflowException as e:
            msg = u"Status change failed"
            msg_type = 'error'
        IStatusMessage(self.request).add(msg, type=msg_type)
        next = self.request['HTTP_REFERER']
        if not next or next == self.request['URL']:
            next = self.context.absolute_url()
        self.request.response.redirect(next)


class JobManagerAPI(BrowserView):
    # job manager on experiment

    @returnwrapper
    def getJobStatus(self):
        return IJobTracker(self.context).state

    @returnwrapper
    def getJobStates(self):
        return IJobTracker(self.context).states


from ZPublisher.Iterators import IStreamIterator
from zope.interface import implementer


@implementer(IStreamIterator)
class UrlLibResponseIterator(object):

    def __init__(self, resp):
        self.resp = resp
        try:
            self.length = int(resp.headers.getheader('Content-Length'))
        except:
            self.length = 0

    def __iter__(self):
        return self

    def next(self):
        data = self.resp.next()
        if not data:
            raise StopIteration
        return data

    def __len__(self):
        return self.length


class ALAProxy(BrowserView):

    #@returnwrapper ... returning file here ... returnwrapper not handling it properly
    def autojson(self, q, geoOnly=None, idxType=None, limit=None,
                 callback=None):
        # TODO: do parameter checking and maybe set defaults so that
        # js side doesn't have to do it
        ala = getUtility(IALAService)
        return self._doResponse(ala.autojson(q, geoOnly, idxType, limit,
                                             callback))

    #@returnwrapper ... returning file here ... returnwrapper not handling it properly
    def searchjson(self, q, fq=None, start=None, pageSize=None,
                   sort=None, dir=None, callback=None):
        # TODO: do parameter checking and maybe set defaults so that
        #       js side doesn't have to do it
        ala = getUtility(IALAService)
        return self._doResponse(ala.searchjson(q, fq, start, pageSize,
                                               sort, dir, callback))

    def _doResponse(self, resp):
        # TODO: add headers like:
        #    User-Agent
        #    orig-request
        #    etc...
        # TODO: check response code?
        for name in ('Date', 'Pragma', 'Expires', 'Content-Type',
                     'Cache-Control', 'Content-Language', 'Content-Length',
                     'transfer-encoding'):
            value = resp.headers.getheader(name)
            if value:
                self.request.response.setHeader(name, value)
        self.request.response.setStatus(resp.code)
        ret = UrlLibResponseIterator(resp)
        if len(ret) != 0:
            # we have a content-length so let the publisher stream it
            return ret
        # we don't have content-length and stupid publisher want's one
        # for stream, so let's stream it ourselves.
        while True:
            try:
                data = ret.next()
                self.request.response.write(data)
            except StopIteration:
                break


class DataMover(BrowserView):

    # TODO: typo in view ergistartion in api.zcml-> update js as well
    @returnwrapper
    def pullOccurrenceFromALA(self, lsid, taxon,  common=None):
        # TODO: check permisions?
        # 1. create new dataset with taxon, lsid and common name set
        portal = getToolByName(self.context, 'portal_url').getPortalObject()
        dscontainer = portal[defaults.DATASETS_FOLDER_ID][defaults.DATASETS_SPECIES_FOLDER_ID]['ala']

        title = [taxon]
        if common:
            title.append(u"({})".format(common))
        # TODO: check whether title will be updated in transmog import?
        #       set title now to "Whatever (import pending)"?
        # TODO: make sure we get a better content id that dataset-x
        ds = createContentInContainer(dscontainer,
                                      'org.bccvl.content.dataset',
                                      title=u' '.join(title))
        # TODO: add number of occurences to description
        ds.description = u' '.join(title) + u' imported from ALA'
        md = IBCCVLMetadata(ds)
        # TODO: provenance ... import url?
        # FIXME: verify input parameters before adding to graph
        md['genre'] = 'DataGenreSpeciesOccurrence'
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
        jt = IJobTracker(ds)
        status, message = jt.start_job()
        # reindex object to make sure everything is up to date
        ds.reindexObject()
        # Job submission state notifier
        IStatusMessage(self.request).add(message, type=status)

        return (status, message)

    @returnwrapper
    def checkALAJobStatus(self, job_id):
        # TODO: check permissions? or maybe git rid of this here and
        #       use job tracking for status. (needs job annotations)
        dm = getUtility(IDataMover)
        return dm.check_move_status(job_id)


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

        zipurl = self.context.absolute_url() + '/resultdownload'

        from org.bccvl.tasks.datamover import export_result
        from org.bccvl.tasks.plone import after_commit_task
        # FIXME: Do mapping from serviceid to service type? based on interface
        #        background task will need serviceid and type, but it may resolve
        #        servicetype via API with serviceid
        export_task = export_result.si(
            zipurl,
            serviceid, {'context': context_path,
                        'user': {
                            'id': member.getUserName(),
                            'email': member.getProperty('email'),
                            'fullname': member.getProperty('fullname')
                            }})
        # queue job submission
        after_commit_task(export_task)

        # self.new_job('TODO: generate id', 'generate taskname: export_result')
        # self.set_progress('PENDING', u'Result export pending')

        status = 'info'
        message = u'Export request for "{}" succesfully submitted! Please check the service and any associated email accounts to confirm the data\'s availability'.format(self.context.title)

        IStatusMessage(self.request).add(message, type=status)
        nexturl = self.request.get('HTTP-REFERER')
        if not nexturl:
            # this method should only be called on a result folder
            # we should be able to safely redirect back to the pacent experiment
            nexturl = self.context.__parent__.absolute_url()
        self.request.response.redirect(nexturl, 307)
        return (status, message)
