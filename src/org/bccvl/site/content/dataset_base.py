from org.bccvl.site.interfaces import IBCCVLMetadata
from org.bccvl.site.content.interfaces import IBlobDataset
from org.bccvl.site.content.interfaces import IRemoteDataset
from org.bccvl.site.content.dataset import ISpeciesDataset
from org.bccvl.site.content.dataset import ILayerDataset
from org.bccvl.site.content.dataset import ITraitsDataset


class DatasetMetadataAdapter(object):
    """
    Gives z3c.form datamanagers attribute access to the metadata object.

    This class takes care of properly updateing the underlying storage object.
    """
    # There is a datamanager problem.
    # The Datamanager is looked up for the context (which returns an AttributeField manager)
    # but then the Datamanager adapts the context to this adapter and tries attribute
    # access which fails.

    def __init__(self, context):
        self._data = IBCCVLMetadata(context)

    def __getattr__(self, name):
        ob = self._data
        try:
            if name in ('scientificName', 'taxonID', 'vernacularName'):
                return ob['species'][name]
            else:
                return ob[name]
        except:
            raise AttributeError('Attribute %s not found' % name)

    def __setattr__(self, name, value):
        if name == '_data':
            self.__dict__['_data'] = value
            # shortcut here to not store _data in metadata dictionary
            return
        if name in ('scientificName', 'taxonID', 'vernacularName'):
            # FIXME: need a new dict here?
            ob = self._data.setdefault('species', {})
        else:
            ob = self._data
        ob[name] = value

    def __delattr__(self, name):
        if name in ('scientificName', 'taxonID', 'vernacularName'):
            # FIXME: update dict?
            ob = self._data['species']
            del ob[name]
            if not ob:
                del self._data['species']
        else:
            del self._data[name]


# FIXME: this works nice for edit forms, but display forms should be completery custom
class DatasetFieldMixin(object):
    """
    A mixin class for display and edit views to add genre specific fields
    to the form schema.
    """

    # fields = Fields(IBasic, IDataset)
    genre_interface_map = {
        'DataGenreSpeciesAbsence': ISpeciesDataset,
        'DataGenreSpeciesAbundance': ISpeciesDataset,
        'DataGenreSpeciesOccurrence': ISpeciesDataset,
        'DataGenreCC': ILayerDataset,
        'DataGenreFC': ILayerDataset,
        'DataGenreE': ILayerDataset,
        'DataGenreTraits': ITraitsDataset
    }

    def getGenreSchemata(self):
        schemata = []
        md = IBCCVLMetadata(self.context)
        genre = md.get('genre')
        if genre in self.genre_interface_map:
            schemata.append(self.genre_interface_map[genre])
        if IBlobDataset.providedBy(self.context):
            schemata.append(IBlobDataset)
        if IRemoteDataset.providedBy(self.context):
            schemata.append(IRemoteDataset)
        return schemata
