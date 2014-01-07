from zope.interface import alsoProvides
from zope.component import adapter, getMultiAdapter
from zope.schema.interfaces import IDict
from .interfaces import IDatasetsWidget
from z3c.form.converter import BaseDataConverter
from z3c.form.interfaces import IFieldWidget, IFormAware, IDataConverter


@adapter(IDict, IDatasetsWidget)
class DatasetsConverter(BaseDataConverter):
    """
    Dataconverter used to glue datasets_layer dict and datasetswidget together
    """

    def _getConverter(self, field):
        # We rely on the default registered widget, this is probably a
        # restriction for custom widgets. If so use your own MultiWidget and
        # register your own converter which will get the right widget for the
        # used value_type.
        widget = getMultiAdapter((field, self.widget.request), IFieldWidget)
        if IFormAware.providedBy(self.widget):
            # form property required by objectwidget
            widget.form = self.widget.form
            alsoProvides(widget, IFormAware)
        converter = getMultiAdapter((field, widget), IDataConverter)
        return converter

    def toWidgetValue(self, value):
        """Just dispatch it."""
        if value is self.field.missing_value:
            return {}
        converter = self._getConverter(self.field.value_type)
        #key_converter = self._getConverter(self.field.key_type)

        # we always return a list of values for the widget
        return dict(((k, converter.toWidgetValue(v))for k, v in value.items()))

    def toFieldValue(self, value):
        """Just dispatch it."""
        if not len(value):
            return self.field.missing_value

        converter = self._getConverter(self.field.value_type)
        #key_converter = self._getConverter(self.field.key_type)

        return dict(((k, converter.toFieldValue(v)) for k, v in value.items()))
