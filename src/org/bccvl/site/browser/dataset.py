# from plone.dexaterity.browser.view import DefaultView (template override
# in plone.app.dexterity.browser)
import binascii

from AccessControl import Unauthorized
from Acquisition import aq_inner
from Acquisition import aq_parent
from Products.Five.browser import BrowserView
from Products.Five.browser.pagetemplatefile import ViewPageTemplateFile
from Products.statusmessages.interfaces import IStatusMessage
from plone.namedfile.browser import Download
from plone.session.tktauth import splitTicket
from plone.app.uuid.utils import uuidToObject
from z3c.form import field, button, form
from z3c.form.widget import AfterWidgetUpdateEvent
from z3c.form.interfaces import DISPLAY_MODE
from zope.component import getUtility
from zope.event import notify
from zope.interface import implementer
from zope.lifecycleevent import modified
from zope.publisher.interfaces import IPublishTraverse, NotFound
from zope.security import checkPermission
from org.bccvl.site.content.interfaces import IExperiment, IProjectionExperiment
from org.bccvl.site.interfaces import IBCCVLMetadata
# from zope.browserpage.viewpagetemplatefile import Viewpagetemplatefile
from org.bccvl.site.job.interfaces import IJobTracker
from org.bccvl.site.stats.interfaces import IStatsUtility
from org.bccvl.site.swift.interfaces import ISwiftUtility


class DatasetRemoveView(form.Form):
    """
    The remove view marks a dataset as 'removed' and deletes the associated blob. It is distinct from the built in delete
    view in that the dataset object is not actually deleted.
    """

    label = u"Do you really want to remove this item?"
    fields = field.Fields()
    enableCSRFProtection = True

    @button.buttonAndHandler(u'Remove')
    def handle_delete(self, action):
        title = self.context.Title()
        parent = aq_parent(aq_inner(self.context))

        # Objects to be deleted
        dsobjs = [self.context]
        # FIXME: would be faster to deal with brains here instead of objects
        if hasattr(self.context, "parts"):
            dsobjs += [uuidToObject(ds) for ds in self.context.parts]

        stats = getUtility(IStatsUtility)

        for context in dsobjs:
            # removed file working on frontend Javascript
            if hasattr(context, "file"):
                context.file = None
            # FIXME: we should probably delete it instead of marking it as REMOVED
            jt = IJobTracker(context)
            if (jt.state != 'REMOVED'):
                jt.state = 'REMOVED'
                context.reindexObject()
            # collect stats
            stats.count_dataset(source=context.dataSource,
                                portal_type=context.portal_type,
                                state='REMOVED')

        #####
        IStatusMessage(self.request).add(
            u'{0[title]} has been removed.'.format({u'title': title}))
        self.request.response.redirect(parent.absolute_url())

    @button.buttonAndHandler(u'Cancel')
    def handle_cancel(self, action):
        self.request.response.redirect(self.context.absolute_url())

    def render(self):
        if self.index:
            return self.index()
        return super(DatasetRemoveView, self).render()


@implementer(IPublishTraverse)
class RemoteDatasetDownload(BrowserView):

    def __init__(self, context, request):
        super(RemoteDatasetDownload, self).__init__(context, request)
        self.filename = None

    def publishTraverse(self, request, name):
        # allow filename in url, so that it is possible to parse the url
        if self.filename is None:  # ../@@download/filename
            self.filename = name
        elif name == 'HEAD':
            return self
        else:
            raise NotFound(self, name, request)
        return self

    def check_allowed(self):
        # check if content is protected
        if getattr(self.context, 'downloadable', False):
            # open for download
            return True
        # check if current user has general download permission
        #    this permission overrides the downloadable flag on the context
        if checkPermission('org.bccvl.DownloadDataset', self.context):
            return True
        # check if current user ticket has required token
        # TODO: maybe use local roles? http://docs.plone.org/develop/plone/security/dynamic_roles.html
        # assumes, that the cookie name is __ac and that it has already been
        # verified by PAS
        ticket = binascii.a2b_base64(self.request.get('__ac', '')).strip()
        try:
            (digest, userid, tokens, user_data, timestamp) = splitTicket(ticket)
            if 'org.bccvl.DownloadDataset' in tokens:
                return True
        except ValueError:
            # ignore token parse errors
            pass
        # nothing allows acces, so we deny it
        return False

    def __call__(self):
        # respect field level security as defined in plone.autoform
        # check if attribute access would be allowed!
        # url = guarded_getattr(self.context, 'remoteUrl', None)
        remoteUrl = getattr(self.context, 'remoteUrl', None)
        if remoteUrl is None:
            raise NotFound(self, 'remoteUrl', self.request)
        # check if download allowed
        if not self.check_allowed():
            raise Unauthorized("You may not download this object")
        # Generate temp url
        tool = getUtility(ISwiftUtility)
        try:
            url = tool.generate_temp_url(url=remoteUrl)
        except:
            url = remoteUrl
        return self.request.RESPONSE.redirect(url.encode('utf-8'))

    def HEAD(self):
        # we wan't to redirect here as well
        return self.__call__()


