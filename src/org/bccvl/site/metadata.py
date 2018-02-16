import StringIO
import os, os.path
import json
import re
from copy import deepcopy
from decimal import Decimal
from plone.app.uuid.utils import uuidToObject, uuidToCatalogBrain
from zope.interface import implementer
from zope.component import adapter, getUtility
from zope.schema.interfaces import IVocabularyFactory
from zope.annotation import IAnnotations, IAttributeAnnotatable
from persistent.dict import PersistentDict
from Products.CMFCore.interfaces import ISiteRoot
from org.bccvl.site.behavior.collection import ICollection
from org.bccvl.site.content.interfaces import IExperiment, IProjectionExperiment
from org.bccvl.site.interfaces import IBCCVLMetadata, IDownloadInfo, IProvenanceData, IExperimentMetadata, IExperimentParameter
from org.bccvl.compute.utils import getdatasetparams

# TODO: this will become future work to enhance performance by
# reducing the amonut of queries we have to do against the triple
# store (no more direkt data fetching from triple store, as we don't
# utilise the full power anyway)
# TODO: will this adapter do a write on read? (should be avoided)


KEY = 'org.bccvl.site.content.metadata'


@implementer(IBCCVLMetadata)
@adapter(IAttributeAnnotatable)
class BCCVLMetadata(object):
    '''
    Adapter to manage additional metadata for BCCVL Datasets.
    '''

    __marker = object()

    def __init__(self, context):
        self.context = context
        annotations = IAnnotations(context)
        self._md = annotations.setdefault(KEY, PersistentDict())

    def __getitem__(self, key):
        return self._md.__getitem__(key)

    def __setitem__(self, key, value):
        return self._md.__setitem__(key, value)

    def __delitem__(self, key):
        return self._md.__delitem__(key)

    def update(self, *args, **kw):
        return self._md.update(*args, **kw)

    def get(self, k, default=None):
        return self._md.get(k, default)

    def keys(self):
        return self._md.keys()

    def __iter__(self):
        return self._md.__iter__()

    def setdefault(self, key, default):
        return self._md.setdefault(key, default)

    def pop(self, key, default=__marker):
        if default is self.__marker:
            return self._md.pop(key)
        return self._md.pop(key, default)


PROV_KEY = 'org.bccvl.site.content.provenance'
    
@implementer(IProvenanceData)
@adapter(IAttributeAnnotatable)
class ProvenanceData(object):
    '''
    Adapter to manage provenance data on result containers
    '''

    __marker = object()

    def __init__(self, context):
        self.context = context
        self.annots = IAnnotations(context)

    @property
    def data(self):
        return self.annots.get(PROV_KEY)

    @data.setter
    def data(self, value):
        # check if graph or string
        # serialise or store as is
        self.annots[PROV_KEY] = value
    

