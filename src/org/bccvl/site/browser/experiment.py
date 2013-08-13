from plone.directives import dexterity, form
from zope.schema import TextLine
from z3c.form import button
from z3c.form.form import extends
from org.bccvl.site.content.experiment import IExperiment
from org.bccvl.site.interfaces import IJobTracker
from zope.component import adapter
from zope.interface import implementer
from Products.statusmessages.interfaces import IStatusMessage
#from Products.Five.browser.pagetemplatefile import ViewPageTemplateFile
from zope.browserpage.viewpagetemplatefile import ViewPageTemplateFile
from plone.dexterity.browser import add, edit, view
from zope.i18n import translate


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
    """The view. May will a template from <modulename>_templates/view.pt,
    and will be called 'view' unless otherwise stated.
    """
    # id = 'view'
    # enctype = None
    mode = DISPLAY_MODE

    extends(dexterity.DisplayForm)

    additionalSchemata = (IJobStatus, )

    #template = ViewPageTemplateFile('view.pt')

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

       # super does not work... ekpcts different kind of template
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
