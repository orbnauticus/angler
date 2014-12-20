#!/usr/bin/env python3

import os
import sqlite3
from collections import namedtuple
from inspect import getmembers
from importlib import import_module

from .plugin import Plugin


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


Edge = namedtuple('Edge', 'source sink')

Node = namedtuple('Node', 'uri value')


class Session(object):
    def __init__(self, manifest):
        self.nodes = set(Node(*row) for row in manifest.connection.execute("""
            SELECT uri, value FROM node"""))
        self.edges = set(Edge(*row) for row in manifest.connection.execute("""
            SELECT source, sink FROM edge"""))

    def __iter__(self):
        return self

    def __next__(self):
        sinks = set(edge.sink for edge in self.edges)
        nodes_with_no_incoming_edges = set(
            node for node in self.nodes if node.uri not in sinks)
        self.nodes -= nodes_with_no_incoming_edges
        for node in nodes_with_no_incoming_edges:
            self.edges -= set(edge for edge in self.edges
                              if edge.source == node.uri)
        if nodes_with_no_incoming_edges:
            return nodes_with_no_incoming_edges
        elif self.nodes:
            raise CycleError(self.nodes)
        else:
            raise StopIteration


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

    def load_plugins(self):
        handlers = {}
        for name in os.listdir('modules'):
            if name.endswith('.py'):
                module = import_module('modules.{}'.format(name[:-3]))
                for name, value in getmembers(module):
                    if issubclass(value, Plugin):
                        for scheme in value.schemes:
                            handlers[scheme] = value
        return handlers

    def sorted(self):
        return Session(self)


default_manifest = 'angler.manifest'
