from Acquisition import aq_inner
import logging
from Products.Five import BrowserView
from plone.dexterity.browser.add import DefaultAddForm
from Products.CMFCore.utils import getToolByName
from collective.transmogrifier.transmogrifier import Transmogrifier
from plone.dexterity.utils import addContentToContainer
from plone.app.dexterity.behaviors.metadata import IDublinCore
from z3c.form.field import Fields
from org.bccvl.site import defaults
from org.bccvl.site.interfaces import IBCCVLMetadata
from org.bccvl.site.content.dataset import (IBlobDataset,
                                            ISpeciesDataset,
                                            ILayerDataset,
                                            ITraitsDataset)
from Products.Five.browser.pagetemplatefile import ViewPageTemplateFile
from zope.schema import Bool
from z3c.form import button
from Products.statusmessages.interfaces import IStatusMessage


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
        new_object = addContentToContainer(container, object)
        # set data genre:
        if self.datagenre:
            IBCCVLMetadata(new_object)['genre'] = self.datagenre
            # rdf commit should happens in transmogrifier step later on
        # if fti.immediate_view:
        #     self.immediate_view = "%s/%s/%s" % (container.absolute_url(), new_object.id, fti.immediate_view,)
        # else:
        #     self.immediate_view = "%s/%s" % (container.absolute_url(), new_object.id)
        # run transmogrify md extraction here
        # TODO: move this to an event listener?

        tm = Transmogrifier(new_object)
        tm('org.bccvl.site.add_file_metadata')

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
        'vernacularName', 'rightsstatement')
    datagenre = 'DataGenreSpeciesAbsence'


class SpeciesAbundanceAddForm(BCCVLUploadForm):

    title = u"Upload Species Abundance Data"
    description = (
        u"<p>Upload abundance data for single species</p>"
        u"<p>An abundance dataset is expected to be in CSV format."
        u" BCCVL will only try to interpret columns with labels"
        u" 'lon' and 'lat'.</p>")
    fields = Fields(IBlobDataset, IDublinCore, ISpeciesDataset).select(
        'file', 'title', 'description', 'scientificName', 'taxonID',
        'vernacularName', 'rightsstatement')
    datagenre = 'DataGenreSpeciesAbundance'


class SpeciesOccurrenceAddForm(BCCVLUploadForm):

    title = u"Upload Species Occurrence Data"
    description = (
        u"<p>Upload occurrences data for single species</p>"
        u"<p>An occurrence dataset is expected to be in CSV format."
        u" BCCVL will only try to interpret columns with labels"
        u" 'lon' and 'lat'.</p>")
    fields = Fields(IBlobDataset, IDublinCore, ISpeciesDataset).select(
        'file', 'title', 'description', 'scientificName', 'taxonID',
        'vernacularName', 'rightsstatement')
    datagenre = 'DataGenreSpeciesOccurrence'


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
        'temporal', 'rightsstatement')
    datagenre = 'DataGenreCC'
    # datatype, gcm, emissionscenario


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
        'temporal', 'rightsstatement')
    datagenre = 'DataGenreE'
    # datatype, gcm, emissionscenario


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
        'resolution', 'resolutiono', 'temporal', 'rightsstatement')
    datagenre = 'DataGenreFC'
    # datatype, gcm, emissionscenario


class SpeciesTraitAddForm(BCCVLUploadForm):
    # TODO: these wolud be schema forms... sholud try it

    title = u"Upload Species Traits"
    description = \
        u"<p>Upload CSV file to use for species traits modelling.</p>"

    fields = Fields(IBlobDataset, IDublinCore, ITraitsDataset).select(
        'file', 'title', 'description', 'rightsstatement')
    datagenre = 'DataGenreTraits'


# FIXME: this view needs to exist for default browser layer as well
#        otherwise diazo.off won't find the page if set up.
#        -> how would unthemed markup look like?
#        -> theme would only have updated template.
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
