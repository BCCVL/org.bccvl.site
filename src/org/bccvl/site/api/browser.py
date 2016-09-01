import logging

from plone import api as ploneapi
from plone.app.uuid.utils import uuidToCatalogBrain

from zope.component import getUtility, queryUtility
from zope.interface import implementer
from zope.publisher.interfaces import NotFound, BadRequest
from zope.schema.interfaces import IContextSourceBinder
from zope.schema.vocabulary import getVocabularyRegistry

from org.bccvl.site.api.base import BaseAPITraverser, BaseService
from org.bccvl.site.api.decorators import api
from org.bccvl.site.api.interfaces import (
    IAPIService, IDMService, IJobService, IExperimentService, ISiteService,
    IToolkitService, IAPITraverser)
from org.bccvl.site.job.interfaces import IJobUtility
import pkg_resources
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart


LOG = logging.getLogger(__name__)


@implementer(IAPITraverser)
class APITraverser(BaseAPITraverser):

    # entry point needs name, as we can't use browser:view registration
    __name__ = "API"

    title = u'BCCVL APIs'
    description = u'BCCVL API endpoint'
    service_iface = IAPIService
    linkrel = 'service'


@implementer(IAPIService)
class DMVersionTraverser(BaseAPITraverser):

    title = u'Dataset API'
    description = u'Access datasets'
    service_iface = IDMService
    linkrel = 'version'


@implementer(IAPIService)
class JobVersionTraverser(BaseAPITraverser):

    title = u'Job API'
    description = u'Access jobs'
    service_iface = IJobService
    linkrel = 'version'


@implementer(IAPIService)
class ExperimentVersionTraverser(BaseAPITraverser):

    title = u'Experiment API'
    description = u'Access experiments'
    service_iface = IExperimentService
    linkrel = 'version'


@implementer(IAPIService)
class SiteVersionTraverser(BaseAPITraverser):

    title = u'Site API'
    description = u'Access site information'
    service_iface = ISiteService
    linkrel = 'version'


@implementer(IAPIService)
class ToolkitVersionTraverser(BaseAPITraverser):

    title = u'Toolkit API'
    description = u'Access toolkit information'
    service_iface = IToolkitService
    linkrel = 'version'


@api('job_v1.json')
@implementer(IJobService)
class JobService(BaseService):

    title = u'Job API v1'
    description = u'Access jobs'

    def state(self):
        jobid = self.request.form.get('jobid', None)
        uuid = self.request.form.get('uuid', None)
        job = None
        try:
            jobtool = getUtility(IJobUtility)
            if jobid:
                job = jobtool.get_job_by_id(jobid)
            elif uuid:
                job = jobtool.find_job_by_uuid(uuid)
            else:
                raise BadRequest('Reqired parameter jobid or uuid missing')
        except KeyError:
            LOG.warning("Can't find job with id %s", jobid)
        # check current user permissions:
        # TODO: should we check if we have view permissions in case we look at job state for content object?
        # only give access to job state if manager or owner
        user = ploneapi.user.get_current()
        if user.getId() != job.userid:
            roles = user.getRoles()
            # intersect required roles with user roles
            if not (set(roles) & set(('Manager', 'SiteAdministrator'))):
                job = None
        if job:
            return job.state
        # No job found
        raise NotFound(self, 'state', self.request)

    def query(self):
        # FIXME: add owner check here -> probably easiest to make userid query
        # parameter part of jobtool query function?  ; could also look inteo
        # allowed_roles in catalog?
        query = self.request.form
        if not query:
            raise BadRequest('No query parameters supplied')
        jobtool = getUtility(IJobUtility)
        # add current userid to query
        user = ploneapi.user.get_current()
        roles = user.getRoles()
        # intersect required roles with user roles
        if not (set(roles) & set(('Manager', 'SiteAdministrator'))):
            query['userid'] = user.getId()

        brains = jobtool.query(**query)
        if brains:
            brain = brains[0]
            return {
                'id': brain.id,
                'state': brain.state
            }
        else:
            return {}

    # TODO: check security


@api('site_v1.json')
@implementer(ISiteService)
class SiteService(BaseService):

    title = u'Global misc. API v1'
    description = u'Access site wide information'

    # getindexnames .. for querying(+type?)
    # getvocabnames

    def can_access(self):
        uuid = self.request.form.get('uuid')
        if uuid:
            context = uuidToCatalogBrain(uuid)
        else:
            context = self.context
        if context is None:
            return 'denied'
        else:
            return 'allowed'

    def send_support_email(self):
        url = self.request.form.get('url')
        try:
            if url is None:
                raise Exception("URL is not specified")

            # get username
            member = ploneapi.user.get_current()
            if member.getId():
                user = {
                    'id': member.getUserName(),
                    'email': member.getProperty('email'),
                    'fullname': member.getProperty('fullname')
                }
            else:
                raise Exception("Invalid user")

            portal_email = ploneapi.portal.get().getProperty('email_from_address')
            email_to = [portal_email, user['email']]
            subject = "Help: BCCVL experiment failed"
            body = pkg_resources.resource_string(
                "org.bccvl.site.api", "help_email.txt")
            body = body.format(experiment_url=url, username=user[
                'fullname'], user_email=user['email'])

            htmlbody = pkg_resources.resource_string(
                "org.bccvl.site.api", "help_email.html")
            htmlbody = htmlbody.format(experiment_url=url, username=user[
                'fullname'], user_email=user['email'])

            msg = MIMEMultipart('alternative')
            msg.attach(MIMEText(body, 'plain'))
            msg.attach(MIMEText(htmlbody, 'html'))

            ploneapi.portal.send_email(
                recipient=email_to, sender=portal_email, subject=subject, body=msg.as_string())
            return {
                'success': True,
                'message': u'Your email has been sent'
            }
        except Exception as e:
            LOG.error('send_support_email: exception %s', e)
            return {
                'success': False,
                'message': u'Fail to send your email to BCCVL support. Exception {}'.format(e)
            }

    def vocabulary(self):
        # TODO: check if there are vocabularies that need to be protected
        name = self.request.form.get('name', None)
        vocab = ()
        try:
            # TODO: getUtility(IVocabularyFactory???)
            vr = getVocabularyRegistry()
            vocab = vr.get(self.context, name)
        except:
            # eat all exceptions
            pass
        if not vocab:
            # try IContextSourceBinder
            vocab = queryUtility(IContextSourceBinder, name=name)
            if vocab is None:
                return []
            vocab = vocab(self.context)
        result = []
        for term in vocab:
            data = {'token': term.token,
                    'title': term.title}
            if hasattr(term, 'data'):
                data.update(term.data)
            result.append(data)
        return result
