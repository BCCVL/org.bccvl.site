import logging
import os

from AccessControl import Unauthorized
from Products.CMFCore.interfaces import ISiteRoot
from Products.CMFCore.utils import getToolByName

from plone import api as ploneapi
from plone.app.uuid.utils import uuidToCatalogBrain
from plone.batching import Batch
from plone.dexterity.utils import createContentInContainer
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
from org.bccvl.site.interfaces import IBCCVLMetadata, IExperimentJobTracker
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
                options={'immutable': True})

            from org.bccvl.tasks.plone import after_commit_task
            after_commit_task(update_task)
            # track background job state
            jt = IJobTracker(obj)
            job = jt.new_job('TODO: generate id',
                             'generate taskname: update_metadata')
            job.type = obj.portal_type
            jt.set_progress('PENDING', 'Metadata update pending')
            return job.id
        except Exception as e:
            LOG.error('Caught exception %s', e)
        raise NotFound(self, 'update_metadata', self.request)

    def import_trait_data(self):
        source = self.request.form.get('source', None)
        species = self.request.form.get('species', None)
        traits = self.request.form.get('traits', None)
        environ = self.request.form.get('environ', None)
        context = None
        # get import context
        if ISiteRoot.providedBy(self.context):
            # we have been called at site root... let's traverse to default
            # import location
            context = self.context.restrictedTraverse(
                "/".join((defaults.DATASETS_FOLDER_ID,
                          defaults.DATASETS_SPECIES_FOLDER_ID,
                          'aekos')))
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
        if not source or source not in ('aekos'):
            raise BadRequest("source parameter bust be 'aekos'")
        if not species or not isinstance(species, (basestring, list)):
            raise BadRequest("Missing or invalid species parameter")
        elif isinstance(species, basestring):
            species = [species]
        if not traits and not environ:
            raise BadRequest("At least on of traits or environ has to be set")
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
        ds = createContentInContainer(context, portal_type, title=title)
        ds.dataSource = source
        ds.description = u' '.join([
            title, ','.join(traits), ','.join(environ),
            u' imported from {}'.format(source.upper())])
        md = IBCCVLMetadata(ds)
        md['genre'] = 'DataGenreTraits'
        md['categories'] = ['traits']
        md['species'] = [{
            'scientificName': spec,
            'taxonID': spec} for spec in species]
        md['traits'] = traits
        md['environ'] = environ
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
