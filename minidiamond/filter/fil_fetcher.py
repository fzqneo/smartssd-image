from io import BytesIO
import pycurl
from urlparse import urlparse

from opendiamond.filter import Filter, Session
from minidiamond import ATTR_DATA

class Fetcher(Filter):
    def __init__(self, args, blob, session=Session('filter')):
        super(Fetcher, self).__init__(args, blob, session=session)
        self._curl = pycurl.Curl()

    def __call__(self, obj):
        parts = urlparse(obj.src)
        if parts.scheme in ('file', ''):
            # shortcut read local file.
            # although Curl also supports the FILE protocol
            # using Curl to read local file is slower.
            body = open(parts.path, 'rb').read()
        else:
            buffer = BytesIO()
            c = self._curl
            c.setopt(c.URL, obj.src)
            c.setopt(c.WRITEDATA, buffer)
            c.perform()
            body = buffer.getvalue()

        obj.set_binary(ATTR_DATA, body)
        return True
