#!/usr/bin/env python

# To run:
# ./main.py
# and visit localhost:8888

# todo
# s3 files
# should check to make sure a file with that name does not already
# exist, or change filename to ensure uniqueness
# printing!
# add support for appending to existing tag/story
# add timezone to datetime in response

import tornado.httpserver
import tornado.ioloop
import tornado.web
import urllib, urllib2
import os, datetime, subprocess, uuid
from s3file import s3open
from local_settings import local_settings

try:
    import json
except:
    import simplejson as json
import pymongo

class MainHandler(tornado.web.RequestHandler):
    def get(self):
        self.render('index.html')

class UploadHandler(tornado.web.RequestHandler):
    ''' base class for the web and api handlers. subclasses need to
    implement the self.post_processing() method for any additional
    processing. '''
    def post_processing(self, tag_id):
        ''' implemented by sub class'''
        pass

    def save(self, thistag):
        db = pymongo.Connection()[settings['database']]

        # if there's a file, store it in s3 and replace the file body
        # with the s3 url
        if thistag.get('file', None):
            unique_filename = str(uuid.uuid4())
            file_url = "http://assets.2d.sunlightlabs.com/%s" % unique_filename
            f = s3open(file_url, settings['S3_KEY'], settings['S3_SECRET'])
            f.write(thistag['file'])
            f.close()
            thistag['file'] = file_url

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
            newtag['file'] = self.request.files['file'][0]['body']
            newtag['content_type'] = self.request.files['file'][0]['content_type']

        # save it to the db and create a uri for the content
        try:
            print 'newtag will be created with the following information'
            print newtag
            tag_id = self.save(newtag)
            context['tag_id'] = tag_id
        except BaseException, e:
            print 'there was an error from mongo:'
            print e
            self.write("There was a problem")
            return

        self.post_processing(tag_id)

def jsonify(record):
    ''' takes a record an converts the datetime objects and object ID
    to string, and returns it as a json-encoded string'''
    record['_id'] = str(record['_id'])
    record['last_updated'] = record['last_updated'].strftime("%Y/%m/%d %H:%M:%S")
    items = []
    for item in record['contents']:
        item['created'] = item['created'].strftime("%Y/%m/%d %H:%M:%S")
        items.append(item)
    record['contents'] = items
    js = json.dumps(record)
    return js

def printqr(img_data):    
    # generate the command to print the file. subprocess takes a list
    # or arguments, hence the call to split()
    tmpfile = '/tmp/qrcode.png'
    fp = open(tmpfile, 'w')
    fp.write(img_data)
    fp.close()
    print_file = 'lp -d SUNLIGHT_LABEL_PRINTER -o media=label '.split() + [tmpfile]
    subprocess.call(print_file)
    

class APIUploadHandler(UploadHandler):
    def post_processing(self, tag_id):
        ''' returns a json object with the tag/story contents'''

        record = get_record(self, tag_id)        
        js = jsonify(record)
        print 'will send response:'
        print js
        self.set_header("Content-Type", "application/json")
        self.write(js)
        return

class WebUploadHandler(UploadHandler):
    def post_processing(self, tag_id):

        # generate the qr code and send it to printer
        qr_url = create_qr(tag_uri(tag_id))
        fp = urllib2.urlopen(qr_url)
        qr_data = fp.read()        

        # show the user their newly created story page
        self.redirect('/tag/%s' % str(tag_id))            

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

def get_record(request, tag_id):
    ''' get the record from the db if it exists, and retrieves any
    image associated with the record. returns a dictionary. '''
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
        request.write('''No tag by that name. Perhaps you'd like to <a href="/">create a new one</a>?''')
        return None

    return record

class ViewHandler(tornado.web.RequestHandler):
    def get(self, tag_id):        
        print 'retrieving view info for tag_id %s' % tag_id        
        record = get_record(self, tag_id)
        if not record:
            return
        self.post_processing(record)

    def post_processing(self, record):
        pass

class WebViewHandler(ViewHandler):
    def post_processing(self, record):
        tag_id = str(record['_id'])
        context = { 'qr_url' : create_qr(tag_uri(tag_id)) }
        context['tag_items'] = record['contents']
        self.render('view.html', context=context)        

class APIViewHandler(ViewHandler):
    def post_processing(self, record):
        js = jsonify(record)
        self.set_header("Content-Type", "application/json")
        self.write(js)
        return

# application settings here; private or local settings in
# local_settings.py
settings = {
    'qrx' : 100, #pixels
    'qry' : 100, #pixels,
    'labelx': 0, 
    'labely': 0,
    
}    
settings.update(local_settings)

application = tornado.web.Application([
        (r'/', MainHandler),
        (r'/upload', WebUploadHandler),
        (r'/upload.json', APIUploadHandler),        
        (r'/tag/([\w]+)', WebViewHandler),
        (r'/tag/([\w]+)\.json', APIViewHandler),
        ], cookie_secret="pYqy/FIEQKiXs/2XOlFMQ+GojmHkkUtnvxMxmifRxYA=", **settings)

if __name__ == '__main__':
    http_server = tornado.httpserver.HTTPServer(application)
    http_server.listen(8888)
    tornado.ioloop.IOLoop.instance().start()
