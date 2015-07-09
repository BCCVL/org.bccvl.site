from decimal import Decimal
import logging
from zope.component import getMultiAdapter, getUtility
from zope.interface import implementer, implementer_only
from zope.schema.interfaces import (ITitledTokenizedTerm,
                                    IVocabularyFactory)
from z3c.form import util
from z3c.form.interfaces import (IFieldWidget, NO_VALUE)
from z3c.form.widget import FieldWidget, Widget, SequenceWidget
from z3c.form.browser.checkbox import CheckBoxWidget
from z3c.form.browser.widget import (HTMLFormElement, HTMLInputWidget,
                                     addFieldClass)
from zope.i18n import translate
from .interfaces import (IDatasetWidget,
                         IDatasetDictWidget,
                         IFunctionsWidget,
                         IExperimentSDMWidget,
                         IFutureDatasetsWidget,
                         IExperimentResultWidget,
                         IExperimentResultProjectionWidget,
                         IJSWrapper)
from plone.app.uuid.utils import uuidToCatalogBrain
from plone.z3cform.interfaces import IDeferSecurityCheck
from Products.CMFCore.utils import getToolByName
from org.bccvl.site.interfaces import IBCCVLMetadata, IDownloadInfo
from org.bccvl.site.api import dataset
import json
from itertools import chain
from collections import OrderedDict


LOG = logging.getLogger(__name__)

# Wrap js code into a document.ready wrapper and CDATA section
JS_WRAPPER = u"""//<![CDATA[
    $(document).ready(function(){%(js)s});
//]]>"""

JS_WRAPPER_ADAPTER = lambda req, widget: JS_WRAPPER


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
        items = []
        for count, term in enumerate(self.terms):
            checked = self.isChecked(term)
            id = '%s-%i' % (self.id, count)
            if ITitledTokenizedTerm.providedBy(term):
                label = translate(term.title, context=self.request,
                                  default=term.title)
            else:
                label = util.toUnicode(term.value)
            items.append ({'id': id, 'name': self.name + ':list', 'value':term.token,
                   'label':label, 'checked': checked,
                   'subject': term.brain.Subject})
        return items


@implementer(IFieldWidget)
def FunctionsFieldWidget(field, request):
    return FieldWidget(field, FunctionsWidget(request))


@implementer(IDatasetWidget)
class DatasetWidget(HTMLInputWidget, Widget):
    """
    Widget that stores a dataset uuid.
    """

    genre = None
    multiple = None
    filters = ['text', 'source']

    def items(self):
        if self.value:
            for uuid in self.value:
                brain = uuidToCatalogBrain(uuid)
                yield brain

    def js(self):
        # TODO: shouldn't we use #self.id instead of #self.__name__ ?
        js = u"".join((
            u'bccvl.select_dataset($("a#', self.__name__, '-popup"),',
            json.dumps({
                'field': self.__name__,
                'genre': self.genre,
                'widgetname': self.name,
                'widgetid': self.id,
                'multiple': self.multiple,
                'filters': self.filters,
                'widgeturl': '{0}/++widget++{1}'.format(self.request.getURL(),
                                                        self.__name__)
            }),
            u');'))
        jswrap = getMultiAdapter((self.request, self), IJSWrapper)
        return jswrap % {'js':  js}

    def extract(self):
        value = self.request.get(self.name, NO_VALUE)
        if self.multiple == 'multiple':
            # make sure we have only unique values
            value = list(OrderedDict.fromkeys(value))
        return value


@implementer(IFieldWidget)
def DatasetFieldWidget(field, request):
    return FieldWidget(field, DatasetWidget(request))


# TODO: change the widget below? ...
#       e.g. browse for datasets with layers and do layer selection on page (instead of popup)
#       or: make layers a sort of fold down within dataset?
#       or: ...

