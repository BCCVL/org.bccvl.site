import logging
import decimal

from plone import api as ploneapi
from plone.autoform.interfaces import MODES_KEY
from plone.supermodel import loadString
from plone.uuid.interfaces import IUUID
from zope.interface import implementer

from org.bccvl.site.api.base import BaseService
from org.bccvl.site.api.decorators import api
from org.bccvl.site.api.interfaces import IToolkitService
from org.bccvl.site import defaults


LOG = logging.getLogger(__name__)


TYPEMAP = {
    int: "integer",
    long: "integer",
    float: "number",
    decimal.Decimal: "number",
    type(None): "null",
    None: "null",
    str: "string",
    unicode: "string",
    list: "array",
    set: "array",
    bool: "boolean"
}


def type_to_string(pytypes):
    if not isinstance(pytypes, (list, tuple)):
        pytypes = [pytypes]
    for pytype in pytypes:
        if pytype in TYPEMAP:
            return TYPEMAP[pytype]
    return "object"


def toolkit_schema(schema):
    parameters_model = loadString(schema)
    parameters_schema = parameters_model.schema
    modes = {name: mode for ifc, name,
             mode in parameters_schema.queryTaggedValue(MODES_KEY, ())}
    ret = {
        'type': 'object',
        'properties': {}
    }
    for name in parameters_schema.names():
        field = parameters_schema[name]
        if field.readonly:
            continue
        if modes.get(name, '') == 'hidden':
            continue
        ret['properties'][name] = {
            'type': type_to_string(field._type),
            'title': field.title,
            'default': field.default,
            'description': field.description,
        }
    return ret


@api('toolkit_v1.json')
@implementer(IToolkitService)
class ToolkitService(BaseService):

    def list(self):
        portal = ploneapi.portal.get()
        toolkits = portal[defaults.TOOLKITS_FOLDER_ID]
        ret = {}
        for tool in toolkits.values():
            if not tool.experiment_type:
                continue
            ret[tool.id] = {
                'id': tool.id,
                'uuid': IUUID(tool),
                'title': tool.title,
                'description': tool.description,
                'schema': toolkit_schema(tool.schema),
                'category': tool.algorithm_category,
                'experiment_type': tool.experiment_type
            }
        return ret
