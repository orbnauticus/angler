#!/usr/bin/env python3

import os
import sqlite3


def setup(database):
    connection = sqlite3.connect(database)
    connection.executescript("""
        CREATE TABLE node(uri TEXT PRIMARY KEY, value TEXT);

        CREATE TABLE edge(
          source NOT NULL REFERENCES node,
          sink NOT NULL REFERENCES node,
          PRIMARY KEY(source, sink) ON CONFLICT REPLACE);
        """)
    for name in os.listdir('modules'):
        if name.endswith('.sql'):
            connection.executescript(
                open(os.path.join('modules', name)).read())


class CycleError(Exception):
    pass


class Manifest(object):
    def __init__(self, database):
        self.connection = sqlite3.connect(database)

    def insert_node(self, uri, value):
        self.connection.execute(
            """INSERT INTO node VALUES (?,?);""", [uri, value])
        self.connection.commit()

    def insert_edge(self, source, sink):
        self.connection.execute(
            """INSERT INTO edge VALUES (?,?);""", [source, sink])
        self.connection.commit()

    def sorted(self):
        self.connection.executescript("""
            CREATE TEMPORARY TABLE node_order(
            source, sink, leaf INT DEFAULT 0);

            INSERT INTO node_order(source, sink)
            SELECT source, sink FROM edge;

            -- Create fake edges so that nodes without outgoing edges are
            --  reported in the final pass

            INSERT INTO node_order(source, leaf)
            SELECT DISTINCT sink, 1 FROM edge;
            """)
        while True:
            nodes_with_no_incoming_edges = set(row for row in
                self.connection.execute("""
                    SELECT DISTINCT source, value
                    FROM node_order, node ON source=uri
                    WHERE source NOT IN (
                        SELECT sink FROM node_order WHERE leaf = 0);
                    """).fetchall())
            if not nodes_with_no_incoming_edges:
                break
            yield nodes_with_no_incoming_edges
            self.connection.execute("""
                DELETE FROM node_order WHERE source NOT IN (
                SELECT sink FROM node_order WHERE leaf = 0);
                """)
        cycle = self.connection.execute("""
            SELECT source, sink FROM node_order WHERE leaf = 0;
            """).fetchall()
        self.connection.execute("""DROP TABLE node_order;""")
        if cycle:
            raise CycleError(cycle)


default_manifest = 'angler.manifest'