@implementer(IDatasetDictWidget)
class DatasetDictWidget(HTMLFormElement, Widget):
    """
    Allow user to select elements within a dataset/experiment defined by
    catalog query.
    """

    genre = None
    multiple = None
    filters = ['text', 'source']

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
        selectedlayers = self.value.get(dsbrain.UID) or ()
        for layer in sorted(md.get('layers', ())):
            subitem = {
                'id': layer,
                'title': layer_vocab.getTerm(layer).title,
                'selected': layer in selectedlayers,
            }
            yield subitem

    def items(self):
        # return dict with keys for dataset/experiment uuid
        # and list of uuids for sub element
        item = {}
        #pc = getToolByName(self.context, 'portal_catalog')
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

    def js(self):
        js = u"".join((
            u'bccvl.select_dataset_dict($("a#', self.__name__, '-popup"),',
            json.dumps({
                'field': self.__name__,
                'genre': self.genre,
                'multiple': self.multiple,
                'widgetname': self.name,
                'widgetid': self.id,
                'filters': self.filters,
                'widgeturl': '{0}/++widget++{1}'.format(self.request.getURL(),
                                                        self.__name__)
            }),
            u');'))
        jswrap = getMultiAdapter((self.request, self), IJSWrapper)
        return jswrap % {'js':  js}

    def items_old(self):
        # FIXME importing here to avoid circular import of IDataset
        from org.bccvl.site.api.dataset import getdsmetadata
        if self.value:
            for uuid in self.value:
                brain = uuidToCatalogBrain(uuid)
                # TODO: could use layer vocab again

                md = getdsmetadata(brain)
                layers = self.value[uuid]
                # FIXME: check if layers or layers_used here
                for layer, layeritem in md['layers'].iteritems():
                    if not layer in layers:
                        continue
                    mimetype = 'application/octet-stream'
                    layerfile = None
                    if 'filename' in layeritem:
                        # FIXME: hardcoded mimetype logic for zip files.
                        #        should draw mimetype info from layer metadata
                        #        assumes there are only geotiff in zip files
                        mimetype = 'image/geotiff'
                        layerfile = layeritem['filename']
                        vizurl = '{0}#{1}'.format(md['vizurl'], layerfile)
                    else:
                        vizurl = md['vizurl']
                        mimetype = md['mimetype']
                    yield {"brain": brain,
                           "resolution": self.dstools.resolution_vocab.getTerm(brain['BCCResolution']),
                           "layer": self.dstools.layer_vocab.getTerm(layer),
                           "vizurl": vizurl,
                           'mimetype': mimetype,
                           'vizlayer': layerfile}

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
        # try to find up to count layers
        for idx in range(0, count):
            uuid = self.request.get('{}.item.{}'.format(self.name, idx))
            subuuid = self.request.get('{}.item.{}.item'.format(self.name, idx))
            if uuid:
                if not subuuid:
                    subuuid = set()
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


