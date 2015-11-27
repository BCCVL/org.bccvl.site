import logging

from Acquisition import aq_inner
from Products.CMFCore.utils import getToolByName
from Products.Five import BrowserView
from Products.Five.browser.pagetemplatefile import ViewPageTemplateFile
from Products.statusmessages.interfaces import IStatusMessage

from plone import api
from plone.app.dexterity.behaviors.metadata import IDublinCore
from plone.dexterity.browser.add import DefaultAddForm
from plone.dexterity.utils import addContentToContainer
from z3c.form import button
from z3c.form.field import Fields
from zope.schema import Bool

from org.bccvl.site import defaults
from org.bccvl.site.interfaces import IBCCVLMetadata
from org.bccvl.site.content.dataset import (IBlobDataset,
                                            ISpeciesDataset,
                                            ILayerDataset,
                                            ITraitsDataset)
from org.bccvl.tasks.celery import app
from org.bccvl.site.job.interfaces import IJobTracker
from org.bccvl.tasks.plone import after_commit_task


LOG = logging.getLogger(__name__)


# TODO: provenance field:
#       -> created by experiment, imorted from ALA, uploaded by user,
#          provided by system

class BCCVLUploadForm(DefaultAddForm):

    # #form.extends(DefaultAddForm, ignoreButtons=True)
    # buttons = button.Buttons(DefaultAddForm.buttons['cancel'])

    css_class = 'form-horizontal'

    template = ViewPageTemplateFile('dataset_upload_subform.pt')

    datagenre = None

    def add(self, object):
        # FIXME: this is a workaround, which is fine for small uploaded files.
        #        large uploads should go through another process anyway
        # TODO: re implementing this method is the only way to know
        #       the full path of the object. We need the path to apply
        #       the transmogrifier chain.
        #fti = getUtility(IDexterityFTI, name=self.portal_type)
        container = aq_inner(self.context)
        try:
            # traverse to subfolder if possible
            container = container.restrictedTraverse('/'.join(self.subpath))
        except Exception as e:
            LOG.warn('Could not traverse to %s/%s', '/'.join(container.getPhysicalPath()), '/'.join(self.subpath))
        new_object = addContentToContainer(container, object)
        # set data genre:
        if self.datagenre:
            IBCCVLMetadata(new_object)['genre'] = self.datagenre
        if self.categories:
            IBCCVLMetadata(new_object)['categories'] = self.categories
            # rdf commit should happens in transmogrifier step later on
        # if fti.immediate_view:
        #     self.immediate_view = "%s/%s/%s" % (container.absolute_url(), new_object.id, fti.immediate_view,)
        # else:
        #     self.immediate_view = "%s/%s" % (container.absolute_url(), new_object.id)
        # TODO: upload to swift somehow?
        # start background import process (just a metadata update)

        # run transmogrify md extraction here
        context_path = '/'.join(new_object.getPhysicalPath())
        member = api.user.get_current()
        # FIXME works only for local files
        update_task = app.signature(
            "org.bccvl.tasks.datamover.update_metadata",
            args=('{}/@@download/file/{}'.format(new_object.absolute_url(), new_object.file.filename),
                  new_object.file.filename,
                  new_object.file.contentType,
                  {'context': context_path,
                   'user': {
                       'id': member.getUserName(),
                       'email': member.getProperty('email'),
                       'fullname': member.getProperty('fullname')
                   }}),
            options={'immutable': True});
        # queue job submission
        after_commit_task(update_task)
        # create job tracking object
        jt = IJobTracker(new_object)
        job = jt.new_job('TODO: generate id', 'generate taskname: update_metadata')
        job.type = new_object.portal_type
        jt.set_progress('PENDING', u'Metadata update pending')
        # We have to reindex after updating the object
        new_object.reindexObject()

    def nextURL(self):
        # redirect to default datasets page
        portal = getToolByName(self.context, 'portal_url').getPortalObject()
        return portal[defaults.DATASETS_FOLDER_ID].absolute_url()

    def updateWidgets(self):
        super(BCCVLUploadForm, self).updateWidgets()
        self.widgets['description'].rows = 6
        #self.widgets['rights'].rows = 6

    def updateActions(self):
        super(BCCVLUploadForm, self).updateActions()
        self.actions['save'].disabled = "disabled"

    def updateFields(self):
        # don't fetch plone default fields'
        self.fields += Fields(
            Bool(
                __name__ = 'legalcheckbox',
                title = u'I agree to the <a href="http://www.bccvl.org.au/bccvl/legals/" target="_blank">Terms and Conditions</a>',
                required=True,
                default=False
            )
        )
            # ITermsAndConditions, ignoreContext=True)

    @button.buttonAndHandler(u'Save', name='save')
    def handleAdd(self, action):
        data, errors = self.extractData()
        if errors:
            self.status = self.formErrorsMessage
            return
        # FIXME: here is a good place to validate TermsAndConditions
        # FIXME: legalcheckbox should probably not be in self.fields, but rather a manually created and validated checkbox in the form template
        del data['legalcheckbox']
        obj = self.createAndAdd(data)
        if obj is not None:
            # mark only as finished if we get the new object
            self._finishedAdd = True
            IStatusMessage(self.request).addStatusMessage(
                u"Item created", "info success"
            )

    @button.buttonAndHandler(u'Cancel', name='cancel')
    def handleCancel(self, action):
        # We call a ButtonHandler not a method on super, so we have to pass in self as well
        super(BCCVLUploadForm, self).handleCancel(self, action)  # self, form, action


