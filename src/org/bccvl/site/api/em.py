import os
import json
import logging
import urllib
from pkg_resources import resource_string

from plone import api as ploneapi
from plone.registry.interfaces import IRegistry
from plone.supermodel import loadString
from plone.uuid.interfaces import IUUID

from zope.component import getUtility
from zope.interface import implementer
from zope.publisher.interfaces import BadRequest
from zope.schema import getFields

from org.bccvl.site import defaults
from org.bccvl.site.api.base import BaseService
from org.bccvl.site.api.decorators import api, apimethod, returnwrapper
from org.bccvl.site.api.interfaces import IExperimentService
from org.bccvl.site.interfaces import (
    IBCCVLMetadata, IDownloadInfo, IExperimentJobTracker)
from org.bccvl.site.job.interfaces import IJobUtility, IJobTracker
from org.bccvl.site.swift.interfaces import ISwiftSettings


LOG = logging.getLogger(__name__)


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
        props['modelling_region'] = json.dumps(
            params.get('modelling_region', ''))
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
