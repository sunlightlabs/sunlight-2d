#!/usr/bin/python

# To run:
# ./main.py
# and visit localhost:8888

# fix files
# add support for appending to a tag 


import tornado.httpserver
import tornado.ioloop
import tornado.web
import urllib, urllib2
import os, datetime
from gridfs import GridFS

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

class UploadAPIHandler(tornado.web.RequestHandler):
    def post(self):
        pass

class UploadHandler(tornado.web.RequestHandler):
    def post(self):
        context = {}
        # arguments is a dict of key:value pairs where each value is a
        # list (even if there is only one item). 
        form = self.request.arguments
        print 'Arguments were:'
        print form
        print 'files submitted were:'
        print self.request.files

        # make sure the user submitted at least one of the fields:
        if self.get_argument('body', "") == "" and not self.request.files.get('file', None):
            self.set_secure_cookie("message", "You must submit either a message or a file")
            self.redirect('/')
            return        

        # build the new tag
        newtag = {}
        if self.get_argument('body', None):
            newtag['body'] = self.get_argument('body')

        if self.request.files.get('file', None):
            newtag['filebody'] = self.request.files['file'][0]['body']
            newtag['content_type'] = self.request.files['file'][0]['content_type']

        # save it to the db and create a uri for the content
        try:
            print 'newtag will be created with the following information'
            print newtag
            tag_id = self.db_save(newtag)
            context['tag_id'] = tag_id
        except BaseException, e:
            print 'there was an error from mongo:'
            print e
            self.write("There was a problem")
            return

        # generate a qr code with the uri
        context['qr_url'] = create_qr(tag_uri(tag_id))

        # send the qr code to printer

        # show the user their newly created tag
        self.redirect('/tag/%s' % str(tag_id))
            
    def db_save(self, thistag):
        db = pymongo.Connection()[settings['database']]

        # if there's a file, store it using gridFS and replace the
        # file body in thistag, with reference to the file in
        # gridFS (the file_id)
#        if thistag.get('filebody', None):
#            gfs = GridFS(db)
#            file_id = gfs.put(thistag['filebody'], thistag['content_type'])
#            print 'filebody'
#            print thistag['filebody']
#            del thistag['filebody']
#            thistag['file'] = file_id

        # create 'body' as a list; there might be more body
        # elements added if multiple people edit the same tag
        thistag['created'] = datetime.datetime.now()
        tag = {'contents': [thistag,],
               'last_updated' : thistag['created']
               }        
        table = db[settings['table']]
        _id = table.insert(tag, safe=True)
        db.connection.disconnect()
        return _id

def tag_uri(tag_id):
    uri = settings['root_url'].strip('/') + '/tag/' + str(tag_id)
    return uri

def create_qr(uri):        
    args = {
        'chs' : '%dx%d' % (settings['qrx'], settings['qry']),
        'chl' : uri,            
        }
    params = urllib.urlencode(args)
    url = "http://chart.apis.google.com/chart?cht=qr&"+params
    return url

class ViewHandler(tornado.web.RequestHandler):
    def get(self, tag_id):        
        print 'retrieving view info for tag_id %s' % tag_id        
        context = { 'qr_url' : create_qr(tag_uri(tag_id)) }
        table = pymongo.Connection()[settings['database']][settings['table']]        

        try:
            oid = pymongo.objectid.ObjectId(tag_id)
            record = table.find_one({'_id': oid})
            if not record:
                print 'no record with the id %s' % tag_id
                raise Exception
            else:
                print 'tag record retrieved'
                print record
        except BaseException, e:
            print 'there was an error retrieving the record'
            print e
            self.write('''No tag by that name. Perhaps you'd like to <a href="/">create a new one</a>?''')
            return            

        if record.get('file', None):
            gfs = GridFS(db)
            filebody = gfs.get(record.get('file'))  
            record['file'] = filebody.read()
        context['tag_items'] = record['contents']
        self.render('view.html', context=context)        

settings = {
    'qrx' : 100,
    'qry' : 100,
    'root_url' : "http://localhost:8888",
    'database' : 'qrtaggr',
    'table' : 'tags',
}

application = tornado.web.Application([
        (r'/', MainHandler),
        (r'/upload', UploadHandler),
        (r'/upload.json', UploadAPIHandler),
        (r'/tag/([\w]+)', ViewHandler),
        ], cookie_secret="pYqy/FIEQKiXs/2XOlFMQ+GojmHkkUtnvxMxmifRxYA=", **settings)

if __name__ == '__main__':
    http_server = tornado.httpserver.HTTPServer(application)
    http_server.listen(8888)
    tornado.ioloop.IOLoop.instance().start()
