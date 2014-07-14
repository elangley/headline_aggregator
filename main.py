import feedparser
from flask import Flask, url_for, redirect, request, render_template, make_response
import jinja_filters
import json
import logging
import random

app = Flask(__name__)
app.template_filter('mesc')(jinja_filters.markdown_quote)

def count_chars(word):
    special = set('ijltf')
    return sum( (0.5 if l in special else 1) for l in word )

def divide_entries(entries):
    def chars_to_lines(entry):
        title, _, __, is_head, _ = entry
        divisor = 30 if is_head else 43
        char_count = len(title)
        line_count = char_count / divisor
        line_count = max(line_count, 1) # everything always takes at least one line
        return line_count

    tagged_entries = [(chars_to_lines(x), x) for x in entries] # 36: no. chars in line
    total_lines = sum(x for x,_ in tagged_entries)
    target_lines = total_lines / 3

    #target_chars = total_chars / 3
    #average_chars = total_chars // len(entries)

    #target_ents = len(entries) / 3
    #average_target_chars = average_chars * target_ents

    #print(target_chars, average_target_chars)

    #target_chars = (target_chars*2 + average_target_chars*3) // 5

    #print(target_chars)

    columns = [[]]
    accum = 0
    print()
    for n, entry in tagged_entries:
        accum += n
        if (
            (accum > target_lines and len(columns) < 3)
        ):
            columns.append([])
            print(accum)
            accum = accum - target_lines
        columns[-1].append(entry)
    print(accum)
    return columns

import redis
import blog_puller
def get_columns(urls):
    r = redis.Redis()
    feeds = blog_puller.Feeds(urls, r)
    entries = []
    for feed in feeds.feeds:
        entries.append( (feed.title, feed.link, False, True, None) )
        for entry in feed.entries:
            entries.append( (entry.title, entry.url, entry.sep, False, None) )

    return divide_entries(entries)


def get_blogs():
    with open('blogs.json') as f:
        blogs = json.load(f)
    columns = get_columns(blogs)
    for x in columns:
        a,b,_,d, e = x.pop()
        x.append( (a,b,False,d, e) )
    return columns

@app.route("/")
def main(idx=0):
    return render_template('main.html', columns=get_blogs())

@app.route("/<fn>.md")
@app.route("/.md")
def markdown(idx=0, fn=None):
    return  make_response(render_template('markdown.md', columns=get_blogs()),
                200, {'Content-Type': 'text/markdown; charset=utf-8'})

@app.route("/toolbar/<path:url>")
def toolbar(url):
    return render_template('toolbar.html', url=url)

@app.route("/show/<path:url>")
def ope(url=None):
    if url is not None:
        resp = make_response(render_template('frame.html', target_site=url), 200)
        resp.headers['X-Frame-Options'] = 'GOFORIT'
        return resp
    else:
        return 'not found'

app.run('172.16.1.2', debug=True)
