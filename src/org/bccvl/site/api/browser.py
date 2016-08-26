import os
import json
import logging
import urllib
from pkg_resources import resource_string

from AccessControl import Unauthorized
from Products.CMFCore.interfaces import ISiteRoot

from plone import api as ploneapi
from plone.app.uuid.utils import uuidToCatalogBrain
from plone.dexterity.utils import createContentInContainer
from plone.registry.interfaces import IRegistry
from plone.supermodel import loadString
from plone.uuid.interfaces import IUUID

from zope.component import getUtility, queryUtility
from zope.interface import implementer
from zope.publisher.interfaces import NotFound, BadRequest
from zope.schema import getFields
from zope.schema.interfaces import IContextSourceBinder
from zope.schema.vocabulary import getVocabularyRegistry
from zope.security import checkPermission

from org.bccvl.site import defaults
from org.bccvl.site.api import dataset
from org.bccvl.site.api.base import BaseAPITraverser, BaseService
from org.bccvl.site.api.decorators import api, apimethod, returnwrapper
from org.bccvl.site.api.interfaces import (
    IAPIService, IDMService, IJobService, IExperimentService, ISiteService)
from org.bccvl.site.interfaces import (
    IBCCVLMetadata, IDownloadInfo, IExperimentJobTracker)
from org.bccvl.site.job.interfaces import IJobUtility, IJobTracker
from org.bccvl.site.swift.interfaces import ISwiftSettings
import pkg_resources
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart


LOG = logging.getLogger(__name__)


