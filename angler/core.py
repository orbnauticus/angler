#!/usr/bin/env python3

from collections import namedtuple
from inspect import getfile, getmembers, isclass
from importlib import import_module

import json
import logging
import os
import sqlite3
import sys

try:
    from logcolors.logging import handlers
except ImportError:
    logging.basicConfig(level=logging.DEBUG)
else:
    logging.basicConfig(handlers=handlers(), level=logging.DEBUG)

from .plugin import Definition
from .config import Configuration


def setup(database):
    connection = sqlite3.connect(database)
    connection.executescript("""
        DROP TABLE IF EXISTS node;
        CREATE TABLE node(
            uri TEXT PRIMARY KEY,
            value TEXT,
            author TEXT);

        DROP TABLE IF EXISTS edge;
        CREATE TABLE edge(
          source NOT NULL REFERENCES node,
          sink NOT NULL REFERENCES node,
          author TEXT,
          PRIMARY KEY(source, sink) ON CONFLICT REPLACE);
        """)


class CycleError(Exception):
    pass


Edge = namedtuple('Edge', 'source sink author')


class Node(namedtuple('Node', 'uri value author')):
    @classmethod
    def from_sql(cls, row):
        if row is None:
            return
        return cls(row[0], json.loads(row[1]), row[2])

    def __hash__(self):
        return hash(self.uri)

    def __repr__(self):
        return 'Node({!r}, {!r})'.format(*self)


class Session(object):
    def __init__(self, manifest):
        self.nodes = set(Node.from_sql(row) for row in
            manifest.connection.execute(
                """SELECT uri, value, author FROM node"""))
        self.edges = set(Edge(*row) for row in manifest.connection.execute("""
            SELECT source, sink, author FROM edge"""))
        self.logger = logging.getLogger('session')

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


class PluginLoader:
    def __init__(self, manager):
        self.manager = manager
        if getattr(self, 'logger_name', False):
            self.logger = manager.logger.getChild(self.logger_name)
        else:
            self.logger = manager.logger


class PythonPluginLoader(PluginLoader):
    logger_name = 'python'

    def load(self, folder, name):
        sys.path.insert(0, folder)
        try:
            self.load_module(name)
        finally:
            if sys.path[0] == folder:
                del sys.path[0]

    def load_module(self, name):
        module = import_module(name[:-3])
        for class_name, value in getmembers(module):
            if isstrictsubclass(value, Definition):
                for scheme in getattr(value, 'schemes', [class_name.lower()]):
                    self.manager.add(scheme, value)


class PluginManager(dict):
    def __init__(self, searchpaths=None):
        self.searchpaths = searchpaths or []
        self.logger = logging.getLogger('plugin')

    def add(self, scheme, plugin):
        if scheme in self:
            self.logger.critical(
                "Found multiple handlers for {!r}: {} and {}".format(
                    scheme, getfile(self[scheme]), getfile(plugin)))
            exit(1)
        self.logger.debug('Found handler for {!r} in {}'.format(
            scheme, getfile(plugin)))
        self[scheme] = plugin

    def discover(self):
        for folder in self.searchpaths:
            self.logger.debug('Searching {!r} for plugins'.format(
                os.path.abspath(folder)))
            for name in os.listdir(folder):
                path = os.path.join(folder, name)
                if not os.path.isfile(path):
                    continue
                firstline = open(path).readline()
                if firstline.rstrip() == '#!/usr/bin/env python3':
                    PythonPluginLoader(self).load(folder, name)
                else:
                    self.logger.error('Not sure how to load {}'.format(path))

    def definition_from_node(self, node):
        scheme = node.uri.partition('://')[0]
        try:
            plugin = self[scheme]
        except KeyError:
            return None
        return plugin.from_node(node)


class Manifest(object):
    def __init__(self, database):
        self.logger = logging.getLogger('manifest')
        self.settings = Configuration()
        self.database = database
        self.connection = sqlite3.connect(database)
        self.plugins = PluginManager(searchpaths=['modules'])
        self.plugins.discover()

    def add_definition(self, definition):
        self.insert_node(definition.get_uri(), definition.value,
                         definition.get_uri())

    def insert_node(self, uri, value, author=None):
        conflict_node = Node.from_sql(self.connection.execute(
            """SELECT * FROM node WHERE uri=?""", [uri]).fetchone())
        if conflict_node and (value is None or conflict_node.value == value):
            return
        elif conflict_node and conflict_node.value is None:
            pass
        elif conflict_node is not None:
            raise ValueError((uri, conflict_node.value, value))
        else:
            self.logger.debug('Found{} node {} = {!r}'.format(
                '' if author is None else ' automatic', uri, value))
        self.connection.execute(
            """INSERT INTO node(uri,value,author) VALUES (?,?,?);""",
            [uri, json.dumps(value), author])
        self.connection.commit()
        definition = self.plugins.definition_from_node(
            Node(uri, value, author))
        if definition is None:
            self.logger.error('No handler for {!r}'.format(uri))
        else:
            definition.found_node(self)

    def add_order(self, before, after, author=None):
        self.insert_edge(before.get_uri(), after.get_uri(), author)

    def insert_edge(self, source, sink, author=None):
        if self.connection.execute("SELECT * FROM edge WHERE"
                                   " source=? and sink=?", [source, sink]
                                   ).fetchone():
            return
        self.logger.debug('Found{} edge {} -> {}'.format(
            '' if author is None else ' automatic', source, sink))
        self.connection.execute(
            """INSERT INTO edge(source,sink,author) VALUES (?,?,?);""",
            [source, sink, author])
        self.connection.commit()

    def run_once(self, swapped=False, dryrun=False, verify=False):
        session = Session(self)
        self.logger = logging.getLogger('manifest')
        for level, stage in enumerate(session):
            logger = logging.getLogger('stage[{}]'.format(level))
            for node in sorted(stage, reverse=swapped):
                try:
                    definition = self.plugins.definition_from_node(node)
                except Exception as error:
                    logger.exception(
                        "Error loading plugin for {!r}...".format(node.uri))
                if definition is None:
                    logger.error("No handler was found for {!r}".format(
                        node.uri))
                else:
                    self.apply_definition(definition, dryrun=dryrun,
                                          verify=verify, logger=logger)

    def apply_definition(self, definition, dryrun=False, verify=False,
                         logger=None):
        uri = definition.get_uri()
        current_state = definition.get_state()
        if current_state == definition.value:
            if logger:
                logger.debug('Skipping {} with desired state {!r}'.format(
                    uri, current_state))
        elif not dryrun:
            if logger:
                logger.info('Applying {} -> {!r}'.format(
                    uri, definition.value))
            try:
                definition.set_state(current_state)
            except Exception as error:
                if logger:
                    logger.exception(
                        "Error setting state {!r} on {}".format(
                            definition.value, uri))
                else:
                    raise
        else:
            if logger:
                logger.info('Would apply {} -> {!r}'.format(
                    uri, definition.value))


default_manifest = 'angler.manifest'
