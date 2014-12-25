#!/usr/bin/env python3

from collections import namedtuple
from inspect import getmembers, isclass
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


def setup(database):
    connection = sqlite3.connect(database)
    connection.executescript("""
        CREATE TABLE node(
            uri TEXT PRIMARY KEY,
            value TEXT,
            automatic INT DEFAULT 0);

        CREATE TABLE edge(
          source NOT NULL REFERENCES node,
          sink NOT NULL REFERENCES node,
          PRIMARY KEY(source, sink) ON CONFLICT REPLACE);
        """)


class CycleError(Exception):
    pass


Edge = namedtuple('Edge', 'source sink')


class Node(namedtuple('Node', 'uri value')):
    def __hash__(self):
        return hash(self.uri)

    def __repr__(self):
        return 'Node({!r}, {!r})'.format(*self)


class Session(object):
    def __init__(self, manifest):
        self.nodes = set(
            Node(uri, json.loads(value)) for uri, value in
            manifest.connection.execute("""SELECT uri, value FROM node"""))
        self.edges = set(Edge(*row) for row in manifest.connection.execute("""
            SELECT source, sink FROM edge"""))
        self.logger = logging.getLogger('session')

    def add_node(self, node):
        uri = node.get_uri()
        new_node = Node(uri, node.value)
        conflicts = set(node for node in self.nodes
                        if node.uri == new_node.uri)
        if conflicts:
            if new_node.value is None:
                return
            conflict_node = conflicts.pop()
            assert len(conflicts) == 0
            if conflict_node.value is None:
                self.nodes.add(new_node)
            elif conflict_node.value == new_node.value:
                return
            else:
                raise ValueError((uri, conflict_node.value, new_node.value))
        else:
            self.logger.debug('Found automatic node {} = {!r}'.format(
                uri, node.value))
            self.nodes.add(new_node)

    def add_edge(self, source, sink):
        source_uri = source.get_uri()
        sink_uri = sink.get_uri()
        self.logger.debug('Found automatic edge {} -> {}'.format(
            source_uri, sink_uri))
        self.edges.add(Edge(source_uri, sink_uri))

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
    def __init__(self, searchpaths=None):
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
                        self.update(self.load_module_plugins(folder, name))
            finally:
                if sys.path[0] == folder:
                    del sys.path[0]

    def load_module_plugins(self, folder, module_name):
        plugins = {}
        module = import_module(module_name[:-3])
        for _, value in getmembers(module):
            if isstrictsubclass(value, Definition):
                for scheme in value.schemes:
                    self.logger.debug('Found handler for {!r} in {}'.format(
                        scheme, os.path.join(folder, module_name)))
                    plugins[scheme] = value
        return plugins

    def definition_from_node(self, node):
        scheme = node.uri.partition('://')[0]
        try:
            plugin = self[scheme]
        except KeyError:
            return None
        return plugin.from_node(node)


class Manifest(object):
    def __init__(self, database):
        self.database = database
        self.connection = sqlite3.connect(database)
        self.plugins = PluginManager(searchpaths=['modules'])
        self.plugins.discover()

    def insert_node(self, uri, value):
        self.connection.execute(
            """INSERT INTO node(uri,value) VALUES (?,?);""",
            [uri, json.dumps(value)])
        self.connection.commit()

    def insert_edge(self, source, sink):
        self.connection.execute(
            """INSERT INTO edge(source,sink) VALUES (?,?);""", [source, sink])
        self.connection.commit()

    def run_once(self, swapped=False, dryrun=False, verify=False):
        session = Session(self)
        self.logger = logging.getLogger('manifest')
        for node in set(session.nodes):
            definition = self.plugins.definition_from_node(node)
            if definition is None:
                self.logger.error('No handler for {!r}'.format(node.uri))
            else:
                definition.found_node(session)
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
