from zope.component import adapter
from zope.schema.interfaces import IDict, IList
from .interfaces import IDatasetLayersWidget, IExperimentSDMWidget, IFutureDatasetsWidget, IExperimentResultWidget, IExperimentResultProjectionWidget
from z3c.form.converter import BaseDataConverter


# TODO: all these converters do exactly the same.
#       -> create generic converter and register for each interface combination

@adapter(IDict, IDatasetLayersWidget)
class DatasetLayersConverter(BaseDataConverter):
    """
    Dataconverter used to glue datasets_layer dict and datasetswidget together
    """

    def toWidgetValue(self, value):
        """Just dispatch it."""
        if value is self.field.missing_value:
            return None

        # we pretty much leave it as is, because the the value is the same as what
        # get's stored in the field
        # TODO: check if the above is true... need to convert TextLine? or Set?
        return value

    def toFieldValue(self, value):
        """Just dispatch it."""
        if not len(value):
            return self.field.missing_value

        # TODO: do I need to return a copy?
        #       or convert texline, set?
        return value


@adapter(IDict, IExperimentSDMWidget)
class ExperimentsSDMConverter(BaseDataConverter):
    """
    Data converter used to glue experiment-sdm dict and experimentssdmwidget together
    """

    def toWidgetValue(self, value):
        """Just dispatch it."""
        if value is self.field.missing_value:
            return None

        # we pretty much leave it as is, because the the value is the same as what
        # get's stored in the field
        # TODO: check if the above is true... need to convert TextLine? or Set?
        return value

    def toFieldValue(self, value):
        """Just dispatch it."""
        if not len(value):
            return self.field.missing_value

        # TODO: do I need to return a copy?
        #       or convert texline, set?
        return value


@adapter(IDict, IExperimentResultWidget)
class ExperimentsResultConverter(BaseDataConverter):
    """
    Data converter used to glue experiment-sdm dict and experimentssdmwidget together
    """

    def toWidgetValue(self, value):
        """Just dispatch it."""
        if value is self.field.missing_value:
            return None

        # we pretty much leave it as is, because the the value is the same as what
        # get's stored in the field
        # TODO: check if the above is true... need to convert TextLine? or Set?
        return value

    def toFieldValue(self, value):
        """Just dispatch it."""
        if not len(value):
            return self.field.missing_value

        # TODO: do I need to return a copy?
        #       or convert texline, set?
        return value


@adapter(IList, IFutureDatasetsWidget)
class FutureDatasetsConverter(BaseDataConverter):
    """
    Data converter used to glue experiment-sdm dict and experimentssdmwidget together
    """

    def toWidgetValue(self, value):
        """Just dispatch it."""
        if value is self.field.missing_value:
            return None

        # we pretty much leave it as is, because the the value is the same as what
        # get's stored in the field
        # TODO: check if the above is true... need to convert TextLine? or Set?
        return value

    def toFieldValue(self, value):
        """Just dispatch it."""
        if not len(value):
            return self.field.missing_value

        # TODO: do I need to return a copy?
        #       or convert texline, set?
        return value


@adapter(IDict, IExperimentResultProjectionWidget)
class ExperimentResultProjectionConverter(BaseDataConverter):
    """
    Data converter used to glue experiment-sdm dict and experimentssdmwidget together
    """

    def toWidgetValue(self, value):
        """Just dispatch it."""
        if value is self.field.missing_value:
            return None

        # we pretty much leave it as is, because the the value is the same as what
        # get's stored in the field
        # TODO: check if the above is true... need to convert TextLine? or Set?
        return value

    def toFieldValue(self, value):
        """Just dispatch it."""
        if not len(value):
            return self.field.missing_value

        # TODO: do I need to return a copy?
        #       or convert texline, set?
        return value
