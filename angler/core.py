#!/usr/bin/env python3

import sqlite3


def setup(database):
    connection = sqlite3.connect(database)
    connection.executescript("""
        CREATE TABLE node(uri TEXT PRIMARY KEY, value TEXT);

        CREATE TABLE edge(
          source NOT NULL REFERENCES node,
          sink NOT NULL REFERENCES node,
          PRIMARY KEY(source, sink) ON CONFLICT REPLACE);

        CREATE VIEW topological_order AS
        WITH RECURSIVE source(uri, level) AS (
            SELECT uri, 0
            FROM node
            WHERE uri NOT IN (SELECT sink FROM `edge`)
        UNION
            SELECT edge.sink, level+1
            FROM source, edge, node as sink
            WHERE source.uri=edge.source AND sink.uri=edge.sink)
        SELECT uri, value, level
        FROM node JOIN source USING(uri)
        GROUP BY uri ORDER BY level, uri;

        CREATE VIEW cycle_first AS
        SELECT * FROM node
        WHERE uri NOT IN (SELECT uri FROM topological_order) LIMIT 1;

        CREATE VIEW cycle AS
        WITH RECURSIVE source(uri) AS (
            SELECT uri FROM cycle_first
        UNION
            SELECT edge.sink FROM source, edge, node as sink
            WHERE source.uri=edge.source AND sink.uri=edge.sink)
        SELECT uri FROM node JOIN source USING(uri);

        """)
    for name in os.listdir('fixture'):
        if name.endswith('.sql'):
            connection.executescript(
                open(os.path.join('fixture', name)).read())


class Manifest(object):
    def __init__(self, database):
        self.connection = sqlite3.connect(database)

    def insert_node(self, uri, value):
        self.connection.execute(
            "INSERT INTO node VALUES (?,?);", [uri, value])
        self.connection.commit()

    def insert_edge(self, source, sink):
        self.connection.execute(
            "INSERT INTO edge VALUES (?,?);", [source, sink])
        self.connection.commit()

    def __iter__(self):
        cursor = self.connection.execute(
            "SELECT level, uri, value FROM topological_order;")
        return iter(cursor)

    def detect_cycle(self):
        cursor = self.connection.execute("""
            SELECT * FROM cycle;
        """)
        return cursor.fetchall()


default_manifest = 'angler.manifest'
