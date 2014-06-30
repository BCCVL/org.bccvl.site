from plone.directives import form
from plone.dexterity.content import Item
from zope.interface import implementer
from plone.app.contenttypes.interfaces import IFile
from gu.z3cform.rdf.schema import (RDFURIChoiceField,
                                   RDFLiteralLineField,
                                   RDFDateRangeField,
                                   RDFURIRefField)
from org.bccvl.site.namespace import BCCPROP, DWC, BCCVOCAB
from org.bccvl.site.content.interfaces import IDataset, IBlobDataset
from ordf.namespace import DC as DCTERMS
from org.bccvl.site import MessageFactory as _


@implementer(IBlobDataset, IFile)
class Dataset(Item):

    pass

    @property
    def format(self):
        if self.file is not None:
            return self.file.contentType
        # TODO: is this a good fallback?
        #       that one is used in RFC822 marshaller
        return self.conent_type()


class ISpeciesDataset(form.Schema):
    """
    a schema to drive the forms for species data sets
    """
    datagenre = RDFURIChoiceField(
        prop=BCCPROP['datagenre'],
        title=_(u'Data Genre'),
        vocabulary=u'org.bccvl.site.SpeciesDataGenreVocabulary'
    )

    specieslayer = RDFURIChoiceField(
        prop=BCCPROP['specieslayer'],
        required=False,
        title=u'Species Layer',
        vocabulary=u'org.bccvl.site.SpeciesLayerVocabulary'
    )

    scientificName = RDFLiteralLineField(
        prop=DWC['scientificName'],
        required=True,
        title=u'Scientific name',
        description=u'The full scientific name, with authorship and date information if known. When forming part of an Identification, this should be the name in lowest level taxonomic rank that can be determined. This term should not contain identification qualifications, which should instead be supplied in the IdentificationQualifier term.'
    )

    taxonID = RDFLiteralLineField(  # lsid
        prop=DWC['taxonID'],
        required=False,
        title=u'Taxon ID',
        description=u'''An identifier for the set of taxon information (data associated with the Taxon class). May be a global unique identifier or an identifier specific to the data set.

                Examples: "8fa58e08-08de-4ac1-b69c-1235340b7001", "32567", "http://species.gbif.org/abies_alba_1753", "urn:lsid:gbif.org:usages:32567"'''
    )

    vernacularName = RDFLiteralLineField(  # common Name,
        prop=DWC['vernacularName'],
        required=False,
        title=u'Common Name',
        description=u'A common or vernacular name.',
    )


class ILayerDataset(form.Schema):

    # moref fields;
    #-> projection, spatial units, spatial coverage,
    #-> pixel units, (value space)
    datagenre = RDFURIChoiceField(
        prop=BCCPROP['datagenre'],
        title=_(u'Data Genre'),
        vocabulary=u'org.bccvl.site.EnvironmentalDataGenreVocabulary'
    )

    datatype = RDFURIChoiceField(
        prop=BCCPROP['datatype'],
        required=False,
        title=u'Type of Dataset',
        vocabulary=u'org.bccvl.site.DatasetTypeVocabulary')

    resolution = RDFURIChoiceField(
        prop=BCCPROP['resolution'],
        title=u'Resolution',
        required=False,
        vocabulary=u'org.bccvl.site.ResolutionVocabulary')

    resolutiono = RDFLiteralLineField(
        prop=BCCPROP['resolutionother'],
        required=False,
        title=u'Resolution (other)')

    temporal = RDFDateRangeField(
        prop=DCTERMS['temporal'],
        required=False,
        title=u'Temporal coverage')

    emissionscenario = RDFURIChoiceField(
        prop=BCCPROP['emissionscenario'],
        required=False,
        title=u'Emission Scenario',
        vocabulary=u'org.bccvl.site.EMSCVocabulary')

    gcm = RDFURIChoiceField(
        prop=BCCPROP['gcm'],
        required=False,
        title=u'Global Climate Model',
        vocabulary=u'org.bccvl.site.GCMVocabulary')


class ITraitsDataset(form.Schema):

    form.omitted('datagenre')
    datagenre = RDFURIRefField(
        prop=BCCPROP['datagenre'],
        title=_(u'Data Genre'),
        default=BCCVOCAB['DataGenreTraits'],
        readonly=True,
        required=True,
    )
