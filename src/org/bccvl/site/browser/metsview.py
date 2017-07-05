from datetime import datetime

from org.bccvl.site.api.dataset import getdsmetadata
from org.bccvl.site.content.interfaces import IBlobDataset
from org.bccvl.site.interfaces import IProvenanceData, IExperimentMetadata

from Products.CMFCore.utils import getToolByName
from Products.Five.browser import BrowserView
from zope.browserpage.viewpagetemplatefile import ViewPageTemplateFile


class MetsView(BrowserView):

    template = ViewPageTemplateFile('mets_xml.pt')

    def __call__(self):
        # parse request for parameters?
        self.request.response.setHeader("Content-type", "text/xml; charset=utf-8")
        return self.render()

    def render(self):
        # 1. get template
        template = self.template
        # 2. return rendered template
        return template(mets=self.build_mets_data())

    def build_mets_data(self):
        # TODO: add time zone ?
        # get rid of milliseconds
        now = datetime.now().replace(microsecond=0)

        mets = {
            'created': now.isoformat(),
            'title': self.context.title,
            'description': self.context.__parent__.description, # use experiment description?
            'creators': self.context.creators, # current users full name,
            'contributors': self.context.contributors,
            'subjects': self.context.subject, # should collect subjects?
            'rights': self.context.rights, # license ? rights? bccvl global rights?
            'content': self.get_content(),
            }
        return mets

    def get_content(self):
        # search for all files within result
        # and generate items for mets.xml template
        pc = getToolByName(self.context, 'portal_catalog')
        brains = pc.searchResults(path='/'.join(self.context.getPhysicalPath()),
                                  object_provides=IBlobDataset.__identifier__)

        for brain in brains:
            content = brain.getObject()
            # ob.file should be a NamedFile ... need to get fs name for that
            arcname = '/'.join((self.context.title, 'data', content.file.filename))

            yield {
                'filename': arcname,
                'mimetype': content.file.contentType,
            }


class ProvView(BrowserView):

    def __call__(self):
        self.request.response.setHeader("Content-type", "text/turtle; charset=utf-8")
        provdata = IProvenanceData(self.context)
        return provdata.data


class ExpmdView(BrowserView):

    def __call__(self):
        self.request.response.setHeader("Content-type", "text/plain; charset=utf-8")
        self.request.response.setHeader("Content-Disposition", "Attachment")
        md = IExperimentMetadata(self.context)
        return md.data
