from zope.component import adapter
from zope.interface import implementer
from zope.schema.interfaces import ISequence
from z3c.form.interfaces import IFieldWidget,  IFormLayer
from z3c.form.widget import FieldWidget
from z3c.form.interfaces import IOrderedSelectWidget
from z3c.form.browser.orderedselect import OrderedSelectWidget


class IOrderedCheckboxWidget(IOrderedSelectWidget):
    """
    Interface for Ordered select widget that renders checkboxes
    """


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
