from plone.directives import dexterity
from z3c.form import button
from z3c.form.field import Fields
from z3c.form.form import extends
from z3c.form.interfaces import ActionExecutionError
from org.bccvl.site.interfaces import IJobTracker
from Products.Five.browser.pagetemplatefile import ViewPageTemplateFile
from Products.statusmessages.interfaces import IStatusMessage
from plone.dexterity.browser import add, edit
from org.bccvl.site import MessageFactory as _
from org.bccvl.site.browser.xmlrpc import getdsmetadata
from org.bccvl.site.browser.job import IJobStatus
from zope import schema
from zope.interface import Invalid
from zope.dottedname.resolve import resolve
from plone.z3cform.fieldsets.group import GroupFactory
from org.bccvl.site.api import QueryAPI


from z3c.form.interfaces import DISPLAY_MODE


# DefaultEditView = layout.wrap_form(DefaultEditForm)
# from plone.z3cform import layout
class View(edit.DefaultEditForm):
    """The view. Will be a template from <modulename>_templates/view.pt,
    and will be called 'view' unless otherwise stated.
    """
    # id = 'view'
    # enctype = None
    mode = DISPLAY_MODE

    extends(dexterity.DisplayForm)

    additionalSchemata = (IJobStatus, )

    template = ViewPageTemplateFile("experiment_view.pt")

    label = ''

    #@button.handler(IJobStatus.apply
    # condition=lambda form: form.showApply)
    @button.buttonAndHandler(u'Start Job')
    def handleStartJob(self, action):
        data, errors = self.extractData()

        if errors:
            self.status = self.formErrorsMessage
            return

        #msgtype, msg = IJobStatus(self.context)
        msgtype, msg = IJobTracker(self.context).start_job(self.request)
        if msgtype is not None:
            IStatusMessage(self.request).add(msg, type=msgtype)
        self.request.response.redirect(self.context.absolute_url())

    # def render(self):
    #     '''See interfaces.IForm'''
    #     # render content template
    #     import zope.component
    #     from zope.pagetemplate.interfaces import IPageTemplate

    #     if self.template is None:
    #         template = zope.component.getMultiAdapter((self, self.request),
    #             IPageTemplate)
    #         return template(self)
    #     return self.template()

       # super does not work... expects different kind of template
        # return super(View,  self).render()
    #     template = getattr(self, 'template', None)
    #     if template is not None:
    #         return self.template.render(self)
    #     return zope.publisher.publish.mapply(self.render, (), self.request)
    # render.base_method = True


class SDMView(View):

    def updateFields(self):
        super(SDMView, self).updateFields()
        addToolkitFields(self)


class Edit(edit.DefaultEditForm):

    pass


class SDMEdit(Edit):

    def updateFields(self):
        super(Edit, self).updateFields()
        addToolkitFields(self)


def addToolkitFields(form):
    # context is usually a folder (add form) or experiment (edit, display)
    api = QueryAPI(form.context)
    fields = []
    functions = getattr(form.context, 'functions', None) or ()
    for toolkit in (brain.getObject() for brain in api.getFunctions()):
        if form.mode == DISPLAY_MODE and toolkit.UID() not in functions:
            # filter out unused algorithms in display mode
            continue
        # FIXME: need to cache
        from plone.supermodel import xmlSchema
        parameters_model = xmlSchema(toolkit.schema)
        parameters_schema = resolve(toolkit.interface)
        from plone.supermodel.utils import syncSchema
        # FIXME: sync only necessary on schema source update
        syncSchema(parameters_model.schema, parameters_schema)

        field_schema = schema.Object(
            __name__='parameters_%s' % toolkit.id,
            title=u'configuration for %s' % toolkit.title,
            schema=parameters_schema,
            required=False,
        )
        if len(field_schema.schema.names()) == 0:
            field_schema.description = u"No configuration options"
        fields.append(field_schema)
    # FIXME: need a recursive rendering GroupFactory here?
    config_group = GroupFactory('parameters', Fields(*fields),
                                'Configuration', None)
    # FIXME: group id
    # make it the first fieldset so it always has the same ID for diazo
    # ...there must be a better way to do that
    form.groups.insert(0, config_group)