@implementer(IExperimentParameter)
@adapter(IAttributeAnnotatable)
class ExperimentParameter(object):
    '''
    Adapter to manage parameters data on result containers
    '''

    __marker = object()

    def __init__(self, context):
        self.context = context

    def __generateParameters(self, params, portal_type):
        # This code formats the input parameters to experiments, and is a mirror "copy" of get_sdm_params, 
        # get_project_params, get_biodiverse_params, get_traits_params, get_ensemble_params in org.bccvl.compute.
        inp = deepcopy(params)
        for key, val in inp.items():
            if key in ('species_occurrence_dataset', 'species_absence_dataset'):
                if val:
                    val = getdatasetparams(val)
                    val['species'] = re.sub(u"[ _,\-'\"/\(\)\{\}\[\]]", u".", val.get('species', u'Unknown'))

            if key in ('environmental_datasets', 'future_climate_datasets'):
                envlist = []
                for uuid, layers in val.items():
                    dsinfo = getdatasetparams(uuid)
                    for layer in layers:
                        dsdata = {
                            'uuid': dsinfo['uuid'],
                            'filename': dsinfo['filename'],
                            'downloadurl': dsinfo['downloadurl'],
                            # TODO: should we use layer title or URI?
                            'layer': layer,
                            'type': dsinfo['layers'][layer]['datatype']
                        }
                        # if this is a zip file we'll have to set zippath as well
                        # FIXME: poor check whether this is a zip file
                        if dsinfo['filename'].endswith('.zip'):
                            dsdata['zippath'] = dsinfo['layers'][layer]['filename']
                        envlist.append(dsdata)
                val = envlist

            # for SDM model as input to Climate Change experiement
            if key == 'species_distribution_models':
                if val:
                    uuid = val
                    val = getdatasetparams(uuid)
                    val['species'] = re.sub(u"[ _\-'\"/\(\)\{\}\[\]]", u".", val.get('species', u"Unknown"))
                    sdmobj = uuidToObject(uuid)
                    sdmmd = IBCCVLMetadata(sdmobj)
                    val['layers'] = sdmmd.get('layers_used', None)

                    # do SDM projection results
                    sdm_projections = []
                    for resuuid in inp['sdm_projections']:
                         sdm_projections.append(getdatasetparams(resuuid))
                    inp['sdm_projections'] = sdm_projections

            # for projection as input to Biodiverse experiment
            if key == 'projections':
                dslist = []
                for dsparam in val:
                    dsinfo = getdatasetparams(dsparam['dataset'])
                    dsinfo['threshold'] = dsparam['threshold']
                    # Convert threshold value from Decimal to float
                    for thkey, thvalue in dsinfo['threshold'].items():
                        if isinstance(thvalue, Decimal):
                            dsinfo['threshold'][thkey] = float(thvalue)
                    dslist.append(dsinfo)
                # replace projections param
                val = dslist

            # projection models as input to Ensemble experiment
            if key == 'datasets':
                dslist = []
                for uuid in val:
                    dslist.append(getdatasetparams(uuid))
                # replace datasets param
                val = dslist

            # for trait dataset as input to Species Trait Modelling experiment
            if key == 'traits_dataset':
                dsinfo = getdatasetparams(val)
                if dsinfo['filename'].endswith('.zip'):
                    dsinfo['zippath'] = dsinfo['layers'].values()[0]['filename']
                val = dsinfo

            if isinstance(val, Decimal):
                val = float(val)
            inp[key] = val

        if portal_type == ('org.bccvl.content.sdmexperiment',
                           'org.bccvl.content.msdmexperiment',
                           'org.bccvl.content.mmexperiment'):
            inp.update({
                'rescale_all_models': False,
                'selected_models': 'all',
                'modeling_id': 'bccvl',
                # generic dismo params
                'tails': 'both',
                })
        elif portal_type == 'org.bccvl.content.projectionexperiment':
            inp.update({
                'selected_models': 'all',
                'projection_name': os.path.splitext(dsinfo['filename'])[0]
                })

        inputParams = {
            # example of input/ouput directories
            'env': {
                'inputdir': './input',
                'outputdir': './output',
                'scriptdir': './script',
                'workdir': './workdir'
            },
            'params': inp
        }
        return json.dumps(inputParams, default=str, indent=4)
    @property
    def data(self):
        exp_type = self.context.__parent__.portal_type if self.context.__parent__ else ''
        return self.__generateParameters(self.context.job_params, exp_type)


EXPMD_KEY = 'org.bccvl.site.content.expmetadata'
    