class APITraverser(BaseAPITraverser):

    # entry point needs name, as we can't use browser:view registration
    __name__ = "API"

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
    def update_metadata(self, uuid=None):
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

    @returnwrapper
    @apimethod(
        method='POST',
        encType="application/x-www-form-urlencoded",
        properties={
            'source': {
                'type': 'string',
                'title': 'data source',
            },
            'species': {
                'type': 'list',
                'title': 'List of source specific species identifiers.',
            },
            'traits': {
                'type': 'list',
                'title': 'List of source specific trait identifiers.',
            },
            'environ': {
                'type': 'list',
                'title': 'List of source specific environment variables.',
            }
        })
    def import_trait_data(self, source=None, species=None,
                          traits=None, environ=None):
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
        # FIXME: add owner check here -> probably easiest to make userid query
        # parameter part of jobtool query function?  ; could also look inteo
        # allowed_roles in catalog?
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
        encType='application/json',
        properties={
            'title': {
                'type': 'string',
                'title': 'Experiment title',
                'description': 'A title for this experiment',
            },
            'description': {
                'type': 'string',
                'title': 'Description',
                'description': 'A short description for this experiment',
            },
            'occurrence_data': {
                'title': 'Occurrence Data',
                'type': 'object',
                'description': 'Occurrence data to use',
                'properties': {
                    'source': {
                        'title': 'Occurrence data source',
                        'description': 'Source from where to fetch the occurrence data',
                        'type': 'string',
                        'enum': ['ala', 'bccvl', 'gbif', 'aekos']
                    },
                    'id': {
                        'title': 'Dataset id',
                        'description': 'Dataset id specific for data source',
                    }
                }
            },
            'abbsence_data': {
                'title': 'Occurrence Data',
                'type': 'object',
                'description': 'Occurrence data to use',
                'properties': {
                    'source': {
                        'title': 'Abasence data source',
                        'description': 'Source from where to fetch the absence data',
                        'type': 'string',
                        'enum': ['bccvl']
                    },
                    'id': {
                        'title': 'Dataset id',
                        'description': 'Dataset id specific for data source',
                    }
                }
            },
            'scale_down': {
                'type': 'booloan',
                'title': 'Common resolution',
                'description': 'Scale to highest (true) or lowest (false) resolution',
            },
            'environmental_data': {
                'title': 'Climate & Environmental data',
                'description': 'Selected climate and environmental data',
                'type': 'object',
                'patternProperties': {
                    '.+': {
                        'title': 'Dataset',
                        'description': "key is a dataset id, and value should be alist of layer id's availaible within this dataset",
                        'type': 'array',
                        'items': {'type': 'string'}
                    }
                }
            },
            'modelling_region': {
                'title': 'Modelling Region',
                'description': "A region to constrain the modelling area to. The value is expected to be a GeoJSON object of type 'feature'",
                'type': 'object'
            },
            'algorithms': {
                'title': 'Algorithms',
                'description': 'Algorithms to use.',
                'type': 'object',
                'patternProperties': {
                    '.+': {
                        'title': 'Algorithm',
                        'description': 'The algorithm id. Properties for each algorithm describe the algorithm parameters.',
                        'type': 'object'
                    }
                }
            }
        })
    def submit_sdm(self):
        if self.request.get('REQUEST_METHOD', 'GET').upper() != 'POST':
            self.record_error('Request must be POST', 400)
            raise BadRequest('Request must be POST')
        # parse request body
        import ipdb
        ipdb.set_trace()
        params = json.load(self.request.BODYFILE)
        # validate input
        # TODO: should validate type as well..... (e.g. string has to be
        # string)
        # TODO: validate dataset and layer id's existence if possible
        props = {}
        if not params.get('title', None):
            self.record_error('Bad Request', 400, 'Missing parameter title',
                              {'parameter': 'title'})
        else:
            props['title'] = params['title']
        props['description'] = params.get('description', '')
        if not params.get('occurrence_data', None):
            self.record_error('Bad Request', 400, 'Missing parameter occurrence_data',
                              {'parameter': 'occurrence_data'})
        else:
            # FIXME:  should properly support source / id
            #         for now only bccvl source is supported
            props['species_occurrence_dataset'] = params[
                'occurrence_data']['id']
        # FIXME: should properly support source/id for onw only bccvl source is
        # supported
        props['species_abesnce_dataset'] = params.get(
            'absence_data', {}).get('id', None)
        props['scale_down'] = params.get('scale_down', False)
        if not params.get('environmental_data', None):
            self.record_error('Bad Request', 400,
                              'Missing parameter environmental_data',
                              {'parameter': 'environmental_data'})
        else:
            props['environmental_datasets'] = params['environmental_data']
        # FIXME: it is supposed to be a string
        props['modelling_region'] = params.get('modelling_region', None)
        if not params.get('algorithms', None):
            self.record_error('Bad Request', 400,
                              'Missing parameter algorithms',
                              {'parameter': 'algorithms'})
        else:
            portal = ploneapi.portal.get()
            props['functions'] = {}
            # FIXME: make sure we get the default values from our func object
            for algo, algo_params in params['algorithms'].items():
                if algo_params is None:
                    algo_params = {}
                toolkit = portal[defaults.FUNCTIONS_FOLDER_ID][algo]
                toolkit_model = loadString(toolkit.schema)
                toolkit_schema = toolkit_model.schema

                func_props = {}

                for field_name in toolkit_schema.names():
                    field = toolkit_schema.get(field_name)
                    value = algo_params.get(field_name, field.missing_value)
                    if value == field.missing_value:
                        func_props[field_name] = field.default
                    else:
                        func_props[field_name] = value

                props['functions'][IUUID(toolkit)] = func_props

        if self.errors:
            raise BadRequest("Validation Failed")

        # create experiment with data as form would do
        # TODO: make sure self.context is 'experiments' folder?
        from plone.dexterity.utils import createContent, addContentToContainer
        experiment = createContent("org.bccvl.content.sdmexperiment", **props)
        experiment = addContentToContainer(self.context, experiment)
        # TODO: check if props and algo params have been applied properly
        experiment.parameters = dict(props['functions'])
        # TODO: need to get resolution from somewhere
        IBCCVLMetadata(experiment)['resolution'] = 'Resolution30m'

        # submit newly created experiment
        # TODO: handle background job submit .... at this stage we wouldn't
        #       know the model run job ids
        # TODO: handle submit errors and other errors that may happen above?
        #       generic exceptions could behandled in returnwrapper
        retval = {
            'experiment': {
                'url': experiment.absolute_url(),
                'uuid': IUUID(experiment)
            },
            'jobs': [],
        }
        jt = IExperimentJobTracker(experiment)
        msgtype, msg = jt.start_job(self.request)
        if msgtype is not None:
            retval['message'] = {
                'type': msgtype,
                'message': msg
            }
        for result in experiment.values():
            jt = IJobTracker(result)
            retval['jobs'].append(jt.get_job().id)
        return retval

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
        # Run SDM on a species given by lsid (from ALA), followed by a Climate
        # Change projection.
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

        # Get the future climate for climate change projection
        portal = ploneapi.portal.get()
        dspath = '/'.join([defaults.DATASETS_FOLDER_ID,
                           defaults.DATASETS_CLIMATE_FOLDER_ID,
                           'australia', 'australia_1km',
                           'RCP85_ukmo-hadgem1_2085.zip'])
        ds = portal.restrictedTraverse(dspath)
        dsuuid = IUUID(ds)
        dlinfo = IDownloadInfo(ds)
        dsmd = IBCCVLMetadata(ds)
        futureclimatelist = []
        for layer in ('B05', 'B06', 'B13', 'B14'):
            futureclimatelist.append({
                'uuid': dsuuid,
                'filename': dlinfo['filename'],
                'downloadurl': dlinfo['url'],
                'layer': layer,
                'type': dsmd['layers'][layer]['datatype'],
                'zippath': dsmd['layers'][layer]['filename']
            })
        # Climate change projection name
        cc_projection_name = os.path.splitext(dlinfo['filename'])[0]

        # Get the current climate for SDM
        dspath = '/'.join([defaults.DATASETS_FOLDER_ID,
                           defaults.DATASETS_CLIMATE_FOLDER_ID,
                           'australia', 'australia_1km',
                           'current.76to05.zip'])
        ds = portal.restrictedTraverse(dspath)
        dsuuid = IUUID(ds)
        dlinfo = IDownloadInfo(ds)
        dsmd = IBCCVLMetadata(ds)
        envlist = []
        for layer in ('B05', 'B06', 'B13', 'B14'):
            envlist.append({
                'uuid': dsuuid,
                'filename': dlinfo['filename'],
                'downloadurl': dlinfo['url'],
                'layer': layer,
                'type': dsmd['layers'][layer]['datatype'],
                'zippath': dsmd['layers'][layer]['filename']
            })

        # FIXME: we don't use a IJobTracker here for now
        # get toolkit and
        func = portal[defaults.TOOLKITS_FOLDER_ID]['demosdm']
        # build job_params:
        job_params = {
            'resolution': IBCCVLMetadata(ds)['resolution'],
            'function': func.getId(),
            'species_occurrence_dataset': {
                'uuid': 'ala_occurrence_dataset',
                'species': u'demoSDM',
                'downloadurl': 'ala://ala?lsid={}'.format(lsid),
            },
            'environmental_datasets': envlist,
            'future_climate_datasets': futureclimatelist,
            'cc_projection_name': cc_projection_name
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
        # where to store results.
        result = {
            'results_dir': 'swift+{}/wordpress/{}/'.format(swiftsettings.storage_url, urllib.quote_plus(lsid)),
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
                'environmental_datasets',
                'future_climate_datasets'
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

        return {
            'state': os.path.join(result['results_dir'], 'state.json'),
            'result': os.path.join(result['results_dir'], 'proj_metadata.json'),
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

    @returnwrapper
    @apimethod(
        properties={
            'uuid': {
                'type': 'string',
                'title': 'Experiment URL',
            }
        }
    )
    def send_support_email(self, url=None):
        try:
            if url is None:
                raise Exception("URL is not specified")

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

            portal_email = ploneapi.portal.get().getProperty('email_from_address')
            email_to = [portal_email, user['email']]
            subject = "Help: BCCVL experiment failed"
            body = pkg_resources.resource_string(
                "org.bccvl.site.api", "help_email.txt")
            body = body.format(experiment_url=url, username=user[
                'fullname'], user_email=user['email'])

            htmlbody = pkg_resources.resource_string(
                "org.bccvl.site.api", "help_email.html")
            htmlbody = htmlbody.format(experiment_url=url, username=user[
                'fullname'], user_email=user['email'])

            msg = MIMEMultipart('alternative')
            msg.attach(MIMEText(body, 'plain'))
            msg.attach(MIMEText(htmlbody, 'html'))

            ploneapi.portal.send_email(
                recipient=email_to, sender=portal_email, subject=subject, body=msg.as_string())
            return {
                'success': True,
                'message': u'Your email has been sent'
            }
        except Exception as e:
            LOG.error('send_support_email: exception %s', e)
            return {
                'success': False,
                'message': u'Fail to send your email to BCCVL support. Exception {}'.format(e)
            }

    @returnwrapper
    @apimethod(
        properties={
            'uuid': {
                'type': 'string',
                'title': 'Vocabulary Name',
                'description': 'The name for a registered vocabulary',
            }
        }
    )
    def vocabulary(self, name=None):
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
