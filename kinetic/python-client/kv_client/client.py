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

import ssl
import hmac
import time
import errno
import Queue
import socket
import struct
import hashlib
import itertools
from collections import defaultdict
from threading import Event, Lock, Condition, Thread
import batch
import common
import kinetic_pb2

_disable_hmac = False
if _disable_hmac:
    print "zf: This module has disabled hmac calculation"
class Client(object):
    """
    Client is the main class that is used to interface with a
    kinetic device.
    """

    class Semaphore:
        """
        This class is mostly copied from python 2.7 threading library
        BoundedSemaphore class.
        The following changes were made:
        - Dynamically resizable
        - Clear method
        - Minimum of 1 (instead of 0)
        - Failure to release returns False (instead of throwing an exception)
        - Allow read-only access of the condition object and outstanding value
        """
        def __init__(self, value=1):
            if value <= 0:
                raise ValueError("semaphore initial value must be > 0")
            self.depth = value
            self._cond = Condition(Lock())
            self._outstanding = 0

        @property
        def condition(self):
            return self._cond

        @property
        def outstanding(self):
            return self._outstanding

        def clear(self):
            with self._cond:
                self._outstanding = 0
                self._cond.notifyAll()

        def release(self):
            with self._cond:
                if self._outstanding <= 0:
                    return False
                self._outstanding -= 1
                self._cond.notify()
            return True

        def acquire(self, blocking=True):
            rc = False
            with self._cond:
                while self._outstanding >= self.depth:
                    if not blocking:
                        break
                    self._cond.wait()
                else:
                    self._outstanding += 1
                    rc = True
            return rc

        __enter__ = acquire

        def __exit__(self, t, v, tb):
            self.release()

    NO_OP_LIST = ['PINOP', 'SECURITY', 'SETUP']
    OP_DICT = {'getnext':'get_next', 'getprevious':'get_previous', 'getkeyrange':'get_key_range',
               'getversion':'get_version', 'getlog':'get_log', 'flushalldata':'flush_all_data',
               'mediascan':'media_scan', 'mediaoptimize':'media_optimize', 'secure_erase':'instant_secure_erase'}

    def __init__(self,
                 hostname = 'localhost',
                 port = 8123,
                 use_ssl = False,
                 identity = 1,
                 secret = 'asdfasdf',
                 cluster_version = None,
                 queue_depth = 1,
                 debug = False,
                 implicit_flush = False,
                 callback_delegate = None,
                 auto_reconnect_count = 0,
                 connect_timeout = 2.0,
                 socket_timeout = 60.0,
                 chunk_size = 64*1024):
        """
        Initialize a client object.

        Args:
            hostname (str): The host that the client is connecting to
            port (int): The port number that the client is connecting to
            use_ssl (bool): If true, connect the client through a TLS/SSL connection
            identity (int): The identity of the ACL user to communicate with, default is kinetic's demo identity
            secret (str): String used to calculate hmac, default is kinetic's demo identity
            cluster_version (int): Is the number of the cluster definition
            queue_depth (int): How many commands can be outstanding at a time
            debug (bool): If true, print every incoming and outgoing command
            implicit_flush (bool): If true, once the queue depth is reached, the client will send an additional flush command
            callback_delegate (func): Call this function for responses to following commands
            auto_reconnect_count (int): How many times the client should try to reconnect while issuing commands on a dead connection
            connect_timeout (int): The amount of time that connecting to the kinetic device should take
            socket_timeout (int): The amount of time that a socket.send or socket.recv should take
            chunk_size (str): Amount of data sent at a time
        """
        # Configurable
        self.hostname = hostname
        self.port = port
        self.use_ssl = use_ssl
        self.identity = identity
        self.secret = secret
        self.cluster_version = cluster_version
        self.debug = debug
        self.implicit_flush = implicit_flush
        self.callback_delegate = callback_delegate
        self.auto_reconnect_count = auto_reconnect_count
        self.connect_timeout = connect_timeout
        self.socket_timeout = socket_timeout
        self.chunk_size = chunk_size

        # Read-only
        self._sign_on_msg = None
        self._connection_id = None
        self._last_issued_seq = None

        # Internal book-keeping
        self._connected = Event()
        self._stdout_lock = Lock()
        self._pending = dict()
        self._last_comp_op_time = None
        self._sequence = itertools.count()
        self._batch_id = itertools.count()
        self._socket = socket.socket()
        self._listening_thread = Thread()
        self._queue_semaphore = Client.Semaphore(queue_depth)

        # Initial setup
        self.clear_histogram()
        self._set_up_operations()

    @property
    def is_connected(self):
        return self._connected.isSet()

    @property
    def connection_id(self):
        return self._connection_id

    @property
    def sign_on_msg(self):
        return self._sign_on_msg

    @property
    def last_issued_seq(self):
        return self._last_issued_seq

    @property
    def histogram(self):
        return self._histogram

    @property
    def secret(self):
        return self._secret

    @secret.setter
    def secret(self, value):
        d = hashlib.sha1()
        if len(value) > d.block_size:
            mac = hmac.new(value, digestmod=hashlib.sha1)
            self._secret = mac.digest_cons(value).digest()
        else:
            self._secret = value

    @property
    def queue_depth(self):
        return self._queue_semaphore.depth

    @queue_depth.setter
    def queue_depth(self, depth):
        self._queue_semaphore.depth = depth

    def _calculate_hmac(self, command):
        """
        Calculated the HMAC, for standard commands.

        Args:
            command (str): Command object serialized to a string
            and used to help calculate the HMAC using its length

        Returns:
            str: The calculated HMAC
        """

        mac = hmac.new(self._secret, digestmod=hashlib.sha1)
        # Converting to big endian to be compatible with java implementation.
        mac.update(struct.pack(">I", len(command)))
        mac.update(command)
        d = mac.digest()
        return d

    def _check_for_socket_timeouts(self):
        t0 = time.time()
        temp = [bool(t0 >= self._pending[x]['timeout']) for x in self._pending]
        return bool(True in temp)

    def connect(self):
        """
        Establishes a connection to a kinetic device. If connection has
        already been established then return immediately.
        """
        if self.is_connected:
            return

        # Create socket
        info = socket.getaddrinfo(self.hostname, self.port, 0, 0, socket.SOL_TCP)
        (family,_,_,_, sockaddr) = info[0]
        self._socket = socket.socket(family)
        if self.use_ssl:
            self._socket = ssl.wrap_socket(self._socket)
        self._socket.settimeout(self.connect_timeout)

        try:
            # Connect
            self._socket.connect(sockaddr)
            self._socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        except socket.error as e:
            self._client_error_callback(kinetic_pb2.Command.Status.REMOTE_CONNECTION_ERROR, str(e))
            return

        try:
            # Process initial messages
            msg, cmd, value = self._network_recv() # unsolicited status
            self.cluster_version = cmd.header.clusterVersion
            self._connection_id = cmd.header.connectionID
            self._sign_on_msg = cmd
            self._on_response(msg, cmd, value)
        except (AttributeError, ValueError) as e:
            self._client_error_callback(kinetic_pb2.Command.Status.REMOTE_CONNECTION_ERROR, str(e))
            return

        # Initialize connection variables
        self._sequence = itertools.count()
        self._batch_id = itertools.count()

        # Begin listening on the socket
        self._socket.settimeout(self.socket_timeout)
        self._listening_thread = Thread(target=self._listen)
        self._listening_thread.daemon = True
        self._connected.set()
        self._listening_thread.start()

    def close(self):
        """
        Closes the connection between Client object
        and Kinetic device.

        Args:

        Returns:

        """
        self._connected.clear()
        try:
            self._socket.shutdown(socket.SHUT_RDWR)
            self._socket.close()
        except socket.error:
            pass
        self._pending = dict()
        self._queue_semaphore.clear()
        self._listening_thread.join()
        self._listening_thread = Thread()

    def _network_recv(self):
        """
        Receive Kinetic message, response, and value from network (Kinetic device).

        Args:

        Returns:
            Message (message header), Command (proto response), String (Value)
        """
        msg = self._fast_read(9)

        magic, proto_ln, value_ln = struct.unpack_from(">bii", buffer(msg))
        # read proto message
        raw_proto = self._fast_read(proto_ln)

        value = ''
        if value_ln > 0:
            value = self._fast_read(value_ln)

        msg = kinetic_pb2.Message()
        msg.ParseFromString(str(raw_proto))

        cmd = kinetic_pb2.Command()
        cmd.ParseFromString(msg.commandBytes)
        # update connectionId to whatever the drive said.
        if cmd.header.connectionID:
            self._connection_id = cmd.header.connectionID
        return msg, cmd, value

    def _fast_read(self, toread):
        """
        Helper method that does the actually receive from the socket.

        Args:
            toread (int): The size of the data being read from the socket

        Returns:
            bytearray: The packet from socket.
        """
        buf = bytearray(toread)
        view = memoryview(buf)
        while toread:
            nbytes = self._socket.recv_into(view, toread)
            if nbytes == 0:
                raise socket.error
            view = view[nbytes:]
            toread -= nbytes

        return buf

    def _update_header(self, command, command_start_time, batch_flag=False):
        """
        Helper method that updates the command header.

        Args:
            command (Command): The actual Command object whose header
                is going to be updated.

            command_start_time(int): Time to keep track of command latency.

            batch_flag (bool): Batch and normal commands are treated slightly
                different, so there is a flag to denote the difference.
        """
        header = command.header
        header.clusterVersion = self.cluster_version
        header.connectionID = self.connection_id
        header.sequence = self._sequence.next()
        self._last_issued_seq = header.sequence
        if not batch_flag:
            self._pending[header.sequence] = {'callback': self.callback_delegate,
                                              't0': command_start_time,
                                              'timeout': time.time()+self.socket_timeout}

    def _packet_send(self, aux, value):
        """
        Helper method that does the actual sending of the network packets to the drive.

        Args:
            aux(bytearray): The actual kinetic message packet that is being sent to the drive.
            value(str): The value, during a put operation, that is being sent over.
                The kinetic message and the value are sent in different packets.

        """
        value_ln = 0
        if value:
            value_ln = len(value)
        i = 0

        while i < len(aux):
            try:
                i += self._socket.send(aux)
            except socket.timeout:
                pass

        if value_ln > 0:
            # write value
            to_send = len(value)
            i = 0
            while i < to_send:
                try:
                    i += self._socket.send(value[i:i + self.chunk_size])
                except socket.timeout:
                    pass
                except socket.error:
                    break

    def _build_packet(self, m, command, value):
        """
        Helper method that builds the network packets from the
        Kinetic objects.

        Args:
            m (Message): Message is an authorization and command bytes.
            command(Command): The Kinetic Command object.
            value(str): The value, during a put operation, that is being sent over.
                The kinetic message and the value are sent in different packets.
        Returns:
            bytearry: The kinetic packet, Message: message authorization
        """
        command_bytes = command.SerializeToString()
        if not m:
            m = kinetic_pb2.Message()
            m.authType = kinetic_pb2.Message.HMACAUTH
            m.hmacAuth.identity = self.identity
            # zf: hack disble hmac on send
            if not _disable_hmac:
                m.hmacAuth.hmac = self._calculate_hmac(command_bytes)

        m.commandBytes = command_bytes

        # build message (without value) to write
        out = m.SerializeToString()
        value_ln = 0
        if value:
            value_ln = len(value)

        buff = struct.pack(">Bii", ord('F'), len(out), value_ln)

        # Send it all in one packet
        aux = bytearray(buff)
        aux.extend(out)
        return aux, m

    def _network_send(self, m, command, value, command_start_time, message_build_time=0, batch_flag=False):
        """
        Helper method that sends the kinetic packets through python's socket interface to the
        kinetic device. In case of a socket error, if the auto reconnect feature is set, the client
        will attempt to reconnect depending on the number of reconnect tries. Then resend the packet,
        that received the socket error.

        Args:
            m (Message): Message is an authorization and command bytes.
            command(Command): The Kinetic Command object.
            value(str): The value, during a put operation, that is being sent over.
                The kinetic message and the value are sent in different packets.
            comand_start_time(float): Start time, in seconds, of the command.
            message_build_type(float): The about of time, in seconds, to build the message.
            batch_flag(bool): Flag that denotes if a command is a batch command or not.
                Also used to indicate to the client whether to wait for a response or not for a START_BATCH, END_BATCH,
                or ABORT_BATCH.
        """
        reconnect = 0
        while not self.is_connected and reconnect < self.auto_reconnect_count:
            self.connect()
            reconnect += 1
        if not self.is_connected:
            self._client_error_callback(kinetic_pb2.Command.Status.NOT_ATTEMPTED, "call connect() before the operation")

        self._update_header(command, command_start_time, batch_flag)
        aux, message_header = self._build_packet(m, command, value)

        if self.debug and self.is_connected:
            with self._stdout_lock:
                print message_header
                print command
        try:
            self._packet_send(aux, value)
            if self.implicit_flush and self._queue_semaphore.outstanding == self._queue_semaphore.depth:
                self.queue_depth += 1
                self.flush_all_data()
                self.queue_depth -= 1
        except socket.error as e:
            self._client_error_callback(kinetic_pb2.Command.Status.NOT_ATTEMPTED, "network_send:"+str(e))

    def _build_message(self, cmd, messageType, key=None, value=None, **kwargs):
        """
        Helper method that builds the kinetic message, by setting the fields of the command object.

        Args:
            command(Command): The Kinetic Command object.
            messageType(int): The message type of the commands.
            key(str): Entry key of kinetic object.
            value(str): The value, during a put operation, that is being sent over.
                     The kinetic message and the value are sent in different packets.

        Kwargs:
            version(str): Entry version in store.
            new_version(str): On a put or delete, this is the next version that the data will be.
            force(bool): On a put or delete, this forces the write to ignore the existing version of existing data (if it exists).
            tag(str): The integrity value of the data.
            algorithm(int): Algorithm used to protect data.
            synchronization(int): Allows the puts and deletes to determine if they are to be WRITETHROUGH, WRITEBACK, OR FLUSH.
            startKey(str): Start key field for the range operations.
            endKey(str): End key field for the range operations.
            startKeyInclusive(bool): Field for range operations.
            level(int): Power level field for SET_POWER_LEVEL.
            endKeyInclusive(bool): Field for range operations.
            reverse(bool): Field for range operations
            maxReturned(int): Number returned for a range operation.
            types(:obj:`list` of :obj:`int`): List for GETLOG fields to be returned.
            device(str): Name of requested log from the device, such as command history.

        Returns:
            Command: Kinetic command object, String: value, Float: total build time for message.
        """
        build_message_start_time = time.time()
        cmd.header.messageType = messageType

        if key is not None:
            cmd.body.keyValue.key = key

        if 'timeout' in kwargs:
            cmd.header.timeout = kwargs['timeout']

        if 'priority' in kwargs:
            cmd.header.priority = kwargs['priority']

        if 'early_exit' in kwargs:
            cmd.header.earlyExit = kwargs['early_exit']

        if 'time_quanta' in kwargs:
            cmd.header.TimeQuanta = kwargs['time_quanta']

        if 'batch_id' in kwargs:
            cmd.header.batchID = kwargs['batch_id']

        if 'batch_op_count' in kwargs:
            cmd.body.batch.count = kwargs['batch_op_count']

        if 'version' in kwargs:
            cmd.body.keyValue.dbVersion = kwargs['version']

        if 'new_version' in kwargs:
            cmd.body.keyValue.newVersion = kwargs['new_version']

        if 'force' in kwargs:
            cmd.body.keyValue.force = kwargs['force']

        if 'metadataOnly' in kwargs:
            cmd.body.keyValue.metadataOnly = kwargs['metadataOnly']

        if 'level' in kwargs:
            cmd.body.power.level = kwargs['level']

        if 'tag' in kwargs and 'algorithm' in kwargs:
            cmd.body.keyValue.tag = kwargs['tag']
            cmd.body.keyValue.algorithm = kwargs['algorithm']
        elif messageType == kinetic_pb2.Command.PUT:
            # default to sha1
            cmd.body.keyValue.algorithm = kinetic_pb2.Command.SHA1
            if value:
                cmd.body.keyValue.tag = hashlib.sha1(value).digest()
            else:
                cmd.body.keyValue.tag = hashlib.sha1('').digest()
        elif messageType == kinetic_pb2.Command.GETKEYRANGE or messageType == kinetic_pb2.Command.MEDIASCAN \
                or messageType == kinetic_pb2.Command.MEDIAOPTIMIZE:
            kr = cmd.body.range
            if 'startKey' in kwargs:
                kr.startKey = kwargs['startKey']

            if 'endKey' in kwargs:
                kr.endKey = kwargs['endKey']

            if 'startKeyInclusive' in kwargs:
                kr.startKeyInclusive = kwargs['startKeyInclusive']

            if 'endKeyInclusive' in kwargs:
                kr.endKeyInclusive = kwargs['endKeyInclusive']

            if 'reverse' in kwargs:
                kr.reverse = kwargs['reverse']

            if 'maxReturned' in kwargs:
                kr.maxReturned = kwargs['maxReturned']

        if 'synchronization' in kwargs:
            cmd.body.keyValue.synchronization = kwargs['synchronization']

        if 'types' in kwargs:
            log = cmd.body.getLog
            log.types.extend(set(kwargs['types']))
            if 'device' in kwargs:
                log.device.name = kwargs['device']

        build_message_end_time = time.time()
        total_build_message_time = build_message_end_time - build_message_start_time

        return cmd, value, total_build_message_time

    def _async_recv(self):
        """
        Helper method that receives data from the socket and reports either a failure or a successful status.
        """
        msg, cmd, value = self._network_recv()
        # (zf) hack: disable HMAC validation on receive
        # # Validate HMAC on HMACAUTH responses
        if not _disable_hmac:
            if msg.authType == 1:
                cal_hmac = self._calculate_hmac(cmd.SerializeToString())
                if not msg.hmacAuth.hmac or cal_hmac != msg.hmacAuth.hmac:
                    self._client_error_callback(kinetic_pb2.Command.Status.HMAC_FAILURE, "failed HMAC validation on response")
                    return
        self._on_response(msg, cmd, value)

    def _listen(self):
        """
        Thread that receives data from the socket while there is still a connection, and no error.
        """
        while self.is_connected:
            try:
                self._async_recv()
            except socket.timeout:
                if self._check_for_socket_timeouts():
                    self._client_error_callback(kinetic_pb2.Command.Status.EXPIRED, "command timeout detected while listening")
                elif not self.is_connected:
                    break
            except ssl.SSLError:
                if not self.is_connected:
                    break
            except socket.error as e:
                if e.errno == errno.EWOULDBLOCK:
                    pass
                elif self.is_connected:
                    self._client_error_callback(kinetic_pb2.Command.Status.INTERNAL_ERROR, "_listen.socket error:"+str(e))
                    break
            except ValueError as e:
                self._client_error_callback(kinetic_pb2.Command.Status.INTERNAL_ERROR, "_listen.value error:"+str(e))

    def _set_up_operations(self):
        """
        Set up HMAC and PIN based operations from the kinetic proto buf.
        """
        mt = kinetic_pb2.Command.MessageType
        for (k,v) in mt.items():
            if v%2 == 0 and (k not in self.NO_OP_LIST):
                name = k.lower()
                if name in self.OP_DICT.keys():
                    name = self.OP_DICT[name]
                self._add_operation(name,v)

        pin_op = kinetic_pb2.Command.PinOperation.PinOpType
        for (k,v) in pin_op.items():
            if v>0:
                name = k.lower().strip('_pinop')
                if name in self.OP_DICT.keys():
                    name = self.OP_DICT[name]
                self._add_pin_op(name,v)

    def _add_operation(self, name, number):
        """
        Set the HMAC AUTH operations as methods.

        Args:
            name(str): Name of operation.
            number(int): MessageType of operation.
        """

        def proto_operation(key=None, value=None, batch_flag=False, **kwargs):
            """
            HMAC AUTH operations.

            Args:
            key(str): Entry key of kinetic object.
            value(str): The value, during a put operation, that is being sent over.
                        The kinetic message and the value are sent in different packets.
            batch_flag(bool): Flag that denotes if a command is a batch command or not.
                Also used to indicate to the client whether to wait for a response or not for a START_BATCH, END_BATCH,
                or ABORT_BATCH.
            """
            if not self.is_connected and self.auto_reconnect_count < 1:
                self._client_error_callback(kinetic_pb2.Command.Status.NOT_ATTEMPTED, "call connect() before the operation")
            else:
                if not batch_flag:
                    self._queue_semaphore.acquire()

                command_start_time = time.time()
                cmd = kinetic_pb2.Command()
                cmd, value, message_build_time = \
                    self._build_message(cmd, proto_operation.__number__, key=key, value=value, **kwargs)
                self._network_send(None, cmd, value, command_start_time, message_build_time, batch_flag)

        proto_operation.__name__ = name
        proto_operation.__number__ = number
        setattr(self, proto_operation.__name__, proto_operation)

    def _add_pin_op(self, name, number):
        """
        Set PIN AUTH based operations as methods.

         Args:
                name(str): Name of operation.
                number(int): Messagetype of operaion.
        """

        def pin_operation(pin=None, **kwargs):
            """
            PIN AUTH operations

            Args:
            pin(str): Pin for the pin based commands.
            """
            if not self.is_connected and self.auto_reconnect_count < 1:
                self._client_error_callback(kinetic_pb2.Command.Status.NOT_ATTEMPTED, "call connect() before the operation")
            else:
                self._queue_semaphore.acquire()
                command_start_time = time.time()
                m = kinetic_pb2.Message()
                m.authType = kinetic_pb2.Message.PINAUTH
                if pin is not None:
                    m.pinAuth.pin = pin
                cmd = kinetic_pb2.Command()
                cmd, _, message_build_time = self._build_message(cmd, kinetic_pb2.Command.PINOP, **kwargs)
                cmd.body.pinOp.pinOpType = pin_operation.__number__
                self._network_send(m, cmd, "", command_start_time, message_build_time)

        pin_operation.__name__ = name
        pin_operation.__number__ = number
        setattr(self, pin_operation.__name__, pin_operation)

    def _command_decorator(func):
        def check_connection(self, *args, **kwargs):
            if not self.is_connected and self.auto_reconnect_count < 1:
                self._client_error_callback(kinetic_pb2.Command.Status.NOT_ATTEMPTED, "call connect() before the operation")
            else:
                self._queue_semaphore.acquire()
                command_start_time = time.time()
                cmd = kinetic_pb2.Command()
                value, message_build_time = func(self, cmd=cmd, *args, **kwargs)
                self._network_send(None, cmd, value, command_start_time, message_build_time)
        return check_connection

    @_command_decorator
    def set_cluster_version(self, cluster_version, cmd, **kwargs):
        """
        Setup command to set the cluster version

        Args:
            cluster_version(int): Is the  number of the cluster definition.
        """
        cmd, value, message_build_time = self._build_message(cmd, kinetic_pb2.Command.SETUP, **kwargs)
        cmd.body.setup.newClusterVersion = cluster_version
        cmd.body.setup.setupOpType = kinetic_pb2.Command.Setup.CLUSTER_VERSION_SETUPOP
        return value, message_build_time

    @_command_decorator
    def update_firmware(self, firmware, cmd, **kwargs):
        """
        Setup command to update drive firmware.

        Args:
            firmware(str): The firmware, in raw bytes, that will be uploaded on the drive.
        """
        cmd, _, message_build_time = self._build_message(cmd, kinetic_pb2.Command.SETUP, **kwargs)
        cmd.body.setup.setupOpType = kinetic_pb2.Command.Setup.FIRMWARE_SETUPOP
        return firmware, message_build_time

    @_command_decorator
    def set_lock_pin(self, old_pin, new_pin, cmd, **kwargs):
        """
        Setup command to set the lock pin.

        Args:
            old_pin(str): Current lock pin of drive.
            new_pin(str): Pin that end user wants to change the lock pin to.
        """
        cmd, value, message_build_time = self._build_message(cmd, kinetic_pb2.Command.SECURITY, **kwargs)
        cmd.body.security.securityOpType = kinetic_pb2.Command.Security.LOCK_PIN_SECURITYOP
        op = cmd.body.security
        op.oldLockPIN = old_pin
        op.newLockPIN = new_pin
        return value, message_build_time

    @_command_decorator
    def set_erase_pin(self, old_pin, new_pin, cmd, **kwargs):
        """
        Setup command to set the erase pin.

        Args:
            old_pin(str): Current lock pin of drive.
            new_pin(str): Pin that end user wants to change the lock pin to.
        """
        cmd, value, message_build_time = self._build_message(cmd, kinetic_pb2.Command.SECURITY, **kwargs)
        cmd.body.security.securityOpType = kinetic_pb2.Command.Security.ERASE_PIN_SECURITYOP
        op = cmd.body.security
        op.oldErasePIN = old_pin
        op.newErasePIN = new_pin
        return value, message_build_time

    def _stuff_acl_data(self, acls, cmd):
        proto_acls = []
        for acl in acls:
            proto_acl = kinetic_pb2.Command.Security.ACL(identity=acl.identity, key=acl.key,
                                                        hmacAlgorithm=acl.hmacAlgorithm)
            if acl.max_priority is not None:
                proto_acl.maxPriority = acl.max_priority

            proto_scopes = []
            for scope in acl.scopes:
                proto_s = kinetic_pb2.Command.Security.ACL.Scope()
                if scope.tlsRequired is not None:
                    proto_s.TlsRequired = scope.tlsRequired
                if scope.permissions is not None:
                    proto_s.permission.extend(scope.permissions)
                if scope.offset is not None:
                    proto_s.offset = scope.offset
                if scope.value is not None:
                    proto_s.value = scope.value
                proto_scopes.append(proto_s)

            proto_acl.scope.extend(proto_scopes)
            proto_acls.append(proto_acl)
        cmd.body.security.acl.extend(proto_acls)

    @_command_decorator
    def set_acl(self, acls, cmd):
        """
        Security command to set the ACLs (Access Control Lists) .

        Args:
            acls((:obj:`list` of :obj:`ACL`)): List of ACLs.
        """
        cmd, value, message_build_time = self._build_message(cmd, kinetic_pb2.Command.SECURITY)
        cmd.body.security.securityOpType = kinetic_pb2.Command.Security.ACL_SECURITYOP
        self._stuff_acl_data(acls, cmd)
        return value, message_build_time

    def create_batch_operation(self, batch_flag=True, **kwargs):
        """
        Operation that start a batch operation and returns a batch object.
        batch_flag(bool): Flag that denotes if a command is a batch command or not.
                Also used to indicate to the client whether to wait for a response or not for a START_BATCH, END_BATCH,
                or ABORT_BATCH.
        Returns:
            Batch object
        """
        if not self.is_connected and self.auto_reconnect_count < 1:
            self._client_error_callback(kinetic_pb2.Command.Status.NOT_ATTEMPTED, "call connect() before the operation")
        else:
            try:
                next_batch_id = kwargs['batch_id']
            except KeyError:
                next_batch_id = self._batch_id.next()
                kwargs['batch_id'] = next_batch_id
            finally:
                self.start_batch(batch_flag=batch_flag, **kwargs)
                return batch.Batch(self, next_batch_id)

    def _client_error_callback(self, status_code, status_msg):
        msg = kinetic_pb2.Message()
        msg.authType = kinetic_pb2.Message.INVALID_AUTH_TYPE
        cmd = kinetic_pb2.Command()
        cmd.status.statusMessage = "client reported."+status_msg
        cmd.status.code = status_code
        cmd.header.messageType = kinetic_pb2.Command.INVALID_MESSAGE_TYPE
        self._on_response(msg, cmd, "")

    def _on_response(self, msg, cmd, value):
        """
        Helper method that processes response messages

        Args:
            msg (Message): Message part of the proto
            cmd (Command): Command part of the proto (commandBytes de-serialized)
            value(str):  The value, during a put operation, that is being sent over
        """
        t1 = time.time()
        if self.debug:
            with self._stdout_lock:
                print msg
                print cmd
                print value

        seq = cmd.header.ackSequence
        mt = cmd.header.messageType

        if cmd.status.code == kinetic_pb2.Command.Status.SUCCESS:
            if mt == kinetic_pb2.Command.START_BATCH_RESPONSE and seq not in self._pending:
                return

        # Handle responses we sent
        if seq in self._pending:
            # Latency Calculations
            latency_conversion = 1000 # store latency in ms
            if self._last_comp_op_time is None:
                self._last_comp_op_time = self._pending[seq]['t0']
            intercmd = int((t1 - self._last_comp_op_time)*latency_conversion)
            response = int((t1 - self._pending[seq]['t0'])*latency_conversion)
            self._histogram['intercmd'][mt][intercmd] += 1
            self._histogram['response'][mt][response] += 1
            self._last_comp_op_time = t1

            # User specified callback
            if self._pending[seq]['callback'] is not None:
                self._pending[seq]['callback'](msg, cmd, value)

            # Clean up
            del self._pending[seq]
            self._queue_semaphore.release()

        # Handle other responses
        elif self.callback_delegate:
            self.callback_delegate(msg, cmd, value)

    def clear_histogram(self):
        """
        Clears the client's histogram data.
        """
        self._histogram = {'intercmd': defaultdict(lambda : defaultdict(int)),
                           'response': defaultdict(lambda : defaultdict(int))}

    def wait_q(self, outstanding=0, timeout=31556926):
        """
        Method that waits till when the number of pending commands equals the allowed number
        of outstanding commands or till a timeout, whichever happens first.

        Args:
            outstanding(int): Number of outstanding commands to allow at a time, default is 0
            timeout(int): max amount of time to wait before returning, default
                     is one year so that the wait can be interrupted

        Returns:
        True: when the number of pending commands hit the specified limit(outstanding commands)
        False: the wait timed out
        """
        with self._queue_semaphore.condition:
            current_time = start_time = time.time()
            while current_time < start_time + timeout:
                if self._queue_semaphore.outstanding <= outstanding:
                    return True
                else:
                    self._queue_semaphore.condition.wait(timeout - current_time + start_time)
                    current_time = time.time()
        return False