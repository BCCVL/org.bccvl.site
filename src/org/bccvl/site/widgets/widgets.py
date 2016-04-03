import logging
from zope.component import getMultiAdapter, getUtility
from zope.interface import implementer, implementer_only
from zope.schema.interfaces import ITitledTokenizedTerm, IVocabularyFactory
from z3c.form import util
from z3c.form.interfaces import (IFieldWidget, NO_VALUE)
from z3c.form.widget import FieldWidget, Widget, SequenceWidget
from z3c.form.browser.widget import (HTMLFormElement, HTMLInputWidget,
                                     addFieldClass)
from zope.i18n import translate
from .interfaces import (IDatasetWidget,
                         IDatasetDictWidget,
                         IFunctionsWidget,
                         IFunctionsRadioWidget,
                         IExperimentSDMWidget,
                         IFutureDatasetsWidget,
                         IExperimentResultWidget,
                         IExperimentResultProjectionWidget)
from plone.app.uuid.utils import uuidToCatalogBrain
from Products.CMFCore.utils import getToolByName
from org.bccvl.site.interfaces import IBCCVLMetadata, IDownloadInfo
from org.bccvl.site.api import dataset
from itertools import chain
from collections import OrderedDict


LOG = logging.getLogger(__name__)


@implementer_only(IFunctionsRadioWidget)
class FunctionsRadioWidget(HTMLInputWidget, SequenceWidget):
    """
    This is an updated standard RadioWidget with proper handling of
    item list generation. It derives from IRadioWidget as well to allow
    re-use of the standard check box widget templates.
    (Having this extra class allows to use special templates for functions field)
    """

    klass = u'radio-widget'
    css = u'radio'

    def isChecked(self, term):
        return term.token in self.value

    def update(self):
        super(FunctionsRadioWidget, self).update()
        addFieldClass(self)

    def items(self):
        # TODO: check if we should cache the return list
        if self.terms is None:  # update() not yet called
            return ()
        vocab = getUtility(IVocabularyFactory, "org.bccvl.site.algorithm_category_vocab")(self.context)
        items = OrderedDict((cat.value,[]) for cat in vocab)
        for count, term in enumerate(self.terms):
            alg = term.brain.getObject()
            # skip algorithm without category
            if alg.algorithm_category is None or alg.algorithm_category not in items:
                continue
            itemList = items[alg.algorithm_category]
            checked = self.isChecked(term)
            id = '%s-%i' % (self.id, count)
            if ITitledTokenizedTerm.providedBy(term):
                label = translate(term.title, context=self.request, default=term.title)
            else:
                label = util.toUnicode(term.value)

            itemList.append ({'id': id, 'name': self.name + ':list', 'value':term.token,
                   'label':label, 'checked': checked,
                   'subject': term.brain.Subject,
                   'description': term.brain.Description,
                   'category': vocab.getTerm(alg.algorithm_category),
                   'pos': len(itemList) })
        return items.values()


@implementer(IFieldWidget)
def FunctionsRadioFieldWidget(field, request):
    return FieldWidget(field, FunctionsRadioWidget(request))


