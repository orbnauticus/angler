#!/usr/bin/env python3

from collections import namedtuple
from inspect import getmembers, isclass
from importlib import import_module

import logging
import os
import sqlite3
import sys

try:
    from logcolors.logging import handlers
except ImportError:
    logging.basicConfig(level=logging.INFO)
else:
    logging.basicConfig(handlers=handlers(), level=logging.DEBUG)

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

    def add_node(self, node):
        assert '://' in node.get_uri(), vars(node)
        self.nodes.add(Node(node.get_uri(), node.value))

    def add_edge(self, source, sink):
        self.edges.add(Edge(source.get_uri(), sink.get_uri()))

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


def isstrictsubclass(obj, class_):
    return isclass(obj) and obj is not class_ and issubclass(obj, class_)


class Manifest(object):
    def __init__(self, database):
        self.connection = sqlite3.connect(database)
        self.module_paths = ['modules']

    def insert_node(self, uri, value):
        self.connection.execute(
            """INSERT INTO node VALUES (?,?);""", [uri, value])
        self.connection.commit()

    def insert_edge(self, source, sink):
        self.connection.execute(
            """INSERT INTO edge VALUES (?,?);""", [source, sink])
        self.connection.commit()

    def load_plugins(self):
        logger = logging.getLogger('plugin')
        self.plugins = {}
        for folder in self.module_paths:
            logger.debug('Searching {!r} for plugins'.format(
                os.path.abspath(folder)))
            sys.path.insert(0, folder)
            try:
                for name in os.listdir(folder):
                    if name.endswith('.py'):
                        self.plugins.update(self.retrieve_plugins(name))
            finally:
                del sys.path[0]

    def retrieve_plugins(self, module_name):
        plugins = {}
        logger = logging.getLogger('plugin')
        module = import_module(module_name[:-3])
        for _, value in getmembers(module):
            if isstrictsubclass(value, Plugin):
                for scheme in value.schemes:
                    logger.debug('Found handler for {!r} in {}'.format(
                        scheme, module_name))
                    plugins[scheme] = value
        return plugins

    def run_once(self, swapped=False):
        self.load_plugins()
        logger = logging.getLogger('manifest')
        session = Session(self)
        for node in set(session.nodes):
            scheme = node.uri.partition('://')[0]
            try:
                plugin = self.plugins[scheme]
            except KeyError:
                logger.error('No handler for {!r}'.format(node.uri))
            else:
                plugin.from_node(session, node).found_node()
        for level, stage in enumerate(session):
            for uri, value in sorted(stage, reverse=swapped):
                logger.debug('[{}]:{} = {!r}'.format(level, uri, value))


default_manifest = 'angler.manifest'
