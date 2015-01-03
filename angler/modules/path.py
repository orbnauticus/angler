#!/usr/bin/env python3

from angler.plugin import Definition, main

import os
import stat


class Path(Definition):
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
            value={"folder": {}},
        )

    def found_node(self, manifest):
        if self.query:
            base = self.copy(query='', value=None)
            manifest.add_definition(base)
            base.found_node(manifest)
            manifest.add_order(base, self)
        else:
            parent = self.get_parent()
            if parent:
                manifest.add_definition(parent)
                parent.found_node(manifest)
                manifest.add_order(parent, self)

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
            return {'absent': {}}
        if stat.S_ISDIR(mode):
            return {'folder': {}}
        elif stat.S_ISREG(mode):
            return {'file': {}}
        elif stat.S_ISLNK(mode):
            return {'link': {}}
        else:
            return None

    def get_permission_state(self):
        try:
            result = os.lstat(self.path)
        except FileNotFoundError:
            umask = os.umask(0)
            os.umask(umask)
            return {'exact': {'mode': '%o' % (0o777 & ~umask)}}
        return {'exact': {'mode': '%o' % (stat.S_IMODE(result.st_mode))}}

    def set_state(self, old, new):
        if not self.query:
            self.set_node_state(old, new)
        elif self.query == 'permission':
            self.set_permission_state(old, new)
        elif self.query == 'ownership':
            self.set_ownership_state(old, new)
        else:
            raise ValueError("Unknown property {!r}".format(self.query))

    def set_node_state(self, old, new):
        old_key = list(old.keys())[0]
        if old_key != 'absent':
            if old_key == 'folder':
                shutil.rmtree(self.path)
            else:
                os.remove(self.path)
        new_key = list(self.value.keys())[0]
        if new_key == 'folder':
            os.mkdir(self.path)
        elif new_key == 'file':
            open(self.path, 'w').close()
        elif new_key == 'link':
            pass


if __name__ == '__main__':
    main(Path)