class SpeciesAbsenceAddForm(BCCVLUploadForm):

    title = u"Upload Species Absence Data"
    description = (
        u"<p>Upload absence data for single species</p>"
        u"<p>An absence dataset is expected to be in CSV format."
        u" BCCVL will only try to interpret columns with labels"
        u" 'lon' and 'lat'.</p>")
    fields = Fields(IBlobDataset, IDublinCore, ISpeciesDataset).select(
        'file', 'title', 'description', 'scientificName', 'taxonID',
        'vernacularName', 'rights')
    datagenre = 'DataGenreSpeciesAbsence'
    categories = ['absence']
    subpath = [defaults.DATASETS_SPECIES_FOLDER_ID, 'user']


class SpeciesAbundanceAddForm(BCCVLUploadForm):

    title = u"Upload Species Abundance Data"
    description = (
        u"<p>Upload abundance data for single species</p>"
        u"<p>An abundance dataset is expected to be in CSV format."
        u" BCCVL will only try to interpret columns with labels"
        u" 'lon' and 'lat'.</p>")
    fields = Fields(IBlobDataset, IDublinCore, ISpeciesDataset).select(
        'file', 'title', 'description', 'scientificName', 'taxonID',
        'vernacularName', 'rights')
    datagenre = 'DataGenreSpeciesAbundance'
    categories = ['abundance']


class SpeciesOccurrenceAddForm(BCCVLUploadForm):

    title = u"Upload Species Occurrence Data"
    description = (
        u"<p>Upload occurrences data for single species</p>"
        u"<p>An occurrence dataset is expected to be in CSV format."
        u" BCCVL will only try to interpret columns with labels"
        u" 'lon' and 'lat'.</p>")
    fields = Fields(IBlobDataset, IDublinCore, ISpeciesDataset).select(
        'file', 'title', 'description', 'scientificName', 'taxonID',
        'vernacularName', 'rights')
    datagenre = 'DataGenreSpeciesOccurrence'
    categories = ['occurrence']
    subpath = [defaults.DATASETS_SPECIES_FOLDER_ID, 'user']

class ClimateCurrentAddForm(BCCVLUploadForm):

    title = u"Upload Current Climate Data"
    description = (
        u"<p>Upload current climate data</p>"
        u"<p>BCCVL can only deal with raster data in GeoTIFF format."
        u" Valid files are either single GeoTiff files or a number of"
        u" GeoTiff packaged within a zip file."
        u" Idealy the map projection information is embedded as metadata"
        u" within the GeoTiff itself. In case of missing map projection"
        u" BCCVL assumes WGS-84 (EPSG:4326)</p>")

    fields = Fields(IBlobDataset, IDublinCore, ILayerDataset).select(
        'file', 'title', 'description', 'resolution', 'resolutiono',
        'rights')
    datagenre = 'DataGenreCC'
    categories = ['current']
    # datatype, gcm, emissionscenario
    subpath = [defaults.DATASETS_CLIMATE_FOLDER_ID, 'user']


