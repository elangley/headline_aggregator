import url_handler
import feedparser
import hashlib
import json
#import redis

class Feed(object):
	@property
	def url(self):
		return self._url
	@url.setter
	def url(self, url):
		self.urlhash = hashlib.md5(url.encode('utf-8')).hexdigest()
		self._url = url

	def __init__(self, title, link, url, etag=None, modified=None, status=0):
		self.urlhash = hashlib.md5(url.encode('utf-8')).hexdigest()
		self.title, self.link, self.url = title, link, url
		print('__init__', 'etag is', etag, 'modified is', modified)
		self.etag = etag
		self.modified = modified
		self.status = int(status)
		self.entries = []
	def add_entry(self, entry):
		if self.entries:
			self.entries[-1].sep = False
		self.entries.append(entry)
		self.entries[-1].sep = True

	def to_redis(self, redis):
		feed_key = self.get_feed_key(self.url)
		object_prefix = '%s:%%s' % feed_key
		print(object_prefix)
		redis.set(feed_key, 'exists')
		redis.set(object_prefix % 'title', self.title)
		redis.set(object_prefix % 'link', self.link)
		redis.set(object_prefix % 'url', self.url)
		redis.set(object_prefix % 'etag', self.etag)
		redis.set(object_prefix % 'modified', self.modified)
		redis.set(object_prefix % 'status', self.status)
		self.put_entries(redis, object_prefix)

	def put_entries(self, redis, object_prefix):
		for entry in reversed(self.entries):
			eid = hashlib.md5(entry.id.encode('utf-8')).hexdigest()
			entry_key = object_prefix % ('entry:%s' % eid)
			redis.sadd(object_prefix % 'entries', eid)
			entry.to_redis(redis, entry_key)

	@classmethod
	def get_feed_key(cls, url):
		return 'feed:%s' % hashlib.md5(url.encode('utf-8')).hexdigest()

	@classmethod
	def from_redis(cls, redis, url):
		feed_key = cls.get_feed_key(url)
		if redis.get(feed_key):
			object_prefix = '%s:%%s' % feed_key
			title = redis.get(object_prefix % 'title').decode('utf-8')
			link = redis.get(object_prefix % 'link').decode('utf-8')
			url = redis.get(object_prefix % 'url').decode('utf-8')
			etag = redis.get(object_prefix % 'etag').decode('utf-8')
			modified = redis.get(object_prefix % 'modified').decode('utf-8')
			status = redis.get(object_prefix % 'status').decode('utf-8')
			self = cls(title, link, url)
			entries = redis.smembers(object_prefix % 'entries')
			for eid in entries:
				eid = eid.decode('utf-8')
				entry_key = object_prefix % ('entry:%s' % eid)
				hl = Headline.from_redis(redis, entry_key)
				if hl is None: break
				else: self.add_entry(hl)

			if self.entries != []:
				self.entries[-1].sep = False
				self.entries.sort(key=lambda x:x.date)
				self.entries[-1].sep = True
			return self

	@classmethod
	def pull_feed(cls, url, etag=None, modified=None):
		print('etag is', etag, 'modified is', modified)
		feed = url_handler.URLHandler.handle(url, etag=etag, modified=modified)
		return cls.from_parsed_feed(feed, url)

	@classmethod
	def from_parsed_feed(cls, data, url):
		title = data.feed.title
		url = url
		link = data.feed.link
		etag = data.etag if hasattr(data, 'etag') else 'No Etag'
		modified = data.modified if hasattr(data, 'modified') else 'No Last Modified'
		print('parsed_feed', 'etag is', etag, 'modified is', modified)
		status = data.status

		self = cls(title, link, url, etag=etag, modified=modified, status=status)

		for entry in data.entries:
			hl = Headline(entry.title, entry.link, date=entry.published_parsed, id=entry.id)
			self.add_entry(hl)
		return self

	@classmethod
	def get_feed(cls, url, redis=None):
		res = None
		update = False
		newfeed = None

		if redis is not None:
			res = cls.from_redis(redis, url)
			if res is not None:
				newfeed = url_handler.URLHandler.handle(url, etag=res.etag, modified=res.modified)
				update = newfeed.status != 304
				print('newfeed.status is', newfeed.status, 'update is', update)

		print('res is', res, 'update is', update, 'url is', url)
		if update or res is None:
			if update:
				updates = cls.from_parsed_feed(newfeed, url)
				object_prefix = '%s:%%s' % cls.get_feed_key(url)
				updates.put_entries(redis, object_prefix)
				print('putting updates!')
				updates.to_redis(redis)
				res = cls.from_redis(redis, url)
			else:
				data = url_handler.URLHandler.handle(url)
				res = cls.from_parsed_feed(data, url)
				res.to_redis(redis)
		return res


class Headline(object):
	@property
	def url(self):
		return self._url
	@url.setter
	def url(self, url):
		self.urlhash = hashlib.md5(url.encode('utf-8')).hexdigest()
		self._url = url

	serialized_attributes = ['title', 'url', 'img', 'id', 'date']
	def __init__(self, title, url, sep=False, img=None, id=None, date=None):
		for x in self.serialized_attributes:
			setattr(self, x, locals()[x])
		self.date = list(self.date)
		self.sep = sep

	def __repr__(self):
		return '<%s>' % ', '.join(str(getattr(self,x)) for x in self.serialized_attributes)
	trans_map = dict(date=json.dumps)
	rtrans_map = { y:x for (x,y) in trans_map.items() }
	def to_redis(self, redis, entry_key):
		redis.set(entry_key, 'exists')
		object_prefix = '%s:%%s' % entry_key
		for x in self.serialized_attributes:
			redis.set(object_prefix % x, self.trans_map.get(x, lambda x:x)(getattr(self, x)))

	@classmethod
	def from_redis(cls, redis, entry_key):
		if redis.get(entry_key) is not None:
			object_prefix = '%s:%%s' % entry_key
			args = {}
			for x in cls.serialized_attributes:
				args[x] = redis.get(object_prefix % x).decode('utf-8')
				args[x] = cls.rtrans_map.get(x, lambda x:x)(args[x])
			return cls(**args)

	@classmethod
	def from_rss(cls, entry):
		name_mapping = dict(
			url='link',
			date='published_parsed',
		)
		self = cls(entry.title, entry.link, id=entry.id, date=entry.published_parsed)

	def to_json(self):
		return json.dumps([self.title, self.link, self.sep, self.img])
	@classmethod
	def from_json(cls, enc):
		enc = json.loads(enc)
		self = cls(*json.loads(enc))

class Feeds(object):
	def __init__(self, urls, redis=None):
		self.feeds = list(filter(None, (Feed.get_feed(url, redis) for url in urls)))
		print(self.feeds)

if __name__ == '__main__':
	import json
	import redis
	print('getting feeds . . .', end=' ')
	with open('blogs.json') as f:
		feeds = json.load(f)
	feeds = Feeds(feeds, redis.Redis())
	print('done.')
