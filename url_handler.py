import re
import time
import collections
import urllib.request
import urllib.parse
import feedparser
import json

def urlopen(url):
	headers = {'User-Agent': "the/edgent"}
	req = urllib.request.Request(url, headers=headers)
	return urllib.request.urlopen(req)

class URLHandler(object):
	registry = collections.OrderedDict()

	@classmethod
	def register(cls, pattern):
		def _inner(ncls):
			cls.registry[re.compile(pattern)] = ncls
			return ncls
		return _inner

	@classmethod
	def handle(cls, url, **args):
		print(args)
		for x in reversed(cls.registry):
			if x.match(url):
				return cls.registry[x](url).run(url, **args)

	def __init__(self, url):
		self.url = url

	def run(self, url, **args):
		data = self.get_data(url, **args)
		return self.postprocess(data)

	def get_data(self, url, **args): return urlopen(url)
	def postprocess(self, result): return result

@URLHandler.register('.')
class BasicHandler(URLHandler):
	def get_data(self, url, **args):
		return feedparser.parse(self.url, **args)

@URLHandler.register(r'^http[s]?://(www\.)?reddit.com/r/[^/]*/$')
class RedditJSONHandler(URLHandler):
	def get_data(self, url, **args):
		result = urlopen('%s.json' % url)
		result = result.read().decode(result.headers.get_content_charset())
		return json.loads(result)
	def postprocess(self, data):
		result = feedparser.FeedParserDict()
		desc = urllib.parse.urljoin(self.url, 'about.json')
		desc = urlopen(desc)
		desc = json.loads(desc.read().decode(desc.headers.get_content_charset()))['data']

		result['feed'] = feedparser.FeedParserDict()
		result.feed['title'] = desc['title']
		result.feed['link'] = 'http://reddit.com/%s' % desc['url']
		result['entries'] = []
		result.etag = None
		result.modified = None
		result.status = 200

		for x in data['data']['children']:
			result.entries.append(feedparser.FeedParserDict())
			dat = x['data']
			result.entries[-1]['title'] = dat['title']
			result.entries[-1]['link'] = dat['url']
			result.entries[-1]['published_parsed'] = time.gmtime(dat['created_utc'])
			result.entries[-1]['id'] = dat['id']

		return result