@implementer_only(IFunctionsWidget)
class FunctionsWidget(HTMLInputWidget, SequenceWidget):
    """
    This is an updated standard CheckBoxWidget with proper handling of
    item list generation. It derives from ICheckBoxWidget as well to allow
    re-use of the standard check box widget templates.
    (Having this extra class allows to use special templates for functions field)
    """

    klass = u'checkbox-widget'
    css = u'checkbox'

    def isChecked(self, term):
        return term.token in self.value

    def update(self):
        super(FunctionsWidget, self).update()
        addFieldClass(self)

    def items(self):
        # TODO: check if we should cache the return list
        if self.terms is None:  # update() not yet called
            return ()
        vocab = getUtility(IVocabularyFactory, "org.bccvl.site.algorithm_category_vocab")(self.context)
        items = OrderedDict((cat.value,[]) for cat in vocab)
        for count, term in enumerate(self.terms):
            alg = term.brain.getObject()
            # skip algorithm without category
            if alg.algorithm_category is None or alg.algorithm_category not in items:
                continue
            itemList = items[alg.algorithm_category]
            checked = self.isChecked(term)
            id = '%s-%i' % (self.id, count)
            if ITitledTokenizedTerm.providedBy(term):
                label = translate(term.title, context=self.request, default=term.title)
            else:
                label = util.toUnicode(term.value)

            itemList.append ({'id': id, 'name': self.name + ':list', 'value':term.token,
                   'label':label, 'checked': checked,
                   'subject': term.brain.Subject,
                   'description': term.brain.Description,
                   'category': vocab.getTerm(alg.algorithm_category),
                   'pos': len(itemList) })
        return items.values()


@implementer(IFieldWidget)
def FunctionsFieldWidget(field, request):
    return FieldWidget(field, FunctionsWidget(request))


# FIXME: rename to SelectListWidget
@implementer(IDatasetWidget)
class DatasetWidget(HTMLInputWidget, Widget):
    """
    Widget that stores a dataset uuid.
    """

    multiple = None

    def items(self):
        if self.value:
            for uuid in self.value:
                brain = uuidToCatalogBrain(uuid)
                yield brain

    def extract(self):
        value = self.request.get(self.name, NO_VALUE)
        if self.multiple == 'multiple':
            # make sure we have only unique values
            value = list(OrderedDict.fromkeys(value))
        return value


@implementer(IFieldWidget)
def DatasetFieldWidget(field, request):
    return FieldWidget(field, DatasetWidget(request))


# FIXME: rename to SelectDictWidget
@implementer(IDatasetDictWidget)
class DatasetDictWidget(HTMLFormElement, Widget):
    """
    Allow user to select elements within a dataset/experiment defined by
    catalog query.
    """

    multiple = None

    _dstools = None

    @property
    def dstools(self):
        if not self._dstools:
            self._dstools = getMultiAdapter((self.context, self.request),
                                            name="dataset_tools")
        return self._dstools

    def resolutions(self):
        # FIXME: this method should probably not be here
        # helper method to show a warning to the user that selected datasets
        # have different resolutions
        if self.value:
            pc = getToolByName(self.context, 'portal_catalog')
            brains = pc.searchResults(UID=self.value.keys())
            # TODO: should use vocab to turn into token
            return set(unicode(b['BCCResolution']) for b in brains)
        return []

    # TODO: move this into subclass, make this a base class with a NotImplementedError
    def subitems(self, dsbrain):
        # return a generator of selectable items within dataset
        md = IBCCVLMetadata(dsbrain.getObject())
        layer_vocab = self.dstools.layer_vocab
        selectedsubitems = self.value.get(dsbrain.UID) or ()
        for layer in sorted(md.get('layers', ())):
            subitem = {
                'id': layer,
                'title': layer_vocab.getTerm(layer).title,
                'selected': not selectedsubitems or layer in selectedsubitems,
            }
            yield subitem
        for subdsid in sorted(getattr(dsbrain.getObject(), 'parts', ())):
            part = uuidToCatalogBrain(subdsid)
            # TODO: should we just ignore it?
            if not part:
                continue
            subitem = {
                'id': subdsid,
                'title': part.Title,
                'selected': not selectedsubitems or subdsid in selectedsubitems
            }
            yield subitem

    def items(self):
        # return dict with keys for dataset/experiment uuid
        # and list of uuids for sub element
        if self.value:
            for dsuuid in self.value.keys():
                dsbrain = uuidToCatalogBrain(dsuuid)
                if dsbrain:
                    yield {
                        'id': dsuuid,
                        'title': dsbrain.Title,
                        'brain': dsbrain,
                        'dlinfo': IDownloadInfo(dsbrain),
                        'subitems': self.subitems(dsbrain)
                    }
                else:
                    # FIXME: inform user that dateset no longer exists
                    #        make sure template works with made up info as well
                    #        for now exclude data
                    LOG.warn("Dataset not found: %s for experiment %s", dsuuid, self.context.absolute_url())

    def extract(self):
        # extract the value for the widget from the request and return
        # a tuple of (key,value) pairs
        value = {}
        try:
            count = int(self.request.get('{}.count'.format(self.name)))
        except:
            count = 0
        # no count?
        if count <= 0:
            return NO_VALUE
        # try to find up to count items (layers)
        for idx in range(0, count):
            uuid = self.request.get('{}.item.{}'.format(self.name, idx))
            subuuid = self.request.get('{}.item.{}.item'.format(self.name, idx))
            if uuid:
                if not subuuid:
                    subuuid = set()  # FIXME: whether set or list should depend on field
                value.setdefault(uuid, set()).update(subuuid)
        if not value:
            return NO_VALUE
        return value


