import os
import json
import logging
from pkg_resources import resource_string

from plone import api as ploneapi
from plone.app.uuid.utils import uuidToCatalogBrain
from plone.registry.interfaces import IRegistry
from plone.supermodel import loadString
from plone.uuid.interfaces import IUUID

from zope.component import getUtility
from zope.interface import implementer
from zope.publisher.interfaces import NotFound, BadRequest
from zope.schema import getFields

from org.bccvl.site import defaults
from org.bccvl.site.api import dataset
from org.bccvl.site.api.base import BaseAPITraverser, BaseService
from org.bccvl.site.api.decorators import api, apimethod, returnwrapper
from org.bccvl.site.api.interfaces import IAPIService, IDMService, IJobService, IExperimentService, ISiteService
from org.bccvl.site.interfaces import IBCCVLMetadata, IDownloadInfo
from org.bccvl.site.job.interfaces import IJobUtility
from org.bccvl.site.swift.interfaces import ISwiftSettings


LOG = logging.getLogger(__name__)


class APITraverser(BaseAPITraverser):

    __name__ = "API"  # entry point needs name, as we can't use browser:view registration

    title = u'BCCVL APIs'
    description = u'BCCVL API endpoint'
    service_iface = IAPIService
    linkrel = 'service'


@implementer(IAPIService)
class DMVersionTraverser(BaseAPITraverser):

    title = u'Dataset API'
    description = u'Access datasets'
    method = 'GET'
    service_iface = IDMService
    linkrel = 'version'


@implementer(IAPIService)
class JobVersionTraverser(BaseAPITraverser):

    title = u'Job API'
    description = u'Access jobs'
    method = 'GET'
    service_iface = IJobService
    linkrel = 'version'


@implementer(IAPIService)
class ExperimentVersionTraverser(BaseAPITraverser):

    title = u'Experiment API'
    description = u'Access experiments'
    method = 'GET'
    service_iface = IExperimentService
    linkrel = 'version'


@implementer(IAPIService)
class SiteVersionTraverser(BaseAPITraverser):

    title = u'Site API'
    description = u'Access site information'
    method = 'GET'
    service_iface = ISiteService
    linkrel = 'version'


@api
@implementer(IDMService)
class DMService(BaseService):

    title = u'Dataset API v1'
    description = u'Access datasets'
    method = 'GET'
    encType = "application/x-www-form-urlencoded"

    @returnwrapper
    @apimethod(
        properties={
            'uuid': {
                'type': 'string',
                'title': 'Dataset UUID',
            }
        })
    def metadata(self, uuid):
        try:
            brain = uuidToCatalogBrain(uuid)
            if brain:
                return dataset.getdsmetadata(brain)
        except Exception as e:
            LOG.error('Caught exception %s', e)
        raise NotFound(self, 'metadata', self.request)

    @returnwrapper
    @apimethod(
        properties={
            'uuid': {
                'type': 'string',
                'title': 'Dataset UUID',
            }
        })
    def update_metadata(self, uuid):
        try:
            brain = uuidToCatalogBrain(uuid)
            if brain:
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
                obj_url = brain.getURL()
                obj = brain.getObject()
                if obj.portal_type == 'org.bccvl.content.dataset':
                    filename = obj.file.filename
                    obj_url = '{}/@@download/file/{}'.format(obj_url, filename)
                else:
                    filename = os.path.basename(obj.remoteUrl)
                    obj_url = '{}/@@download/{}'.format(obj_url, filename)

                from org.bccvl.tasks.celery import app
                update_task = app.signature(
                    "org.bccvl.tasks.datamover.update_metadata",
                    args=(obj_url,
                          filename,
                          obj.format,
                          {
                              'context': '/'.join(obj.getPhysicalPath()),
                              'user': user,
                          }
                    ),
                    options={'immutable': True});

                from org.bccvl.tasks.plone import after_commit_task
                from org.bccvl.site.job.interfaces import IJobTracker
                after_commit_task(update_task)
                # track background job state
                jt = IJobTracker(obj)
                job = jt.new_job('TODO: generate id', 'generate taskname: update_metadata')
                job.type = obj.portal_type
                jt.set_progress('PENDING', 'Metadata update pending')
                return job.id
        except Exception as e:
            LOG.error('Caught exception %s', e)
        raise NotFound(self, 'update_metadata', self.request)


