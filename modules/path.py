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
        if not self.query:
            return self.get_node_state()
        elif self.query == 'permission':
            return self.get_permission_state()
        elif self.query == 'ownership':
            return self.get_ownership_state()
        else:
            raise ValueError("Unknown property {!r}".format(self.query))

    def get_node_state(self):
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

    def get_permission_state(self):
        try:
            result = os.lstat(self.path)
        except FileNotFoundError:
            umask = os.umask(0)
            os.umask(umask)
            return '%o' % (0o777 & ~umask)
        return '%o' % (stat.S_IMODE(result.st_mode))

    def set_state(self, current_state):
        if not self.query:
            self.set_node_state(current_state)
        elif self.query == 'permission':
            self.set_permission_state(current_state)
        elif self.query == 'ownership':
            self.set_ownership_state(current_state)
        else:
            raise ValueError("Unknown property {!r}".format(self.query))

    def set_node_state(self, current_state):
        if current_state != 'absent':
            if current_state == 'folder':
                shutil.rmtree(self.path)
            else:
                os.remove(self.path)
        if self.value == 'folder':
            os.mkdir(self.path)
        elif self.value == 'file':
            open(self.path,'w').close()
        elif self.value == 'link':
            pass