class DatasetDownload(Download):

    def publishTraverse(self, request, name):
        # allow filename in url, so that it is possible to parse the url
        if self.filename and self.fieldname and name == 'HEAD':
            return self
        return super(DatasetDownload, self).publishTraverse(request, name)

    def check_allowed(self):
        # check if content is protected
        if getattr(self.context, 'downloadable', False):
            # open for download
            return True
        # check if current user has general download permission
        #    this permission overrides the downloadable flag on the context
        if checkPermission('org.bccvl.DownloadDataset', self.context):
            return True
        # check if current user ticket has required token
        # TODO: maybe use local roles? http://docs.plone.org/develop/plone/security/dynamic_roles.html
        # assumes, that the cookie name is __ac and that it has already been
        # verified by PAS
        ticket = binascii.a2b_base64(self.request.get('__ac', '')).strip()
        try:
            (digest, userid, tokens, user_data, timestamp) = splitTicket(ticket)
            if 'org.bccvl.DownloadDataset' in tokens:
                return True
        except ValueError:
            # ignore token parse errors
            pass
        # nothing allows acces, so we deny it
        return False

    def __call__(self):
        # check if download allowed
        if not self.check_allowed():
            raise Unauthorized("You may not download this object")
        return super(DatasetDownload, self).__call__()

    def HEAD(self):
        # we wan't to redirect here as well
        return self.__call__()



@implementer(IPublishTraverse)
class ConstraintRegionDownload(BrowserView):

    def __init__(self, context, request):
        super(ConstraintRegionDownload, self).__init__(context, request)
        self.filename = None

    def publishTraverse(self, request, name):
        # allow filename in url, so that it is possible to parse the url
        if self.filename is None:  # ../@@download/filename
            self.filename = name
        elif name == 'HEAD':
            return self
        else:
            raise NotFound(self, name, request)
        return self

    def check_allowed(self):
        # check if content is protected
        if getattr(self.context, 'downloadable', False):
            # open for download
            return True
        # check if current user has general download permission
        #    this permission overrides the downloadable flag on the context
        if checkPermission('org.bccvl.DownloadDataset', self.context):
            return True
        # check if current user ticket has required token
        # TODO: maybe use local roles? http://docs.plone.org/develop/plone/security/dynamic_roles.html
        # assumes, that the cookie name is __ac and that it has already been
        # verified by PAS
        ticket = binascii.a2b_base64(self.request.get('__ac', '')).strip()
        try:
            (digest, userid, tokens, user_data, timestamp) = splitTicket(ticket)
            if 'org.bccvl.DownloadDataset' in tokens:
                return True
        except ValueError:
            # ignore token parse errors
            pass
        # nothing allows acces, so we deny it
        return False

    def __call__(self):
        # respect field level security as defined in plone.autoform
        # check if attribute access would be allowed!
        # url = guarded_getattr(self.context, 'remoteUrl', None)

        exp = self.context
        if IProjectionExperiment.providedBy(exp):
            if exp.projection_region:
                return exp.projection_region.data
            if not exp.species_distribution_models:
                raise NotFound(self, 'species_distribution_models', self.request)
            # Return the SDM's modelling region
            sdmuuid = exp.species_distribution_models.keys()[0]
            sdmobj = uuidToObject(sdmuuid)
            if sdmobj and sdmobj.modelling_region:
                return sdmobj.modelling_region.data
        elif IExperiment.providedBy(exp):
            if exp.modelling_region:
                return exp.modelling_region.data
        else:
            # Move one level up if this is an exp result file
            if not IExperiment.providedBy(exp.__parent__):
                exp = exp.__parent__
        if IExperiment.providedBy(exp.__parent__):
            # this is the result folder
            if IProjectionExperiment.providedBy(exp.__parent__):
                if exp.job_params['projection_region']:
                    return exp.job_params['projection_region'].data
                # Get constraint from SDM experiment result file. 
                # Use the modelling_region.json file in the sdm result if available.
                if not 'species_distribution_models' in exp.job_params:
                    raise NotFound(self, 'species_distribution_models', self.request)
                sdmuuid = exp.job_params['species_distribution_models']
                sdmobj = uuidToObject(sdmuuid).__parent__
            else:
                sdmobj = exp

            # Return the modelling_region attribute only if no modelling_region.json file
            if not 'modelling_region.json' in sdmobj.keys():
                return sdmobj.modelling_region.data

            # Redirect to download the modelling_region.json
            constraint_region = sdmobj.get('modelling_region.json')
            remoteUrl = getattr(constraint_region, 'remoteUrl', None)
            if remoteUrl is None:
                raise NotFound(self, 'remoteUrl', self.request)
            # Generate temp url
            tool = getUtility(ISwiftUtility)
            try:
                url = tool.generate_temp_url(url=remoteUrl)
            except:
                url = remoteUrl
            return self.request.RESPONSE.redirect(url.encode('utf-8'))
        else:
            raise NotFound(self, 'constraint_region', self.request)

    def HEAD(self):
        # we wan't to redirect here as well
        return self.__call__()