class Add(add.DefaultAddForm):

    extends(dexterity.DisplayForm,
            ignoreButtons=True)

    buttons = button.Buttons(add.DefaultAddForm.buttons['cancel'])

    @button.buttonAndHandler(_('Create and start'), name='save')
    def handleAdd(self, action):
        data, errors = self.extractData()
        self.validateAction(data)
        if errors:
            self.status = self.formErrorsMessage
            return
        # TODO: this is prob. a bug in base form, because createAndAdd
        #       does not return the wrapped object.
        obj = self.createAndAdd(data)
        if obj is None:
            # TODO: this is probably an error here?
            #       object creation/add failed for some reason
            return
        # get wrapped instance fo new object (see above)
        obj = self.context[obj.id]
        # mark only as finished if we get the new object
        self._finishedAdd = True
        IStatusMessage(self.request).addStatusMessage(_(u"Item created"),
                                                      "info")
        # auto start job here
        jt = IJobTracker(obj)
        msgtype, msg = jt.start_job(self.request)
        if msgtype is not None:
            IStatusMessage(self.request).add(msg, type=msgtype)

    @button.buttonAndHandler(_('Create'), name='create')
    def handleCreate(self, action):
        data, errors = self.extractData()
        self.validateAction(data)
        if errors:
            self.status = self.formErrorsMessage
            return
        # TODO: this is prob. a bug in base form, because createAndAdd
        #       does not return the wrapped object.
        obj = self.createAndAdd(data)
        if obj is None:
            # TODO: this is probably an error here?
            #       object creation/add failed for some reason
            return
        # get wrapped instance fo new object (see above)
        obj = self.context[obj.id]
        # mark only as finished if we get the new object
        self._finishedAdd = True
        IStatusMessage(self.request).addStatusMessage(_(u"Item created"),
                                                      "info")

    # TODO: deprecate once data mover/manager API is finished?
    template = ViewPageTemplateFile("experiment_add.pt")

    def occurrences_mapping(self):
        import json
        from org.bccvl.site.api import QueryAPI
        api = QueryAPI(self.context)
        mapping = dict()
        for brain in api.getSpeciesOccurrenceDatasets():
            dataset_info = getdsmetadata(brain.getObject())
            mapping[dataset_info['id']] = {
                'object': dataset_info['url'],
                'file': dataset_info['file'],
            }
        js_tmpl = """
            window.bccvl || (window.bccvl = {});
            window.bccvl.lookups || (window.bccvl.lookups = {});
            window.bccvl.lookups.occurrencesMap = %s;
        """
        return js_tmpl % json.dumps(mapping)


class SDMAdd(Add):

    def updateFields(self):
        super(Add, self).updateFields()
        addToolkitFields(self)

    def updateWidgets(self):
        super(SDMAdd, self, ).updateWidgets()
        # envirodatasetswidget = self.widgets.get('environmental_datasets', None)
        # if not envirodatasetswidget.key_widgets:
        #     envirodatasetswidget.appendAddingWidget()

    def validateAction(self, data):
        # ActionExecutionError ... form wide error
        # WidgetActionExecutionError ... widget specific
        # TODO: validate all sort of extra info- new object does not exist yet
        # e.g. do spatial scale validation here
        pass


class ProjectionAdd(Add):

    def validateAction(self, data):
        # ActionExecutionError ... form wide error
        # WidgetActionExecutionError ... widget specific
        # TODO: do spatial scale validation as well (find_projection
        #       might be able to do it already)
        #
        from org.bccvl.site.content.experiment import find_projections
        result = find_projections(self.context, data.get('emission_scenarios'),
                                  data.get('climate_models'),
                                  data.get('years'))
        if not len(result):
            raise ActionExecutionError(Invalid(u"The combination of projection points does not match any datasets"))


class ProjectionAddView(add.DefaultAddView):
    """
    The formwrapper wrapping Add form above
    """

    form = ProjectionAdd


class SDMAddView(add.DefaultAddView):

    form = SDMAdd
