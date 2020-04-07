# Public License, v. 2.0. If a copy of the MPL was not
# distributed with this file, You can obtain one at
# https://mozilla.org/MP:/2.0/.
#
# This program is distributed in the hope that it will be useful,
# but is provided AS-IS, WITHOUT ANY WARRANTY; including without
# the implied warranty of MERCHANTABILITY, NON-INFRINGEMENT or
# FITNESS FOR A PARTICULAR PURPOSE. See the Mozilla Public
# License for more details.
#
# See www.openkinetic.org for more project information
#
class LatencyConfiguration:
    DEFAULT = "status_to_status_latency"
    COMMAND_RESPONSE_LATENCY = "command_response_latency"

class ACL(object):
    def __init__(self, identity=1, key='asdfasdf', algorithm=1, max_priority=9):
        self.identity = identity
        self.key = key
        self.hmacAlgorithm = algorithm
        self.max_priority = max_priority
        self.scopes = set()

class Scope(object):
    def __init__(self, permissions, tlsRequired=False, offset=0, value=""):
        self.permissions = set(permissions)
        self.tlsRequired = tlsRequired
        self.offset = offset
        self.value = value

class P2pOp(object):
    def __init__(self, key, version=None, newKey=None, force=None):
        self.key = key
        self.version = version
        self.newKey = newKey
        self.force = force

class Peer(object):
    def __init__(self, hostname='localhost', port=8123, tls=None):
        self.hostname = hostname
        self.port = port
        self.tls = tls
