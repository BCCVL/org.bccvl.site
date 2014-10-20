from zope.interface import Interface
from z3c.form.interfaces import IOrderedSelectWidget, IWidget


class IOrderedCheckboxWidget(IOrderedSelectWidget):
    """
    Interface for Ordered select widget that renders checkboxes
    """


class IDatasetLayersWidget(IWidget):

    pass


class IDatasetWidget(IWidget):

    pass


class IDatasetsMultiSelectWidget(IWidget):

    pass


class IJSWrapper(Interface):

    pass
