
import logging
import os

from .shell import Shell, Lookup


class VirtualEntity(object):
    def __init__(self, name, parent):
        self.name = name
        self.parent = parent

    def path(self):
        return ('/'.join((self.parent.path() or '', self.name))
                if self.parent else self.name)


class VirtualFile(object):
    pass


class VirtualFolder(VirtualEntity, dict):
    def __getitem__(self, key):
        first, complex, remainder = key.partition('/')
        if first == '..':
            item = self.parent
        elif first == '.':
            item = self

        else:
            item = dict.__getitem__(self, first)
        if complex:
            return item[remainder]
        return item

    def mkdir(self, name):
        self[name] = VirtualFolder(name, self)


class VFSEntity(object):
    def __init__(self, filesystem, path):
        self.filesystem = filesystem
        self.path = path

    def get_info(self):
        return self.filesystem.get_info(self.path)

    def list_directory(self):
        return self.filesystem.list_directory(self.path)

    def read(self):
        return self.filesystem.read(self.path)

    def is_folder(self):
        info = self.get_info()
        return info['type'] == 'folder'


def subpath(path, child):
    path = path.rstrip('/')
    if child.startswith(path):
        sub = child[len(path):]
        if sub and sub[0] != '/':
            return False
        return sub or '/'
    return False


class VirtualFileSystem(object):
    def __init__(self):
        self.mountpoints = {'':self}

    def list_directory(self, path):
        if path != '/':
            raise FileNotFoundError(path)
        logging.getLogger('vfs').debug('Searching {}'.format(self.mountpoints))
        return sorted(set(point.split('/')[1] for point in self.mountpoints
                          if '/' in point))

    def get_info(self, path):
        if path == '/' or path in self.mountpoints:
            return PathInfo.folder()
        raise FileNotFoundError(path)

    def lookup(self, path):
        subpaths = [(pnt, subpath(pnt, path)) for pnt in self.mountpoints]
        mountpoint, sub = max(((point, sub) for point, sub in subpaths
                                  if sub), key=lambda x:len(x[0]))
        fs = self.mountpoints[mountpoint]
        return VFSEntity(fs, sub)

    def mount(self, point, filesystem):
        if point.endswith('/'):
            point = point.rstrip('/')
        logging.getLogger('vfs').debug("Mounting {} at {}".format(
            filesystem, point))
        self.mountpoints[point] = filesystem


def abspath(path, pwd):
    if path.startswith('/'):
        return os.path.abspath(path)
    else:
        return os.path.normpath(os.path.join(pwd, path))


class PathInfo(dict):
    @classmethod
    def folder(cls):
        return cls(type='folder')

    @classmethod
    def file(cls):
        return cls(type='file')


class SettingsVFS(object):
    def __init__(self, manifest):
        self.manifest = manifest

    def read(self, path):
        if path == '/module_path':
            return self.manifest.plugins.searchpaths

    def get_info(self, path):
        if path == '/':
            return PathInfo.folder()
        elif path == '/module_path':
            return PathInfo.file()

    def list_directory(self, path):
        logging.getLogger('settingsvfs').debug(
            "List directory {}".format(path))
        if path == '/':
            return ['module_path']
        raise FileNotFoundError


class VfsShell(Shell):
    def __init__(self, history, stdin=None, stdout=None, prompt='$',
                 startpath='/', pwdname='pwd', exit_on_error=False):
        Shell.__init__(self, history, stdin=stdin, stdout=stdout,
                       prompt=prompt, exit_on_error=exit_on_error)
        self.vfs_pwd = startpath
        self.vfs_root = VirtualFileSystem()
        if pwdname:
            self.environment[pwdname] = Lookup(self, attr='vfs_pwd')

    def vfs_mount(self, name, filesystem):
        self.vfs_root.mount(name, filesystem)

    def vfs_get_pwd(self):
        return self.vfs_root.lookup(self.vfs_pwd)

    def do_cd(self, args):
        path = args[0]
        if path[0] == '/':
            self.vfs_pwd = self.vfs_root[path].path()
        else:
            self.vfs_pwd = self.vfs_get_pwd()[path].path()

    def do_pwd(self, args):
        print(self.vfs_pwd)

    def do_ls(self, args):
        path = abspath(args[0] if args else '.', self.vfs_pwd)
        for name in self.vfs_root.lookup(path).list_directory():
            print(name)

    def do_find(self, args):
        path = abspath(args[0] if args else '.', self.vfs_pwd)
        def visit(folder):
            children = folder.list_directory()
            logging.debug(str(folder.path)+str(children))
            for name in children:
                logging.debug(os.path.join(folder.path, name))
                entity = self.vfs_root.lookup(os.path.join(folder.path, name))
                print(entity.path)
                if entity.is_folder():
                    visit(entity)
        visit(self.vfs_root.lookup(path))
