from Products.Five import BrowserView
from org.bccvl.site.content.interfaces import IBlobDataset
from Products.CMFCore.utils import getToolByName
from ZPublisher.Iterators import filestream_iterator
from org.bccvl.site.api.dataset import getdsmetadata
import os
import os.path
import json
import tempfile
import zipfile


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


        # 1. find all IBlobDataset/ IRemotedDataset/ IDataset objects within context
        pc = getToolByName(self.context, 'portal_catalog')
        brains = pc.searchResults(path='/'.join(self.context.getPhysicalPath()),
                                  object_provides=IBlobDataset.__identifier__)
        fname = None
        try:
            # create tmp file
            fd, fname = tempfile.mkstemp()
            fo = os.fdopen(fd, 'w')
            zfile = zipfile.ZipFile(fo, 'w')

            metadata = {}

            # the file/folder name for the zip
            zfilename = self.context.title
            # iterate over files and add to zip
            for brain in brains:
                content = brain.getObject()
                # ob.file should be a NamedFile ... need to get fs name for that
                blobfile = content.file.openDetached()
                arcname = '/'.join((zfilename, 'data', content.file.filename))
                zfile.write(blobfile.name, arcname)
                blobfile.close()

                metadata[arcname] = getdsmetadata(content)
            # all files are in ....
            # TODO: add experiment result metadata

            # put metadata into zip
            zfile.writestr('/'.join((zfilename, 'bccvl', 'metadata.json')),
                           json.dumps(metadata, indent=4))
            # finish zip file
            zfile.close()

            fo.close()

            # create response
            self.request.response.setHeader('Content-Type', 'application/zip')
            self.request.response.setHeader('Content-Disposition',' attachment; filename={}.zip'.format(zfilename))
            self.request.response.setHeader('Content-Length', '{}'.format(os.path.getsize(fname)))
            return tmpfile_stream_iterator(fname)
        except Exception as e:
            # something went wrong ...
            # clean up and re-raise
            if os.path.exists(fname):
                os.remove(fname)
            raise e
