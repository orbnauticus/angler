
from collections import MutableMapping, defaultdict
from configparser import ConfigParser


class MultiDict(MutableMapping):
    """
    Dict which keeps old items accessible

    >>> MultiDict()
    MultiDict({})
    >>> m = MultiDict([('a', 1), ('b', 2), ('a', 3)])

    >>> m['a']
    3

    >>> m.getall('a')
    [1, 3]

    >>> while True:
    ...   try:
    ...     print(m.popvalue('a'))
    ...   except KeyError:
    ...     break
    3
    1
    """
    def __init__(self, init=(), **kwargs):
        if isinstance(init, MultiDict):
            self._dict = init._dict.__copy__()
        else:
            self._dict = defaultdict(list)
            self.update(init or kwargs)

    def __getitem__(self, key):
        return self._dict[key][-1]

    def __setitem__(self, key, value):
        self._dict[key].append(value)

    def __delitem__(self, key):
        del self._dict[key]

    def __len__(self):
        return len(self._dict)

    def __iter__(self):
        return iter(self._dict)

    def getall(self, key):
        return self._dict[key]

    def popvalue(self, key, index=-1):
        values = self._dict[key]
        if values:
            return values.pop(-1)
        else:
            raise KeyError(key)

    def __repr__(self):
        return '%s(%s)' % (
            self.__class__.__name__,
            dict.__repr__(self._dict))


class Configuration(ConfigParser):
    def __init__(self):
        ConfigParser.__init__(self, dict_type=MultiDict)
