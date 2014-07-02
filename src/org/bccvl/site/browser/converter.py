from zope.interface import alsoProvides
from zope.component import adapter, getMultiAdapter
from zope.schema.interfaces import IDict
from .interfaces import IDatasetLayersWidget
from z3c.form.converter import BaseDataConverter
from z3c.form.interfaces import IFieldWidget, IFormAware, IDataConverter
from plone.app.uuid.utils import uuidToObject


@adapter(IDict, IDatasetLayersWidget)
class DatasetLayersConverter(BaseDataConverter):
    """
    Dataconverter used to glue datasets_layer dict and datasetswidget together
    """

    def _getConverter(self, field, contextuuid):
        # We rely on the default registered widget, this is probably a
        # restriction for custom widgets. If so use your own MultiWidget and
        # register your own converter which will get the right widget for the
        # used value_type.
        widget = self.widget.getValueWidget(contextuuid, contextuuid)
        converter = getMultiAdapter((field, widget), IDataConverter)
        return converter

    def toWidgetValue(self, value):
        """Just dispatch it."""
        if value is self.field.missing_value:
            return {}
        #key_converter = self._getConverter(self.field.key_type)

        # we always return a list of values for the widget
        dictgen = ((k, self._getConverter(self.field.value_type, k).toWidgetValue(v))
                   for k, v in value.items())
        return dict(dictgen)

    def toFieldValue(self, value):
        """Just dispatch it."""
        if not len(value):
            return self.field.missing_value

        ret = {}
        for k, v in (x for x in value.iteritems() if x[1]):
            converter = self._getConverter(self.field.value_type, k)
            fv = converter.toFieldValue(v)
            if fv:
                ret[k] = fv
        return ret


from zope.schema import Dict


class DatasetLayersField(Dict):
    """
    updated validation to Dict field.
    """
    # TODO: this is a bit of a hack, but I didn't want to rewrite a whole Dict field
    #       with all it's default registrations

    def _validate(self, value):
        # if we have a value_type we have to bind it to the correct context,
        # so that vocabularies and sources are set up correctly.
        # TODO: would I change a field globally here or am I working on a clone?
        if self.value_type:
            for key, val in value.items():
                ctx = uuidToObject(key)
                # delete current vocabulary that is bound to main context,
                # and rebind to context for key
                self.value_type.value_type.vocabulary = None
                self.value_type = self.value_type.bind(ctx)
                super(DatasetLayersField, self)._validate({key: val})
