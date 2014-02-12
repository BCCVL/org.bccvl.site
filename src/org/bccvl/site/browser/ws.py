from zope.interface import Interface, implementer
from xmlrpclib import ServerProxy
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

    see: http://bie.ala.org.au/bie-service/
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


@implementer(IDataMover)
class DataMover(object):
    # TODO: depending on url discovery it wolud be possible
    #       to register this as utility factory and keep a
    #       serverproxy instance for the lifetime of this utility
    # TODO: call to xmlrpc server might also throw socket
    #       errors. (e.g. socket.error: [Errno 61] Connection refused)

    url = u'http://127.0.0.1:10700/data_mover'

    def __init__(self):
        # TODO: get data_mover location from config file
        #       or some other discovery mechanism
        pass

    def move(self, source, dest):
        proxy = ServerProxy(self.url)
        ret = proxy.move(source, dest)
        return ret

    def check_move_status(self, job_id):
        proxy = ServerProxy(self.url)
        ret = proxy.check_move_status(job_id)
        return ret


@implementer(IALAService)
class ALAService(object):

    baseurl = u'http://bie.ala.org.au/ws/'

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
        return urlopen(self.baseurl + 'search.json?' + urlencode(qs))
