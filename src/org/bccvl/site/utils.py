from decimal import Decimal
import logging
import os
import pwd
import socket
import tempfile

from plone import api
from plone.registry.interfaces import IRegistry
from plone.uuid.interfaces import IUUID
from zope.component import getUtility

from org.bccvl.site.interfaces import IBCCVLMetadata
from org.bccvl.site.swift.interfaces import ISwiftSettings
from org.bccvl.tasks import datamover


LOG = logging.getLogger(__name__)


def decimal_encoder(o):
    """ converts Decimal to something the json module can serialize.
    Usually with python 2.7 float rounding this creates nice representations
    of numbers, but there might be cases where rounding may cause problems.
    E.g. if precision required is higher than default float rounding.
    """
    if isinstance(o, Decimal):
        return float(o)
    raise TypeError(repr(o) + " is not JSON serializable")


# FIXME: no longer needed?
def get_public_ip():
    # check if the environment variable EXT_IP has some useful value
    ip = os.environ.get('EXT_IP', None)
    if ip:
        return ip
    # otherwise we connect to some host, and check which local ip the socket
    # uses
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('google.com', 80))
        # TODO: could do name lookup with socket.gethostbyaddr('ip')[0]
        #       or socket.getnameinfo(s.getsockname())[0]
        #       namelookup may throw another exception?
        return s.getsockname()[0]
    except Exception as e:
        LOG.warn("couldn't connect to google.com: %s", repr(e))
    # we still have no clue, let's try it via hostname
    try:
        return socket.gethostbyname(socket.gethostname())
    except Exception as e:
        LOG.warn("couldn't resolve '%s': %s", socket.gethostname(), repr(e))
    # last chance
    return socket.getfqdn()


def get_hostname(request):
    """ Extract hostname in virtual-host-safe manner

    @param request: HTTPRequest object, assumed contains environ dictionary

    @return: Host DNS name, as requested by client. Lowercased, no port part.
             Return None if host name is not present in HTTP request headers
             (e.g. unit testing).
    """

    if "HTTP_X_FORWARDED_HOST" in request.environ:
        # Virtual host
        host = request.environ["HTTP_X_FORWARDED_HOST"]
    elif "HTTP_HOST" in request.environ:
        # Direct client request
        host = request.environ["HTTP_HOST"]
    else:
        return None

    # separate to domain name and port sections
    host = host.split(":")[0].lower()

    return host


def get_username():
    return pwd.getpwuid(os.getuid()).pw_name


def get_results_dir(result, request):
    swiftsettings = getUtility(IRegistry).forInterface(ISwiftSettings)
    if swiftsettings.storage_url:
        results_dir = 'swift+{storage_url}/{container}/{path}/'.format(
            storage_url=swiftsettings.storage_url,
            container=swiftsettings.result_container,
            path=IUUID(result)
        )
    else:
        # if swift is not setup we use local storage
        results_dir = 'scp://{uid}@{ip}:{port}{path}/'.format(
            uid=pwd.getpwuid(os.getuid()).pw_name,
            # FIXME: hostname from request is not good enough...
            #        need to get ip or host from plone_worker that does actual
            #        import
            #        store in registry?
            #        (is ok for testing)
            # ip=get_public_ip(),
            ip=get_hostname(request),
            port=os.environ.get('SSH_PORT', 22),
            path=tempfile.mkdtemp(prefix='result_import_')
        )
    return results_dir


def build_ala_import_task(lsid, dataset, request):
    # creates task chain to import ala dataset
    """
    lsid .. species id
    context ... a dictionary with keys:
      - context: path to context object
      - userid: zope userid
    """
    # we need site-path, context-path and lsid for this job
    dataset_path = '/'.join(dataset.getPhysicalPath())
    member = api.user.get_current()
    context = {
        'context': dataset_path,
        'user': {
            'id': member.getUserName(),
            'email': member.getProperty('email'),
            'fullname': member.getProperty('fullname')
        }
    }

    results_dir = get_results_dir(dataset, request)
    if dataset.dataSource == 'gbif':
        return datamover.pull_occurrences_from_gbif.si(lsid,
                                                       results_dir, context)
    elif dataset.dataSource == 'aekos':
        return datamover.pull_occurrences_from_aekos.si(lsid,
                                                        results_dir, context)
    else:
        return datamover.pull_occurrences_from_ala.si(lsid,
                                                      results_dir, context)


def build_traits_import_task(dataset, request):
    # creates task chain to import ala dataset
    """
    context ... a dictionary with keys:
      - context: path to context object
      - userid: zope userid
    """
    # we need site-path, context-path and lsid for this job
    dataset_path = '/'.join(dataset.getPhysicalPath())
    member = api.user.get_current()
    context = {
        'context': dataset_path,
        'user': {
            'id': member.getUserName(),
            'email': member.getProperty('email'),
            'fullname': member.getProperty('fullname')
        }
    }

    results_dir = get_results_dir(dataset, request)
    if dataset.dataSource == 'aekos':
        md = IBCCVLMetadata(dataset)
        return datamover.pull_traits_from_aekos.si(
            traits=md['traits'],
            species=[sp['scientificName'] for sp in md['species']],
            envvars=md['environ'],
            dest_url=results_dir,
            context=context)
