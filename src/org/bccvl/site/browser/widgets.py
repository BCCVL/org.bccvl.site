from zope.component import adapter, getMultiAdapter
from zope.interface import implementer, alsoProvides
from zope.schema.interfaces import ISequence, ITitledTokenizedTerm
from z3c.form.interfaces import IFieldWidget,  IFormLayer, ITerms, IFormAware, NO_VALUE
from z3c.form.widget import FieldWidget, Widget
from z3c.form.browser.orderedselect import OrderedSelectWidget
from z3c.form.browser.widget import HTMLFormElement, addFieldClass
from .interfaces import IDatasetsWidget, IOrderedCheckboxWidget


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


@implementer(IDatasetsWidget)
class DatasetsWidget(HTMLFormElement, Widget):
    """
    render a list of checkboxes for keys in dictionary.
    render a default widget for values per key
    """
    # TODO: assumes that values are independent of keys for now.

    items = ()

    @property
    def markerName(self):
        return "{}.marker".format(self.name)

    @property
    def marker(self):
        return '<input type="hidden" name="{}" value="1"/>'.format(
            self.markerName)

    def getValueWidget(self, token, value, prefix=None):
        valueType = getattr(self.field, 'value_type')
        widget = getMultiAdapter((valueType, self.request),
                                 IFieldWidget)
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
        widget.update()
        return widget

    def setValueWidgetName(self, widget, idx, prefix=None):
        names = lambda id: [str(n) for n in [id]+[prefix, idx]
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
        super(DatasetsWidget, self).update()
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
        values = []
        for item in self.items:
            cbname = '{}.select'.format(item['name'])
            if cbname in self.request:
                value_widget = self.getValueWidget(item['token'], item['value'])
                values.append((item['value'], value_widget.value))
        return dict(values)


def DatasetsFieldWidget(field, request):
    """
    Widget to select datasets and layers
    """
    return FieldWidget(field,  DatasetsWidget(request))
