#!/usr/bin/env python

class CycleError(Exception):
	def __init__(self, members):
		Exception.__init__(self, 'Cycle detected: %s'%', '.join(map(repr,members)))

class Topsort(object):
	'''
	>>> sorter = Topsort()
	>>> sorter.add('a','b') #a depends on b
	>>> sorter.add('b','d') #b depends on d
	>>> sorter.add('a','c') #a depends on c
	>>> sorter.add('c','d') #c depends on d

	Find the order for the whole set by calling resolve after nodes are added

	>>> map(sorted,sorter.resolve())
	[['d'], ['b', 'c'], ['a']]

	Or search for a subset of the graph by providing a start node

	>>> map(sorted, sorter.resolve('c'))
	[['d'], ['c']]

	If a source change is detected, use cascade to propagate to its dependencies

	>>> map(sorted, sorter.cascade('b'))
	[['b'], ['a']]

	Both resolve and cascade accept multiple arguments

	>>> map(sorted, sorter.cascade('b', 'c'))
	[['b', 'c'], ['a']]

	Cycles are automatically detected and reported

	>>> sorter.add('d', 'a') #d depends on a
	>>> map(sorted, sorter.resolve())
	Traceback (most recent call last):
	    ...
	CycleError: Cycle detected: 'a', 'c', 'b', 'd'
	'''
	def __init__(self, vertices=None):
		self.vertices = dict((k,set(v)) for k,v in (vertices or {}).items())

	def add(self, parent, child):
		if parent not in self.vertices:
			self.vertices[parent] = set()
		self.vertices[parent].add(child)

	def resolve(self, *nodes):
		data = dict(self.vertices)
		extra = reduce(set.union, data.values()) - set(data.keys())
		data.update({item:set() for item in extra})
		if nodes:
			relevant,children = set(),set(nodes)
			while not children.issubset(relevant):
				relevant.update(children)
				children = reduce(set.union,(data[k] for k in data if k in relevant))
			data = dict(i for i in data.items() if i[0] in relevant)
		return self._sort(data)

	def __iter__(self):
		for level in self.resolve():
			for el in level:
				yield el

	def add(self, parent, *children):
		p = self.vertices.setdefault(parent, set())
		for child in children:
			p.add(child)
			self.vertices.setdefault(child, set())

	def discard(self, parent, *children):
		p = self.vertices.setdefault(parent, set())
		for child in children:
			p.discard(child)

	@staticmethod
	def _sort(data):
		#Performs the grunt work, requires a dict of node:set(dependencies)
		while True:
			ordered = set(item for item,dep in data.items() if not dep)
			if not ordered:
				break
			yield ordered
			data = {item:(dep-ordered) for item,dep in data.items() if item not in ordered}
		if data:
			raise CycleError(data)

	def cascade(self, *nodes):
		backward = Topsort()
		for key in self.vertices:
			for value in self.vertices[key]:
				backward.add(value, key)
		return reversed(list(backward.resolve(*nodes)))

if __name__=='__main__':
	import doctest
	doctest.testmod()
