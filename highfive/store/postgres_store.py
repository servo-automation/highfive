from interface import IntegrationStore
from urlparse import urlparse

import json
import psycopg2

DB_JSON_LEN = 10000
DB_KEY_LEN = 100

# FIXME: Revisit this and refactor as necessary. It was hacked to make highfive work in
# Heroku's basic dyno (it's currently not being used by Servo, but when we do, we also need tests!)

class PostgreSqlStore(IntegrationStore):
    '''
    Store backed by PostgreSql database. This maintains a table for each installation, encodes the
    handler's dict object into JSON and writes it as a row in that table. This store is chosen if
    `database_url` key is specified in the config.
    '''

    def __init__(self, database_url):
        super(PostgreSqlStore, self).__init__()
        url = urlparse(database_url)
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
        self.logger.debug('Executing query: %s', query[0] % tuple(query[1:]))
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
        return map(lambda v: int(v[0][2:]), res)    # listing all tables (in the format t_ID)

    def get_object(self, inst_id, key):
        self._execute_query('CREATE TABLE IF NOT EXISTS t_%s ( key varchar(%s), data varchar(%s) )',
                            inst_id, DB_KEY_LEN, DB_JSON_LEN)
        res = self._execute_query('SELECT data FROM t_%s WHERE key = %s', inst_id, key, fetch=True)
        return json.loads(res[0][0]) if res else {}

    def remove_object(self, inst_id, key):
        self._execute_query('DELETE FROM t_%s WHERE key = %s', inst_id, key)

    def write_object(self, data, inst_id, key):
        data = json.dumps(data)
        # There's no easy way to do this (insert/replace) in Postgres
        # (we should execute these simultaneously and hope that no collision occurs)
        res = self._execute_query('SELECT 1 FROM t_%s WHERE key = %s', inst_id, key, fetch=True)
        if res:
            self._execute_query('UPDATE t_%s SET data = %s WHERE key = %s;', inst_id, data, key)
        else:
            self._execute_query('INSERT INTO t_%s VALUES (%s, %s)', inst_id, key, data)
