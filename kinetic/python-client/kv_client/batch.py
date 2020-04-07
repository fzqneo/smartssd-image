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

class Batch(object):
    """
    The Batch class is used for grouping a set of delete/put operations, with the
    limit being 15, so all operation are either committed as one unit, or all of
    them are aborted.

    A Batch object is obtained by calling :func:`~client.Client.create_batch_operation`.
    Once all relevant put and delete calls are made, 'commit' should be called
    to apply all of the operations, or 'abort' to cancel them.

    A Batch object cannot be reused for subsequent batches. After the 'commit'
    or 'abort' has completed successfully, a new Batch object should be
    requested for the next batch operation.
    """

    def __init__(self, client, batch_id):
        """
        Initialize instance with Kinetic client and batch identifier.

        Args:
            client: the Kinetic client to use for batch operations.
            batch_id: the batch identifier to be used for client connection.
        """
        self._client = client
        self._connection_id = client.connection_id
        self._batch_id = batch_id
        self._op_count = 0
        self._batch_completed = False   # to detect attempted reuse

    def put(self, key='', value='', **kwargs):
        """
        Put an entry within the batch operation.

        The command is not committed until :func:`~batch.Batch.commit` is
        called and returns successfully. There is a limit of 15 operations
        per batch.

        Args:
            key (str): Key of entry
            value (str): Value of entry

        Kwargs:
            version (str) : Entry version in store
            new_version (str): This is the next version that the data will be.
            force (bool): This forces the write to ignore the existing version of existing data (if it exists).
            tag (int): This is the integrity value of the data
            algorithm (int): Check kv_client/common.py for supported algorithms

        """

        self._op_count += 1
        kwargs['batch_id'] = self._batch_id

        self._client.put(key, value, batch_flag=True, **kwargs)

    def delete(self, key='', **kwargs):
        """
        Delete the entry associated with the specified key.

        The command is not committed until :func:`~batch.Batch.commit` is
        called and returns successfully. There is a limit of 15 operations
        per batch.

        Args:
            key (str): Key of entry

        Kwargs:
            version (str) : Entry version in store
            new_version (str): This is the next version that the data will be.
            force (bool): This forces the write to ignore the existing version of existing data (if it exists).

        """
        self._op_count += 1
        kwargs['batch_id'] = self._batch_id

        self._client.delete(key, batch_flag=True, **kwargs)

    def commit(self, **kwargs):
        """
        Commit the current batch operation.

        When this call returned successfully, all the commands performed in the
        current batch are executed and committed to store successfully.

        If the commit failed. No operation within the batch were committed to the store.

        Kwargs:
            timeout (int): This is the amount of time that this request should take.

            priority (int): Priority is a simple integer that determines the priority of this request.

            early_exit (bool): If true, requests will not attempt multi revolution recoveries even if
                the timeout has not occurred.

            time_quanta (int): A hint of how long a job should run before yielding.

        """
        kwargs['batch_id'] = self._batch_id
        kwargs['batch_op_count'] = self._op_count

        self._client.end_batch(batch_flag=False, **kwargs)
        self._batch_completed = True

    def abort(self, **kwargs):
        """
        Abort the current batch operation.

        When this call returned successfully, all the commands queued in the
        current batch are aborted. Resources related to the current batch are
        cleaned up and released.

        Args:

        Kwargs:
            timeout (int): This is the amount of time that this request should take.

            priority (int): Priority is a simple integer that determines the priority of this request.

            early_exit (bool): If true, requests will not attempt multi revolution recoveries even if
                the timeout has not occurred.

            time_quanta (int): A hint of how long a job should run before yielding.

        """

        kwargs['batch_id'] = self._batch_id

        self._client.abort_batch(batch_flag=False, **kwargs)
        self._batch_completed = True

    def is_completed(self):
        """
        Return boolean indicating whether the batch is completed (either
        committed or aborted)
        """
        return self._batch_completed

    def __len__(self):
        """
        Return the number of operations that have been included in the batch.
        """
        return self._op_count