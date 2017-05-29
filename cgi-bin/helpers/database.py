from methods import ROOT, get_logger
from urlparse import urlparse

import json, os, psycopg2

DB_JSON_LEN = 10000
DB_KEY_LEN = 100

class Database(object):
    def __init___(self):
        self.logger = get_logger(__name__)

    def get_installations(self):
        raise NotImplementedError

    def get_obj(self, _id, path):
        raise NotImplementedError

    def remove_obj(self, _id, path):
        raise NotImplementedError

    def write_obj(self, _id, path):
        raise NotImplementedError


class JsonStore(Database):
    def __init__(self, config):
        super(JsonStore, self).__init__()
        self.dump_path = config['dump_path']

    def get_installations(self):
        for _id in map(int, os.listdir(self.dump_path)):
            self.logger.debug('Found installation %s in %r, adding it to queue', _id, self.dump_path)
            yield _id

    def get_obj(self, inst_id, key):
        data = {}
        parent = os.path.join(self.dump_path, str(inst_id))
        dump_path = os.path.join(parent, key)
        if os.path.isfile(dump_path):
            with open(dump_path, 'r') as fd:
                self.logger.debug('Loading JSON from %r', dump_path)
                data = json.load(fd)
        return data

    def remove_obj(self, inst_id, key):
        parent = os.path.join(self.dump_path, str(inst_id))
        dump_path = os.path.join(parent, key)
        if os.path.isfile(dump_path):
            self.logger.debug('Removing file %r', dump_path)
            os.remove(dump_path)

    def write_obj(self, data, inst_id, key):
        parent = os.path.join(self.dump_path, str(inst_id))
        if not os.path.isdir(parent):       # dir for each installation
            self.logger.debug('Creating %r for dumping JSONs', parent)
            os.mkdir(parent)
        dump_path = os.path.join(parent, key)
        stem, _base = os.path.split(dump_path)
        with open(dump_path, 'w') as fd:
            self.logger.debug('Dumping JSON to %r', dump_path)
            json.dump(data, fd)


class PostgreSql(Database):
    def __init__(self):
        super(PostgreSql, self).__init__()
        url = urlparse(os.environ['DATABASE_URL'])
        self.kwargs = dict(
            database=url.path[1:],
            user=url.username,
            password=url.password,
            host=url.hostname,
            port=url.port
        )

    def _execute_query(self, *query, **kwargs):
        result = None
        conn = psycopg2.connect(**self.kwargs)
        cursor = conn.cursor()
        self.logger.debug('Executing query %r', query[0] % tuple(query[1:]))
        cursor.execute(query[0], tuple(query[1:]))
        if kwargs.get('fetch'):
            result = cursor.fetchall()
        conn.commit()
        cursor.close()
        conn.close()
        return result

    def get_installations(self):
        res = self._execute_query('''
            SELECT table_name FROM information_schema.tables
            WHERE table_type = 'BASE TABLE' AND table_schema = 'public'
        ''', fetch=True)
        return map(lambda v: int(v[0][2:]), res)    # listing all tables (in the format T_ID)

    def get_obj(self, inst_id, key):
        self._execute_query('CREATE TABLE IF NOT EXISTS T_%s ( key varchar(%s), data varchar(%s) )',
                            inst_id, DB_KEY_LEN, DB_JSON_LEN)
        res = self._execute_query('SELECT data FROM T_%s WHERE key = %s', inst_id, key, fetch=True)
        return json.loads(res[0][0])        # assume only one value exists

    def remove_obj(self, inst_id, key):
        self._execute_query('DELETE FROM T_%s WHERE key = %s', inst_id, key)

    def write_obj(self, data, inst_id, key):
        data = json.dumps(data)
        # There's no easy way to do this (insert/replace) in Postgres
        # (we should execute these simultaneously and hope that no collision occurs)
        self._execute_query('''
            UPDATE T_%s SET data = %s WHERE key = %s;
            INSERT INTO T_%s (key, data)
            SELECT %s, %s
            WHERE NOT EXISTS (SELECT 1 FROM T_%s WHERE key = %s);
        ''', inst_id, data, key, inst_id, key, data, inst_id, key)


def create_db(config):
    return PostgreSql() if os.environ.get('DATABASE_URL') else JsonStore(config)