@implementer(IExperimentMetadata)
@adapter(IAttributeAnnotatable)
class ExperimentMetadata(object):
    '''
    Adapter to manage experiment metadata for experiment
    '''
    __marker = object()

    def __init__(self, context):
        self.context = context
        self.md = {
            'BCCVL model outputs guide': [
                u"".join([
                    u"The Biodiversity and Climate Change Virtual Laboratory brings together real-world data from trusted providers with peer-reviewed ",
                    u"scientific analysis tools to facilitate the investigation of climate impacts on the world's biodiversity. The lab hosts a wealth ",
                    u"of data for you to use in your models that has been collected, aggregated and shared by others. Please be aware that correct attribution ",
                    u"is important to ensure that data providers get the credits they deserve and can maintain their work."
                ]),
                u"",
                u"".join([
                    u"The information below describes some system specifications and information about your model. We aim to provide transparency of processes ",
                    u"and procedures of the BCCVL that will allow users to further utilise research data and modelling outputs."
                ]),
                u"",
                u"".join([
                    u"More information about the procedures of the BCCVL can be found here: ",
                    u"https://support.bccvl.org.au/support/solutions/articles/6000176070-bccvl-procedures"
                ]),
                u"",
                u"If you use the BCCVL in a publication or report we ask you to attribute us as follows:",
                u"",
                u"BCCVL application:",
                u"".join([
                    u'Hallgren W, Beaumont L, Bowness A, Chambers L, Graham E, Holewa H, Laffan S, Mackey B, Nix H, Price J and Vanderwal J. 2016. ',
                    u'The Biodiversity and Climate Change Virtual Laboratory: Where ecology meets big data. Environmental Modelling & Software, 76, pp.182-186.'
                ]),
                u"",
                u"Online Open Course in SDM:",
                u"".join([
                    u'Huijbers CM, Richmond SJ, Low-Choy SJ, Laffan SW, Hallgren W, Holewa H (2016) SDM Online Open Course. ',
                    u'Biodiversity and Climate Change Virtual Laboratory, http://www.bccvl.org.au/training/. DDMMYY of access.'
                ]),
            ],
            'Model outputs:': u''.join([
                u'Detailed information on how to interpret the outputs of a Species Distribution Model experiment can be ',
                u'found on our support page: https://support.bccvl.org.au/support/solutions/articles/6000127046-interpretation-of-model-outputs'
            ]),
            'System specifications': {
                "Linux OS": u"CentOS release 6.7", 
                "R version": u"3.2.2",
                "R packages":  u" ".join([
                    "abind 1.4-5, biomod2 3.3-7, car 2.1-0, caret 6.0-78, class 7.3-14, colorspace 1.3-2, deldir 0.1-15, dichromat 2.0-0,",
                    "digest 0.6.13, dismo 1.1-4, doParallel 1.0.11, evaluate 0.10.1, FNN 1.1, foreach 1.4.4, foreign 0.8-69, gam 1.14-4, gamlss 4.3-8,",
                    "gamlss.data 4.3-2, gamlss.dist 4.3-5, gbm 2.1.3, gdalUtils 2.0.1.7, ggdendro 0.1-20, ggplot2 2.2.1, gridExtra 2.3, gstat 1.1-5,",
                    "gtable 0.2.0, hexbin 1.27.1, intervals 0.15.1, iterators 1.0.9, labeling 0.3, lattice 0.20-35, latticeExtra 0.6-28, lazyeval 0.2.1,",
                    "lme4 1.1-14, magrittr 1.5, MASS 7.3-47, Matrix 1.2-3, MatrixModels 0.4-1, mda 0.4-10, mgcv 1.8-22, minqa 1.2.4, mmap 0.6-15,",
                    "ModelMetrics 1.1.0, munsell 0.4.3, nlme 3.1-131, nloptr 1.0.4, nnet 7.3-12, ordinal 2015.6-28, pbkrtest 0.4-2, plyr 1.8.3,",
                    "png 0.1-7, pROC 1.8, proto 1.0.0, quantreg 5.34, R.methodsS3 1.7.1, R.oo 1.20.0, R.utils 2.2.0, R2HTML 2.3.1, randomForest 4.6-12,",
                    "raster 2.6-7, rasterVis 0.41, RColorBrewer 1.1-2, Rcpp 0.12.4, RcppEigen 0.3.3.3.0, reshape 0.8.7, reshape2 1.4.3, rgdal 1.1-3,",
                    "rgeos 0.3-23, rjson 0.2.15, scales 0.5.0, SDMTools 1.1-221, sp 1.2-5, spacetime 1.2-1, SparseM 1.77, spatial 7.3-11,",
                    "spatial.tools 1.4.8, stringi 1.1.6, stringr 1.2.0, survival 2.41-3, tibble 1.3.4, ucminf 1.1-4, xts 0.10-0, zoo 1.8-0,",
                    "base 3.2.2, boot 1.3-17, class 7.3-14, cluster 2.0.3, codetools 0.2-14, compiler 3.2.2, datasets 3.2.2, foreign 0.8-65,",
                    "graphics 3.2.2, grDevices 3.2.2, grid 3.2.2, KernSmooth 2.23-15, MASS 7.3-47, methods 3.2.2, parallel 3.2.2,",
                    "rpart 4.1-10, splines 3.2.2, stats 3.2.2, stats4 3.2.2, tcltk 3.2.2, tools 3.2.2, utils 3.2.2"
                ])
            }
        }    

    def __paramName(self, param):
        pname = param.strip().replace("_", " ")
        if param == "prevalence":
            pname = "weighted response weights"
        elif param == "var_import":
            pname = "resampling"
        elif param == "nbcv":
            pname = "number of cross validations (NbCV)"
        elif param == "n_trees":
            pname = "trees added each cycle (n_trees)"
        elif param == "control_xval":
            pname = "cross-validations folds"
        elif param == "control_minbucket":
            pname = "minimum bucket"
        elif param == "control_minsplit":
            pname = "minimum split"
        elif param == "control_cp":
            pname = "complexity parameter"
        elif param == "control_maxdepth":
            pname = "maximum depth"
        elif param == "irls_reg":
            pname = "irls.reg"
        elif param == "maxit":
            pname = "maximum iterations (maxit)"
        elif param == "mgcv_tol":
            pname = "convergence tolerance"
        elif param == "mgcv_half":
            pname = "number of halvings"
        elif param == "n_minobsinnode":
            pname = "terminal node size (n.minobsinnode)"
        elif param == "control_epsilon":
            pname = "epsilon"
        elif param == "control_maxit":
            pname = "maximum MLE iterations"
        elif param == "control_trace":
            pname = "MLE iteration output"
        elif param == "model":
            pname = "Model returned"
        elif param == "x":
            pname = "x returned"
        elif param == "y":
            pname = "y returned"
        elif param == "qr":
            pname = "QR returned"
        elif param == "singular_ok":
            pname = "Singular fit ok"
        elif param == "thresh":
            pname = "threshold"
        elif param == "maximumiterations":
            pname = "Maximum iterations"
        elif param == "ntree":
            pname = "maximum number of trees"
        elif param == "mtry":
            pname = "number of variables at each split (mtry)"
        elif param == "nodesize":
            pname = "terminal node size"
        elif param == "maxnodes":
            pname = "maximum number of terminal nodes"
        elif param == "pa_ratio":
            pname = "absence-presence ratio"
        elif param == "lq2lqptthreshold":
            pname = "product/threshold feature threshold"
        elif param == "lq2lqthreshold":
            pname = "quadratic feature threshold"
        elif param == "hingethreshold":
            pname = "hinge feature threshold"
        elif param == "beta_threshold":
            pname = "threshold feature regularization"
        elif param == "beta_categorical":
            pname = "categorical feature regularization"
        elif param == "beta_lqp":
            pname = 'linear/quadratic/product feature regularization'
        elif param == "beta_hinge":
            pname = "hinge feature regularization"
        elif param == "defaultprevalence":
            pname = "prevalence"
        elif param == "nk":
            pname = "maximum number of terms"
        elif pname == "degree":
            pname = "maximum interaction degree"
        elif param == "shrinkage":
            pname = "learning rate (shrinkage)"
        elif param == "cv_folds":
            pname = "number of subsets used for cross-validation"
        elif param == "rang":
            pname = "initial random weights (rang)"
        return pname

    # To do: Read in the algorthm option parameters from the algorithm config xml file.
    def __algoConfigOption(self, algo, job_params):
        params = []
        if algo == "ann":
            params = ["prevalence", "maxit", "nbcv", "rang", "random_seed"]
        elif algo == "brt":
            params = ["tree_complexity", "learning_rate", "bag_fraction", "n_folds", "prev_stratify", \
                      "family", "n_trees", "max_trees", "tolerance_method", "tolerance_value", "random_seed"]
        elif algo == "cta":
            params = ["prevalence", "method", "control_xval", "control_minbucket", \
                      "control_minsplit", "control_cp", "control_maxdepth", "random_seed"]
        elif algo == "fda":
            params = ["prevalence", "var_import", "method", "random_seed"]
        elif algo == "gam":
            params = ["prevalence", "interaction_level", "family", "irls_reg", "epsilon", \
                      "maxit", "mgcv_tol", "mgcv_half", "random_seed"]
        elif algo == "gbm":
            params = ["prevalence", "distribution", "n_trees", "interaction_depth", "n_minobsinnode", \
                      "shrinkage", "bag_fraction", "train_fraction", "cv_folds", "random_seed"]
        elif algo == "glm":
            params = ["prevalence", "type", "interaction_level", "test", "family", \
                      "mustart", "control_epsilon", "control_maxit", "control_trace", "random_seed"]
        elif algo == "mars":
            params = ["prevalence", "var_import", "degree", "nk", "penalty", "thresh", "prune", "random_seed"]
        elif algo == "maxent":
            params = ["prevalence", "maximumiterations", "linear", "quadratic", "product", \
                      "threshold", "hinge", "lq2lqptthreshold", "lq2lqthreshold", "hingethreshold", \
                      "beta_threshold", "beta_categorical", "beta_lqp", "beta_hinge", "defaultprevalence", \
                      "random_seed"]
        elif algo == "rf":
            params = ["prevalence", "ntree", "mtry", "nodesize", "maxnodes", "random_seed"]
        elif algo == "sre":
            params = ["prevalence", "var_import", "quant", "random_seed"]
        elif algo == "speciestrait_cta":
            params = ["control_xval", "control_minbucket", "control_minsplit", "control_cp", "control_maxdepth", \
                      "random_seed"]
        elif algo == "speciestrait_glmm":
            params = ["family", "na_action", "random_seed"]
        elif algo in ["speciestrait_gam", "speciestrait_glm", "traitdiff_glm"]:
            params = ["family", "na_action", "method", "random_seed"]
        else:
            params = ["random_seed"]

        options = []
        for param in params:
            if param in job_params:
                optionstr = "{} = {}".format(
                    self.__paramName(param), 
                    str(job_params.get(param)) if job_params.get(param) is not None else ''
                )
                options.append(optionstr)
        return '\n'.join(options)

    def __getMetadataText(self, key, md):
        value = md.get(key)
        if not value:
            return ""
        if isinstance(value, str) or isinstance(value, unicode):
            return(u"{}\n".format(key) + value + u"\n\n") 
        elif isinstance(value, dict):
            dv = value.values()[0]
            if isinstance(dv, str) or isinstance(dv, unicode):
                return (u"{}\n".format(key) + 
                        u"\n".join([u"{}: {}".format(k, v) for k, v in md.get(key, {}).items()]) + 
                        u"\n\n")
            else:
                vtext = u"{}\n".format(key)                
                for k, v in md.get(key, {}).items():
                    if isinstance(v, dict):
                        vtext += self.__getMetadataText(k, md.get(key))
                    elif isinstance(v, list):
                        vtext += self.__getMetadataText(k, md.get(key))
                return vtext
        elif isinstance(value, list):
            if isinstance(value[0], str) or isinstance(value[0], unicode):
                return(u"{}\n".format(key) + u"\n".join(value) + u"\n\n")
            elif isinstance(value[0], dict):
                vtext = u"{}\n".format(key)
                for lv in value:
                    vtext += u"\n".join([u"{}: {}".format(k, v) for k, v in lv.items()]) + u"\n"
                return vtext + u"\n"

    def __createExpmetadata(self, job_params):
        # To do: add other R package versions dynamically
        # Get experiment title
        self.md['Model specifications'] = {
            'Title': self.context.title, 
            'Date/time run': self.context.creation_date.__str__(),
            'Description': self.context.description or ''
        }

        # iterate over all input datasets and add them as entities
        self.md['Input datasets:'] = {}
        for key in ('species_occurrence_dataset', 'species_absence_dataset', 'traits_dataset'):
            spmd = {}
            if not job_params.has_key(key):
                continue
            dsbrain = uuidToCatalogBrain(job_params[key])
            if not dsbrain:
                continue
            ds = dsbrain.getObject()
            mdata = IBCCVLMetadata(ds)
            if mdata and mdata.get('rows', None):
                spmd = {'Title': "{} ({})".format(ds.title, mdata.get('rows'))}
            else:
                spmd = {'Title': ds.title}
            info = IDownloadInfo(ds)
            spmd['Download URL'] = info['url']

            coll = ds
            while not (ISiteRoot.providedBy(coll) or ICollection.providedBy(coll)):
                coll = coll.__parent__
            spmd['Description'] = ds.description or coll.description or ''
            attribution = ds.attribution or getattr(coll, 'attribution') or ''
            if isinstance(attribution, list):
                attribution = '\n'.join([att.raw for att in attribution])
            spmd['Attribution'] = attribution
            self.md['Input datasets:'][key] = spmd

        key = 'traits_dataset_params'
        if key in job_params:
            self.md['Input datasets:'][key] = job_params.get(key, {})


        # pseudo-absence metadata.
        key = u"pseudo_absence_dataset"
        pa_file = self.context.get('pseudo_absences.csv')
        pa_url = ""
        pa_title = ""
        if pa_file:
            pa_title = pa_file.title
            pa_url = pa_file.absolute_url()
            pa_url = '{}/@@download/{}'.format(pa_url, os.path.basename(pa_url))

            pamd = {
                'Title': pa_title, 
                'Download URL': pa_url,
                'Pseudo-absence Strategy': job_params.get('pa_strategy', ''),
                'Pseudo-absence Ratio' : str(job_params.get('pa_ratio', ''))
            }
            if job_params.get('pa_strategy', '') == 'disc':
                pamd['Minimum distance'] = str(job_params.get('pa_disk_min', ''))
                pamd['Maximum distance'] = str(job_params.get('pa_disk_max', ''))
            if job_params.get('pa_strategy', '') == 'sre':
                pamd['Quantile'] = str(job_params.get('pa_sre_quant', ''))
            self.md['Input datasets:'][key] = pamd
        
        for key in ['environmental_datasets', 'future_climate_datasets']:
            if key not in job_params:
                continue
            env_list = []
            layer_vocab = getUtility(IVocabularyFactory, 'layer_source')(self.context)
            for uuid, layers in job_params[key].items():
                ds = uuidToObject(uuid)
                coll = ds
                while not (ISiteRoot.providedBy(coll) or ICollection.providedBy(coll)):
                    coll = coll.__parent__
                description = ds.description or coll.description
                attribution = ds.attribution or getattr(coll, 'attribution') or ''
                if isinstance(attribution, list):
                    attribution = '\n'.join([att.raw for att in attribution])

                layer_titles = [layer_vocab.getLayerTitle(layer) for layer in layers]
                env_list.append({ 
                   'Title': ds.title, 
                   'Layers': u'\n'.join(layer_titles), 
                   'Description': description, 
                   'Attribution': attribution
                })
            self.md['Input datasets:'][key] = env_list

        key = "datasets"
        if key in job_params:
            dataset_list = []
            for uid in job_params[key]:
                dsbrain = uuidToCatalogBrain(uid)
                if dsbrain:
                    ds = dsbrain.getObject()
                    # get the source experiment
                    source_exp = ds.__parent__
                    while not IExperiment.providedBy(source_exp):
                        source_exp = source_exp.__parent__
                    dataset_list.append({
                        'Source experiment': source_exp.title,
                        'Title': ds.title,
                        'Description': ds.description,
                        'Download URL': '{}/@@download/file/{}'.format(ds.absolute_url(), os.path.basename(ds.absolute_url()))
    ,
                        'Algorithm': ds.__parent__.job_params.get('function', ''),
                        'Species': IBCCVLMetadata(ds).get('species', {}).get('scientificName', ''),
                        'Resolution': IBCCVLMetadata(ds).get('resolution', '')
                    })
            self.md['Input datasets:'][key] = dataset_list


        key = 'species_distribution_models'
        if key in job_params:
            dsbrain = uuidToCatalogBrain(job_params[key])
            if dsbrain:
                ds = dsbrain.getObject()
                # get the source experiment
                source_exp = ds.__parent__
                while not IExperiment.providedBy(source_exp):
                    source_exp = source_exp.__parent__
                
                # get the threshold
                threshold = self.context.species_distribution_models.get(source_exp.UID(), {}).get(ds.UID())
                self.md['Input datasets:'][key] = {
                    'Source experiment': source_exp.title,
                    'Title': ds.title,
                    'Description': ds.description,
                    'Download URL': '{}/@@download/file/{}'.format(ds.absolute_url(), os.path.basename(ds.absolute_url()))
,
                    'Algorithm': ds.__parent__.job_params.get('function', ''),
                    'Species': IBCCVLMetadata(ds).get('species', {}).get('scientificName', ''),
                    'Threshold': "{}({})".format(threshold.get('label', ''), str(threshold.get('value', '')))
                }


        key = 'projections'
        if key in job_params:
            for pds in job_params[key]:
                threshold = pds.get('threshold', {})
                dsbrain = uuidToCatalogBrain(pds.get('dataset'))
                if dsbrain:
                    ds = dsbrain.getObject()
                    # get the source experiment
                    source_exp = ds.__parent__
                    while not IExperiment.providedBy(source_exp):
                        source_exp = source_exp.__parent__
                    self.md['Input datasets:'][key] = {
                        'Source experiment': source_exp.title,
                        'Title': ds.title,
                        'Description': ds.description,
                        'Download URL': '{}/@@download/file/{}'.format(ds.absolute_url(), os.path.basename(ds.absolute_url()))
    ,
                        'Algorithm': ds.__parent__.job_params.get('function', ''),
                        'Species': IBCCVLMetadata(ds).get('species', {}).get('scientificName', ''),
                        'Threshold': "{}({})".format(threshold.get('label', ''), str(threshold.get('value', ''))), 
                        'Biodiverse Cell size (m)': str(job_params.get('cluster_size', ''))
                    }

        # Projection experiment does not have algorithm as input
        if not IProjectionExperiment.providedBy(self.context.__parent__):
            for key in ['function', 'algorithm']:
                if key in job_params:
                    self.md['Algorithm settings:'] = {
                        'Algorithm Name': job_params[key],
                        'Configuration options': self.__algoConfigOption(job_params[key], job_params)
                    }

        # Construct the text
        mdtext = StringIO.StringIO()
        for heading in [
                        'BCCVL model outputs guide', 
                        'System specifications', 
                        'Model specifications',
                        'Input datasets:',
                        'Algorithm settings:',
                        'Model outputs:']:
            mdtext.write(self.__getMetadataText(heading, self.md))
        return mdtext.getvalue()

    @property
    def data(self):
        return self.__createExpmetadata(self.context.job_params)
