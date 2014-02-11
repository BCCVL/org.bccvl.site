from Acquisition import aq_inner
from Products.Five import BrowserView
from plone.dexterity.browser.add import DefaultAddForm
from Products.CMFCore.utils import getToolByName

from plone.app.dexterity.behaviors.metadata import IBasic
from z3c.form.field import Fields
from org.bccvl.site.content.dataset import (IDataset,
                                            ISpeciesDataset,
                                            ILayerDataset)


# TODO: provenance field:
#             -> created by experiment, imorted from ALA, uploaded by user, provided by system

class SpeciesAddForm(DefaultAddForm):

    title = u"Species occurrence data"
    description = u"A set of occurrences for single species"

    fields = Fields(IBasic, IDataset, ISpeciesDataset)

    def updateFields(self):
        pass


class RasterAddForm(DefaultAddForm):

    fields = Fields(IBasic, IDataset, ILayerDataset)

    def updateFields(self):
        pass


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
        # set portal_type only if there is none set already
        #-> AddForm accepts third parameter ti to do this for me
        # self.addspeciesform.portal_type = fti.getId()

        self.addlayerform = RasterAddForm(aq_inner(self.context),
                                          self.request, fti)
        self.addlayerform.__name__ = "addlayerform"
        self.addlayerform.prefix = "addlayer"
        # self.addlayerform.portal_type = fti.getId()

        # z2.switch_on(self, request_layer=IFormLayer)
        # self.form_instance.update()

        self.addspeciesform.update()
        self.addlayerform.update()

        # if self.request.response.getStatus() in (302, 303):
        #      self.contents = ""
        #      return

        #  # A z3c.form.form.AddForm does a redirect in its render method.
        #  # So we have to render the form to see if we have a redirection.
        #  # In the case of redirection, we don't render the layout at all.
        #  self.contents = self.form_instance.render()
        # self.addspeciesform = self.addspeciesform.render()
        # self.addlayerform = self.addlayerform.render()

    def __call__(self):
        self.update()
        return super(DatasetsUploadView, self).__call__()


# add view lookup:
#-> queryMultiAdapter((self.context, self.request, ti),  name=ti.factory)
#-> queryMultiAdapter((self.context, self.request, ti))
#->