@implementer(IFieldWidget)
def DatasetDictFieldWidget(field, request):
    """
    Widget to select datasets and layers
    """
    return FieldWidget(field,  DatasetDictWidget(request))


# TODO: this is a SelectDictWidget
@implementer(IExperimentSDMWidget)
class ExperimentSDMWidget(HTMLInputWidget, Widget):
    """
    Widget that stores an experiment uuid and a list of selected sdm model uuids.

    Gives user the ability to select an experiment and pick a number of sdm models from within.
    """

    genre = ['DataGenreSDMModel']
    multiple = None
    _algo_dict = None

    @property
    def algo_dict(self):
        if self._algo_dict is None:
            pc = getToolByName(self.context, 'portal_catalog')
            brains = pc.searchResults(portal_type='org.bccvl.content.function')
            self._algo_dict = dict(
                (brain.getId, brain) for brain in brains
            )
        return self._algo_dict

    def item(self):
        # return dict with keys for experiment
        # and subkey 'models' for models within experiment
        item = {}
        if self.value:
            experiment_uuid = self.value.keys()[0]
            expbrain = uuidToCatalogBrain(experiment_uuid)
            if expbrain is None:
                return {
                    'title': u'Not Available',
                    'uuid': experiment_uuid,
                    'subitems': []  # models
                }
            item['title'] = expbrain.Title
            item['uuid'] = expbrain.UID
            exp = expbrain.getObject()
            item['layers'] = set((chain(*exp.environmental_datasets.values())))
            expmd = IBCCVLMetadata(exp)
            item['resolution'] = expmd['resolution']
            # now search all models within and add infos
            pc = getToolByName(self.context, 'portal_catalog')
            brains = pc.searchResults(path=expbrain.getPath(),
                                      BCCDataGenre=self.genre)
            # TODO: maybe as generator?
            item['subitems'] = []
            for brain in brains:
                # get algorithm term
                algoid = getattr(brain.getObject(), 'job_params', {}).get('function')
                algobrain = self.algo_dict.get(algoid, None)
                item['subitems'].append(
                    {'item': brain,
                     'uuid': brain.UID,
                     'title': brain.Title,
                     'selected': brain.UID in self.value[experiment_uuid],
                     'algorithm': algobrain
                    }
                )
        return item

    def extract(self):
        # extract the value for the widget from the request and return
        # a tuple of (key,value) pairs
        # get experiment uuid from request
        value = {}
        try:
            count = int(self.request.get('{}.count'.format(self.name)))
        except:
            count = 0
        # no count?
        if count <= 0:
            return NO_VALUE
        # try to find up to count items (datasets)
        for idx in range(0, count):
            uuid = self.request.get('{}.item.{}'.format(self.name, idx))
            subuuid = self.request.get('{}.item.{}.item'.format(self.name, idx))
            if uuid:
                if not subuuid:
                    subuuid = list()  # FIXME: whether set or list should depend on field
                value.setdefault(uuid, list()).extend(subuuid)
        if not value:
            return NO_VALUE
        # FIXME: we support only one experiment at the moment, so let's grap first one from dict
        uuid = value.keys()[0]
        modeluuids = value[uuid]
        return {uuid: modeluuids}


