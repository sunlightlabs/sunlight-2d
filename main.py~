#!/usr/bin/python

# A template for a Tornado project using forms and MongoDB as the
# backend: takes a form submission and stores it as a record in a
# Mongo DB. Don't forget to start Mongo first with the "mongod"
# command.
#
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

class FormHandler(tornado.web.RequestHandler):
    def get(self):
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
            saved_id = self.db_save(arguments)
            message = "Thanks! Your information was successfully submitted with id %s" % str(saved_id)
        except BaseException, e:
            message = "There was a problem with your form submission:<br>%s" % e
        self.render('thanks.html', message=message)

    def db_save(self, record):
        # default host, port
        db = pymongo.Connection()[DATABASE_NAME]
        table = db[TABLE_NAME]

        # this is pretty simplistic. mongodb doesn't support record
        # keys with a period or a dollar sign in them, so in almost
        # all cases you'd want to parse the record out into a specific
        # set of known keys with values. 
        _id = table.insert(record, safe=True)
        db.connection.disconnect()
        return _id

application = tornado.web.Application([
        (r'/', MainHandler),
        (r'/submit', FormHandler),
        ])

if __name__ == '__main__':
    http_server = tornado.httpserver.HTTPServer(application)
    http_server.listen(8888)
    tornado.ioloop.IOLoop.instance().start()
