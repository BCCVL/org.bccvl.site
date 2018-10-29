import os
import json
import logging
import urllib
from pkg_resources import resource_string

from Products.CMFCore.interfaces import ISiteRoot

from plone import api as ploneapi
from plone.app.uuid.utils import uuidToObject, uuidToCatalogBrain
from plone.registry.interfaces import IRegistry
from plone.supermodel import loadString
from plone.uuid.interfaces import IUUID
from plone.namedfile.file import NamedBlobFile

from zope.component import getUtility
from zope.interface import implementer
from zope.publisher.interfaces import BadRequest, NotFound
from zope.schema import getFields
from zope.schema.interfaces import IVocabularyFactory

from org.bccvl.site import defaults
from org.bccvl.site.api.base import BaseService
from org.bccvl.site.api.decorators import api
from org.bccvl.site.api.interfaces import IExperimentService
from org.bccvl.site.interfaces import (
    IBCCVLMetadata, IDownloadInfo, IExperimentJobTracker)
from org.bccvl.site.job.interfaces import IJobUtility, IJobTracker
from org.bccvl.site.stats.interfaces import IStatsUtility
from org.bccvl.site.swift.interfaces import ISwiftSettings


LOG = logging.getLogger(__name__)


@api('em_v1.json')
@implementer(IExperimentService)
class ExperimentService(BaseService):

    title = u'Experiment API v1'
    description = u'Manage experiments'

    TEMPORAL_ENV_DATA_LAYERS = {
        'daily_rainfall': {
            'layer': 'daily_rainfall',
            'varname': 'lwe_thickness_of_precipitation_amount',
            'downloadurl': 'http://dapds00.nci.org.au/thredds/dodsC/rr9/eMAST_data/ANUClimate/ANUClimate_v1-0_rainfall_daily_0-01deg_1970-2014',
            'type': 'continuous'
        },
        'daily_min_temp': {
            'layer': 'daily_min_temp',
            'varname': 'air_temperature',
            'downloadurl': 'http://dapds00.nci.org.au/thredds/dodsC/rr9/eMAST_data/ANUClimate/ANUClimate_v1-1_temperature-min_daily_0-01deg_1970-2014',
            'type': 'continuous'
        },
        'daily_max_temp': {
            'layer': 'daily_max_temp',
            'varname': 'air_temperature',
            'downloadurl': 'http://dapds00.nci.org.au/thredds/dodsC/rr9/eMAST_data/ANUClimate/ANUClimate_v1-1_temperature-max_daily_0-01deg_1970-2014',
            'type': 'continuous'
        },
        'daily_mean_temp': {
            'layer': 'daily_mean_temp',
            'varname': 'air_temperature',
            'downloadurl': 'http://dapds00.nci.org.au/thredds/dodsC/rr9/eMAST_data/ANUClimate/ANUClimate_v1-1_temperature_daily_0-01deg_1970-2014',
            'type': 'continuous'
        },
        'daily_vapour_pressure': {
            'layer': 'daily_vapour_pressure',
            'varname': 'vapour_pressure',
            'downloadurl': 'http://dapds00.nci.org.au/thredds/dodsC/rr9/eMAST_data/ANUClimate/ANUClimate_v1-1_vapour-pressure_daily_0-01deg_1970-2014',
            'type': 'continuous'
        }
    }

    def submitsdm(self):
        # TODO: catch UNAuthorized correctly and return json error
        if self.request.get('REQUEST_METHOD', 'GET').upper() != 'POST':
            self.record_error('Request must be POST', 400)
            raise BadRequest('Request must be POST')
        # make sure we have the right context
        if ISiteRoot.providedBy(self.context):
            # we have been called at site root... let's traverse to default
            # experiments location
            context = self.context.restrictedTraverse(
                defaults.EXPERIMENTS_FOLDER_ID)
        else:
            # custom context.... let's use in
            context = self.context

        # parse request body
        params = self.request.form
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
            self.record_error('Bad Request', 400,
                              'Missing parameter occurrence_data',
                              {'parameter': 'occurrence_data'})
        else:
            # FIXME:  should properly support source / id
            #         for now only bccvl source is supported
            props['species_occurrence_dataset'] = params[
                'occurrence_data']['id']
        # FIXME: should properly support source/id for onw only bccvl source is
        # supported
        props['species_absence_dataset'] = params.get(
            'absence_data', {}).get('id', None)
        props['scale_down'] = params.get('scale_down', False)
        if not params.get('environmental_data', None):
            self.record_error('Bad Request', 400,
                              'Missing parameter environmental_data',
                              {'parameter': 'environmental_data'})
        else:
            props['environmental_datasets'] = params['environmental_data']
        if params.get('modelling_region', ''):
            props['modelling_region'] = NamedBlobFile(
                data=json.dumps(params['modelling_region']))
        else:
            props['modelling_region'] = None
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
        experiment = addContentToContainer(context, experiment)

        # TODO: check if props and algo params have been applied properly
        experiment.parameters = dict(props['functions'])
        # FIXME: need to get resolution from somewhere
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

    def submitcc(self):
        # TODO: catch UNAuthorized correctly and return json error
        if self.request.get('REQUEST_METHOD', 'GET').upper() != 'POST':
            self.record_error('Request must be POST', 400)
            raise BadRequest('Request must be POST')
        # make sure we have the right context
        if ISiteRoot.providedBy(self.context):
            # we have been called at site root... let's traverse to default
            # experiments location
            context = self.context.restrictedTraverse(
                defaults.EXPERIMENTS_FOLDER_ID)
        else:
            # custom context.... let's use in
            context = self.context

        # parse request body
        params = self.request.form
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

        if not params.get('species_distribution_models', None):
            self.record_error('Bad Request', 400,
                              'Missing parameter species_distribution_models',
                              {'parameter': 'species_distribution_models'})
        else:
            props['species_distribution_models'] = params[
                'species_distribution_models']

        if not params.get('future_climate_datasets', None):
            self.record_error('Bad Request', 400,
                              'Missing parameter future_climate_datasets',
                              {'parameter': 'future_climate_datasets'})
        else:
            props['future_climate_datasets'] = params[
                'future_climate_datasets']
        if params.get('projection_region', ''):
            props['projection_region'] = NamedBlobFile(
                data=json.dumps(params['projection_region']))
        else:
            props['projection_region'] = None

        if self.errors:
            raise BadRequest("Validation Failed")

        # create experiment with data as form would do
        # TODO: make sure self.context is 'experiments' folder?
        from plone.dexterity.utils import createContent, addContentToContainer
        experiment = createContent("org.bccvl.content.projectionexperiment",
                                   **props)
        experiment = addContentToContainer(context, experiment)
        # FIXME: need to get resolution from somewhere
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

    def submittraits(self):
        # TODO: catch UNAuthorized correctly and return json error
        if self.request.get('REQUEST_METHOD', 'GET').upper() != 'POST':
            self.record_error('Request must be POST', 400)
            raise BadRequest('Request must be POST')
        # make sure we have the right context
        if ISiteRoot.providedBy(self.context):
            # we have been called at site root... let's traverse to default
            # experiments location
            context = self.context.restrictedTraverse(
                defaults.EXPERIMENTS_FOLDER_ID)
        else:
            # custom context.... let's use in
            context = self.context

        # parse request body
        params = self.request.form
        # validate input
        # TODO: should validate type as well..... (e.g. string has to be
        # string)
        # TODO: validate dataset and layer id's existence if possible
        props = {}
        if params.get('species_list', None):
            props['species_list'] = params['species_list']
        else:
            self.record_error('Bad Request', 400, 'Missing parameter speciesList',
                              {'parameter': 'speciesList'})

        if not params.get('title', None):
            self.record_error('Bad Request', 400, 'Missing parameter title',
                              {'parameter': 'title'})
        else:
            props['title'] = params['title']
        props['description'] = params.get('description', '')
        if not params.get('traits_data', None):
            self.record_error('Bad Request', 400,
                              'Missing parameter traits_data',
                              {'parameter': 'traits_data'})
        else:
            # FIXME:  should properly support source / id
            #         for now only bccvl source is supported
            props['species_traits_dataset'] = params[
                'traits_data']['id']

        props['species_traits_dataset_params'] = {}
        for col_name, col_val in params.get("columns", {}).items():
            if col_val not in ('lat', 'lon', 'species', 'trait_con', 'date'
                               'trait_ord', 'trait_nom', 'env_var_con',
                               'env_var_cat', 'random_con', 'random_cat'):
                continue
            props['species_traits_dataset_params'][col_name] = col_val
        if not props['species_traits_dataset_params']:
            self.record_error('Bad Request', 400,
                              'Invalid values  for columns',
                              {'parameter': 'columns'})

        props['scale_down'] = params.get('scale_down', False)

        # env data is optional
        props['environmental_datasets'] = params.get('environmental_data', None)
        if not (props['environmental_datasets']
                or 'env_var_con' not in props['species_traits_dataset_params'].values()
                or 'env_var_cat' not in props['species_traits_dataset_params'].values()):
            self.record_error('Bad Request', 400,
                              'No Environmental data selected',
                              {'parameter': 'environmental_datasets'})

        # For temporal STM, env datasets are temporal dataset from NCI
        if params.get('temporal_STM', False):
            props['environmental_datasets'] = [ v for k, v in self.TEMPORAL_ENV_DATA_LAYERS.items() if k in params.get('environmental_data', [])]

        if params.get('modelling_region', ''):
            props['modelling_region'] = NamedBlobFile(
                data=json.dumps(params['modelling_region']))
        else:
            props['modelling_region'] = None

        if not params.get('algorithms', None):
            self.record_error('Bad Request', 400,
                              'Missing parameter algorithms',
                              {'parameter': 'algorithms'})
        else:
            props['algorithms_species'] = {}
            props['algorithms_diff'] = {}
            funcs_env = getUtility(
                IVocabularyFactory, 'traits_functions_species_source')(context)
            funcs_species = getUtility(
                IVocabularyFactory, 'traits_functions_diff_source')(context)
            # FIXME: make sure we get the default values from our func object
            for algo_uuid, algo_params in params['algorithms'].items():
                if algo_params is None:
                    algo_params = {}
                toolkit = uuidToObject(algo_uuid)
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

                if algo_uuid in funcs_env:
                    props['algorithms_species'][algo_uuid] = func_props
                elif algo_uuid in funcs_species:
                    props['algorithms_diff'][algo_uuid] = func_props
                else:
                    LOG.warn(
                        'Algorithm {} not in allowed list of functions'.format(toolkit.id))
            if not (props['algorithms_species'] or props['algorithms_diff']):
                self.record_error('Bad Request', 400,
                                  'Iinvalid algorithms selected',
                                  {'parameter': 'algorithms'})

        if self.errors:
            raise BadRequest("Validation Failed")

        # create experiment with data as form would do
        # TODO: make sure self.context is 'experiments' folder?
        from plone.dexterity.utils import createContent, addContentToContainer
        exp_type = "org.bccvl.content.speciestraitsexperiment" if not params.get('temporal_STM', False) else "org.bccvl.content.speciestraitstemporalexperiment"
        experiment = createContent(exp_type, **props)
        experiment = addContentToContainer(context, experiment)
        experiment.parameters = dict(props['algorithms_species'])
        experiment.parameters.update(dict(props['algorithms_diff']))
        # FIXME: need to get resolution from somewhere
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

    def metadata(self):
        uuid = self.request.form.get('uuid')
        exp = uuidToObject(uuid)
        if not exp:
            self.record_error('Not Found', 404,
                              'Experiment not found',
                              {'parameter': 'uuid'})
            raise NotFound(self, 'metadata', self.request)
        # we found an experiment ... let's build the result
        retval = {
            'id': exp.id,
            'uuid': IUUID(exp),
            'title': exp.title,
            'description': exp.description,
            'job_state': IExperimentJobTracker(exp).state,
            'url': exp.absolute_url(),
            'results': []
        }
        # add info about parameters?
        # add info about results
        for result in exp.values():
            # Get the content of blob file for modelling_region/projection_region
            job_params = dict(**result.job_params)
            if 'modelling_region' in result.job_params:
                job_params['modelling_region'] = result.job_params['modelling_region'].data
            if 'projection_region' in result.job_params:
                job_params['projection_region'] = result.job_params['projection_region'].data

            retval['results'].append({
                'id': result.id,
                'uuid': IUUID(result),
                'title': result.title,
                'description': result.description,
                'job_state': IJobTracker(result).state,
                'params': job_params,
                'url': result.absolute_url()
            })
        return retval

    def status(self):
        # redundant? ... see metadata
        uuid = self.request.form.get('uuid')
        exp = uuidToCatalogBrain(uuid)
        if not exp:
            self.record_error('Not Found', 404,
                              'Experiment not found',
                              {'parameter': 'uuid'})
            raise NotFound(self, 'status', self.request)

        jt = IExperimentJobTracker(exp.getObject())
        return {
            'status': jt.state,
            'results': jt.states
        }

    def demosdm(self):
        lsid = self.request.form.get('lsid')
        # Run SDM on a species given by lsid (from ALA), followed by a Climate
        # Change projection.
        if self.request.get('REQUEST_METHOD', 'GET').upper() != 'POST':
            raise BadRequest('Request must be POST')
        # Swift params
        swiftsettings = getUtility(IRegistry).forInterface(ISwiftSettings)

        # get parameters
        if not lsid:
            raise BadRequest('Required parameter lsid missing')
        # we have an lsid,.... we can't really verify but at least some
        #                      data is here
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
        job = jobtool.new_job(
            lsid=lsid,
            toolkit=IUUID(func),
            function=func.getId(),
            type='demosdm'
        )
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
        from org.bccvl.tasks.plone import after_commit_task, HIGH_PRIORITY
        after_commit_task(demo_task, HIGH_PRIORITY, jobdesc, context)
        # let's hope everything works, return result

        # We don't create an experiment object, so we don't count stats here
        # let's do it manually
        getUtility(IStatsUtility).count_experiment(
            user=member.getId(),
            portal_type='demosdm',
        )

        return {
            'state': os.path.join(result['results_dir'], 'state.json'),
            'result': os.path.join(result['results_dir'], 'proj_metadata.json'),
            'jobid': job.id
        }