@implementer(IFieldWidget)
def ExperimentSDMFieldWidget(field, request):
    return FieldWidget(field, ExperimentSDMWidget(request))


@implementer(IFutureDatasetsWidget)
class FutureDatasetsWidget(HTMLFormElement, Widget):
    """
    render a list of checkboxes for keys in dictionary.
    render a default widget for values per key
    """

    multiple = 'multiple'

    _res_vocab = None
    _layer_vocab = None

    def items(self):
        if self.value:
            for uuid in self.value:
                brain = uuidToCatalogBrain(uuid)
                # md = IBCCVLMetadata(brain.getObject())
                yield {'title': brain.Title,
                       'uuid': brain.UID,
                       }

    def extract(self):
        # try to find up to count layers
        uuid = self.request.get(self.name)
        if not uuid:
            return NO_VALUE
        if 'multiple':
            # make sure we have only unique values
            uuid = list(OrderedDict.fromkeys(uuid))
        return uuid


@implementer(IFieldWidget)
def FutureDatasetsFieldWidget(field, request):
    """
    Widget to select datasets and layers
    """
    return FieldWidget(field, FutureDatasetsWidget(request))


@implementer(IExperimentResultWidget)
class ExperimentResultWidget(HTMLInputWidget, Widget):
    """
    Widget that stores an experiment uuid and a list of selected sdm model uuids.

    Gives user the ability to select an experiment and pick a number of sdm models from within.
    """

    genre = ['DataGenreCP', 'DataGenreFP',
             'DataGenreENDW_CWE', 'DataGenreENDW_WE',
             'DataGenreENDW_RICHNESS', 'DataGenreENDW_SINGLE',
             'DataGenreREDUNDANCY_SET1', 'DataGenreREDUNDANCY_SET2',
             'DataGenreREDUNDANCY_ALL',
             'DataGenreRAREW_CWE', 'DataGenreRAREW_RICHNESS',
             'DataGenreRAREW_WE']
    multiple = 'multiple'

    def items(self):
        # return dict with keys for experiment
        # and subkey 'models' for models within experiment
        if self.value:
            for experiment_uuid, model_uuids in self.value.items():
                item = {}
                expbrain = uuidToCatalogBrain(experiment_uuid)
                item['title'] = expbrain.Title
                item['uuid'] = expbrain.UID

                # TODO: what else wolud I need from an experiment?
                exp = expbrain.getObject()
                expmd = IBCCVLMetadata(exp)
                item['resolution'] = expmd.get('resolution')
                item['brain'] = expbrain

                # now search all models within and add infos
                pc = getToolByName(self.context, 'portal_catalog')
                brains = pc.searchResults(path=expbrain.getPath(),
                                          BCCDataGenre=self.genre)
                # TODO: maybe as generator?
                item['subitems'] = [{'uuid': brain.UID,
                                     'title': brain.Title,
                                     'obj': brain.getObject(),
                                     'md': IBCCVLMetadata(brain.getObject()),
                                     'selected': brain.UID in self.value[experiment_uuid]}
                                                 for brain in brains]
                yield item

    def extract(self):
        # extract the value for the widget from the request and return
        # a tuple of (key,value) pairs
        value = {}
        try:
            count = int(self.request.get('{}.count'.format(self.name)))
        except:
            count = 0
        # no count?
        if count <= 0:
            return NO_VALUE
        # try to find count experiments
        for idx in range(0, count):
            uuid = self.request.get('{}.item.{}'.format(self.name, idx))
            models = self.request.get('{}.item.{}.item'.format(self.name, idx), [])
            if uuid:
                value[uuid] = models
        if not value:
            return NO_VALUE
        return value


