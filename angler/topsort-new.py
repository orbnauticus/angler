
class CycleError(Exception):
	def __init__(self, members):
		self.members = members

	def __str__(self):
		return 'Cycle detected: %s' % ', '.join(map(repr,self.members))

union = lambda x:reduce(set.union, x, set())

import collections

class Topsort(collections.MutableSet):
	'''
	>>> sorter = Topsort()
	>>> sorter.add('a','b') #a depends on b
	>>> sorter.add('b','d') #b depends on d
	>>> sorter.add('a','c') #a depends on c
	>>> sorter.add('c','d') #c depends on d

	sorter.vertices holds a mapping of elements to sets of their dependencies,
	i.e. the elements that must come before them.

	>>> for k,v in sorted(sorter.vertices.items()):
	...     print k, sorted(v)
	a ['b', 'c']
	b ['d']
	c ['d']
	d []

	Find the order for the whole set by calling resolve after nodes are added

	>>> x = list(sorter)
	>>> x[0]
	'd'
	>>> sorted(x[1:3])
	['b', 'c']
	>>> x[4]
	'a'

	Or search for a subset of the graph by providing a start node

	>>> map(sorted, sorter.resolve('c'))
	[['d'], ['c']]

	If a source change is detected, use cascade to propagate to its dependencies

	>>> map(sorted, sorter.cascade('b'))
	[['b'], ['a']]

	Cycles are automatically detected and reported

	>>> sorter.add('d', 'a') #d depends on a
	>>> map(sorted, sorter.resolve())
	Traceback (most recent call last):
	    ...
	CycleError: Cycle detected: 'a', 'c', 'b', 'd'
	'''
	def __init__(self, vertices=None):
		# self.vertices holds a dictionary which maps elements to a set of
		#   elements that come before them
		self.vertices = dict((k,set(v)) for k,v in (vertices or {}).items())

	def before(self, node):
		return self.vertices[node]

	def after(self, node):
		return set(k for k in self.vertices if node in self.vertices[k])

	def add(self, parent, *children):
		p = self.vertices.setdefault(parent, set())
		for child in children:
			p.add(child)
			self.vertices.setdefault(child, set())

	def discard(self, parent, *children):
		p = self.vertices.setdefault(parent, set())
		for child in children:
			p.discard(child)

	def __contains__(self, (a, b)):
		return a in self.vertices and b in self.vertices[a]

	def __iter__(self):
		nodes = ()
		data = dict(self.vertices)
		if not data:
			return
		extra = union(data.values()) - set(data.keys())
		data.update(dict((item,set()) for item in extra))
		if nodes:
			relevant,children = set(),set(nodes)
			while not children.issubset(relevant):
				relevant.update(children)
				children = union(v for k,v in data.items() if k in relevant)
			data = dict(i for i in data.items() if i[0] in relevant)
		for level in self._sort(data):
			for el in level:
				yield el

	resolve = __iter__

	def __len__(self):
		return sum(len(x) for x in self.vertices.values())

	@staticmethod
	def _sort(data):
		#Performs the grunt work, requires a dict of node:set(dependencies)
		while True:
			ordered = set(item for item,dep in data.items() if not dep)
			if not ordered:
				break
			yield ordered
			data = dict((item,(dep-ordered)) for item,dep in data.items() if item not in ordered)
		if data:
			raise CycleError(data)

	def cascade(self, *nodes):
		if not nodes: return []
		backward = Topsort()
		for key in self.vertices:
			for value in self.vertices[key]:
				backward.add(value, key)
		return reversed(list(backward.resolve(*nodes)))

__all__ = ['Topsort', 'CycleError']

if __name__=='__main__':
	import doctest
	doctest.testmod()
