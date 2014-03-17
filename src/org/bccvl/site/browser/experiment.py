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
from plone.z3cform.fieldsets.group import GroupFactory, Group
from org.bccvl.site.api import QueryAPI
from z3c.form.interfaces import DISPLAY_MODE
import logging

LOG = logging.getLogger(__name__)

class ExperimentParamGroup(Group):

    def getContent(self):
        import ipdb; ipdb.set_trace()
        if not hasattr(self.context, 'parameters'):
            return {}
        if not self.toolkit in self.context.parameters:
            return {}
        return self.context.parameters[self.toolkit]


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
    groups = []
    functions = getattr(form.context, 'functions', None) or ()
    for toolkit in (brain.getObject() for brain in api.getFunctions()):
        if form.mode == DISPLAY_MODE and toolkit.UID() not in functions:
            # filter out unused algorithms in display mode
            continue
        # FIXME: need to cache
        from plone.supermodel import loadString
        try:
            parameters_model = loadString(toolkit.schema)
        except Exception as e:

            continue

        parameters_schema = resolve(toolkit.interface)
        from plone.supermodel.utils import syncSchema
        # FIXME: sync only necessary on schema source update
        syncSchema(parameters_model.schema, parameters_schema)

        # FIXME: bad hack with field name toolkit.id is fine, but
        #        compute shouldn't rely on hardcoded names'
        param_group = ExperimentParamGroup(
            form.context,
            form.request,
            form)
        param_group.__name__ = "parameters_{}".format(toolkit.id),
        #param_group.prefix = ''+ form.prefix?
        param_group.toolkit = toolkit.id,
        param_group.fields = Fields(parameters_schema)
        param_group.label = u"configuration for {}".format(toolkit.title)
        if len(parameters_schema.names()) == 0:
            param_group.description = u"No configuration options"
        groups.append(param_group)

    form.param_groups = groups


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
        # FIXME: this does look bad, and should probably be handled by a proper widget
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

    def update(self):
        super(SDMAdd, self, ).update()
        for group in self.param_groups:
            try:
                group.update()
            except Exception as e:
                LOG.info("Group %s failed: %s", group.__name__, e)

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
