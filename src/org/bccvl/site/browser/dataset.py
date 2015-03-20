#from plone.dexaterity.browser.view import DefaultView (template override in plone.app.dexterity.browser)


from z3c.form import field, button, form
from z3c.form.widget import AfterWidgetUpdateEvent
from z3c.form.interfaces import DISPLAY_MODE
from zope.event import notify
from zope.lifecycleevent import modified
from org.bccvl.site.interfaces import IBCCVLMetadata
#from zope.browserpage.viewpagetemplatefile import Viewpagetemplatefile
from Products.Five.browser.pagetemplatefile import ViewPageTemplateFile
from Products.Five.browser import BrowserView


class DatasetDetailsView(BrowserView):

    def metadata(self):
        return {}



from Products.statusmessages.interfaces import IStatusMessage
from Acquisition import aq_inner
from Acquisition import aq_parent
from org.bccvl.site.interfaces import IJobTracker

class DatasetRemoveView(form.Form):
    """ 
    The remove view marks a dataset as 'removed' and deletes the associated blob. It is distinct from the built in delete
    view in that the dataset object is not actually deleted.
    """

    fields = field.Fields()
    template = ViewPageTemplateFile('dataset_remove.pt')
    enableCSRFProtection = True

    @button.buttonAndHandler(u'Remove')
    def handle_delete(self, action):
        title = self.context.Title()
        parent = aq_parent(aq_inner(self.context))
        ## removed file working on frontend Javascript
        if hasattr(self.context, "file"):
            self.context.file = None
        jt = IJobTracker(self.context)
        jt.state = 'REMOVED'
        self.context.reindexObject()
        #####
        IStatusMessage(self.request).add(u'{0[title]} has been removed.'.format({u'title': title}))
        self.request.response.redirect(aq_parent(parent).absolute_url())

    @button.buttonAndHandler(u'Cancel')
    def handle_cancel(self, action):
        self.request.response.redirect(self.context.absolute_url())


# FIXME: Turn this whole form into something re-usable
#        e.g. could be used within a widget that renders a button
#             and won't show up on add forms.
#             js turns the button into an ajax form and non-js uses redirects


from plone.z3cform.crud import crud
from zope import schema
from zope.interface import Interface
from zope.component import getUtility
import zipfile


class IFileItemMetadata(Interface):

    # FIXME: adapter to IBCCVLMetadata required?
    # FIXME: fieldnames to match BCCVLMetadata dict keys
    name = schema.TextLine(
        title=u"File name",
        description=u'The file name within the archive',
        readonly=True)

    bioclim = schema.Choice(
        title=u"Bioclimatic Variable",
        vocabulary='layer_source')


def getFileGraph(context):
    """
    create a new set of graphs to hold general file information for
    files within an archive

    """
    file = context.file.open('r')
    zip = zipfile.ZipFile(file)
    ret = []
    for zipinfo in zip.infolist():
        if zipinfo.filename.endswith('/'):
            # skip directories
            continue
        info = {}
        info['fileName'] = zipinfo.filename
        info['fileSize'] = zipinfo.file_size()
        ret.append(info)
    return ret


class EditSubForm(crud.EditSubForm):

    template = ViewPageTemplateFile('datasets_filemd_row.pt')

    def _select_field(self):
        # remove checkbox field
        return field.Fields()


class EditFileMetadataForm(crud.EditForm):
    # only works within crud as well as base form
    template = ViewPageTemplateFile('datasets_filemd_table.pt')

    editsubform_factory = EditSubForm

    @button.buttonAndHandler(u'Apply changes',
                             name='edit',
                             condition=lambda form: form.context.update_schema)
    def handle_edit(self, action):
        success = u"Successfully updated"
        partly_success = u"Some of your changes could not be applied."
        status = no_changes = u"No changes made."
        for subform in self.subforms:
            # With the ``extractData()`` call, validation will occur,
            # and errors will be stored on the widgets amongst other
            # places.  After this we have to be extra careful not to
            # call (as in ``__call__``) the subform again, since
            # that'll remove the errors again.  With the results that
            # no changes are applied but also no validation error is
            # shown.
            data, errors = subform.extractData()
            if errors:
                if status is no_changes:
                    status = subform.formErrorsMessage
                elif status is success:
                    status = partly_success
                continue
            # Wo have no select field in our editsubform
            #del data['select']
            self.context.before_update(subform.content, data)
            changes = subform.applyChanges(data)
            if changes:
                if status is no_changes:
                    status = success
                elif status is subform.formErrorsMessage:
                    status = partly_success

                # If there were changes, we'll update the view widgets
                # again, so that they'll actually display the changes
                for widget in subform.widgets.values():
                    if widget.mode == DISPLAY_MODE:
                        widget.update()
                        notify(AfterWidgetUpdateEvent(widget))
        # don't forget to update our property we manage

        urilist = []
        for subform in self.subforms:
            # TODO: this would handle adds?
            #if not subform.content_id: # we had no filename
            #    import ipdb; ipdb.set_trace()
            urilist.append(subform.content.identifier)
            if IResource.providedBy(subform.content):
                handler.put(subform.content.graph)
            else:
                handler.put(subform.content)
        data = {self.context.property: urilist}
        # here we applyData to the context (actually Crud context)
        # should be fine but cleaner solution would be better?
        # also applyChanges needs self.field which we don't have here
        content = self.context.getContent()
        content.remove((content.identifier, self.context.property, None))
        for uri in urilist:
            content.add((content.identifier, self.context.property, uri))
        # TODO: do only if things have changed
        #      - put current graph into changed queue, to persist changes
        #      - got ordf tool and push graph
        handler.put(content)
        # TODO: update status if necessary
        modified(self.context.context)
        self.status = status
        self.context.redirect()


