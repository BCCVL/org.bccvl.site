from zope.component import adapter
from zope.schema.interfaces import IDict
from .interfaces import IDatasetLayersWidget
from z3c.form.converter import BaseDataConverter


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
