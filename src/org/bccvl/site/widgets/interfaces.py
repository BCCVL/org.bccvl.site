from zope.interface import Interface
from z3c.form.interfaces import IWidget, ICheckBoxWidget


class IFunctionsWidget(ICheckBoxWidget):

    pass


class IDatasetWidget(IWidget):

    pass

class IDatasetDictWidget(IWidget):

    pass

class IExperimentSDMWidget(IWidget):

    pass


class IExperimentResultWidget(IWidget):

    pass


class IFutureDatasetsWidget(IWidget):

    pass


class IExperimentResultProjectionWidget(IWidget):

    pass


class IJSWrapper(Interface):

    pass
