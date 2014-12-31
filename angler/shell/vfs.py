
from abc import ABCMeta, abstractmethod
from collections import defaultdict
import logging
import os
import re

from .shell import Shell, Lookup


class VirtualEntity(object):
    def __init__(self, hierarchy, filesystem, fspath, path):
        self.hierarchy = hierarchy
        self.filesystem = filesystem
        self.fspath = fspath
        self.path = path

    def get_info(self):
        return self.filesystem.get_info(self.path)

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


def abspath(path, pwd):
    if path.startswith('/'):
        return os.path.abspath(path)
    else:
        return os.path.normpath(os.path.join(pwd, path))


def poproot(path):
    match = re.match("(/[^/]+)(/.*)?", path)
    if match is None:
        raise ValueError('{} did not match /*/*'.format(path))
    return match.groups()


class VirtualFileSystem(metaclass=ABCMeta):
    @abstractmethod
    def get_info(self, path):
        pass

    @abstractmethod
    def get_contents(self, path):
        pass

    @abstractmethod
    def list_directory(self, path):
        pass

    @abstractmethod
    def make_directory(self, path):
        pass

    @abstractmethod
    def write_file(self, path, contents):
        pass

    @abstractmethod
    def read_file(self, path):
        pass


class MemoryVFS(VirtualFileSystem):
    def __init__(self):
        self.paths = dict()
        self.make_directory('/')

    def make_directory(self, path):
        self.paths[path] = PathInfo.folder(), None

    def list_directory(self, path):
        if path not in self.paths:
            raise FileNotFoundError(path)
        for child in self.paths:
            try:
                first, remainder = poproot(child)
            except ValueError:
                continue
            if not remainder:
                yield first[1:]

    def get_info(self, path):
        if path == '/':
            return PathInfo.folder()
        if path in self.paths:
            return self.paths[path]
        raise FileNotFoundError(path)

    def get_contents(self, path):
        return

    def write_file(self, path, contents):
        if path not in self.paths:
            raise FileNotFoundError
        self.paths[path]['content'] = contents

    def read_file(self, path):
        if path not in self.paths:
            raise FileNotFoundError
        return self.paths[path]['content']


class VirtualHierarchy(object):
    def __init__(self, rootfs, pwd):
        self.logger = logging.getLogger('vfs')
        self.pwd = pwd
        self.mountpoints = dict()
        self.mount('/', rootfs)

    def abspath(self, path):
        return abspath(path, self.pwd)

    def get_filesystem_for(self, path):
        subpaths = [(pnt, subpath(pnt, path)) for pnt in self.mountpoints]
        mountpoint, sub = max(((point, sub) for point, sub in subpaths
                                  if sub), key=lambda x:len(x[0]))
        return self.mountpoints[mountpoint], mountpoint, sub

    def lookup(self, path):
        path = self.abspath(path)
        filesystem, basepath, subpath = self.get_filesystem_for(path)
        return VirtualEntity(self, filesystem, basepath, subpath)

    def mount(self, point, filesystem):
        point = self.abspath(point)
        if point.endswith('/'):
            point = point.rstrip('/')
        self.logger.debug("Mounting {} at {}".format(
            filesystem, point or '/'))
        self.mountpoints[point] = filesystem

    def mkdir(self, path):
        filesystem, basepath, subpath = self.get_filesystem_for(path)
        filesystem.make_directory(subpath)

    def walk(self, path):
        def visit(item):
            yield item
            entity = self.lookup(item)
            if entity.is_folder():
                for name in self.list_directory(item):
                    for child in visit(os.path.join(item, name)):
                        yield child
        return iter(visit(abspath(path, self.pwd)))

    def list_directory(self, path):
        filesystem, _, subpath = self.get_filesystem_for(path)
        return filesystem.list_directory(subpath)

    def read_file(self, path):
        path = self.abspath(path)
        self.logger.debug('Reading {}'.format(path))
        filesystem, _, subpath = self.get_filesystem_for(path)
        return filesystem.read_file(subpath)

    def cd(self, path):
        self.pwd = self.abspath(path)
        self.logger.debug('Changed working directory to {}'.format(self.pwd))


class PathInfo(dict):
    @classmethod
    def folder(cls):
        return cls(type='folder')

    @classmethod
    def file(cls):
        return cls(type='file')


class SettingsVFS(VirtualFileSystem):
    def __init__(self, settings):
        self.settings = settings

    def read(self, path):
        if path == '/module_path':
            return self.settings.getall('plugin path')

    def get_info(self, path):
        if path == '/':
            return PathInfo.folder()
        elif path == '/module_path':
            return PathInfo.file()

    def list_directory(self, path):
        if path == '/':
            return ['module_path']
        raise FileNotFoundError

    def list_directory(self, path):
        if path != '/':
            raise FileNotFoundError(path)
        return ['module_path']

    def get_contents(self, path):
        pass

    def make_directory(self, path):
        pass

    def write_file(self, path, contents):
        pass

    def read_file(self, path):
        if path == '/module_path':
            return ['modules']
        raise FileNotFoundError


class VfsShell(Shell):
    def __init__(self, history, stdin=None, stdout=None, prompt='$',
                 startpath='/', pwdname='pwd', exit_on_error=False):
        Shell.__init__(self, history, stdin=stdin, stdout=stdout,
                       prompt=prompt, exit_on_error=exit_on_error)
        self.vfs = VirtualHierarchy(MemoryVFS(), startpath)
        if pwdname:
            self.environment[pwdname] = Lookup(self.vfs, attr='pwd')

    def vfs_get_pwd(self):
        return self.vfs.lookup(self.vfs.pwd)

    def do_cd(self, args):
        self.vfs.cd(args[0] if args else '')

    def do_pwd(self, args):
        print(self.vfs.pwd)

    def do_ls(self, args):
        for name in self.vfs.list_directory(args[0] if args else '.'):
            print(name)

    def do_find(self, args):
        for path in self.vfs.walk(args[0] if args else '.'):
            print(path)

    def do_cat(self, args):
        print(self.vfs.read_file(args[0] if args else '.'))