class EnvironmentalAddForm(BCCVLUploadForm):

    title = u"Upload Environmental Data"
    description = (
        u"<p>Upload environmental data</p>"
        u"<p>BCCVL can only deal with raster data in GeoTIFF format."
        u" Valid files are either single GeoTiff files or a number of"
        u" GeoTiff packaged within a zip file."
        u" Idealy the map projection information is embedded as metadata"
        u" within the GeoTiff itself. In case of missing map projection"
        u" BCCVL assumes WGS-84 (EPSG:4326)</p>")

    fields = Fields(IBlobDataset, IDublinCore, ILayerDataset).select(
        'file', 'title', 'description', 'resolution', 'resolutiono',
        'rights')
    datagenre = 'DataGenreE'
    categories = ['environmental']
    # datatype, gcm, emissionscenario
    subpath = [defaults.DATASETS_ENVIRONMENTAL_FOLDER_ID, 'user']

class ClimateFutureAddForm(BCCVLUploadForm):

    title = u"Upload Future Climate Data"
    description = (
        u"<p>Upload future climate data</p>"
        u"<p>BCCVL can only deal with raster data in GeoTIFF format."
        u" Valid files are either single GeoTiff files or a number of"
        u" GeoTiff packaged within a zip file."
        u" Idealy the map projection information is embedded as metadata"
        u" within the GeoTiff itself. In case of missing map projection"
        u" BCCVL assumes WGS-84 (EPSG:4326)</p>")

    fields = Fields(IBlobDataset, IDublinCore, ILayerDataset).select(
        'file', 'title', 'description', 'emsc', 'gcm',
        'resolution', 'resolutiono', 'rights')
    datagenre = 'DataGenreFC'
    categories = ['future']
    # datatype, gcm, emissionscenario
    subpath = [defaults.DATASETS_CLIMATE_FOLDER_ID, 'user']


class SpeciesTraitAddForm(BCCVLUploadForm):
    # TODO: these wolud be schema forms... sholud try it

    title = u"Upload Species Traits"
    description = \
        u"<p>Upload CSV file to use for species traits modelling.</p>"

    fields = Fields(IBlobDataset, IDublinCore, ITraitsDataset).select(
        'file', 'title', 'description', 'rights')
    datagenre = 'DataGenreTraits'
    categories = ['traits']
    subpath = [defaults.DATASETS_SPECIES_FOLDER_ID, 'user']


class DatasetsUploadView(BrowserView):
    """
    upload datasets view
    """
    # forms:
    #-> environmental, future climate,
    #-> future projection, output log file
    #-> species distribution, species distribution model evaluation,
    #-> species occurence
    # common accross all forms:
    #-> title, description, file, format,

    #-> use defaultform, extend updateFields to select only wanted fileds?
    #-> use standard form, create fields manually

    subforms = None

    def update(self):
        self.subforms = []
        ttool = getToolByName(self.context, 'portal_types')
        fti = ttool.getTypeInfo('org.bccvl.content.dataset')

        for form_prefix, form_class in (('speciesabsence', SpeciesAbsenceAddForm),
                                        ('speciesabundance', SpeciesAbundanceAddForm),
                                        ('speciesoccurrence', SpeciesOccurrenceAddForm),
                                        ('climatecurrent', ClimateCurrentAddForm),
                                        ('environmental', EnvironmentalAddForm),
                                        ('climatefuture', ClimateFutureAddForm),
                                        ('speciestrait', SpeciesTraitAddForm)):
            form = form_class(aq_inner(self.context),
                              self.request, fti)
            form.__name__ = "{0}form".format(form_prefix)
            form.prefix = form_prefix
            self.subforms.append(form)
            # always update all forms in case we return and want to preserve
            # entered values
            form.update()

        # render the forms for display or generate redirect
        for idx, subform in enumerate(self.subforms):
            self.subforms[idx] = {'content': subform.render(),
                                  'title': subform.title}

    def __call__(self):
        self.update()
        # if one of our subforms initiated a redirect follow it
        if self.request.response.getStatus() in (302, 303):
            return
        return super(DatasetsUploadView, self).__call__()