class CrudFileMetadataForm(crud.CrudForm):
    # TODO: should cater for add, delete, and edit
    #

    # works on specific property on context
    # and allows to edit/view/display list of graphs referenced
    # by this property
    # Could be used as generic form for a specific property
    # .. lookup by (property)name ?

    # TODO: remember return address and maybe all form parameters (to
    #       return to previous form in same state if possible); makes this
    #       form work the same way with or without ajax
    template = ViewPageTemplateFile('datasets_filemd_master.pt')
    # TODO generalise this
    property = 'layers'

    update_schema = field.Fields(IFileItemMetadata).omit('name')
    view_schema = field.Fields(IFileItemMetadata).select('name')
    editform_factory = EditFileMetadataForm
    addform_factory = crud.NullForm

    _content = None
    _items = None
    _referer = None

    def __init__(self, context, request):
        super(CrudFileMetadataForm, self).__init__(context, request)
        # TODO: need to store the referer as hiddon field on form or in session
        #       .... referer/ returnURL processing should happen in update
        #       .... __init__ is also called on submit and will set
        #            current url... so request param must win over http header
        # could also check 'PARENTS', 'PATH_INFO','PATH_TRANSLATED',
        #                   ACTUAL_URL or URL
        # to get context + previous view name

    def redirect(self):
        # get current context and redirect to @@edit
        nexturl = self.context.absolute_url() + '/edit'
        self.request.response.redirect(nexturl)

    def getContent(self):
        # FIXME: maybe no longer necessary as it can be adapted directly?
        if not self._content:
            self._content = IBCCVLMetadata(self.context)
        return self._content

    def get_items(self):
        g = self.getContent()
        r = Resource(g, g.identifier)
        if not self._items:
            handler = getUtility(IORDF).getHandler()
            items = {}
            try:
                for ref in r.objects(self.property):
                    obj = next(ref.objects(), None)
                    if obj is None:
                        ref = Resource(handler.get(ref.identifier), ref.identifier)
                    itemid = ref.value(NFO['fileName']).toPython()
                    items[str(itemid)] = ref
            except:
                # something wrong with file metadata ... regenerate it
                items = {}
            if not items:  # was empty
                # FIXME: remove this, not practicable with remote datasets
                items = getFileGraph(self.context)
            self._items = items
        # TODO: sort key configurable
        return sorted(self._items.items(),
                      key=lambda x: x[0])

    def add(self, data):
        #import ipdb; ipdb.set_trace()
        #super(CrudFileMetadataForm, self).add(data)
        # TODO: implement this someday
        pass

    def remove(self, (id, item)):
        # import ipdb; ipdb.set_trace()
        # super(CrudFileMetadataForm, self).remove((id, item))
        # TODO: implement this someday
        pass

    # def before_update(self, item, data):
    #     import ipdb; ipdb.set_trace()
    #     super(CrudFileMetadataForm, self).before_update(item, data)


#TODO: Move to dataset layer:
class ICurrentClimateMetadata(Interface):
    # missing: resolution, source

    year_from = schema.Int(
        title=u"Year from",
        required=False)

    year_to = schema.Int(
        title=u"Year to",
        required=False)


# TODO: Move to dataset layer
class IFutureClimateMetadata(Interface):
    # missing: resolution, source

    year = schema.Int(
        title=u"Year",
        required=False)

    gcm = schema.Choice(
        title=u"GCM",
        # value_type=URIRefField(),
        vocabulary='gcm_source')

    emc = schema.Choice(
        title=u"Emmision Scenario",
        # value_type=URIRefField(),
        vocabulary='emsc_source')






# DataSetView ... if mime type show file content? or just coverage
#                 if data gence climate layers?

# DataSetViewlet?  (would replace view)

# DataSetEdit?  (add button to edit zip file metadata if climate layer)
# ->  DataSet Climate Layer Edit:
#       for to edit  layers ... better to keep separate from standard edit,  as it needs the file available (or at least the file list)
