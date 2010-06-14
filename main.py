#!/usr/bin/python

# To run:
# ./main.py
# and visit localhost:8888

import tornado.httpserver
import tornado.ioloop
import tornado.web
import urllib, urllib2
import os, datetime
try:
    import json
except:
    import simplejson as json
import pymongo

# settings
DATABASE_NAME = 'demo_database'
TABLE_NAME = 'demo_table'

class MainHandler(tornado.web.RequestHandler):
    def get(self):
        self.render('index.html')

class UploadHandler(tornado.web.RequestHandler):
    database = 'qrtaggr'
    table = 'tags'
    def post(self):
        # arguments is a dict of key:value pairs where each value is a
        # list (even if there is only one item). 
        arguments = self.request.arguments
        print 'Arguments were:'
        print arguments
        # mongo speaks in dicts! so we can just pass the arguments
        # right to the db, but in reality there's some processing
        # here...
        # 
        # then:
        try:
            tag_id = self.db_save(arguments)
        except BaseException, e:
            tag_id = None
        self.render('view.html', tag_id = tag_id)

    def db_save(self, record):
        db = pymongo.Connection()[self.database]
        table = db[self.table]

        _id = table.insert(record, safe=True)
        db.connection.disconnect()
        return _id

class ViewHandler(tornado.web.RequestHandler):
    pass

application = tornado.web.Application([
        (r'/', MainHandler),
        (r'/upload', UploadHandler),
        (r'/[\w]+', ViewHandler),
        ])

if __name__ == '__main__':
    http_server = tornado.httpserver.HTTPServer(application)
    http_server.listen(8888)
    tornado.ioloop.IOLoop.instance().start()
