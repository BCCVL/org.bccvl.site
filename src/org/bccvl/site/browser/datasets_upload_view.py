from Acquisition import aq_inner
from Products.Five import BrowserView
from plone.dexterity.browser.add import DefaultAddForm
from Products.CMFCore.utils import getToolByName

from plone.app.dexterity.behaviors.metadata import IBasic
from z3c.form.field import Fields
from org.bccvl.site import defaults
from org.bccvl.site.content.dataset import (IDataset,
                                            ISpeciesDataset,
                                            ILayerDataset)
#from zope.pagetemplate.pagetemplatefile import PageTemplateFile
from Products.Five.browser.pagetemplatefile import ViewPageTemplateFile


# TODO: provenance field:
#             -> created by experiment, imorted from ALA, uploaded by user, provided by system

class SpeciesAddForm(DefaultAddForm):

    title = u"Upload Species Data"
    description = u"Upload ccurrences or abundance data for single species"

    fields = Fields(IBasic, IDataset, ISpeciesDataset)

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
    description = u"Upload current or future climate data"

    fields = Fields(IBasic, IDataset, ILayerDataset)

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

    addspeciesform = None
    addlayerform = None

    def update(self):
        ttool = getToolByName(self.context, 'portal_types')
        fti = ttool.getTypeInfo('org.bccvl.content.dataset')

        self.addspeciesform = SpeciesAddForm(aq_inner(self.context),
                                             self.request, fti)
        self.addspeciesform.__name__ = "addspeciesform"
        self.addspeciesform.prefix = "addspecies"

        self.addlayerform = RasterAddForm(aq_inner(self.context),
                                          self.request, fti)
        self.addlayerform.__name__ = "addlayerform"
        self.addlayerform.prefix = "addlayer"

        # always update both forms in case we return and want to preserve
        # entered values
        self.addspeciesform.update()
        self.addlayerform.update()

        # render the forms for display or generate redirect
        self.addspeciesform = self.addspeciesform.render()
        self.addlayerform = self.addlayerform.render()

    def __call__(self):
        self.update()
        # if one of our subforms initiated a redirect follow it
        if self.request.response.getStatus() in (302, 303):
            return
        return super(DatasetsUploadView, self).__call__()
