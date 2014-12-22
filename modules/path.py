#!/usr/bin/env python

from angler.plugin import Plugin

import os
import stat

class Path(Plugin):
    schemes = ['path']

    def get_parent(self):
        path = os.path.dirname(self.path)
        if path == '/':
            return None
        return Path(
            scheme=self.scheme,
            host=self.host,
            path=path,
            query='',
            fragment='',
            value='folder',
        )

    def found_node(self, session):
        if self.query:
            base = self.copy(query='', value=None)
            session.add_node(base)
            base.found_node(session)
            session.add_edge(base, self)
        else:
            parent = self.get_parent()
            if parent:
                session.add_node(parent)
                parent.found_node(session)
                session.add_edge(parent, self)

    def get_state(self):
        try:
            mode = os.lstat(self.path).st_mode
        except FileNotFoundError:
            return 'absent'
        if stat.S_ISDIR(mode):
            return 'folder'
        elif stat.S_ISREG(mode):
            return 'file'
        elif stat.S_ISLNK(mode):
            return 'link'
        else:
            return None

    def set_state(self, current_state):
        if current_state != 'absent':
            if self.value == 'folder':
                os.mkdir(self.path)

