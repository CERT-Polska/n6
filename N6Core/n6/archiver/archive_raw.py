#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Component archive_raw -- adds raw data to the archive database (MongoDB).
A new source is added as a new collection.
"""

import datetime
import hashlib
import itertools
import math
import os
import socket
import subprocess
import sys
import tempfile
import time
import re

import gridfs
import pymongo
from gridfs import GridFS
from bson.json_util import loads
from bson.json_util import dumps

from n6lib.config import Config
from n6.base.queue import QueuedBase, n6QueueProcessingException
from n6lib.log_helpers import get_logger, logging_configured


LOGGER = get_logger(__name__)

FORBIDDEN_DB_NAME_CHAR = '/\\." \n\t\r'
FORBIDDEN_COLLECTION_NAME_CHAR = '$ \n\t\r'
INSUFFICIENT_DISK_SPACE_CODE = 17035

first_letter_collection_name = re.compile("^(?!system)[a-z_].*", re.UNICODE)


def backup_msg(fname, collection, msg, header):
    with open(fname, 'w') as f:
        if isinstance(msg, basestring):
            payload = (msg.encode('utf-8') if isinstance(msg, unicode)
                       else msg)
        else:
            payload = (repr(msg).encode('utf-8') if isinstance(repr(msg), unicode)
                       else repr(msg))

        hdr = (repr(header).encode('utf-8') if isinstance(repr(header), unicode)
                       else repr(header))
        f.write('\n'.join(( collection, hdr, payload )))


def timeit(method):
    def timed(*args, **kw):
        start = datetime.datetime.now()
        result = method(*args, **kw)
        stop = datetime.datetime.now()
        delta = stop - start
        print '%r %r (%r, %r) %r ' % \
              (str(datetime.datetime.now()), method.__name__, args, kw, str(delta))
        return result
    return timed


def safe_mongocall(call):
    def _safe_mongocall(*args, **kwargs):
        count_try_connection = 86400  # 5 days
        while True:
            try:
                return call(*args, **kwargs)
            except pymongo.errors.AutoReconnect:
                LOGGER.error("Cannot connect to mongodb.  Retrying...")
                time.sleep(5)
                count_try_connection -= 1
                ob = args[0]
                if (isinstance(ob, JsonStream) or
                    isinstance(ob, FileGridfs) or
                    isinstance(ob, BlackListCompacter)):
                    LOGGER.debug("backup_msg")
                    try:
                        backup_msg(ob.dbm.backup_msg, ob.dbm.currcoll, ob.data, ob.headers)
                    except Exception as exc:
                        LOGGER.debug('backup_msg_error: %r', exc)
                    ob.dbm.get_connection()
                elif isinstance(ob, DbManager):
                    LOGGER.debug("backup_msg")
                    try:
                       backup_msg(ob.backup_msg, ob.currcoll, ob.backup_msg_data, ob.backup_msg_headers)
                    except Exception as exc:
                        LOGGER.error('backup_msg_error: %r', exc)
                    ob.get_connection()
                if count_try_connection < 1:
                    LOGGER.error("Could not connect to mongodb.  Exiting...")
                    sys.exit(1)
    return _safe_mongocall


class IndexesStore(object):
    _collections_tmp_store = {}

    def __init__(self, connection, db_name, collection_name):
        self.db = connection[db_name]
        collection = self.db[collection_name]
        docs = collection.find().sort("ns", pymongo.ASCENDING)
        for i in docs:
            coll = Collection(i['ns'].replace(''.join((db_name, '.')), ''))
            self.add_to_storage(coll, i['key'].keys()[0])

    @staticmethod
    def add_to_storage(collection, index):
        if collection.name not in IndexesStore._collections_tmp_store.keys():
            # new collection, add index, and initialize key in store dict
            collection.indexes.append(index)
            IndexesStore._collections_tmp_store.update({collection.name: collection})
        else:
            # collection in store, add only new index name
            IndexesStore._collections_tmp_store[collection.name].indexes.append(index)

    @staticmethod
    def name_of_indexed_collection_n6():
        # simple select a collection, no system and no tip chunks
        # to check the amount of indexes
        return [name for name in IndexesStore._collections_tmp_store.keys()
                if ('.chunks' not in name) and name not in ('n6.system.namespaces')]

    @staticmethod
    def cleanup_store():
        IndexesStore._collections_tmp_store = {}


class Collection(object):
    __slots__ = ['name', 'indexes']

    def __init__(self, name):
        self.name = name
        self.indexes = []


class DbManager(object):
    """"""

    def __init__(self, config=None):
        """
        Args:
            config: dict containing: mongohost, mongoport, mongodb,
             count_try_connection, time_sleep_between_try_connect, uri
        """
        if config is None:
            config = Config(required={"archiveraw": ("mongohost",
                                                     "mongoport",
                                                     "mongodb",
                                                     "count_try_connection",
                                                     "time_sleep_between_try_connect",
                                                     "uri")})
            self.config = config["archiveraw"]
        else:
            self.config = config
        self.host = self.config['mongohost']
        self.port = int(self.config['mongoport'])
        self._currdb = self.config['mongodb']
        self.uri = self.config["uri"]
        self.connection = None
        self._currcoll = None
        self.conn_gridfs = None
        self.time_sleep_between_try_connect = int(self.config['time_sleep_between_try_connect'])
        self.count_try_connection = int(self.config['count_try_connection'])
        self.indexes_store = []
        self.backup_msg = '.backup_msg'
        self.backup_msg_data = None
        self.backup_msg_headers = None

    def get_connection(self):
        """
        Get a connection to MongoDB.
        Try `self.count_try_connection` times, then (if not succeeded)
        raise SystemExit.

        Returns:
            `self.connection`, as returned by MongoClient(<self.host>, <self.port>).

        Raises:
            SystemExit
        """
        count_try_connection = self.count_try_connection
        while True:
            try:
                #self.connection = pymongo.mongo_client.MongoClient(self.host, port=self.port)
                self.connection = pymongo.mongo_client.MongoClient(self.uri,
                                                                   sockettimeoutms=2000,
                                                                   connecttimeoutms=2000,
                                                                   waitqueuetimeoutms=2000,
                                                                   )
                return self.connection

            except pymongo.errors.ConnectionFailure:
                LOGGER.error("Cannot connect to mongodb@ %s:%s. Retrying...",
                             self.host, self.port)
                time.sleep(self.time_sleep_between_try_connect)
                count_try_connection -= 1
                if count_try_connection < 1:
                    LOGGER.error("Cannot connect to mongodb@ %s:%s. Exiting...",
                                 self.host, self.port)
                    sys.exit(1)

    @safe_mongocall
    def get_conn_db(self):
        """Get connection to db."""
        return self.connection[self.currdb]

    @safe_mongocall
    def get_conn_collection(self, gridfs=False):
        """Get connection to collection."""
        return self.get_conn_db()[self.currcoll]

    @safe_mongocall
    def get_conn_gridfs(self):
        """Get connection to gridfs api to put, and get files."""
        assert self.currcoll, 'not set self.currcoll'
        self.conn_gridfs = gridfs.GridFS(self.get_conn_db(), collection=self.currcoll)

    @safe_mongocall
    def put_file_to_db(self, data, **kwargs):
        """Put file in mongo."""
        assert self.conn_gridfs, 'not set self.conn_gridfs'
        return self.conn_gridfs.put(data, **kwargs)

    @safe_mongocall
    def get_file_from_db(self, id_):
        """Get file from db."""
        assert self.conn_gridfs, 'not set self.conn_gridfs'
        return str(self.conn_gridfs.get(id_).read())

    @safe_mongocall
    def get_file_from_db_raw(self, id_):
        """Get file from db, raw not str."""
        assert self.conn_gridfs, 'not set self.conn_gridfs'
        return self.conn_gridfs.get(id_).read()

    @property
    def currdb(self):
        return self._currdb

    @currdb.setter
    def currdb(self, value):
        value_str = str(value)
        if len(value_str) >= 64 or len(value_str) < 1:
            LOGGER.error('to long db name in mongo, max 63 chars, min 1 char : %r', value_str)
            raise n6QueueProcessingException("to long db name in mongo, max 63 chars, min 1 char"
                                             ": {0}".format(value_str))
        for forbidden_char in FORBIDDEN_DB_NAME_CHAR:
            if forbidden_char in value_str:
                LOGGER.error('name of db: %r, contains forbidden_char: %r', value_str,
                             forbidden_char)
                raise n6QueueProcessingException("name of db: {}, "
                                                 "contains forbidden_char: {}".format(value_str, forbidden_char))
        self._currdb = value

    @property
    def currcoll(self):
        return self._currcoll

    @currcoll.setter
    def currcoll(self, value):
        if value is None:
            self._currcoll = value
            return
        value_str = str(value)
        m = re.match(first_letter_collection_name, value_str)
        if not m or len(value_str) < 1:
            raise n6QueueProcessingException('Collection names should begin with an underscore '
                                             'or a letter character, and not be an empty string '
                                             '(e.g. ""), and not begin with the system. prefix. '
                                             '(Reserved for internal use.)')
        for forbidden_char in FORBIDDEN_COLLECTION_NAME_CHAR:
            if forbidden_char in value_str:
                LOGGER.error('name of collection: %r, contains forbidden_char: %r', value_str,
                             forbidden_char)
                raise n6QueueProcessingException("name of collection: {0}, "
                                                 "contains forbidden_char: {1}".
                                                 format(value_str, forbidden_char))
        self._currcoll = value

    def database_exists(self):
        """Check if the database exists on the server."""
        return self.currdb in self.connection.database_names()

    def collection_exists(self):
        """Check if the collection exists in the database.
        Not very good in terms of performance!."""
        if self.currcoll not in self.get_conn_db().collection_names():
            # only for manageApi
            return self.currcoll + '.files' in self.get_conn_db().collection_names()
        return self.currcoll in self.get_conn_db().collection_names()

    def initialize_index_store(self):
        if self.connection:
            IndexesStore.cleanup_store()
            index_store = IndexesStore(self.connection, self.currdb, 'system.indexes')
            self.indexes_store = index_store.name_of_indexed_collection_n6()
        else:
            LOGGER.error('No connection to initialize index store')


class MongoConnection(object):
    """
    MongoConnection - a set of common attributes of classes
    (JsonStream, FileGridfs, BlackListCompacter).

    Args:
        `dbmanager`  : object DbManager type.
        `properties` : properties from AMQP. Required for the next processing
        `**kwargs` : (dict with additional data)
    """
    indexes_common = ['rid', 'received', 'md5']

    def __init__(self, dbmanager=None, properties=None, **kwargs):
        self.dbm = dbmanager
        self.data = {}
        self.raw = None
        self.content_type = None
        self.headers = {}
        if properties:
            if properties.headers:
                self.headers = properties.headers.copy()
                if "meta" in properties.headers:
                    self.headers['meta'].update(properties.headers['meta'])
                else:
                    # empty meta, add key meta, adds key meta
                    # another data  such. rid, received, contentType....
                    self.headers["meta"] = {}
                    LOGGER.debug('No "meta" in headers: %r', properties.headers)
            else:
                # empty headers, add key meta, adds key
                # meta another data  such. rid, received, contentType....
                self.headers["meta"] = {}
                LOGGER.debug('Empty headers: %r', properties.headers)

            if properties.type in ('file', 'blacklist'):
                # content_type required fo type file and blacklist
                try:
                    self.headers['meta'].update({'contentType': properties.content_type})
                except AttributeError as exc:
                    LOGGER.error('No "content_type" in properties: %r', properties.headers)
                    raise
            # always add
            self.headers['meta'].update({'rid': properties.message_id,
                                         'received': self.get_time_created(properties.timestamp)})
        else:
            # empty properties, it is very bad
            raise n6QueueProcessingException("empty properties, it is very bad"
                                             ": {0}".format(properties))

    def get_time_created(self, ts):
        try:
            return datetime.datetime.utcfromtimestamp(ts)
        except TypeError as exc:
            LOGGER.error("Bad type timestamp: %r, exc: %r, collection: %r", ts, exc,
                         self.dbm.currcoll)
            raise

    def create_indexes(self, coll):
        """Create indexes on new collection."""
        for idx in MongoConnection.indexes_common:
            LOGGER.info("Create indexes: %r on collection: %r", idx, coll.name)
            coll.create_index(idx)
        # refresh indexes store
        self.dbm.initialize_index_store()


class JsonStream(MongoConnection):
    """
    This class is responsible for the different types of writing to mongo.
    This class extJson|Json format stores only
    (http://docs.mongodb.org/manual/reference/mongodb-extended-json/).
    JsonStream inherits from the MongoConnection.
    """
    def preparations_data(self, data):
        """
        Data preparation.

        Args:
            `data` : data from AMQP.

        Raises:
            `n6QueueProcessingException` when except processing data.
        """
        try:
            self.raw = loads(data)
            # calculate md5, inplace its fastest
            self.headers['meta'].update({
                'md5': hashlib.md5(dumps(self.raw, sort_keys=True)).hexdigest()})

        except Exception as exc:
            LOGGER.error('exception when processing: %r %r %r (%r)',
                         self.dbm.currdb, self.dbm.currcoll, data, exc)
            raise

        else:
            self.write()

    @safe_mongocall
    def write(self):
        """
        Write data to db as json store.

        Raises:
            `UnicodeDecodeError` when collection name or the database name is not allowed
            `pymongo.errors.AutoReconnect` when problem with connection to mongo.
            `n6QueueProcessingException` if catch other exception.
        """
        LOGGER.debug('Stream inserting...')
        LOGGER.debug('HEADER: %r', self.headers)
        self.data['data'] = self.raw
        self.data['uploadDate'] = datetime.datetime.utcfromtimestamp(time.time())
        self.data.update(self.headers['meta'])

        # for backup msg
        self.dbm.backup_msg_data = self.data
        self.dbm.backup_msg_headers = self.headers

        try:
            try:
                if self.dbm.currcoll not in self.dbm.indexes_store:
                    self.create_indexes(self.dbm.get_conn_collection())

                self.dbm.get_conn_collection().insert(self.data)
            except pymongo.errors.OperationFailure as exc:
                if exc.code == INSUFFICIENT_DISK_SPACE_CODE:
                    sys.exit(repr(exc))
                raise
        except pymongo.errors.AutoReconnect as exc:
            LOGGER.error('%r', exc)
            raise
        except UnicodeDecodeError as exc:
            LOGGER.error("collection name or the database name is not allowed: %r, %r, %r",
                         self.dbm.currdb, self.dbm.currcoll, exc)
            raise
        except Exception as exc:
            LOGGER.error('save data in mongodb FAILED, header: %r , exception: %r',
                         self.headers, exc)
            raise n6QueueProcessingException('save data in mongob FAILED')
        else:
            LOGGER.debug('Insert done.')

    def gen_md5(self, data):
        """Generate md5 hash In the data field."""
        return hashlib.md5(dumps(data, sort_keys=True)).hexdigest()


class FileGridfs(MongoConnection):
    """
    This class is responsible for the different types of writing to mongo.
    This class files and other binary format stores.
    FileGridfs inherits from the MongoConnection.
    """
    def preparations_data(self, data):
        """
        Data preparation.

        Args:
            `data` : data from AMQP.

        Raises:
            `n6QueueProcessingException` when except processing data.
        """

        try:
            self.data = data
        except Exception as exc:
            LOGGER.error('exception when processing: %r %r %r (%r)',
                         self.dbm.currdb, self.dbm.currcoll, data, exc)
            raise
        else:
            self.write()

    @safe_mongocall
    def write(self):
        """
        Write data to db as GridFS store.

        Raises:
            `UnicodeDecodeError` when collection name or the database name is not allowed.
            `pymongo.errors.AutoReconnect` when problem with connection to mongo.
            `n6QueueProcessingException` if catch other exception.
        """
        LOGGER.debug('Binary inserting...')
        LOGGER.debug('HEADER: %r', self.headers)

        # for backup msg
        self.dbm.backup_msg_data = self.data
        self.dbm.backup_msg_headers = self.headers

        try:
            try:
                self.dbm.get_conn_gridfs()
                coll = self.dbm.get_conn_collection().files
                if coll.name not in self.dbm.indexes_store:
                    self.create_indexes(coll)
                self.dbm.put_file_to_db(self.data, **self.headers['meta'])
            except pymongo.errors.OperationFailure as exc:
                if exc.code == INSUFFICIENT_DISK_SPACE_CODE:
                    sys.exit(repr(exc))
                raise
        except pymongo.errors.AutoReconnect as exc:
            LOGGER.error('%r', exc)
            raise
        except UnicodeDecodeError as exc:
            LOGGER.error("collection name or the database name is not allowed: %r, %r, %r",
                         self.dbm.currdb, self.dbm.currcoll, exc)
            raise
        except Exception as exc:
            LOGGER.error('save data in mongodb FAILED, header: %r , exception: %r',
                         self.headers, exc)
            raise n6QueueProcessingException('save data in mongob FAILED')
        else:
            LOGGER.debug('Saving data, with meta key, done')

    def get_file(self, currdb, currcoll, **kw):
        """Get file/s from mongo gridfs system. Not implemented."""
        pass


class DBarchiver(QueuedBase):
    """ Archive data """
    input_queue = {"exchange": "raw",
                   "exchange_type": "topic",
                   "queue_name": "dba",
                   "binding_keys": ["#"]
                   }

    def __init__(self, *args, **kwargs):
        self.manager = DbManager()
        self.connectdb = self.manager.get_connection()
        self.manager.initialize_index_store()  # after call get_connection
        self.connectdb.secondary_acceptable_latency_ms = 5000  # max latency for ping
        super(DBarchiver, self).__init__(*args, **kwargs)

    __count = itertools.count(1)
    __tf = []
    def input_callback(self, routing_key, body, properties):
      #t0 = time.time()
      #try:
        """
        Channel callback method.

        Args:
            `routing_key` : routing_key from AMQP.
            `body` : message body from AMQP.
            `properties` : properties from AMQP. Required for the next processing

        Raises:
            `n6QueueProcessingException`:
                From JsonStream/FileGridfs or when message type is unknown.
            Other exceptions (e.g. pymongo.errors.DuplicateKeyError).
        """
        #  Headers required for the next processing
        if properties.headers is None:
           properties.headers = {}

        # Suspend writing to Mongo if header is set to False
        try:
            writing = properties.headers['write_to_mongo']
        except KeyError:
            writing = True

        LOGGER.debug("Received properties :%r", properties)
        LOGGER.debug("Received headers :%r", properties.headers)
        # set collection name
        self.manager.currcoll = routing_key
        type_ = properties.type
        payload = (body.encode('utf-8') if isinstance(body, unicode)
                   else body)

        # Add to archive
        if writing:
            if type_ == 'stream':
                s = JsonStream(dbmanager=self.manager, properties=properties)
                s.preparations_data(payload)
            elif type_ == 'file':
                s = FileGridfs(dbmanager=self.manager, properties=properties)
                s.preparations_data(payload)
            elif type_ == 'blacklist':
                s = BlackListCompacter(dbmanager=self.manager, properties=properties)
                s.preparations_data(payload)
                s.start()
            else:
                raise n6QueueProcessingException(
                    "Unknown message type: {0}, source: {1}".format(type_, routing_key))
      #finally:
      #  self.__tf.append(time.time() - t0)
      #  if next(self.__count) % 5000 == 0:
      #      try:
      #          LOGGER.critical('ARCHIVE-RAW INPUT CALLBACK TIMES: min %s, avg %s',
      #                          min(tf),
      #                          math.fsum(tf) / len(tf))
      #      finally:
      #          del tf[:]


class BlackListCompacter(MongoConnection):
    """
    Performs a diff of a record (patches) to the database, the differences recovers file ORIGINAL
    (saves space)
    """
    generate_all_file = False
    init = 1
    period = 14

    def __init__(self, dbmanager=None, properties=None):
        LOGGER.debug('run blacklist : collection: %r',
                     dbmanager.currcoll)
        super(BlackListCompacter, self).__init__(dbmanager=dbmanager,
                                                 properties=properties,
                                                 )
        self.list_tmp_files = []
        self.prefix = '.csv_'
        self.suffix = 'bl-'
        self.marker_db_init = 0
        self.marker_db_diff = 1
        self.prev_id = None
        self.file_init = None
        self.payload = None
        self.dbm = dbmanager
        # for backup msg
        self.dbm.backup_msg_data = self.data
        self.dbm.backup_msg_headers = self.headers
        try:
            self.dbm.get_conn_gridfs()
            # name collection in gridfs is src.subsrc.files|chunks
            self.collection = self.dbm.get_conn_collection().files
        except UnicodeDecodeError as exc:
            LOGGER.error("collection name or the database name is not allowed: %r, %r",
                         self.dbm.currcoll, exc)
            raise
        # create indexes
        if self.collection.name not in self.dbm.indexes_store:
            self.create_indexes(self.collection)

    def preparations_data(self, data):
        """
        Data preparation.

        Args:
            `data` : data from AMQP.

        Raises:
            `n6QueueProcessingException` when except processing data.
        """

        try:
            self.payload = data
            self.init_files()
        except Exception as exc:
            LOGGER.error('exception when processing: %r %r %r (%r)',
                         self.dbm.currdb, self.dbm.currcoll, data, exc)
            raise

    def init_files(self):
        """Init all tmp files"""
        self.tempfilefd_file_init, self.tempfile_file_init = tempfile.mkstemp(self.prefix,
                                                                              self.suffix)
        self.tempfilefd_file, self.tempfile_file = tempfile.mkstemp(self.prefix,
                                                                    self.suffix)
        self.tempfilefd_patch_all, self.tempfile_patch_all = tempfile.mkstemp(self.prefix,
                                                                              self.suffix)
        self.tempfilefd_patch, self.tempfile_patch = tempfile.mkstemp(self.prefix, self.suffix)
        self.tempfilefd_patch_tmp, self.tempfile_patch_tmp = tempfile.mkstemp(self.prefix,
                                                                              self.suffix)
        self.tempfilefd_patch_u, self.tempfile_patch_u = tempfile.mkstemp(self.prefix,
                                                                          self.suffix)
        (self.tempfilefd_file_recovery_0,
         self.tempfile_file_recovery_0) = tempfile.mkstemp(self.prefix, self.suffix)
        self.tempfilefd_ver, self.tempfile_ver = tempfile.mkstemp(self.prefix, self.suffix)

        self.list_tmp_files.append((self.tempfilefd_file_init, self.tempfile_file_init))
        self.list_tmp_files.append((self.tempfilefd_file, self.tempfile_file))
        self.list_tmp_files.append((self.tempfilefd_patch_all, self.tempfile_patch_all))
        self.list_tmp_files.append((self.tempfilefd_patch_tmp, self.tempfile_patch_tmp))
        self.list_tmp_files.append((self.tempfilefd_patch_u, self.tempfile_patch_u))
        self.list_tmp_files.append((self.tempfilefd_file_recovery_0,
                                    self.tempfile_file_recovery_0))
        self.list_tmp_files.append((self.tempfilefd_patch, self.tempfile_patch))
        self.list_tmp_files.append((self.tempfilefd_ver, self.tempfile_ver))

        # save orig init file
        with open(self.tempfile_file_init, 'w') as fid:
            LOGGER.debug('WTF: %r', type(self.payload))
            fid.write(self.payload)
        self.file_init = self.tempfile_file_init

        for fd, fn in self.list_tmp_files:
            os.close(fd)
            os.chmod(fn, 0644)
        LOGGER.debug('run blacklist init tmp files')

    @safe_mongocall
    def save_file_in_db(self, marker, data):
        """
              Save  file in DB

              Args: `marker` int,  0 - init file, 1,2,...,self.period - diff files
                      `data` file

              Return: None

              Raises:
                     `pymongo.errors.AutoReconnect` when problem with connection to mongo.
                     `n6QueueProcessingException` if catch other exception.
              """
        # marker indicates the beginning of a sequence of file patch, length period.
        # override these attr,  results in a new sequence differences(diffs)
        # override is very important !
        self.headers["meta"]["marker"] = marker
        self.headers["meta"]["prev_id"] = self.prev_id
        # for bakup_msg
        self.data = data
        self.dbm.backup_msg_data = self.data
        self.dbm.backup_msg_headers = self.headers
        try:
            try:
                self.dbm.put_file_to_db(data, **self.headers["meta"])
            except pymongo.errors.OperationFailure as exc:
                if exc.code == INSUFFICIENT_DISK_SPACE_CODE:
                    sys.exit(repr(exc))
                raise
        except pymongo.errors.AutoReconnect as exc:
            LOGGER.error('%r', exc)
            raise
        except Exception as exc:
            LOGGER.error('save file in mongodb FAILED, header: %r , exception: %r',
                         self.headers, exc)
            raise n6QueueProcessingException('save file in mongob FAILED')
        else:
            LOGGER.debug('save file in db marker: %r', marker)

    @safe_mongocall
    def get_patches(self):
        """
              Get patch from DB

              Args: None

              Return: first_file_id, cursor(with patch files without first init file)
              """
        cursor = self.collection.find(
            {
                "marker": self.marker_db_init}
        ).sort("received", pymongo.DESCENDING).limit(1)

        row = cursor.next()
        date = row["received"]
        first_file_id = row["_id"]

        cursor = self.collection.find(
            {
                "marker": {"$gte": self.marker_db_init},
                "received": {"$gte": date}
            }
        ).sort("received", pymongo.ASCENDING)

        LOGGER.debug('first_file_id :%s date: %s', first_file_id, date)
        return first_file_id, cursor

    def save_diff_in_db(self, files):
        """
        Saves Diff, used Unix features: diff.

        Args:  `files`

        Return: None
        """
        file1, file2 = files
        f_sout = open(self.tempfile_patch_u, "w")
        if BlackListCompacter.init:
            BlackListCompacter.init = 0
            subprocess.call("diff -u " + file1 + " " + file2,
                            stdout=f_sout, stderr=subprocess.STDOUT, shell=True)
            f_sout.close()

            self.save_file_in_db(self.marker_db_init,
                                 open(self.tempfile_patch_u, 'r').read())
            LOGGER.debug(' marker init in db:%s ', self.marker_db_init)
        else:
            subprocess.call("diff -u " + file1 + " " +
                            file2, stdout=f_sout, stderr=subprocess.STDOUT, shell=True)
            f_sout.close()

            self.save_file_in_db(self.marker_db_diff,
                                 open(self.tempfile_patch_u, 'r').read())
            LOGGER.debug('marker in period in db :%s ', self.marker_db_diff)

    def generate_orig_file(self, cursor, file_id):
        """
        Generates one or more files, patching one file to another.
        Used Unix features: patch.

        Args: `cursor`: (with all the patch from one period)
              `file_id`: first init file id to generate first patch

        Return: None
        """
        LOGGER.debug('BlackListCompacter.GENERATE_ALL_FILE: %r',
                     BlackListCompacter.generate_all_file)
        # generate first file
        files_count = 1
        # stdout in file
        f_sout = open(self.tempfile_patch_u, "w")
        # first diff file post init in GENERATE_ALL_FILE mode
        if cursor.count() > 0 and BlackListCompacter.generate_all_file:
            out = subprocess.call("patch  " + self.tempfile_file + " -i  " +
                                  self.tempfile_patch_tmp + " -o " +
                                  self.tempfile_ver + str(files_count - 1),
                                  stdout=f_sout, stderr=subprocess.STDOUT, shell=True)
            LOGGER.debug('patch_next_file(return code): %r', out)
            self.list_tmp_files.append((self.tempfile_ver,
                                        self.tempfile_ver +
                                        str(files_count - 1)))
            os.chmod(self.tempfile_ver + str(files_count - 1), 0644)

        # # first diff file post init in GENERATE_ONE_FILE mode
        elif cursor.count() > 0 and (not BlackListCompacter.generate_all_file):
            out = subprocess.call("patch  " + self.tempfile_file + " -i  " +
                                  self.tempfile_patch_tmp + " -o " +
                                  self.tempfile_file_recovery_0,
                                  stdout=f_sout, stderr=subprocess.STDOUT, shell=True)
            LOGGER.debug('patch_next_file(return code): %r', out)

        else:
            file_db = self.dbm.get_file_from_db_raw(file_id)
            patch_file = open(self.tempfile_patch_tmp, 'w')
            patch_file.write(file_db)
            patch_file.close()

            out = subprocess.call("patch  " +
                                  self.tempfile_file_recovery_0 + " -i  " +
                                  self.tempfile_patch_tmp, stdout=f_sout, stderr=subprocess.STDOUT, shell=True)
            LOGGER.debug('patch_first_file(return code): %r', out)

        for i in cursor:
            id_dba = i["_id"]
            # set prev id in current doc.
            self.prev_id = id_dba
            file_db = self.dbm.get_file_from_db_raw(id_dba)
            patch_file = open(self.tempfile_patch_tmp, 'w')
            patch_file.write(file_db)
            patch_file.close()

            # # gen. tmp all version files
            self.list_tmp_files.append((self.tempfilefd_ver,
                                        self.tempfile_ver +
                                        str(files_count)))

            if BlackListCompacter.generate_all_file:
                # # generate all partial files
                out = subprocess.call("patch  " + self.tempfile_ver +
                                      str(files_count - 1) + " -i  " +
                                      self.tempfile_patch_tmp + " -o " +
                                      self.tempfile_ver + str(files_count),
                                      stdout=f_sout, stderr=subprocess.STDOUT, shell=True)
                os.chmod(self.tempfile_ver + str(files_count), 0644)
                LOGGER.debug('patch_all_files(return code): %r', out)

            else:
                out = subprocess.call(
                    "patch  " + self.tempfile_file_recovery_0 + " -i  " + self.tempfile_patch_tmp,
                    stdout=f_sout, stderr=subprocess.STDOUT, shell=True
                )
                LOGGER.debug('patch(return code): %r', out)

            files_count += 1
        f_sout.close()
        return self.tempfile_file_recovery_0

    def start(self):
        """Start BlackListCompacter."""
        LOGGER.debug('BlackListCompacter.GENERATE_ALL_FILE: %r',
                     BlackListCompacter.generate_all_file)
        LOGGER.debug('BlackListCompacter.PERIOD: %r', BlackListCompacter.period)
        LOGGER.debug('BlackListCompacter.INIT: %r', BlackListCompacter.init)
        file_id = None
        try:
            file_id, cursor = self.get_patches()
            LOGGER.debug('file_id:%r, cursor:%r:', file_id, cursor)
            # count files orig + diffs
            # cursor.count it is ok, if we count from zero(marker=0)
            files_count = cursor.count()

            self.marker_db_diff = files_count
            LOGGER.debug('files_count: %r', files_count)
        except StopIteration, exc:
            # first file
            LOGGER.warning('First file, initialize: %r', exc)
            BlackListCompacter.init = 1
            # init files, set marker = 0
            self.marker_db_diff = self.marker_db_init
            # init file, set prev id = null
            self.prev_id = None

        if file_id:  # patch_start exist
            if files_count <= BlackListCompacter.period:
                # add new patch_diffs.txt in DB
                BlackListCompacter.init = 0
                orig = self.generate_orig_file(cursor, file_id)
                self.save_diff_in_db((orig, self.file_init))
            else:
                # # generate new patch_start.txt, and save to DB
                BlackListCompacter.init = 1
                self.save_diff_in_db((self.tempfile_file, self.file_init))
        else:
            # failure to file patch_start.txt, initialize new cycle
            BlackListCompacter.init = 1
            self.save_diff_in_db((self.tempfile_file, self.file_init))

        self.cleanup()

    def cleanup(self):
        """Cleanup all tmp files."""

        for fd, fn in self.list_tmp_files:
            if os.path.exists(fn):
                os.remove(fn)
        LOGGER.debug('cleanup tmp files')


def main():
    with logging_configured():
        t = DBarchiver()
        try:
            t.run()
        except KeyboardInterrupt:
            LOGGER.debug('SIGINT. waiting for ...')
            t.stop()
        except socket.timeout as exc:
            # at the moment need to capture sys.exit tool for monitoring
            LOGGER.critical('socket.timeout: %r', exc)
            print >> sys.stderr, exc
            sys.exit(1)
        except socket.error as exc:
            # at the moment need to capture sys.exit tool for monitoring
            LOGGER.critical('socket.error: %r', exc)
            print >> sys.stderr, exc
            sys.exit(1)


if __name__ == "__main__":
    main()
