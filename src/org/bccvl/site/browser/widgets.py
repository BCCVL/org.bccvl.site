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
from .interfaces import (IDatasetLayersWidget, IDatasetsRadioWidget,
                         IOrderedCheckboxWidget, IDatasetsMultiSelectWidget)
from plone.app.uuid.utils import uuidToCatalogBrain
from org.bccvl.site.interfaces import IDownloadInfo
from plone.z3cform.interfaces import IDeferSecurityCheck


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


@implementer(IDatasetLayersWidget)
class DatasetLayersWidget(HTMLFormElement, Widget):
    """
    render a list of checkboxes for keys in dictionary.
    render a default widget for values per key
    """
    # TODO: where is this used? SDMExperiment?
    # TODO: assumes that values are independent of keys for now.

    items = ()

    @property
    def markerName(self):
        return "{}.marker".format(self.name)

    @property
    def marker(self):
        return '<input type="hidden" name="{}" value="1"/>'.format(
            self.markerName)

    # TODO: can I cache the value widgets somewhere?
    def getValueWidget(self, token, value, prefix=None):
        valueType = getattr(self.field, 'value_type')
        #widget = getMultiAdapter((valueType, self.request),
        #                         IFieldWidget)
        widget = SequenceCheckboxFieldWidget(valueType, self.request)
        # we set the context so that the contextsourcebinder for choices can be set correctly.
        # TODO: check if this is secure?
        widget.context = uuidToCatalogBrain(value).getObject()  # TODO: IContextAware?
        self.setValueWidgetName(widget, token, prefix)
        widget.mode = self.mode
        if IFormAware.providedBy(self):
            widget.form = self.form
            alsoProvides(widget, IFormAware)
        # TODO: is this the wrong way round? shouldn't I update first
        #       and the set the value? For some reason the OrderedSelect
        #       needs to know the value before it updates
        #       As it is now, the widget might re-set the value from request
        if self.value and value in self.value:
            widget.value = self.value[value]
        # TODO: try to use current dataset / key as context for layers
        #       vocabulary / source?
        widget.update()
        return widget

    def setValueWidgetName(self, widget, idx, prefix=None):
        names = lambda id: [str(n) for n in [prefix, idx] + [id]
                            if n is not None]
        widget.name = '.'.join([str(self.name)]+names(None))
        widget.id = '-'.join([str(self.id)]+names(None))

    def getItem(self, term):
        id = '{}-{}'.format(self.id, term.token)
        name = '{}.{}'.format(self.name, term.token)
        if ITitledTokenizedTerm.providedBy(term):
            content = term.title
        else:
            content = term.value
        value_widget = self.getValueWidget(term.token, term.value)
        return {'id': id, 'name': name,
                'token': term.token,
                'value': term.token, 'content': content,
                'checked': self.value and term.token in self.value,
                'value_widget': value_widget}

    def update(self):
        super(DatasetLayersWidget, self).update()
        addFieldClass(self)
        keyterms = getMultiAdapter(
            (self.context, self.request, self.form, self.field.key_type, self),
            ITerms)

        self.items = [
            self.getItem(term)
            for term in keyterms]

    def extract(self):
        # extract the value for the widget from the request and return
        # a tuple of (key,value) pairs

        # check marker so that we know if we have a request to look at or
        # whether we should check for values from current context
        if not self.markerName in self.request:
            return NO_VALUE
        # widget names are encoded as:
        #    prefix.<dsuid>.layer = <uri>
        values = []
        for item in self.items:
            # extract layers for current dataset (item)
            # let our sub widget decide how to do that
            value_widget = item['value_widget']
            values.append((item['value'], value_widget.value))
        return dict(values)


def DatasetLayersFieldWidget(field, request):
    """
    Widget to select datasets and layers
    """
    return FieldWidget(field,  DatasetLayersWidget(request))


@implementer(IDatasetsRadioWidget)
class DatasetsRadioWidget(HTMLInputWidget, SequenceWidget):

    klass = u'radio-widget'
    css = u'radio'

    # Flag to check whether we have to update this widget before publishing
    _widget_traversed = False

    def isChecked(self, term):
        return term.token in self.value

    def __call__(self):
        # FIXME: this is a workaround to fix a weirdness in ++widget++ traverser.
        #        the traverser updates the widget during traversal, but at this stage
        #        the user is not authenticated and therefore the vocabulary loaded
        #        contains only entries visible to anonymous users.
        #        the updateTerms function here checks this and won't update the terms
        #        during ++widget++ traversal. We'll have to call update here though,
        #        when the widget is being published.
        if self._widget_traversed:
            self.update()
            # we deactivate diazo as well here
            self.request.response.setHeader('X-Theme-Disabled',  'True')
        return super(DatasetsRadioWidget, self).__call__()

    @property
    def items(self):
        # TODO: could this be a generator?
        items = []
        # TODO: do we have a request here? (search, filter, paginate etc...)
        #       add: species name, rows, bbox?, description, shared, owned, etc...
        #            date, link?
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
                 'label': label, 'checked': checked,
                 'dlinfo': IDownloadInfo(term.brain)})
        return items

    def updateTerms(self):
        if not IDeferSecurityCheck.providedBy(self.request):
            return super(DatasetsRadioWidget, self).updateTerms()
        else:
            self._widget_traversed = True
        return self.terms


@implementer(IFieldWidget)
def DatasetsRadioFieldWidget(field, request):
    return FieldWidget(field, DatasetsRadioWidget(request))


@implementer(IDatasetsMultiSelectWidget)
class DatasetsMultiSelectWidget(HTMLInputWidget, SequenceWidget):

    klass = u'radio-widget'
    css = u'radio'

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
            'layers': envlayers
        }

    def update(self):
        envvocab = getUtility(IVocabularyFactory,
                              name='org.bccvl.site.BioclimVocabulary')
        # TODO: could also cache the next call per request?
        self.envlayervocab = envvocab(self.context)
        super(DatasetsMultiSelectWidget, self).update()
        addFieldClass(self)


@implementer(IFieldWidget)
def DatasetsMultiSelectFieldWidget(field, request):
    return FieldWidget(field, DatasetsMultiSelectWidget(request))