@implementer(IFieldWidget)
def ExperimentResultFieldWidget(field, request):
    return FieldWidget(field, ExperimentResultWidget(request))


@implementer(IExperimentResultProjectionWidget)
class ExperimentResultProjectionWidget(HTMLInputWidget, Widget):
    """
    Widget that stores an experiment uuid and a list of selected projection output uuids, and threshold values.

    Gives user the ability to select an experiment and pick a number of projection outputs from within.
    """

    experiment_type = None
    genre = ['DataGenreCP', 'DataGenreFP']
    multiple = 'multiple'

    def items(self):
        # return dict with keys for experiment
        # and subkey 'models' for models within experiment
        if self.value:
            for experiment_uuid, model_uuids in self.value.items():
                item = {}
                expbrain = uuidToCatalogBrain(experiment_uuid)
                # TODO: we have an experiment_uuid, but can't access the
                #       experiment (deleted?, access denied?)
                #       shall we at least try to get some details?
                if expbrain is None:
                    continue
                item['title'] = expbrain.Title
                item['uuid'] = expbrain.UID
                item['brain'] = expbrain

                # TODO: what else wolud I need from an experiment?
                exp = expbrain.getObject()
                expmd = IBCCVLMetadata(exp)
                item['resolution'] = expmd.get('resolution')

                # now search all datasets within and add infos
                pc = getToolByName(self.context, 'portal_catalog')
                brains = pc.searchResults(path=expbrain.getPath(),
                                          BCCDataGenre=self.genre)
                # TODO: maybe as generator?
                item['subitems'] = []
                for brain in brains:
                    # FIXME: I need a different list of thresholds for display; esp. don't look up threshold, but take vales (threshold id and value) from field as is
                    thresholds = dataset.getThresholds(brain.UID)[brain.UID]
                    threshold = self.value[experiment_uuid].get(brain.UID)
                    # is threshold in list?
                    if threshold and threshold['label'] not in thresholds:
                        # maybe a custom entered number?
                        # ... I guess we don't really care as long as we produce the same the user entered. (validate?)
                        thresholds[threshold['label']] = threshold['label']
                    dsobj = brain.getObject()
                    dsmd = IBCCVLMetadata(dsobj)
                    item['subitems'].append({
                         'uuid': brain.UID,
                         'title': brain.Title,
                         'selected': brain.UID in self.value[experiment_uuid],
                         'threshold': threshold,
                         'thresholds': thresholds,
                         'brain': brain,
                         'md': dsmd,
                         'obj': dsobj,
                         # TODO: this correct? only one layer ever?
                         'layermd': dsmd['layers'].values()[0]
                    })
                yield item

    def extract(self):
        # extract the value for the widget from the request and return
        # a tuple of (key,value) pairs
        # TODO: maybe turn this into a list to keep order of entries as is
        value = {}
        try:
            count = int(self.request.get('{}.count'.format(self.name)))
        except:
            count = 0
        # no count?
        if count <= 0:
            return NO_VALUE
        # try to find count experiments
        for idx in range(0, count):
            uuid = self.request.get('{}.item.{}'.format(self.name, idx))
            if not uuid:
                continue
            value[uuid] = {}
            try:
                dscount = int(self.request.get('{}.item.{}.count'.format(self.name, idx)))
            except:
                dscount = 0
            for dsidx in range(0, dscount):
                dsuuid = self.request.get('{}.item.{}.item.{}.uuid'.format(self.name, idx, dsidx))
                dsth = self.request.get('{}.item.{}.item.{}.threshold'.format(self.name, idx, dsidx))
                if dsuuid:
                    value[uuid][dsuuid] = {'label': dsth}
        if not value:
            return NO_VALUE
        return value


@implementer(IFieldWidget)
def ExperimentResultProjectionFieldWidget(field, request):
    return FieldWidget(field, ExperimentResultProjectionWidget(request))
