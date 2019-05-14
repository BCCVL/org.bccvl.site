from zope.interface import Interface, implementer
from urllib import urlencode, urlopen


class IDataMover(Interface):
    """
    A component that is able to talk to data mover
    """

    def move(source, dest):
        """
        initiate datatransfer from source to dest
        """

    def check_move_status(job_id):
        """
        check status of move job
        """


class IALAService(Interface):
    """
    A component to talk to ALA's web services

    see: https://bie-ws.ala.org.au/bie-service/
    """

    def autojson(q, geoOnly=None, idxType=None, limit=None, callback=None):
        """
        ALA's autocomplete service
        """

    def searchjson(q, fq=None, start=None, pageSize=None, sort=None, dir=None,
                   callback=None):
        """
        ALA's search service
        """


class IGBIFService(Interface):
    """
    A component to talk to GBIF's web services

    see: http://www.gbif.org/developer/summary
    """

    def autojson(q, datasetKey=None, rank=None, callback=None):
        """
        GBIFs autocomplete service
        """

    def searchjson(name, datasetKey=None, start=None, pageSize=None,
                   callback=None):
        """
        GBIFs's search service
        """

    def speciesjson(genusKey, datasetKey=None, start=None, pageSize=None,
                    callback=None):
        """
        GBIFs's species search service for a specified genus
        """


@implementer(IALAService)
class ALAService(object):

    baseurl = u'https://bie-ws.ala.org.au/ws/'

    def __init__(self):
        pass

    def autojson(self, q, geoOnly=None, idxType=None, limit=None,
                 callback=None):
        qs = [p for p in
              (('q', q),
               ('geoOnly', geoOnly),
               ('idxType', idxType),
               ('limit', limit),
               ('callback', callback)) if p[1]]
        # TODO: maybe do some error catching here?
        return urlopen(self.baseurl + 'search/auto.json?' + urlencode(qs))

    def searchjson(self, q, fq=None, start=None, pageSize=None,
                   sort=None, dir=None, callback=None):
        qs = [p for p in
              (('q', q),
               ('fq', fq),
               ('start', start),
               ('pageSize', pageSize),
               ('sort', sort),
               ('dir', dir),
               ('callback', callback)) if p[1]]
        # TODO: maybe do some error catching here?
        return urlopen(self.baseurl + 'search.json?' + urlencode(qs, True))


@implementer(IGBIFService)
class GBIFService(object):

    baseurl = u'http://api.gbif.org/v1/'

    def __init__(self):
        pass

    def autojson(self, q, datasetKey=None, rank=None, callback=None):
        qs = [p for p in
              (('q', q),
               ('datasetKey', datasetKey),
               ('rank', rank),
               ('callback', callback)) if p[1]]
        # TODO: maybe do some error catching here?
        return urlopen(self.baseurl + 'species/suggest?' + urlencode(qs))

    def searchjson(self, name, datasetKey=None, start=None, pageSize=None,
                   callback=None):
        qs = [p for p in
              (('name', name),
               ('datasetKey', datasetKey),
               ('offset', start),
               ('limit', pageSize),
               ('callback', callback)) if p[1]]
        # TODO: maybe do some error catching here?
        return urlopen(self.baseurl + 'species?' + urlencode(qs, True))

    def speciesjson(self, genusKey, datasetKey=None, start=None, pageSize=None,
                    callback=None):
        qs = [p for p in
              (('datasetKey', datasetKey),
               ('offset', start),
               ('limit', pageSize),
               ('callback', callback)) if p[1]]
        # TODO: maybe do some error catching here?
        return urlopen(self.baseurl + 'species/' + genusKey + '/children?' +
                       urlencode(qs, True))
