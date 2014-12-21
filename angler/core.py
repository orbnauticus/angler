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


class PluginManager(dict):
    def __init__(self, session, searchpaths=None):
        self.session = session
        self.searchpaths = searchpaths or []
        self.logger = logging.getLogger('plugin')

    def discover(self):
        for folder in self.searchpaths:
            self.logger.debug('Searching {!r} for plugins'.format(
                os.path.abspath(folder)))
            sys.path.insert(0, folder)
            try:
                for name in os.listdir(folder):
                    if name.endswith('.py'):
                        self.update(self.load_module_plugins(name))
            finally:
                if sys.path[0] == folder:
                    del sys.path[0]

    def load_module_plugins(self, module_name):
        plugins = {}
        module = import_module(module_name[:-3])
        for _, value in getmembers(module):
            if isstrictsubclass(value, Plugin):
                for scheme in value.schemes:
                    self.logger.debug('Found handler for {!r} in {}'.format(
                        scheme, module_name))
                    plugins[scheme] = value
        return plugins

    def new_from_node(self, node):
        scheme = node.uri.partition('://')[0]
        plugin = self[scheme]
        return plugin.from_node(self.session, node)


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

    def run_once(self, swapped=False, plugin_paths=['modules']):
        session = Session(self)
        plugins = PluginManager(session, plugin_paths)
        plugins.discover()
        self.logger = logging.getLogger('manifest')
        for node in set(session.nodes):
            try:
                plugins.new_from_node(node).found_node()
            except KeyError:
                self.logger.error('No handler for {!r}'.format(node.uri))
        for level, stage in enumerate(session):
            for node in sorted(stage, reverse=swapped):
                logger = logging.getLogger('stage[{}]'.format(level))
                try:
                    plugin = plugins.new_from_node(node)
                except KeyError as error:
                    logger.error("No handler was found for {!r}".format(
                        error.args[0]))
                    continue
                except Exception as error:
                    logger.exception(
                        "Error loading plugin for {!r}...".format(node.uri))
                    continue
                current_state = plugin.get_state()
                if current_state == node.value:
                    logger.debug('Skipping {} with desired state {!r}'.format(
                        node.uri, current_state))
                else:
                    logger.info('Applying {} -> {!r}'.format(
                        node.uri, node.value))
                    try:
                        plugin.set_state()
                    except Exception as error:
                        logger.exception(
                            "Error setting state {!r} on {}".format(
                                node.value, node.uri))



default_manifest = 'angler.manifest'
