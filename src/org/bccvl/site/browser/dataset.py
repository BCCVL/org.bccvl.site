#from plone.dexaterity.browser.view import DefaultView (template override in plone.app.dexterity.browser)
from plone.dexterity.browser.edit import DefaultEditForm
from plone.dexterity.browser.view import DefaultView
from z3c.form import form, field, button
from z3c.form.widget import AfterWidgetUpdateEvent
from z3c.form.interfaces import DISPLAY_MODE
from zope.event import notify
from org.bccvl.site.content.dataset import (ISpeciesDataset,
                                            ILayerDataset)
from org.bccvl.site.namespace import BCCPROP, BCCVOCAB
from org.bccvl.site.browser.job import IJobStatus


class DatasetFieldMixin(object):

    # fields = Fields(IBasic, IDataset)

    @property
    def additionalSchemata(self):
        for schema in super(DatasetFieldMixin, self).additionalSchemata:
            yield schema
        md = IGraph(self.context)
        genre = md.value(md.identifier, BCCPROP['datagenre'])
        # TODO: do a better check for genre. e.g. query store for classes of genre?
        if genre in (BCCVOCAB['DataGenreSA'], BCCVOCAB['DataGenreSO']):
            yield ISpeciesDataset
        elif genre in (BCCVOCAB['DataGenreFC'], BCCVOCAB['DataGenreE']):
            yield ILayerDataset
        yield IJobStatus

    # def updateFields(self):
    #     md = IGraph(self.context)
    #     genre = md.value(md.identifier, BCCPROP['datagenre'])
    #     # TODO: do a better check for genre. e.g. query store for classes of genre?
    #     import ipdb; ipdb.set_trace()
    #     if genre in (BCCVOCAB['DataGenreFC'], BCCVOCAB['DataGenreSD'],
    #                  BCCVOCAB['DataGenreSO']):
    #         self.fields += Fields(ISpeciesDataset)
    #     else:
    #         self.fields += Fields(ILayerDataset)


class DatasetDisplayView(DatasetFieldMixin, DefaultView):

    # schema = None
    # additionalSchemata = ()

    # def updateFieldsFromSchemata(self):
    #     self.updateFields()

    def _update(self):
        # import ipdb; ipdb.set_trace()
        super(DatasetDisplayView, self)._update()


# FIXME: Turn this whole form into something re-usable
#        e.g. could be used within a widget that renders a button
#             and won't show up on add forms. (could easily be configure via Fresnel)
#             js turns the button into an ajax form and non-js uses redirects


class DatasetEditView(DatasetFieldMixin, DefaultEditForm):

    # kw: ignoreFields, ignoreButtons, ignoreHandlers
    form.extends(DefaultEditForm, ignoreFields=True)

    # TODO: do this only for zipped files
    @button.buttonAndHandler(u'Edit File Details', name='edit_file_metadata')
    def handleEditFileMetadata(self, action):
        # do whatever here and redirect to metadata edit view
        # TODO: use restrictedTraverse to check security as well? (would avoid login page)
        url = self.context.absolute_url() + '/@@editfilemetadata'
        self.request.response.redirect(url)


from plone.z3cform.crud import crud
from zope import schema
from zope.interface import Interface
import gu.z3cform.rdf.schema as rdfschema
from rdflib import RDF, Graph, Literal
from zope.component import getUtility
from gu.z3cform.rdf.interfaces import IORDF, IGraph
import zipfile
from org.bccvl.site.namespace import BIOCLIM, NFO


class IFileItemMetadata(Interface):

    name = rdfschema.RDFLiteralLineField(
        title=u"File name",
        prop = NFO['fileName'],
        description=u'The file name within the archive',
        readonly=True)

    bioclim = rdfschema.RDFURIChoiceField(
        title=u"Bioclimatic Variable",
        prop = BIOCLIM['bioclimVariable'],
        vocabulary='org.bccvl.site.BioclimVocabulary')


def getFileGraph(context):
    """
    create a new set of graphs to hold general file information for files within an archive
    """
    file = context.file.open('r')
    zip = zipfile.ZipFile(file)
    ret = {}
    ordf = getUtility(IORDF)
    for zipinfo in zip.infolist():
        if zipinfo.filename.endswith('/'):
            # skip directories
            continue
        info = Graph(identifier=ordf.generateURI())
        info.add((info.identifier, RDF['type'], NFO['ArchiveItem']))
        #info.add((info.identifier, RDF['type'], NFO['RasterImage']))
        #info.add((info.identifier, NFO['fileCreated'], NFO['ArchiveItem'])) # xsd:datetime
        info.add((info.identifier, NFO['fileName'], Literal(zipinfo.filename))) # XSD:string
        info.add((info.identifier, NFO['fileSize'], Literal(zipinfo.file_size))) # XSD:integer
        ret[hash(info.identifier)] = info
    return ret


class EditFileMetadataForm(crud.EditForm):
    # only works within crud as well as base form

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
            del data['select']
            self.context.before_update(subform.content, data)
            changes = subform.applyChanges(data)
            if changes:
                if status is no_changes:
                    status = success
                elif status is subform.formErrorsMessage:
                    status = partly_success

                # If there were changes, we'll update the view widgets
                # again, so that they'll actually display the changes
                for widget in  subform.widgets.values():
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
        handler = getUtility(IORDF).getHandler()
        handler.put(content)
        # TODO: update status if necessary
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
    # TODO: remember return address and maybe all form parameters (to return to previous form in same state if possible); makes this form work the same way with or without ajax

    # TODO generalise this
    property = BCCPROP['hasArchiveItem']

    update_schema = field.Fields(IFileItemMetadata).omit('name')
    view_schema = field.Fields(IFileItemMetadata).select('name')
    editform_factory = EditFileMetadataForm
    addform_factory = crud.NullForm

    _content = None
    _items =  None
    _referer = None

    def __init__(self, context, request):
        super(CrudFileMetadataForm, self).__init__(context, request)
        # TODO: need to store the referer as hiddon field on form or in session
        #       .... referer/ returnURL processing should happen in update
        #       .... __init__ is also called on submit and will set current url...
        #            so request param must win over http header
        # could also check 'PARENTS', 'PATH_INFO','PATH_TRANSLATED', ACTUAL_URL or URL
        # to get context + previous view name

    def redirect(self):
        # get current context and redirect to @@edit
        nexturl = self.context.absolute_url() +  '/edit'
        self.request.response.redirect(nexturl)

    def getContent(self):
        if not self._content:
            self._content = IGraph(self.context)
        return self._content

    def get_items(self):
        g = self.getContent()
        if not self._items:
            handler = getUtility(IORDF).getHandler()
            items = {}
            for ref in g.objects(g.identifier, self.property):
                item = handler.get(ref)
                items[hash(ref)] = item
            if not items: # was empty
                items = getFileGraph(self.context)
            self._items = items
        # TODO: sort key configurable
        return sorted(self._items.items(), key=lambda x: x[1].value(x[1].identifier, NFO['fileName']))

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
        vocabulary='org.bccvl.site.GCMVocabulary')

    emc = schema.Choice(
        title=u"Emmision Scenario",
        # value_type=URIRefField(),
        vocabulary='org.bccvl.site.EMSCVocabulary')






# DataSetView ... if mime type show file content? or just coverage
#                 if data gence climate layers?

# DataSetViewlet?  (would replace view)

# DataSetEdit?  (add button to edit zip file metadata if climate layer)
# ->  DataSet Climate Layer Edit:
#       for to edit  layers ... better to keep separate from standard edit,  as it needs the file available (or at least the file list)
