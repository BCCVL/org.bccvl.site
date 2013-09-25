from plone.directives import dexterity, form
from zope.schema import TextLine
from z3c.form import button
from z3c.form.form import extends
from org.bccvl.site.content.experiment import IExperiment
from org.bccvl.site.interfaces import IJobTracker
from zope.component import adapter
from zope.interface import implementer
from Products.Five.browser.pagetemplatefile import ViewPageTemplateFile
from Products.statusmessages.interfaces import IStatusMessage
from plone.dexterity.browser import add, edit, view
from zope.i18n import translate
from org.bccvl.site import MessageFactory as _
from org.bccvl.site.browser.xmlrpc import getdsmetadata


class IJobStatus(form.Schema):

    status = TextLine(title=u'Current Job Status',
                      required=False,
                      readonly=True)

    #apply = button.Button(title=u'Apply')


from z3c.form.interfaces import DISPLAY_MODE


@adapter(IExperiment)
@implementer(IJobStatus)
class JobStatus(object):

    def __init__(self, context):
        self.context = context

    @property
    def status(self):
        js = IJobTracker(self.context).get_job_status()
        if js is not None:
            return translate(js)
        return None


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
        msgtype, msg = IJobTracker(self.context).start_job()
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

# class Edit(dexterity.EditForm):
#     """A standard edit form.
#     """
#     grok.context(IPage)

#     def updateWidgets(self):
#         super(Edit, self).updateWidgets()
#         self.widgets['title'].mode = 'hidden'


class Add(add.DefaultAddForm):

    extends(dexterity.DisplayForm,
            ignoreButtons=True)

    buttons = button.Buttons(add.DefaultAddForm.buttons['cancel'])

    @button.buttonAndHandler(_('Create and start'), name='save')
    def handleAdd(self, action):
        data, errors = self.extractData()
        if errors:
            self.status = self.formErrorsMessage
            return
        # TODO: this is prob. a bug in base form, because createAndAdd does not return
        #       the wrapped object.
        obj = self.createAndAdd(data)
        if obj is None:
            # TODO: this is probably an error here?
            #       object creation/add failed for some reason
            return
        # get wrapped instance fo new object (see above)
        obj = self.context[obj.id]
        # mark only as finished if we get the new object
        self._finishedAdd = True
        IStatusMessage(self.request).addStatusMessage(_(u"Item created"), "info")
        # auto start job here

        jt = IJobTracker(obj)
        msgtype, msg = jt.start_job()
        if msgtype is not None:
            IStatusMessage(self.request).add(msg, type=msgtype)

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



class AddView(add.DefaultAddView):
    """
    The formwrapper wrapping Add form above
    """

    form = Add
