import copy
import json
import logging
import os
from urlparse import parse_qs

import requests

from AccessControl import Unauthorized
from Products.CMFCore.interfaces import ISiteRoot
from Products.CMFCore.utils import getToolByName

from plone import api as ploneapi
from plone.app.uuid.utils import uuidToCatalogBrain
from plone.batching import Batch
from plone.dexterity.utils import createContent, addContentToContainer
from plone.registry.interfaces import IRegistry
from zope.component import getUtility
from zope.interface import implementer
from zope.publisher.interfaces import NotFound, BadRequest
from zope.security import checkPermission

from org.bccvl.site import defaults
from org.bccvl.site.api import dataset
from org.bccvl.site.api.base import BaseService
from org.bccvl.site.api.decorators import api
from org.bccvl.site.api.interfaces import IDMService
from org.bccvl.site.content.interfaces import IMultiSpeciesDataset
from org.bccvl.site.interfaces import IBCCVLMetadata, IExperimentJobTracker, IDownloadInfo
from org.bccvl.site.job.interfaces import IJobTracker
from org.bccvl.site.swift.interfaces import ISwiftSettings


LOG = logging.getLogger(__name__)


@api('dm_v1.json')
@implementer(IDMService)
class DMService(BaseService):

    title = u'Dataset API v1'
    description = u'Access datasets'

    def search(self):
        kw = self.request.form
        b_start = int(kw.pop('b_start', 0))
        b_size = int(min(kw.pop('b_size', 50), 50))

        # remove path and portal_type
        # TODO: go through catalog indices and restrict parameters to index
        #       names
        kw.pop('path', None)
        kw.pop('portal_type', None)
        kw.pop('object_provides', None)
        kw.pop('used', None)
        kw.pop('_merge', None)

        pc = getToolByName(self.context, 'portal_catalog')
        kw.update({
            'object_provides': 'org.bccvl.site.content.interfaces.IDataset',
            #'object_provides': IDataset.__identifier__,
            'path': '/'.join(self.context.getPhysicalPath()),
        })
        batch = Batch(pc.searchResults(**kw), b_size, b_start)

        result = {
            'total': batch.sequence_length,
            'length': batch.length,
            'b_start': b_start,
            'b_size': b_size,
            'results': []
        }
        # TODO: could add next/prev links to make batch nav easier
        for brain in batch:
            result['results'].append({
                'url': brain.getURL(),
                'uuid': brain.UID,
                'id': brain.getId,
                #'BCCCategory': brain.BCCCategory,
                'BCCDataGenre': brain.BCCDataGenre,
                #'BCCEnviroLayer': brain.BCCEnviroLayer,
                #'BCCEmissionScenairo': brain.BCCEmissionScenairo,
                #'BCCGlobalClimateModel': brain.BCCGlobalClimateModel,
                'BCCResolution': brain.BCCResolution,
                'Description': brain.Description,
                'Title': brain.Title,
                'job_state': brain.job_state,
            })
        return result

    def metadata(self):
        uuid = self.request.form.get('uuid')
        try:
            brain = uuidToCatalogBrain(uuid)
            if brain:
                return dataset.getdsmetadata(brain)
        except Exception as e:
            LOG.error('Caught exception %s', e)
        self.record_error('Not Found', '404', 'dataset not found', {
                          'parameter': 'uuid'})
        raise NotFound(self, 'metadata', self.request)

    def rat(self):
        uuid = self.request.form.get('uuid')
        layer = self.request.form.get('layer')
        brain = None
        try:
            brain = uuidToCatalogBrain(uuid)
        except Exception as e:
            LOG.error('Caught exception %s', e)

        if not brain:
            self.record_error('Not Found', 404,
                              'dataset not found',
                              {'parameter': 'uuid'})
            raise NotFound(self, 'metadata', self.request)
        md = IBCCVLMetadata(brain.getObject())
        if not layer and layer not in md.get('layers', {}):
            self.record_error('Bad Request', 400,
                              'Missing parameter layer',
                              {'parameter': 'layer'})
            raise BadRequest('Missing parameter layer')
        try:
            rat = md.get('layers', {}).get(layer, {}).get('rat')
            rat = json.loads(unicode(rat))
            return rat
        except Exception as e:
            LOG.warning(
                "Couldn't decode Raster Attribute Table from metadata. %s: %s", self.context, repr(e))
        raise NotFound(self, 'rat', self.request)

    def update_metadata(self):
        uuid = self.request.form.get('uuid', None)
        try:
            if uuid:
                brain = uuidToCatalogBrain(uuid)
                if brain is None:
                    raise Exception("Brain not found")

                obj = brain.getObject()
            else:
                obj = self.context

            # get username
            member = ploneapi.user.get_current()
            if member.getId():
                user = {
                    'id': member.getUserName(),
                    'email': member.getProperty('email'),
                    'fullname': member.getProperty('fullname')
                }
            else:
                raise Exception("Invalid user")

            # build download url
            # 1. get context (site) relative path
            obj_url = obj.absolute_url()

            if obj.portal_type == 'org.bccvl.content.dataset':
                filename = obj.file.filename
                obj_url = '{}/@@download/file/{}'.format(obj_url, filename)
            elif obj.portal_type == 'org.bccvl.content.remotedataset':
                filename = os.path.basename(obj.remoteUrl)
                obj_url = '{}/@@download/{}'.format(obj_url, filename)
            elif obj.portal_type == 'org.bccvl.content.multispeciesdataset':
                filename = obj.file.filename
                obj_url = '{}/@@download/file/{}'.format(obj_url, filename)
            else:
                raise Exception("Wrong content type")

            from org.bccvl.tasks.celery import app
            update_task = app.signature(
                "org.bccvl.tasks.datamover.tasks.update_metadata",
                kwargs={
                    'url': obj_url,
                    'filename': filename,
                    'contenttype': obj.format,
                    'context': {
                        'context': '/'.join(obj.getPhysicalPath()),
                        'user': user,
                    }
                },
                immutable=True)

            from org.bccvl.tasks.plone import after_commit_task
            after_commit_task(update_task)
            # track background job state
            jt = IJobTracker(obj)
            job = jt.new_job('TODO: generate id',
                             'generate taskname: update_metadata',
                             function=obj.dataSource,
                             type=obj.portal_type)
            jt.set_progress('PENDING', 'Metadata update pending')
            return job.id
        except Exception as e:
            LOG.error('Caught exception %s', e)
        raise NotFound(self, 'update_metadata', self.request)

    def import_trait_data(self):
        if self.request.get('REQUEST_METHOD', 'GET').upper() != 'POST':
            self.record_error('Request must be POST', 400)
            raise BadRequest('Request must be POST')

        source = self.request.form.get('source', None)
        species = self.request.form.get('species', None)
        traits = self.request.form.get('traits', None)
        environ = self.request.form.get('environ', None)
        dataurl = self.request.form.get('url', None)
        context = None

        if not source or source not in ('aekos', 'zoatrack'):
            raise BadRequest("source parameter must be 'aekos' or 'zoatrack'")

        # get import context
        if ISiteRoot.providedBy(self.context):
            # we have been called at site root... let's traverse to default
            # import location
            context = self.context.restrictedTraverse(
                "/".join((defaults.DATASETS_FOLDER_ID,
                          defaults.DATASETS_SPECIES_FOLDER_ID,
                          str(source))))
        else:
            # custom context.... let's use in
            context = self.context
        # do user check first
        member = ploneapi.user.get_current()
        if member.getId():
            user = {
                'id': member.getUserName(),
                'email': member.getProperty('email'),
                'fullname': member.getProperty('fullname')
            }
        else:
            # We need at least a valid user
            raise Unauthorized("Invalid user")
        # check permission
        if not checkPermission('org.bccvl.AddDataset', context):
            raise Unauthorized("User not allowed in this context")

        # check parameters
        if not species or not isinstance(species, (basestring, list)):
            raise BadRequest("Missing or invalid species parameter")
        elif isinstance(species, basestring):
            species = [species]

        # for zoatrack, url needs to be set
        if source == 'zoatrack' and not dataurl:
            raise BadRequest("url has to be set")
        # for aekos, at least a trait or environment variable must be specified.
        if source == 'aekos' and not traits and not environ:
            raise BadRequest("At least a trait or environent variable has to be set")
        if not traits:
            traits = []
        elif isinstance(traits, basestring):
            traits = [traits]
        if not environ:
            environ = []
        elif isinstance(environ, basestring):
            environ = [environ]

        # all good so far
        # pull dataset from aekos
        title = ' '.join(species)
        # determine dataset type
        portal_type = 'org.bccvl.content.dataset'
        swiftsettings = getUtility(IRegistry).forInterface(ISwiftSettings)
        if swiftsettings.storage_url:
            portal_type = 'org.bccvl.content.remotedataset'
        # create content
        ds = createContent(portal_type, title=title)
        ds.dataSource = source
        ds.description = u' '.join([
            title, ','.join(traits), ','.join(environ),
            u' imported from {}'.format(source.upper())])
        ds = addContentToContainer(context, ds)
        md = IBCCVLMetadata(ds)
        md['genre'] = 'DataGenreTraits'
        md['categories'] = ['traits']
        md['species'] = [{
            'scientificName': spec,
            'taxonID': spec} for spec in species]
        md['traits'] = traits
        md['environ'] = environ
        md['dataurl'] = dataurl
        # FIXME: IStatusMessage should not be in API call
        from Products.statusmessages.interfaces import IStatusMessage
        IStatusMessage(self.request).add('New Dataset created',
                                         type='info')
        # start import job
        jt = IExperimentJobTracker(ds)
        status, message = jt.start_job()
        # reindex ojebct to make sure everything is up to date
        ds.reindexObject()
        # FIXME: IStatutsMessage should not be in API call
        IStatusMessage(self.request).add(message, type=status)

        # FIXME: API should not return a redirect
        #        201: new resource created ... location may point to resource
        from Products.CMFCore.utils import getToolByName
        portal = getToolByName(self.context, 'portal_url').getPortalObject()
        nexturl = portal[defaults.DATASETS_FOLDER_ID].absolute_url()
        self.request.response.setStatus(201)
        self.request.response.setHeader('Location', nexturl)
        # FIXME: should return a nice json representation of success or error
        return {
            'status': status,
            'message': message,
            'jobid': IJobTracker(ds).get_job().id
        }

    def import_ala_data(self):
        if self.request.get('REQUEST_METHOD', 'GET').upper() != 'POST':
            self.record_error('Request must be POST', 400)
            raise BadRequest('Request must be POST')

        context = None
        # get import context
        if ISiteRoot.providedBy(self.context):
            # we have been called at site root... let's traverse to default
            # import location
            context = self.context.restrictedTraverse(
                "/".join((defaults.DATASETS_FOLDER_ID,
                          defaults.DATASETS_SPECIES_FOLDER_ID,
                          'ala')))
        else:
            # custom context.... let's use in
            context = self.context
        # do user check first
        member = ploneapi.user.get_current()
        if member.getId():
            user = {
                'id': member.getUserName(),
                'email': member.getProperty('email'),
                'fullname': member.getProperty('fullname')
            }
        else:
            # We need at least a valid user
            raise Unauthorized("Invalid user")
        # check permission
        if not checkPermission('org.bccvl.AddDataset', context):
            raise Unauthorized("User not allowed in this context")

        params = self.request.form.get('data')

        if not params:
            raise BadRequest("At least on of traits or environ has to be set")

        if params is None:
            self.record_error('Bad Request', 400,
                              'Missing parameter data',
                              {'parameter': 'data'})
        if not params:
            self.record_error('Bad Request', 400,
                              'Empty parameter data',
                              {'parameter': 'data'})
        # TODO: should validate objects inside as well? (or use json schema
        # validation?)

        # all good so far
        # pull dataset from aekos
        # TODO: get better name here
        title = params[0].get('name', 'ALA import')
        # determine dataset type
        # 1. test if it is a multi species import
        species = set()
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
            # FIXME: do we need to treat sandbox downloads differently?
            if res.get('facetResults'):  # do we have some results at all?
                for guid in res['facetResults'][0]['fieldResult']:
                    species.add(guid['label'])
        if len(species) > 1:
            portal_type = 'org.bccvl.content.multispeciesdataset'

        else:
            portal_type = 'org.bccvl.content.dataset'
            swiftsettings = getUtility(IRegistry).forInterface(ISwiftSettings)
            if swiftsettings.storage_url:
                portal_type = 'org.bccvl.content.remotedataset'
        # create content
        ds = createContent(portal_type, title=title)
        ds.dataSource = 'ala'
        ds.description = u' '.join([title, u' imported from ALA'])
        ds.import_params = params
        ds = addContentToContainer(context, ds)
        md = IBCCVLMetadata(ds)
        if IMultiSpeciesDataset.providedBy(ds):
            md['genre'] = 'DataGenreSpeciesCollection'
            md['categories'] = ['multispecies']
        else:
            # species dataset
            md['genre'] = 'DataGenreSpeciesOccurrence'
            md['categories'] = ['occurrence']
        # TODO: populate this correctly as well
        md['species'] = [{
            'scientificName': 'qid',
            'taxonID': 'qid'}]
        # FIXME: IStatusMessage should not be in API call
        from Products.statusmessages.interfaces import IStatusMessage
        IStatusMessage(self.request).add('New Dataset created',
                                         type='info')
        # start import job
        jt = IExperimentJobTracker(ds)
        status, message = jt.start_job()
        # reindex ojebct to make sure everything is up to date
        ds.reindexObject()
        # FIXME: IStatutsMessage should not be in API call
        IStatusMessage(self.request).add(message, type=status)

        # FIXME: API should not return a redirect
        #        201: new resource created ... location may point to resource
        from Products.CMFCore.utils import getToolByName
        portal = getToolByName(self.context, 'portal_url').getPortalObject()
        nexturl = portal[defaults.DATASETS_FOLDER_ID].absolute_url()
        self.request.response.setStatus(201)
        self.request.response.setHeader('Location', nexturl)
        # FIXME: should return a nice json representation of success or error
        return {
            'status': status,
            'message': message,
            'jobid': IJobTracker(ds).get_job().id
        }

    def export_to_ala(self):
        uuid = self.request.form.get('uuid', None)
        try:
            if uuid:
                brain = uuidToCatalogBrain(uuid)
                if brain is None:
                    raise Exception("Brain not found")

                obj = brain.getObject()
            else:
                obj = self.context

            # get username
            member = ploneapi.user.get_current()
            if member.getId():
                user = {
                    'id': member.getUserName(),
                    'email': member.getProperty('email'),
                    'fullname': member.getProperty('fullname')
                }
            else:
                raise Exception("Invalid user")

            # verify dataset
            if obj.portal_type not in ('org.bccvl.content.dataset',
                                       'org.bccvl.content.remotedataset',
                                       'org.bccvl.content.multispeciesdataset'):
                raise Exception("Invalid UUID (content type)")
            md = IBCCVLMetadata(obj)
            if md.get('genre') not in ('DataGenreSpeciesOccurrence',
                                       'DataGenreSpeciesCollection',
                                       'DataGenreTraits'):
                raise Exception("Invalid UUID (data type)")
            # get download url
            dlinfo = IDownloadInfo(obj)

            # download file
            from org.bccvl import movelib
            from org.bccvl.movelib.utils import build_source, build_destination
            import tempfile
            destdir = tempfile.mkdtemp(prefix='export_to_ala')
            try:
                from org.bccvl.tasks.celery import app
                settings = app.conf.get('bccvl', {})
                dest = os.path.join(destdir, os.path.basename(dlinfo['url']))
                movelib.move(build_source(dlinfo['url'], user['id'], settings),
                             build_destination('file://{}'.format(dest)))

                csvfile = None

                if dlinfo['contenttype'] == 'application/zip':
                    # loox at 'layers' to find file within zip
                    arc = md['layers'].keys()[0]

                    import zipfile
                    zf = zipfile.ZipFile(dest, 'r')
                    csvfile = zf.open(arc, 'r')
                else:
                    csvfile = open(dest, 'rb')

                import requests
                # "Accept:application/json" "Origin:http://example.com"
                res = requests.post(settings['ala']['sandboxurl'],
                                    files={'file': csvfile},
                                    headers={
                                        'apikey': settings['ala']['apikey'],
                                        'Accept': 'application/json'
                })
                if res.status_code != 200:
                    self.record_error(res.reason, res.status_code)
                    raise Exception('Upload failed')
                retval = res.json()
                # TODO: do error checking
                #  keys: sandboxUrl, fileName, message, error: Bool, fileId
                return retval
            finally:
                import shutil
                shutil.rmtree(destdir)

        except Exception as e:
            self.record_error(str(e), 500)
            raise
