

import collections
from threading import Lock
from Queue import Queue
import copy

class DQueue(object):
	def __init__(self):
		self.items = collections.deque()
		self.lock = Lock()

	def put(self,item):
		with self.lock:
			self.items.append(item)

	def get(self):
		with self.lock:
			return self.items.popleft()

	def peek(self):
		with self.lock:
			return self.items[0]

	def clear(self):
		with self.lock:
			while self.items:
				self.items.pop()

	def __len__(self):
		return len(self.items)

	def __nonzero__(self):
		return bool(self.items)

	def empty(self):
		with self.lock:
			return len(self.items) == 0

## replicating output queue
## new() creates a new DQueue upon
## which all puts to the output are copied
class OutQueue(object):
	def __init__(self):
		self.mux = []

	def put(self,item):
		for queue in self.mux:
			queue.put(copy.deepcopy(item))

	def new(self):
		queue = DQueue()
		self.mux.append(queue)
		return queue

	def clear(self):
		for queue in self.mux:
			while queue:
				queue.pop()



## parent queue that consoldates
## child queues that are attached to it
## this is queue build for centralized 
## order COMSUMPTION from mulitple child queues
class OrderHandler(object):
	def __init__(self):
		self.items = collections.deque()
		self.qbank = {}
		self.qindex = 0
		self.lock = Lock()

	def add_queue(self,queue,owner=None):
		key = owner
		if not key:
			key = self.qindex
			self.qindex += 1
		self.qbank[key] = queue

	def _flush_children(self):
		for queue in self.qbank.values():
			while queue:
				self.items.append(queue.get())

	## push to the parent queue directly
	def put(self,item):
		with self.lock:
			self.items.append(item)

	def get(self):
		with self.lock:
			self._flush_children()
			return self.items.popleft()

	def peek(self):
		with self.lock:
			self._flush_children()
			return self.items[0]

	def clear(self):
		with self.lock:
			self._flush_children()
			while self.items:
				self.items.pop()

	def __nonzero__(self):
		with self.lock:
			self._flush_children()
			return bool(self.items)

	def __len__(self):
		with self.lock:
			self._flush_children()
			return len(self.items)

	def empty(self):
		with self.lock:
			return len(self.items) == 0

## parent queue that consoldates
## child queues that are attached to it
## this is queue build for centralized 
## fill DISTRIBUTION to mulitple child queues
class FillHandler(object):
	def __init__(self):
		## items acts a composite drop-copy of all fills
		self.items = collections.deque()
		self.qbank = {}
		self.lock = Lock()

	def add_queue(self,queue,owner):
		self.qbank[owner] = queue

	## mux out the items put the respective chil;e
	def put(self,item,owner):
		with self.lock:
			queue = self.qbank[owner]
			queue.put(item)
			self.items.append(copy.deepcopy(item))

	def get(self):
		with self.lock:
			return self.items.popleft()

	def peek(self):
		with self.lock:
			return self.items[0]

	def clear(self):
		with self.lock:
			while self.items:
				self.items.pop()

	def __nonzero__(self):
		with self.lock:
			return bool(self.items)

	def __len__(self):
		with self.lock:
			return len(self.items)

	def empty(self):
		with self.lock:
			return len(self.items) == 0




## DataLatch acts a thread barrier
## it blocks until the latch is 'notified'
## the amount of times allocated to self.size
class DataLatch(object):
	def __init__(self,size):
		self.size = size
		self.counter = 0
		self.blocking_queue = Queue(1)
		self.lock = Lock()

	def notify(self):
		## when the counter hits threshold,
		## release the data
		with self.lock:
			self.counter += 1
			if self.counter >= self.size:
				## reset and pop the data cached
				sink = self.blocking_queue.get()
				self.counter = 0

	def trap(self,data):
		## blocks while at capacity (set to 1)
		self.blocking_queue.put(data)


