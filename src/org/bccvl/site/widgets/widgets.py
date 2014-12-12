from zope.component import adapter, getMultiAdapter, getUtility
from zope.interface import implementer, alsoProvides
from zope.schema.interfaces import (ISequence, ITitledTokenizedTerm,
                                    IVocabularyFactory)
from z3c.form import util
from z3c.form.interfaces import (IFieldWidget,  IFormLayer,
                                 ITerms, IFormAware, NO_VALUE)
from z3c.form.widget import FieldWidget, Widget, SequenceWidget
from z3c.form.browser.orderedselect import OrderedSelectWidget
from z3c.form.browser.widget import (HTMLFormElement, HTMLInputWidget,
                                     addFieldClass)
from zope.i18n import translate
from .interfaces import (IDatasetLayersWidget, IDatasetWidget,
                         IOrderedCheckboxWidget, IDatasetsMultiSelectWidget,
                         IJSWrapper)
from plone.app.uuid.utils import uuidToCatalogBrain
from org.bccvl.site.interfaces import IDownloadInfo
from plone.z3cform.interfaces import IDeferSecurityCheck
from Products.CMFCore.utils import getToolByName


# Wrap js code into a document.ready wrapper and CDATA section
JS_WRAPPER = u"""//<![CDATA[
    $(document).ready(function(){%(js)s});
//]]>"""

JS_WRAPPER_ADAPTER = lambda req, widget: JS_WRAPPER


@implementer(IOrderedCheckboxWidget)
class OrderedCheckboxWidget(OrderedSelectWidget):
    """
    Class that implements IOrderedCheckboxWidget
    """


@adapter(ISequence,  IFormLayer)
@implementer(IFieldWidget)
def SequenceCheckboxFieldWidget(field,  request):
    """
    FieldWidget that uses OrderedCheckboxWidget
    """
    return FieldWidget(field,  OrderedCheckboxWidget(request))


@implementer(IDatasetWidget)
class DatasetWidget(HTMLInputWidget, Widget):
    """
    Widget that stores a dataset uuid.
    """

    genre = None

    def item(self):
        brain = uuidToCatalogBrain(self.value)
        return brain

    def js(self):
        js = u"""
            bccvl.select_dataset($("a#%(fieldname)s-popup"), {
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
                                                    self.__name__)}
        jswrap = getMultiAdapter((self.request, self), IJSWrapper)
        return jswrap % {'js':  js}


@implementer(IFieldWidget)
def DatasetFieldWidget(field, request):
    return FieldWidget(field, DatasetWidget(request))


@implementer(IDatasetLayersWidget)
class DatasetLayersWidget(HTMLFormElement, Widget):
    """
    render a list of checkboxes for keys in dictionary.
    render a default widget for values per key
    """

    _res_vocab = None

    def js(self):
        js = u"""
            bccvl.select_dataset_layers($("a#%(fieldname)s-popup"), {
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

    def resolutions(self):
        if self.value:
            pc = getToolByName(self.context, 'portal_catalog')
            brains = pc.searchResults(UID=self.value.keys())
            # TODO: should use vocab to turn into token
            return set(unicode(b['BCCResolution']) for b in brains)
        return []

    def resolution_term(self, resvalue):
        if not self._res_vocab:
            self._res_vocab = getUtility(IVocabularyFactory, 'resolution_source')(self.context)
        return self._res_vocab.getTerm(resvalue)

    def items(self):
        # FIXME importing here to avoid circular import of IDataset
        from org.bccvl.site.api.dataset import getdsmetadata
        if self.value:
            for uuid in self.value:
                brain = uuidToCatalogBrain(uuid)
                # TODO: could use layer vocab again

                md = getdsmetadata(brain)
                layers = self.value[uuid]
                for layer in md['layers']:
                    if not layer['layer'] in layers:
                        continue
                    if 'filename' in layer:
                        vizurl = '{0}#{1}'.format(md['vizurl'], layer['filename'])
                    else:
                        vizurl = md['vizurl']
                    yield {"brain": brain,
                           "resolution": self.resolution_term(brain['BCCResolution']),
                           "layer": layer,
                           "vizurl": vizurl}

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
            uuid = self.request.get('{}.dataset.{}'.format(self.name, idx))
            layer = self.request.get('{}.layer.{}'.format(self.name, idx))
            # FIXME: use vocab to translate to field value
            # skip none values in case count is larger than actual parameters
            if all((uuid, layer)):
                value.setdefault(uuid, set()).add(layer)
        if not value:
            return NO_VALUE
        return value


@implementer(IFieldWidget)
def DatasetLayersFieldWidget(field, request):
    """
    Widget to select datasets and layers
    """
    return FieldWidget(field,  DatasetLayersWidget(request))






@implementer(IDatasetsMultiSelectWidget)
class DatasetsMultiSelectWidget(HTMLInputWidget, SequenceWidget):

    klass = u'checkbox-widget'
    css = u'checkbox'

    def isChecked(self, term):
        return term.token in self.value

    @property
    def items(self):
        # TODO: could this be a generator?
        items = []
        for count, term in enumerate(self.terms):
            checked = self.isChecked(term)
            id = '%s-%i' % (self.id, count)
            if ITitledTokenizedTerm.providedBy(term):
                label = translate(term.title, context=self.request,
                                  default=term.title)
            else:
                label = util.toUnicode(term.value)
            # do catalog query for additional infos
            items.append(
                {'id': id, 'name': self.name, 'value': term.token,
                 'label': label, 'checked': checked})
        return items

    def get_item_details(self, item):
        # TODO: code duplication see: experiments_listing_view.py:45
        # TODO: fetch additional data for item here
        brain = uuidToCatalogBrain(item['value'])
        sdm = brain.getObject()
        # TODO: we might have two options here sdm could be uploaded,
        #       then we'll show other data; for now ignore this case
        #       and consider only results for sdm experiments
        # TODO: may this fail if access to parents is not possible?
        result = sdm.__parent__
        exp = result.__parent__
        # TODO: What if we don't have access to secies occurrence dataset?
        #       should user still be able to start projection?
        #       would we miss out on species info or so?
        #       Dos SDM have species infos attached?
        occurbrain = uuidToCatalogBrain(exp.species_occurrence_dataset)
        # TODO: absence data
        envlayers = []
        for envuuid, layers in sorted(exp.environmental_datasets.items()):
            envbrain = uuidToCatalogBrain(envuuid)
            envtitle = envbrain.Title if envbrain else u'Missing dataset'
            envlayers.append(
                '{}: {}'.format(envtitle,
                                ', '.join(self.envlayervocab.getTerm(envlayer).title
                                          for envlayer in sorted(layers)))
            )

        # TODO: occurbrain might be None
        return {
            'model': brain,
            'experiment': exp,
            'function': result.job_params['function'],
            'species': occurbrain,
            'layers': ', '.join(envlayers)
        }

    def update(self):
        envvocab = getUtility(IVocabularyFactory,
                              name='layer_source')
        # TODO: could also cache the next call per request?
        self.envlayervocab = envvocab(self.context)
        super(DatasetsMultiSelectWidget, self).update()
        addFieldClass(self)


@implementer(IFieldWidget)
def DatasetsMultiSelectFieldWidget(field, request):
    return FieldWidget(field, DatasetsMultiSelectWidget(request))
