import StringIO
import os, os.path
from plone.app.uuid.utils import uuidToObject, uuidToCatalogBrain
from zope.interface import implementer
from zope.component import adapter, getUtility
from zope.schema.interfaces import IVocabularyFactory
from zope.annotation import IAnnotations, IAttributeAnnotatable
from persistent.dict import PersistentDict
from Products.CMFCore.interfaces import ISiteRoot
from org.bccvl.site.behavior.collection import ICollection
from org.bccvl.site.interfaces import IBCCVLMetadata, IDownloadInfo, IProvenanceData, IExperimentMetadata

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
                    u"The Biodiversity and Climate Change Virtual Laboratory brings together real-world data from trusted providers with peer-reviewed ",
                    u"scientific analysis tools to facilitate the investigation of climate impacts on the world's biodiversity. The lab hosts a wealth ",
                    u"of data for you to use in your models that has been collected, aggregated and shared by others. Please be aware that correct attribution ",
                    u"is important to ensure that data providers get the credits they deserve and can maintain their work.",
                    u"",
                    u"The information below describes some system specifications and information about your model. We aim to provide transparency of processes ",
                    u"and procedures of the BCCVL that will allow users to further utilise research data and modelling outputs.",
                    u"",
                    u"More information about the procedures of the BCCVL can be found here (will be added to Knowledge Base once finalised):",
                    u"https://docs.google.com/document/d/1Wte9hpE41WUueMT6USAEoacFeH6TkYRL5nMPPI1yR4c/edit#",
                    u"",
                    u"If you use the BCCVL in a publication or report we ask you to attribute us as follows:",
            ],
            'BCCVL application:': [
                    u'Hallgren W, Beaumont L, Bowness A, Chambers L, Graham E, Holewa H, Laffan S, Mackey B, Nix H, Price J and Vanderwal J. 2016. ',
                    u'The Biodiversity and Climate Change Virtual Laboratory: Where ecology meets big data. Environmental Modelling & Software, 76, pp.182-186.'
            ],
            'Online Open Course in SDM:': [
                    u'Huijbers CM, Richmond SJ, Low-Choy SJ, Laffan SW, Hallgren W, Holewa H (2016) SDM Online Open Course. ',
                    u'Biodiversity and Climate Change Virtual Laboratory, http://www.bccvl.org.au/training/. DDMMYY of access.'
            ],
            'Model outputs:': [
                    u'Detailed information on how to interpret the outputs of a Species Distribution Model experiment can be ',
                    u'found on our support page: https://support.bccvl.org.au/support/solutions/articles/6000127046-interpretation-of-model-outputs'
            ],
            'System specifications': {
                "Linux OS": u"CentOS release 6.7", 
                "R version": u"3.2.2",
                "R packages":  u" ".join([
                    "abind 1.4-3, biomod2 3.1-64, car 2.1-0, caret 6.0-76, class 7.3-14, colorspace 1.2-6, deldir 0.1-9, dichromat 2.0-0,",
                    "digest 0.6.9, dismo 1.1-1, doParallel 1.0.10, evaluate 0.8, FNN 1.1, foreach 1.4.3, foreign 0.8-66, gam 1.12, gamlss 4.3-8,",
                    "gamlss.data 4.3-2, gamlss.dist 4.3-5, gbm 2.1.1, gdalUtils 2.0.1.7, ggdendro 0.1-20, ggplot2 2.2.1, gridExtra 2.2.0, gstat 1.1-2,",
                    "gtable 0.2.0, hexbin 1.27.1, intervals 0.15.1, iterators 1.0.8, labeling 0.3, lattice 0.20-33, latticeExtra 0.6-28, lazyeval 0.2.0,",
                    "lme4 1.1-11, magrittr 1.5, MASS 7.3-45, Matrix 1.2-3, MatrixModels 0.4-1, mda 0.4-8, mgcv 1.8-9, minqa 1.2.4, mmap 0.6-12,",
                    "ModelMetrics 1.1.0, munsell 0.4.3, nlme 3.1-123, nloptr 1.0.4, nnet 7.3-11, ordinal 2015.1-21, pbkrtest 0.4-2, plyr 1.8.3,",
                    "png 0.1-7, pROC 1.8, proto 0.3-10, quantreg 5.33, R.methodsS3 1.7.1, R.oo 1.20.0, R.utils 2.2.0, R2HTML 2.3.1, randomForest 4.6-12,",
                    "raster 2.5-8, rasterVis 0.37, RColorBrewer 1.1-2, Rcpp 0.12.3, RcppEigen 0.3.3.3.0, reshape 0.8.5, reshape2 1.4.1, rgdal 1.1-3,",
                    "rgeos 0.3-23, rjson 0.2.15, scales 0.4.1, SDMTools 1.1-221, sp 1.2-4, spacetime 1.1-5, SparseM 1.77, spatial 7.3-11,",
                    "spatial.tools 1.4.8, stringi 1.0-1, stringr 1.0.0, survival 2.38-3, tibble 1.3.0, ucminf 1.1-4, xts 0.9-7, zoo 1.7-12,",
                    "base 3.2.2, boot 1.3-17, class 7.3-13, cluster 2.0.3, codetools 0.2-14, compiler 3.2.2, datasets 3.2.2, foreign 0.8-65,",
                    "graphics 3.2.2, grDevices 3.2.2, grid 3.2.2, KernSmooth 2.23-15, lattice 0.20-33, MASS 7.3-43, Matrix 1.2-2, methods 3.2.2,",
                    "mgcv 1.8-7, nlme 3.1-121, nnet 7.3-10, parallel 3.2.2, rpart 4.1-10, spatial 7.3-10, splines 3.2.2, stats 3.2.2, stats4 3.2.2,",
                    "survival 2.38-3, tcltk 3.2.2, tools 3.2.2, utils 3.2.2"
                ])
            }
        }    

    def __getMetadataText(self, key, md):
        value = md.get(key)
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
        for key in ('species_occurrence_dataset', 'species_absence_dataset'):
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
            spmd['Description'] = ds.description or coll.description or '',
            attribution = ds.attribution or getattr(coll, 'attribution') or ''
            if isinstance(attribution, tuple):
                attribution = attribution[0].raw
            spmd['Attribution'] = attribution
            self.md['Input datasets:'][key] = spmd


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
            'Pseudo-absence Strategy': job_params['pa_strategy'] or '',
            'Pseudo-absence Ratio' : str(job_params['pa_ratio']) or ''
        }
        if job_params['pa_strategy'] == 'disc':
            pamd['Minimum distance'] = str(job_params['pa_disk_min']) or ''
            pamd['Maximum distance'] = str(job_params['pa_disk_max']) or ''
        if job_params['pa_strategy'] == 'sre':
            pamd['Quantile'] = str(job_params['pa_sre_quant']) or ''
        self.md['Input datasets:'][key] = pamd
        
        key = 'environmental_datasets'
        env_list = []
        layer_vocab = getUtility(IVocabularyFactory, 'layer_source')(self.context)
        for uuid, layers in job_params[key].items():
            ds = uuidToObject(uuid)
            coll = ds
            while not (ISiteRoot.providedBy(coll) or ICollection.providedBy(coll)):
                coll = coll.__parent__
            description = ds.description or coll.description,
            if isinstance(description, tuple):
                description = description[0]
            attribution = ds.attribution or getattr(coll, 'attribution') or ''
            if isinstance(attribution, tuple):
                attribution = attribution[0].raw


            layer_titles = [layer_vocab.getTerm(layer).title for layer in layers]
            # env_list.append(self.__getMetadataText(ds.title, {
            #         ds.title: { 
            #             'layers': u', '.join(layer_titles), 
            #             'description': description, 
            #             'attribution': attribution[0].raw
            #         }
            #     }))
            env_list.append({ 
               'Title': ds.title, 
               'Layers': u'\n'.join(layer_titles), 
               'Description': description, 
               'Attribution': attribution
            })
        self.md['Input datasets:'][key] = env_list

        key = 'function'
        self.md['Algorithm settings:'] = {'Algorithm Name': job_params[key]}

        # Construct the text
        mdtext = StringIO.StringIO()
        for heading in [
                        'BCCVL model outputs guide', 
                        'BCCVL application:', 
                        'Online Open Course in SDM:', 
                        'System specifications', 
                        'Input datasets:',
                        'Algorithm settings:',
                        'Model outputs:']:
            mdtext.write(self.__getMetadataText(heading, self.md))
        return mdtext.getvalue()

    @property
    def data(self):
        return self.__createExpmetadata(self.context.job_params)