@implementer(IExperimentSDMWidget)
class ExperimentSDMWidget(HTMLInputWidget, Widget):
    """
    Widget that stores an experiment uuid and a list of selected sdm model uuids.

    Gives user the ability to select an experiment and pick a number of sdm models from within.
    """

    experiment_type = None
    genre = ['DataGenreSDMModel']
    multiple = None

    def item(self):
        # return dict with keys for experiment
        # and subkey 'models' for models within experiment
        item = {}
        if self.value:
            experiment_uuid = self.value.keys()[0]
            expbrain = uuidToCatalogBrain(experiment_uuid)
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
            item['models'] = [{'item': brain,
                               'uuid': brain.UID,
                               'title': brain.Title,
                               'selected': brain.UID in self.value[experiment_uuid]}
                               for brain in brains]
        return item

    def js(self):
        # TODO: search window to search for experiment
        js = u"".join((
            u'bccvl.select_dataset($("a#', self.__name__, '-popup"),',
            json.dumps({
                'field': self.__name__,
                'genre': self.genre,
                'widgetname': self.name,
                'widgetid': self.id,
                'widgeturl': '{0}/++widget++{1}'.format(self.request.getURL(),
                                                        self.__name__),
                'remote': 'experiments_listing_popup',
                'experimenttype': self.experiment_type,
            }),
            u');'))
        jswrap = getMultiAdapter((self.request, self), IJSWrapper)
        return jswrap % {'js':  js}

    def extract(self):
        # extract the value for the widget from the request and return
        # a tuple of (key,value) pairs
        # get experiment uuid from request
        uuid = self.request.get(self.name)
        if not uuid:
            return NO_VALUE
        # get selcted model uuids if any..
        # TODO: this supports only one experiment at the moment
        if isinstance(uuid, list):
            uuid = uuid[0]
        modeluuids = self.request.get('{0}.model'.format(self.name),
                                      [])
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

    #TODO:  filter by:  text, gcm, emsc, year
    #        hidden: resolution, layers

    genre = ['DataGenreFC']
    multiple = 'multiple'

    _res_vocab = None
    _layer_vocab = None

    def js(self):
        js = u"""
            bccvl.select_dataset_future($("a#%(fieldname)s-popup"), {
                field: '%(fieldname)s',
                genre: %(genre)s,
                widgetname: '%(widgetname)s',
                widgetid: '%(widgetid)s',
                widgeturl: '%(widgeturl)s',
            });""" % {
            'fieldname': self.__name__,
            'genre': self.genre,
            'widgetname': self.name,
            'widgetid': self.id,
            'widgeturl': '{0}/++widget++{1}'.format(self.request.getURL(),
                                                    self.__name__)
        }
        jswrap = getMultiAdapter((self.request, self), IJSWrapper)
        return jswrap % {'js':  js}

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
                item['datasets'] = [{'uuid': brain.UID,
                                     'title': brain.Title,
                                     'obj': brain.getObject(),
                                     'md': IBCCVLMetadata(brain.getObject()),
                                     'selected': brain.UID in self.value[experiment_uuid]}
                                                 for brain in brains]
                yield item

    def js(self):
        # TODO: search window to search for experiment
        js = u"".join((
            u'bccvl.select_experiment($("a#', self.__name__, '-popup"),',
            json.dumps({
                'field': self.__name__,
                'genre': self.genre,
                'widgetname': self.name,
                'widgetid': self.id,
                'widgeturl': '{0}/++widget++{1}'.format(self.request.getURL(),
                                                        self.__name__),
                'remote': 'experiments_listing_popup',
                'multiple': self.multiple
            }),
            u');'))
        jswrap = getMultiAdapter((self.request, self), IJSWrapper)
        return jswrap % {'js':  js}

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
            uuid = self.request.get('{}.experiment.{}'.format(self.name, idx))
            models = self.request.get('{}.dataset.{}'.format(self.name, idx), [])
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
                item['datasets'] = []
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
                    item['datasets'].append({
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

    def js(self):
        # TODO: search window to search for experiment
        js = u"".join((
            u'bccvl.select_experiment($("a#', self.__name__, '-popup"),',
            json.dumps({
                'field': self.__name__,
                'genre': self.genre,
                'widgetname': self.name,
                'widgetid': self.id,
                'widgeturl': '{0}/++widget++{1}'.format(self.request.getURL(),
                                                        self.__name__),
                'remote': 'experiments_listing_popup',
                'multiple': self.multiple,
                'experimenttype': self.experiment_type,
            }),
            u');'))
        jswrap = getMultiAdapter((self.request, self), IJSWrapper)
        return jswrap % {'js':  js}

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
            uuid = self.request.get('{}.experiment.{}'.format(self.name, idx))
            if not uuid:
                continue
            value[uuid] = {}
            try:
                dscount = int(self.request.get('{}.dataset.{}.count'.format(self.name, idx)))
            except:
                dscount = 0
            for dsidx in range(0, dscount):
                dsuuid = self.request.get('{}.dataset.{}.{}.uuid'.format(self.name, idx, dsidx))
                dsth = self.request.get('{}.dataset.{}.{}.threshold'.format(self.name, idx, dsidx))
                if dsuuid:
                    value[uuid][dsuuid] = {'label': dsth}
        if not value:
            return NO_VALUE
        return value


@implementer(IFieldWidget)
def ExperimentResultProjectionFieldWidget(field, request):
    return FieldWidget(field, ExperimentResultProjectionWidget(request))
