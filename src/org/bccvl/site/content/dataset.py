from plone.autoform import directives
from plone.supermodel import model
from plone.dexterity.content import Item
from zope import schema
from zope.interface import implementer
from plone.app.contenttypes.interfaces import IFile
from org.bccvl.site.content.interfaces import IBlobDataset
from org.bccvl.site.content.interfaces import IDatasetCollection
from org.bccvl.site import MessageFactory as _


@implementer(IBlobDataset, IFile)
class Dataset(Item):

    @property
    def format(self):
        if self.file is not None:
            return self.file.contentType
        # TODO: is this a good fallback?
        #       that one is used in RFC822 marshaller
        return self.content_type()

    @format.setter
    def format(self, value):
        if self.file is not None:
            self.file.contentType = value
        # TODO: really do nothing otherwise?
        #       calling setFormat causes infinite recursion
        #else:
        #    self.setFormat(value)


@implementer(IDatasetCollection)
class DatasetCollection(Item):

    @property
    def format(self):
        if self.file is not None:
            return self.file.contentType
        # TODO: is this a good fallback?
        #       that one is used in RFC822 marshaller
        return self.content_type()

    @format.setter
    def format(self, value):
        if self.file is not None:
            self.file.contentType = value
        # TODO: really do nothing otherwise?
        #       calling setFormat causes infinite recursion
        #else:
        #    self.setFormat(value)


class ISpeciesDataset(model.Schema):
    """
    a schema to drive the forms for species data sets
    """
    genre = schema.Choice(
        title=_(u'Data Genre'),
        vocabulary=u'genre_source'
    )

    scientificName = schema.TextLine(
        required=True,
        title=u'Scientific name',
        description=u'The full scientific name, with authorship and date information if known. When forming part of an Identification, this should be the name in lowest level taxonomic rank that can be determined. This term should not contain identification qualifications, which should instead be supplied in the IdentificationQualifier term.'
    )

    taxonID = schema.TextLine(  # lsid
        required=False,
        title=u'Taxon ID',
        description=u'''An identifier for the set of taxon information (data associated with the Taxon class). May be a global unique identifier or an identifier specific to the data set.

                Examples: "8fa58e08-08de-4ac1-b69c-1235340b7001", "32567", "http://species.gbif.org/abies_alba_1753", "urn:lsid:gbif.org:usages:32567"'''
    )

    vernacularName = schema.TextLine(  # common Name,
        required=False,
        title=u'Common Name',
        description=u'A common or vernacular name.',
    )


class ISpeciesCollection(model.Schema):
    """
    a schema to drive the forms for species collections
    """
    genre = schema.Choice(
        title=_(u'Data Genre'),
        vocabulary=u'genre_source'
    )


class ILayerDataset(model.Schema):

    # more fields;
    #-> projection, spatial units, spatial coverage,
    #-> pixel units, (value space)
    genre = schema.Choice(
        title=_(u'Data Genre'),
        vocabulary=u'genre_source'
    )

    datatype = schema.Choice(
        required=False,
        title=u'Type of Dataset',
        vocabulary=u'datatype_source')

    resolution = schema.Choice(
        title=u'Resolution',
        required=False,
        vocabulary=u'resolution_source')

    resolutiono = schema.TextLine(
        required=False,
        title=u'Resolution (other)')

    emsc = schema.Choice(
        required=False,
        title=u'Emission Scenario',
        vocabulary=u'emsc_source')

    gcm = schema.Choice(
        required=False,
        title=u'Global Climate Model',
        vocabulary=u'gcm_source')


class ITraitsDataset(model.Schema):

    directives.mode(genre='hidden')
    genre = schema.Choice(
        title=_(u'Data Genre'),
        default='DataGenreTraits',
        vocabulary='genre_source',
        readonly=True,
        required=True,
    )