@api
@implementer(IJobService)
class JobService(BaseService):

    title = u'Job API v1'
    description = u'Access jobs'
    method = 'GET'
    encType = "application/x-www-form-urlencoded"

    @returnwrapper
    @apimethod(
        properties={
            'uuid': {
                'type': 'string',
                'title': 'Object uuid',
                'description': 'Experiment, result or datasetid for which to query job state',
                'default': None,
            },
            'jobid': {
                'type': 'string',
                'title': 'Job id',
                'default': None
            },
        })
    def state(self, jobid=None, uuid=None):
        job = None
        try:
            jobtool = getUtility(IJobUtility)
            if jobid:
                job = jobtool.get_job_by_id(jobid)
            elif uuid:
                job = jobtool.find_job_by_uuid(uuid)
            else:
                raise BadRequest('Reqired parameter jobid or uuid missing')
        except KeyError:
            LOG.warning("Can't find job with id %s", jobid)
        # check current user permissions:
        # TODO: should we check if we have view permissions in case we look at job state for content object?
        # only give access to job state if manager or owner
        user = ploneapi.user.get_current()
        if user.getId() != job.userid:
            roles = user.getRoles()
            # intersect required roles with user roles
            if not (set(roles) & set(('Manager', 'SiteAdministrator'))):
                job = None
        if job:
            return job.state
        # No job found
        raise NotFound(self, 'state', self.request)

    @returnwrapper
    @apimethod(
        properties={
            '**kw': {
                'type': 'object',
                'title': 'Query',
                'descirption': 'query parameters as keywords'
            }
    })
    def query(self):
        # FIXME: add owner check here -> probably easiest to make userid query parameter part of jobtool query function?  ; could also look inteo allowed_roles in catalog?
        query = self.request.form
        if not query:
            raise BadRequest('No query parameters supplied')
        jobtool = getUtility(IJobUtility)
        # add current userid to query
        user = ploneapi.user.get_current()
        roles = user.getRoles()
        # intersect required roles with user roles
        if not (set(roles) & set(('Manager', 'SiteAdministrator'))):
            query['userid'] = user.getId()

        brains = jobtool.query(**query)
        if brains:
            brain = brains[0]
            return {
                'id': brain.id,
                'state': brain.state
            }
        else:
            return {}


