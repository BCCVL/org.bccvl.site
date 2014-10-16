from z3c.form import form, button
from plone.dexterity.browser.edit import DefaultEditForm
from org.bccvl.site.content.dataset_base import DatasetFieldMixin


class DatasetEditView(DatasetFieldMixin, DefaultEditForm):

    # kw: ignoreFields, ignoreButtons, ignoreHandlers
    form.extends(DefaultEditForm, ignoreFields=True)

    @property
    def additionalSchemata(self):
        for schema in super(DatasetFieldMixin, self).additionalSchemata:
            yield schema
        for schema in self.getGenreSchemata():
            yield schema

    # TODO: do this only for zipped files
    @button.buttonAndHandler(u'Edit File Details', name='edit_file_metadata')
    def handleEditFileMetadata(self, action):
        # do whatever here and redirect to metadata edit view
        # TODO: use restrictedTraverse to check security as well?
        #       (would avoid login page)
        url = self.context.absolute_url() + '/@@editfilemetadata'
        self.request.response.redirect(url)

    # TODO: when the file get's replaced the metadata about zip
    #       content may become invalid'
