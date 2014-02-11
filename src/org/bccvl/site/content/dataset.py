from plone.directives import form
from plone.namedfile.field import NamedBlobFile
from plone.dexterity.content import Item
from zope.interface import implementer
from org.bccvl.site import MessageFactory as _
from plone.app.contenttypes.interfaces import IFile
from gu.z3cform.rdf.schema import (RDFURIChoiceField,
                                   RDFLiteralLineField,
                                   RDFDateRangeField)
from org.bccvl.site.namespace import BCCPROP, DWC
from ordf.namespace import DC as DCTERMS


class IDataset(form.Schema):

    # TODO: a primary field should not be required. possible bug in plone core
    form.primary('file')
    file = NamedBlobFile(
        title=_(u"File"),
        description=_(u"Data content"),
        required=True)

    datagenre = RDFURIChoiceField(
        prop=BCCPROP['datagenre'],
        title=_(u'Data Genre'),
        vocabulary=u'http://namespaces.zope.org/z3c/form#DataGenreVocabulary')

        # fixed fields
        # RDFURIChoiceField(
        #     __name__='format',
        #     prop=BCCPROP['format'],
        #     required=False,
        #     title=u'Format',
        #     vocabulary=u'http://namespaces.zope.org/z3c/form#DataSetFormatVocabulary')


        # layer
        # RDFURIChoiceField(
        #     __name__='datatype',
        #     prop=BCCPROP['datatype'],
        #     required=False,
        #     title=u'Type of Dataset',
        #     vocabulary=u'http://namespaces.zope.org/z3c/form#DataSetTypeVocabulary'),
        # # not needed?
        # RDFLiteralLineField(
        #     __name__='formato',
        #     prop=DCTERMS['format'],
        #     required=False,
        #     title=u'Data format (other)'),


@implementer(IDataset, IFile)
class Dataset(Item):

    pass


class ISpeciesDataset(form.Schema):
    """
    a schema to drive the forms for species data sets
    """
    specieslayer = RDFURIChoiceField(
        prop=BCCPROP['specieslayer'],
        required=False,
        title=u'Species Layer',
        vocabulary=u'http://namespaces.zope.org/z3c/form#SpeciesLayerVocabulary'
    )

    scientificName = RDFLiteralLineField(
        prop = DWC['scientificName'],
        required = True,
        title = u'Scientific name',
        description = u'The full scientific name, with authorship and date information if known. When forming part of an Identification, this should be the name in lowest level taxonomic rank that can be determined. This term should not contain identification qualifications, which should instead be supplied in the IdentificationQualifier term.'
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

    datatype = RDFURIChoiceField(
        prop=BCCPROP['datatype'],
        required=False,
        title=u'Type of Dataset',
        vocabulary=u'http://namespaces.zope.org/z3c/form#DataSetTypeVocabulary')

    resolution = RDFURIChoiceField(
        prop=BCCPROP['resolution'],
        title=u'Resolution',
        required=False,
        vocabulary=u'http://namespaces.zope.org/z3c/form#ResolutionVocabulary')

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
        vocabulary=u'http://namespaces.zope.org/z3c/form#EmissionScenarioVocabulary')

    gcm = RDFURIChoiceField(
        prop=BCCPROP['gcm'],
        required=False,
        title=u'Global Climate Model',
        vocabulary=u'http://namespaces.zope.org/z3c/form#GlobalClimateModelVocabulary')
