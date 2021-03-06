from Products.Five import BrowserView
from org.bccvl.site.interfaces import IProvenanceData, IExperimentMetadata, IExperimentParameter
from org.bccvl.site.content.interfaces import IBlobDataset, IRemoteDataset
from Products.CMFCore.utils import getToolByName
from ZPublisher.Iterators import filestream_iterator
from org.bccvl.site.api.dataset import getdsmetadata
from org.bccvl.site.swift.interfaces import ISwiftUtility
from zope.component import getMultiAdapter, getUtility
from zope.publisher.interfaces import NotFound
import os
import os.path
import tempfile
import zipfile
from urllib import urlretrieve


class tmpfile_stream_iterator(filestream_iterator):

    def next(self):
        data = self.read(self.streamsize)
        if not data:
            # clean up tmp
            self.close()
            os.remove(self.name)
            raise StopIteration
        return data


class ResultDownloadView(BrowserView):

    def __call__(self):
        try:
            # create tmp file
            fd, fname = tempfile.mkstemp()
            fo = os.fdopen(fd, 'w')
            zfile = zipfile.ZipFile(fo, 'w')

            zfilename = self.context.title
            if self.context.portal_type in ('org.bccvl.content.sdmexperiment', 
                                            'org.bccvl.content.msdmexperiment',
                                            'org.bccvl.content.mmexperiment',
                                            'org.bccvl.content.projectionexperiment',
                                            'org.bccvl.content.biodiverseexperiment',
                                            'org.bccvl.content.speciestraitsexperiment',
                                            'org.bccvl.content.ensemble'):
                for eid, eitem in self.context.contentItems():
                    self._download_results(eitem, zfile)
            else:
                self._download_results(self.context, zfile)

            # finish zip file
            zfile.close()
            fo.close()

            # create response
            self.request.response.setHeader('Content-Type', 'application/zip')
            self.request.response.setHeader('Content-Disposition', 'attachment; filename="{}.zip"'.format(zfilename))
            self.request.response.setHeader('Content-Length', '{}'.format(os.path.getsize(fname)))
            return tmpfile_stream_iterator(fname)
        except Exception as e:
            # something went wrong ...
            # clean up and re-raise
            if os.path.exists(fname):
                os.remove(fname)
            raise e


    def _download_results(self, context, zfile):
        # FIXME: This is a rather lengthy process, and should probably be turned into a background task... (maybe as part of a datamanager service?)

        # 1. find all IBlobDataset/ IRemotedDataset/ IDataset objects within context
        pc = getToolByName(context, 'portal_catalog')
        brains = pc.searchResults(path='/'.join(context.getPhysicalPath()),
                                  object_provides=[IBlobDataset.__identifier__,
                                                   IRemoteDataset.__identifier__])
        metadata = {}

        # the file/folder name for the zip
        zfilename = context.title
        # iterate over files and add to zip
        for brain in brains:
            content = brain.getObject()
            if IBlobDataset.providedBy(content):
                # If data is stored locally:
                arcname = '/'.join((zfilename, 'data', content.file.filename))
                # ob.file should be a NamedFile ... need to get fs name for that
                blobfile = content.file.openDetached()

                zfile.write(blobfile.name, arcname)
                blobfile.close()

            elif IRemoteDataset.providedBy(content):
                # TODO: duplicate code from
                remoteUrl = getattr(content, 'remoteUrl', None)
                if remoteUrl is None:
                    raise NotFound(self, 'remoteUrl', self.request)
                # get arcname from remoteUrl
                arcname = '/'.join((zfilename, 'data', os.path.basename(remoteUrl)))
                # FIXME: should check dataset downloaiable flag here,
                #       but assumption is, that this function can only be called on an experiment result folder....
                # TODO: duplicate code in browser/dataset.py:RemoteDatasetDownload.__call__
                # TODO: may not work in general... it always uses swift as remote url
                tool = getUtility(ISwiftUtility)
                try:
                    url = tool.generate_temp_url(url=remoteUrl)
                except:
                    url = remoteUrl
                # url is now the location from which we can fetch the file
                temp_file, _ = urlretrieve(url)
                zfile.write(temp_file, arcname)
                os.remove(temp_file)
            else:
                # unknown type of Dataset
                # just skip it
                # TODO: Log warning or debug?
                continue
            metadata[arcname] = getdsmetadata(content)
        # all files are in ....
        # TODO: add experiment result metadata

        # put metadata into zip
        # provenance data stored on result container
        provdata = IProvenanceData(context)
        if not provdata.data is None:
            zfile.writestr('/'.join((zfilename, 'prov.ttl')),
                           provdata.data.encode('utf-8'))

        # add experiment metadata
        expmetadata = IExperimentMetadata(context)
        if not expmetadata.data is None:
            zfile.writestr('/'.join((zfilename, 'expmetadata.txt')),
                           expmetadata.data.encode('utf-8'))

        # add mets.xml
        metsview = getMultiAdapter((context, self.request), name="mets.xml")
        zfile.writestr('/'.join((zfilename, 'mets.xml')),
                       metsview.render().encode('utf-8'))

        # add experiment parameters
        params = IExperimentParameter(context)
        if not params.data is None:
            zfile.writestr('/'.join((zfilename, 'params.json')),
                           params.data.encode('utf-8'))
