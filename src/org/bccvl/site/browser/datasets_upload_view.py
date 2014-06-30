from Acquisition import aq_inner
from Products.Five import BrowserView
from plone.dexterity.browser.add import DefaultAddForm
from Products.CMFCore.utils import getToolByName

from plone.app.dexterity.behaviors.metadata import IBasic
from z3c.form.field import Fields
from org.bccvl.site import defaults
from org.bccvl.site.content.dataset import (IBlobDataset,
                                            ISpeciesDataset,
                                            ILayerDataset,
                                            ITraitsDataset)
#from zope.pagetemplate.pagetemplatefile import PageTemplateFile
from Products.Five.browser.pagetemplatefile import ViewPageTemplateFile


# TODO: provenance field:
#       -> created by experiment, imorted from ALA, uploaded by user,
#          provided by system

class SpeciesAddForm(DefaultAddForm):

    title = u"Upload Species Data"
    description = (u"<p>Upload occurrences or abundance data for single species</p>"
                   u"<p>An occurrence dataset is expected to be in CSV format."
                   u" BCCVL will only try to interpret columns with labels 'lon' and 'lat'.</p>" )
    fields = Fields(IBasic, IBlobDataset, ISpeciesDataset).omit('thresholds')

    template = ViewPageTemplateFile('dataset_upload_subform.pt')

    def updateFields(self):
        # don't fetch plone default fields'
        pass

    def nextURL(self):
        # redirect to default datasets page
        portal = getToolByName(self.context, 'portal_url').getPortalObject()
        return portal[defaults.DATASETS_FOLDER_ID].absolute_url()


class RasterAddForm(DefaultAddForm):

    title = u"Upload Environmental Data"
    description = (u"<p>Upload current or future climate data</p>"
                   u"<p>BCCVL can only deal with raster data in GeoTIFF format."
                   u" Valid files are either single GeoTiff files or a number of"
                   u" GeoTiff packaged within a zip file."
                   u" Idealy the map projection information is embedded as metadata"
                   u" within the GeoTiff itself. In case of missing map projection"
                   u" BCCVL assumes WGS-84 (EPSG:4326)</p>")

    fields = Fields(IBasic, IBlobDataset, ILayerDataset).omit('thresholds')

    template = ViewPageTemplateFile('dataset_upload_subform.pt')

    def updateFields(self):
        # don't fetch plone default fields'
        pass

    def nextURL(self):
        # redirect to default datasets page
        portal = getToolByName(self.context, 'portal_url').getPortalObject()
        return portal[defaults.DATASETS_FOLDER_ID].absolute_url()


class SpeciesTraitsAddForm(DefaultAddForm):

    title = u"Upload Species Traits"
    description = u"<p>Upload CSV file to use for species traits modelling.</p>"

    fields = Fields(IBasic, IBlobDataset, ITraitsDataset).omit('thresholds', 'datagenre')

    template = ViewPageTemplateFile('dataset_upload_subform.pt')

    def updateFields(self):
        # don't fetch plone default fields'
        pass

    def nextURL(self):
        # redirect to default datasets page
        portal = getToolByName(self.context, 'portal_url').getPortalObject()
        return portal[defaults.DATASETS_FOLDER_ID].absolute_url()


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

        for form_prefix, form_class in (('addspecies', SpeciesAddForm),
                                        ('addlayer', RasterAddForm),
                                        ('addtraits', SpeciesTraitsAddForm)):
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
            self.subforms[idx] = subform.render()

    def __call__(self):
        self.update()
        # if one of our subforms initiated a redirect follow it
        if self.request.response.getStatus() in (302, 303):
            return
        return super(DatasetsUploadView, self).__call__()
