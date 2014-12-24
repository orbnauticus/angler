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
            if isstrictsubclass(value, Plugin):
                for scheme in value.schemes:
                    self.logger.debug('Found handler for {!r} in {}'.format(
                        scheme, os.path.join(folder, module_name)))
                    plugins[scheme] = value
        return plugins

    def new_from_node(self, node):
        scheme = node.uri.partition('://')[0]
        plugin = self[scheme]
        return plugin.from_node(node)


class Manifest(object):
    def __init__(self, database):
        self.database = database
        self.connection = sqlite3.connect(database)
        self.plugins = PluginManager(searchpaths=['modules'])
        self.plugins.discover()

    def insert_node(self, uri, value):
        self.connection.execute(
            """INSERT INTO node VALUES (?,?);""", [uri, json.dumps(value)])
        self.connection.commit()

    def insert_edge(self, source, sink):
        self.connection.execute(
            """INSERT INTO edge VALUES (?,?);""", [source, sink])
        self.connection.commit()

    def run_once(self, swapped=False, dryrun=False, verify=False):
        session = Session(self)
        self.logger = logging.getLogger('manifest')
        for node in set(session.nodes):
            try:
                self.plugins.new_from_node(node).found_node(session)
            except KeyError:
                self.logger.error('No handler for {!r}'.format(node.uri))
        for level, stage in enumerate(session):
            for node in sorted(stage, reverse=swapped):
                logger = logging.getLogger('stage[{}]'.format(level))
                try:
                    plugin = self.plugins.new_from_node(node)
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
                elif not dryrun:
                    logger.info('Applying {} -> {!r}'.format(
                        node.uri, node.value))
                    try:
                        plugin.set_state(current_state)
                    except Exception as error:
                        logger.exception(
                            "Error setting state {!r} on {}".format(
                                node.value, node.uri))
                else:
                    logger.info('Would apply {} -> {!r}'.format(
                        node.uri, node.value))


default_manifest = 'angler.manifest'