# FIXME: Turn this whole form into something re-usable
#        e.g. could be used within a widget that renders a button
#             and won't show up on add forms.
#             js turns the button into an ajax form and non-js uses redirects


from plone.z3cform.crud import crud
from zope import schema
from zope.interface import Interface
import zipfile


class IFileItemMetadata(Interface):

    # FIXME: adapter to IBCCVLMetadata required?
    # FIXME: fieldnames to match BCCVLMetadata dict keys
    filename = schema.TextLine(
        title=u"File name",
        description=u'The file name within the archive',
        readonly=True)

    layer = schema.Choice(
        title=u"Layer",
        vocabulary='layer_source',
        required=False)

    datatype = schema.Choice(
        title=u"Data type",
        vocabulary='datatype_source')


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
            # del data['select']
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

        # update IBCCVLMetadata['layers'] with current entered values
        ds = self.context.context
        md = IBCCVLMetadata(ds)
        layers = md.get('layers', {})
        # map filenames to layers
        file_map = {}
        for layer in layers.values():
            file_map[layer['filename']] = layer
        # rebuild layers dict with correct keys and datatypes
        layers = {}
        for subform in self.subforms:
            if subform.content['layer']:
                layer_id = subform.content['layer']
            else:
                layer_id = subform.content['filename']

            layer = file_map[subform.content['filename']]
            layer['datatype'] = subform.content['datatype']
            layer['layer'] = layer_id

            layers[layer_id] = layer
        # write changes back
        md['layers'] = layers

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

    update_schema = field.Fields(IFileItemMetadata).omit('filename')
    view_schema = field.Fields(IFileItemMetadata).select('filename')
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
        layers = self.getContent().get('layers', {})
        if not self._items:
            items = {}
            for key in layers:
                # key ... layer identifier
                layer = layers[key]
                items[layer.get('filename', key).encode('utf-8')] = {
                    'layer': layer.get('layer', key),
                    'filename': layer.get('filename', key),
                    'datatype': layer.get('datatype', 'continuous')
                }
            self._items = items
        return sorted(self._items.items(),
                      key=lambda x: x[0])

    def add(self, data):
        # super(CrudFileMetadataForm, self).add(data)
        # TODO: implement this someday
        pass

    def remove(self, (id, item)):
        # super(CrudFileMetadataForm, self).remove((id, item))
        # TODO: implement this someday
        pass

    # def before_update(self, item, data):
    #     super(CrudFileMetadataForm, self).before_update(item, data)


# DataSetView ... if mime type show file content? or just coverage
#                 if data gence climate layers?

# DataSetViewlet?  (would replace view)

# DataSetEdit?  (add button to edit zip file metadata if climate layer)
# ->  DataSet Climate Layer Edit:
# for to edit  layers ... better to keep separate from standard edit,  as
# it needs the file available (or at least the file list)
