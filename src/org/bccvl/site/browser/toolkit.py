from plone.schemaeditor.interfaces import ISchemaContext
from zope.interface import implementer, Interface
from plone.schemaeditor.browser.schema.traversal import SchemaContext
from plone.supermodel import loadString, serializeSchema


class IToolkitSchemaContext(ISchemaContext):

    pass


@implementer(IToolkitSchemaContext)
class ToolkitSchemaContext(SchemaContext):

    toolkit = None

    # we have no intermediate traverser, so name must match view name for this class
    def __init__(self, context, request, name=u'editschema', title=None):

        super(ToolkitSchemaContext, self).__init__(context, request,
                                                   name, title)
        self.toolkit = context
        self.schema = loadString(self.toolkit.schema).schema
        #self.schemaName = u''

        self.Title = lambda: u'Toolkit Schema'
        # turn off green edit border for anything in the type control panel
        request.set('disable_border', 1)

    # def browserDefault(self, request):
    #     return self, ('@@overview',)

    # @property
    # def additionalSchemata(self):
    #     return ()

    pass


def serializeSchemaContext(schema_context, event=None):
    """ Serializes the schema associated with a schema context.

    The serialized schema is saved to the model_source property of the FTI
    associated with the schema context.
    """
    # find the FTI and model
    toolkit = schema_context.toolkit
    #schemaName = schema_context.schemaName
    schema = schema_context.schema
    #model = fti.lookupModel()

    # synchronize changes to the model
    # FIXME: activate this to improve schema caching
    # syncSchema(schema, model.schemata[schemaName], overwrite=True)
    toolkit.schema = serializeSchema(schema)