@api
@implementer(IExperimentService)
class ExperimentService(BaseService):

    title = u'Experiment API v1'
    description = u'Manage experiments'
    method = 'GET'
    encType = "application/x-www-form-urlencoded"

    @returnwrapper
    @apimethod(
        method='POST',
        encType='application/x-www-form-urlencoded',
        properties={
            'lsid': {
                'type': 'string',
                'title': 'Species LSID',
                'description': 'The LSID of a species',
            }
        })
    def demosdm(self, lsid):
        if self.request.get('REQUEST_METHOD', 'GET').upper() != 'POST':
            raise BadRequest('Request must be POST')
        # Swift params
        swiftsettings = getUtility(IRegistry).forInterface(ISwiftSettings)

        # get parameters
        if not lsid:
            raise BadRequest('Required parameter lsid missing')
        # we have an lsid,.... we can't really verify but at least some data is here
        # find rest of parameters
        # FIXME: hardcoded path to environmental datasets
        portal = ploneapi.portal.get()
        dspath = '/'.join([defaults.DATASETS_FOLDER_ID,
                           defaults.DATASETS_CLIMATE_FOLDER_ID,
                           'australia', 'australia_5km',
                           'current.zip'])
        ds = portal.restrictedTraverse(dspath)
        dsuuid = IUUID(ds)
        # FIXME: we don't use a IJobTracker here for now
        # get toolkit and
        func = portal[defaults.TOOLKITS_FOLDER_ID]['demosdm']
        # build job_params:
        dlinfo = IDownloadInfo(ds)
        dsmd = IBCCVLMetadata(ds)
        envlist = []
        for layer in ('B01', 'B04', 'B05', 'B06', 'B12', 'B15', 'B16', 'B17'):
            envlist.append({
                'uuid': dsuuid,
                'filename': dlinfo['filename'],
                'downloadurl': dlinfo['url'],
                'layer': layer,
                'type': dsmd['layers'][layer]['datatype'],
                'zippath': dsmd['layers'][layer]['filename']
            })

        job_params = {
            'resolution': IBCCVLMetadata(ds)['resolution'],
            'function': func.getId(),
            'species_occurrence_dataset': {
                'uuid': lsid,
                'species': u'demoSDM',
                'downloadurl': 'ala://ala?lsid={}'.format(lsid),
            },
            'environmental_datasets': envlist,
        }
        # add toolkit parameters: (all default values)
        # get toolkit schema
        schema = loadString(func.schema).schema
        for name, field in getFields(schema).items():
            if field.default is not None:
                job_params[name] = field.default
        # add other default parameters
        job_params.update({
            'rescale_all_models': False,
            'selected_models': 'all',
            'modeling_id': 'bccvl',
        })
        # generate script to run
        script = u'\n'.join([
            resource_string('org.bccvl.compute', 'rscripts/bccvl.R'),
            resource_string('org.bccvl.compute', 'rscripts/eval.R'),
            func.script])
        # where to store results
        result = {
            'results_dir': 'swift+{}/demosdm/{}/'.format(swiftsettings.storage_url, lsid),
            'outputs': json.loads(func.output)
        }
        # worker hints:
        worker = {
            'script': {
                'name': '{}.R'.format(func.getId()),
                'script': script
            },
            'files': (
                'species_occurrence_dataset',
                'environmental_datasets'
            )
        }
        # put everything together
        jobdesc = {
            'env': {},
            'params': job_params,
            'worker': worker,
            'result': result,
        }

        # create job
        jobtool = getUtility(IJobUtility)
        job = jobtool.new_job()
        job.lsid = lsid
        job.toolkit = IUUID(func)
        job.function = func.getId()
        job.type = 'org.bccvl.content.sdmexperiment'
        jobtool.reindex_job(job)
        # create job context object
        member = ploneapi.user.get_current()
        context = {
            # we use the site object as context
            'context': '/'.join(portal.getPhysicalPath()),
            'jobid': job.id,
            'user': {
                'id': member.getUserName(),
                'email': member.getProperty('email'),
                'fullname': member.getProperty('fullname')
            },
        }

        # all set to go build task chain now
        from org.bccvl.tasks.compute import demo_task
        from org.bccvl.tasks.plone import after_commit_task
        after_commit_task(demo_task, jobdesc, context)
        # let's hope everything works, return result

        swift_url = '{}/demosdm'.format(swiftsettings.storage_url)
        return {
            'state': '{}/{}/state.json'.format(swift_url, lsid),
            'result': '{}/{}/projection.png'.format(swift_url, lsid),
            'jobid': job.id
        }

    # TODO: check security



@api
@implementer(ISiteService)
class SiteService(BaseService):

    title = u'Global misc. API v1'
    description = u'Access site wide information'
    method = 'GET'
    encType = "application/x-www-form-urlencoded"

    @returnwrapper
    @apimethod(
        properties={
            'uuid': {
                'type': 'string',
                'title': 'Object UUID',
                'description': 'The UUID for a content object',
            }
        }
    )
    def can_access(self, uuid=None):
        if uuid:
            context = uuidToCatalogBrain(uuid)
        else:
            context = self.context
        if context is None:
            return 'denied'
        else:
            return 'allowed'
