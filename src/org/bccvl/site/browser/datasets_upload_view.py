from Acquisition import aq_inner
from Products.Five import BrowserView
from plone.dexterity.browser.add import DefaultAddForm
from Products.CMFCore.utils import getToolByName
from z3c.form.interfaces import IFormLayer
from plone.z3cform import z2
from z3c.form.form import AddForm

from plone.app.dexterity.behaviors.metadata import IBasic
from Products.CMFCore.interfaces import IDublinCore
from z3c.form.field import Fields
from org.bccvl.site.content.dataset import IDataset

from gu.z3cform.rdf.schema import (RDFURIChoiceField,
                                   RDFLiteralLineField,
                                   RDFDateRangeField)
from org.bccvl.site.namespace import BCCPROP, DWC
from ordf.namespace import DC as DCTERMS


# TODO: provenance field:
#             -> created by experiment, imorted from ALA, uploaded by user, provided by system

class SpeciesAddForm(DefaultAddForm):

    title = u"Species occurrence data"
    description = u"A set of occurrences for single species"

    fields = (
        Fields(IBasic) +
        Fields(IDataset) +
        Fields(
            # restrict this to???
            RDFURIChoiceField(
                __name__='datagenre',
                prop=BCCPROP['datagenre'],
                required=False,
                title=u'Data Genre',
                vocabulary=u'http://namespaces.zope.org/z3c/form#DataGenreVocabulary'),
            RDFURIChoiceField(
                __name__='specieslayer',
                prop=BCCPROP['specieslayer'],
                required=False,
                title=u'Species Layer',
                vocabulary=u'http://namespaces.zope.org/z3c/form#SpeciesLayerVocabulary'),
            RDFLiteralLineField(
                __name__ = 'scientificName',
                prop = DWC['scientificName'],
                required = True,
                title = u'Scientific name',
                description = u'The full scientific name, with authorship and date information if known. When forming part of an Identification, this should be the name in lowest level taxonomic rank that can be determined. This term should not contain identification qualifications, which should instead be supplied in the IdentificationQualifier term.'),
            RDFLiteralLineField(  # lsid
                __name__='taxonID',
                prop=DWC['taxonID'],
                required=False,
                title=u'Taxon ID',
                description=u'''An identifier for the set of taxon information (data associated with the Taxon class). May be a global unique identifier or an identifier specific to the data set.

                Examples: "8fa58e08-08de-4ac1-b69c-1235340b7001", "32567", "http://species.gbif.org/abies_alba_1753", "urn:lsid:gbif.org:usages:32567"'''
                ),
            RDFLiteralLineField(  # common Name,
                __name__='vernacularName',
                prop=DWC['vernacularName'],
                required=False,
                title=u'Common Name',
                description=u'A common or vernacular name.',
                ),





            # fixed fields
            # RDFURIChoiceField(
            #     __name__='format',
            #     prop=BCCPROP['format'],
            #     required=False,
            #     title=u'Format',
            #     vocabulary=u'http://namespaces.zope.org/z3c/form#DataSetFormatVocabulary'),


            # layer
            # RDFURIChoiceField(
            #     __name__='datatype',
            #     prop=BCCPROP['datatype'],
            #     required=False,
            #     title=u'Type of Dataset',
            #     vocabulary=u'http://namespaces.zope.org/z3c/form#DataSetTypeVocabulary'),

            # RDFURIChoiceField(
            #     __name__='resolution',
            #     prop=BCCPROP['resolution'],
            #     title=u'Resolution',
            #     required=False,
            #     vocabulary=u'http://namespaces.zope.org/z3c/form#ResolutionVocabulary'),
            # RDFLiteralLineField(
            #     __name__='resolutiono',
            #     prop=BCCPROP['resolutionother'],
            #     required=False,
            #     title=u'Resolution (other)'),
            # RDFDateRangeField(
            #     __name__='temporal',
            #     prop=DCTERMS['temporal'],
            #     required=False,
            #     title=u'Temporal coverage'),
            # RDFURIChoiceField(
            #     __name__='emissionscenario',
            #     prop=BCCPROP['emissionscenario'],
            #     required=False,
            #     title=u'Emission Scenario',
            #     vocabulary=u'http://namespaces.zope.org/z3c/form#EmissionScenarioVocabulary'),
            # RDFURIChoiceField(
            #     __name__='gcm',
            #     prop=BCCPROP['gcm'],
            #     required=False,
            #     title=u'Global Climate Model',
            #     vocabulary=u'http://namespaces.zope.org/z3c/form#GlobalClimateModelVocabulary'),

            # # not needed?
            # RDFLiteralLineField(
            #     __name__='formato',
            #     prop=DCTERMS['format'],
            #     required=False,
            #     title=u'Data format (other)'),
        )
    )

    def updateFields(self):
        pass


class RasterAddForm(DefaultAddForm):

    # moref fields;
    #-> projection, spatial units, spatial coverage,
    #-> pixel units, (value space)

    fields = Fields(
        Fields(IBasic) +
        Fields(IDataset) +
        Fields(
            # restrict this to???
            RDFURIChoiceField(
                __name__='datagenre',
                prop=BCCPROP['datagenre'],
                required=False,
                title=u'Data Genre',
                vocabulary=u'http://namespaces.zope.org/z3c/form#DataGenreVocabulary'),
            # fixed fields
            # RDFURIChoiceField(
            #     __name__='format',
            #     prop=BCCPROP['format'],
            #     required=False,
            #     title=u'Format',
            #     vocabulary=u'http://namespaces.zope.org/z3c/form#DataSetFormatVocabulary'),

            # layer
            RDFURIChoiceField(
                __name__='datatype',
                prop=BCCPROP['datatype'],
                required=False,
                title=u'Type of Dataset',
                vocabulary=u'http://namespaces.zope.org/z3c/form#DataSetTypeVocabulary'),
            RDFURIChoiceField(
                __name__='resolution',
                prop=BCCPROP['resolution'],
                title=u'Resolution',
                required=False,
                vocabulary=u'http://namespaces.zope.org/z3c/form#ResolutionVocabulary'),
            RDFLiteralLineField(
                __name__='resolutiono',
                prop=BCCPROP['resolutionother'],
                required=False,
                title=u'Resolution (other)'),
            RDFDateRangeField(
                __name__='temporal',
                prop=DCTERMS['temporal'],
                required=False,
                title=u'Temporal coverage'),
            RDFURIChoiceField(
                __name__='emissionscenario',
                prop=BCCPROP['emissionscenario'],
                required=False,
                title=u'Emission Scenario',
                vocabulary=u'http://namespaces.zope.org/z3c/form#EmissionScenarioVocabulary'),
            RDFURIChoiceField(
                __name__='gcm',
                prop=BCCPROP['gcm'],
                required=False,
                title=u'Global Climate Model',
                vocabulary=u'http://namespaces.zope.org/z3c/form#GlobalClimateModelVocabulary'),

            # # not needed?
            # RDFLiteralLineField(
            #     __name__='formato',
            #     prop=DCTERMS['format'],
            #     required=False,
            #     title=u'Data format (other)'),
        )
    )

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
