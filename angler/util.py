
import json
import re


def json_or_string(value):
    if value[:1] == '{':
        return json.loads(value)
    else:
        return {value: {}}


def urisplit(uri):
    pattern = "^([a-zA-Z+_-]+)://([^/]*)(/[^?#]*)(?:\?([^#]*))?(?:#(.*))?$"
    match = re.match(pattern, uri)
    if match is None:
        raise ValueError("Unable to parse uri {!r}".format(uri))
    return match.groups()


def urijoin(scheme, host, path, query, fragment):
    if not path.startswith('/'):
        raise ValueError("Invalid 'path': {!r}".format(path))
    return '{scheme}://{host}{path}{query}{fragment}'.format(
        scheme=scheme,
        host=host,
        path=path,
        query=(query or '') and '?' + query,
        fragment=(fragment or '') and '?' + fragment
    )

def uri(value):
    return urijoin(*urisplit(value))

def key_value(string):
    key, successful, value = string.partition('=')
    if not successful:
        raise ValueError("Expected [key]=[value], got {!r}".format(string))
    return key, value
