#!/usr/bin/env python

# To run:
# ./main.py
# and visit localhost:8888

# todo
# create tmp dir and cron job to clean tmp dir periodically
# ability to disable printing
# feedback button
# reprint button
# footer telling people where to go to create their own qr code
# "see all" view (all qr codes)
# display error message on index page if it exists
# delineate each section of the story more clearly
# add timezone to datetime in response
# rss feed


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
        # get most recent stories
        tbl = pymongo.Connection()[settings['database']][settings['table']]
        recent = [record for record in tbl.find({"last_updated": {"$exists": True}}).sort("last_updated", pymongo.DESCENDING).limit(4)]

        # check for any error messages
        if self.get_secure_cookie("message"):
            message = self.get_secure_cookie("message")

        self.render('templates/index.html', recent=recent, truncate_words=truncate_words, force_mobile = force_mobile(self.request))

def truncate_words(input_string, length, max_chars=None):
    ''' truncate the input string to the 'length' number of words. If
    max_chars is provided, additionally ensure that the truncated
    string is not longer than max_chars.'''
    words = input_string.split()
    if len(words) > length:
        shortened = ' '.join(words[:length])+'...'
    else: 
        shortened = input_string
    if max_chars and len(shortened) > max_chars:
            return truncate_words(shortened, length-1, max_chars)
    return shortened


class UploadHandler(tornado.web.RequestHandler):
    ''' base class for the web and api handlers. subclasses need to
    implement the self.post_processing() method for any additional
    processing. '''
    def post_processing(self, tag_id):
        ''' implemented by sub class'''
        pass

    def save(self, thistag):
        db = pymongo.Connection()[settings['database']]
        table = db[settings['table']]

        # if there's a file, store it in s3 and replace the file body
        # with the s3 url
        if thistag.get('file', None):
            unique_filename = str(uuid.uuid4())
            file_url = "http://assets.2d.sunlightlabs.com/%s" % unique_filename
            f = s3open(file_url, settings['S3_KEY'], settings['S3_SECRET'])
            f.write(thistag['file'])
            f.close()
            thistag['file'] = file_url    
        thistag['created'] = datetime.datetime.now()

        if not thistag.get('id', None):            
            # create 'contents' as a list of items; people may append
            # content to existing tags
            tag = {'contents': [thistag,],
                   # last_updated will be updated each time a new item is
                   # added to this story
                   'last_updated' : thistag['created'], 
                   'created' : thistag['created'],
                   }        
            _id = table.insert(tag, safe=True)
            
            if self.get_secure_cookie("created"):                
                newvalue = self.get_secure_cookie("created") + "["+str(_id)+"]"
                self.set_secure_cookie("created", newvalue)
            else:
                self.set_secure_cookie("created", "[%s]" % str(_id))

        else:
            _id = pymongo.objectid.ObjectId(thistag.get('id'))
            record = table.find_one({'_id': _id})
            # this is totally not the best way to do this; should
            # design thistag data structure better...
            del thistag['id']
            record['contents'].append(thistag)
            record['last_updated'] = thistag['created']
            table.save(record)            
            if self.get_secure_cookie("updated"):                
                newvalue = self.get_secure_cookie("updated") + "["+str(_id)+"]"
                self.set_secure_cookie("updated", newvalue)
            else:
                self.set_secure_cookie("updated", "[%s]" % str(_id))


        db.connection.disconnect()
        return _id

    def post(self):
        context = {}

        # make sure the user submitted at least one of the fields:
        if self.get_argument('body', "") == "" and not self.request.files.get('file', None):
            self.set_secure_cookie("message", "You must submit either a message or a file")
            self.redirect('/')
            return        

        # build the new tag
        newtag = {}
        if self.get_argument('id', None):
            newtag['id'] = self.get_argument('id')

        if self.get_argument('body', None):
            newtag['body'] = self.get_argument('body')

        if self.request.files.get('file', None):
            newtag['file'] = self.request.files['file'][0]['body']
            newtag['content_type'] = self.request.files['file'][0]['content_type']

        # save it to the db and create a uri for the content
        tag_id = self.save(newtag)
        try:
            print 'newtag will be created with the following information'
            print newtag

            context['tag_id'] = tag_id
        except BaseException, e:
            print 'there was an error from mongo:'
            print e
            self.write("There was a problem: %s" % e)
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

def printqr(tag_id):    
    # generate the command to print the file. subprocess takes a list
    # of arguments, hence the call to split()    
    qr_url = create_qr(tag_uri(tag_id), width=settings['labelx'], height=settings['labely'])
    fp = urllib2.urlopen(qr_url)
    qr_data = fp.read()        
    
    tmpfile = '/tmp/%s.png' % tag_id
    fp = open(tmpfile, 'w')
    fp.write(qr_data)
    fp.close()
    if settings['printing'] == 'enabled':
        print 'printing qr code...'
        print_file = 'lp -d LabelWriter-450-Turbo -o scaling=100 -o position=center'.split() + [tmpfile]
        subprocess.call(print_file)
    else:
        print 'printing disabled. however, tmp file was created: %s' % tmpfile

def force_mobile(request):
    agent = request.headers.get('User-Agent', "")
    return agent.find("iPhone") >= 0 or agent.find("Android") >= 0

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

        # if this is a new tag, generate the qr code and send it
        # to printer
        if not self.get_argument('id', None):
            print 'calling printqr...'
            printqr(tag_id)
        # redirect to the story page
        self.redirect('/tag/%s' % tag_id)

def tag_uri(tag_id):
    uri = settings['root_url'].strip('/') + '/tag/' + str(tag_id)
    return uri

def create_qr(uri, width=100, height=100):        
    args = {
        'chs' : '%dx%d' % (width, height),
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
        context = { 'qr_url' : create_qr(tag_uri(tag_id), width=settings['qrx'], height=settings['qry']) }
        context['record'] = record

        # update our cookie to remove information about this tags
        # status if it exists
        print 'cookie called created'
        print self.get_secure_cookie("created")
        print 'cookie called updated'
        print self.get_secure_cookie("updated")

        marker = "[%s]" % tag_id
        if self.get_secure_cookie("created") and self.get_secure_cookie("created").find(marker) >= 0:
            context['message'] = "Your QR code has been sent to the printer!"
            self.set_secure_cookie("created", self.get_secure_cookie("created").replace(marker,""))
        elif self.get_secure_cookie("updated") and self.get_secure_cookie("updated").find(marker) >= 0:
            context['message'] = "This story has been updated"
            self.set_secure_cookie("updated", self.get_secure_cookie("updated").replace(marker,"")) 

        print 'cookie called created'
        print self.get_secure_cookie("created")
        print 'cookie called updated'
        print self.get_secure_cookie("updated")
            
        self.render('templates/view.html', context=context, force_mobile = force_mobile(self.request))        

class APIViewHandler(ViewHandler):
    def post_processing(self, record):
        js = jsonify(record)
        self.set_header("Content-Type", "application/json")
        self.write(js)
        return

class ReprintHandler(tornado.web.RequestHandler):
    def get(self):
        if self.get_argument('id', None):
            tag_id = self.get_argument('id')
            printqr(tag_id)
        self.redirect('/tag/%s' % tag_id)

# application settings here; private or local settings in
# local_settings.py
settings = {
    'qrx' : 150, #pixels
    'qry' : 150, #pixels,
    'labelx': 200, 
    'labely': 200,
}    
settings.update(local_settings)

application = tornado.web.Application([
        (r'/', MainHandler),
        (r'/upload', WebUploadHandler),
        (r'/upload.json', APIUploadHandler),        
        (r'/tag/([\w]+)', WebViewHandler),
        (r'/tag/([\w]+)\.json', APIViewHandler),
        (r'/reprint', ReprintHandler),
        ], cookie_secret="pYqy/FIEQKiXs/2XOlFMQ+GojmHkkUtnvxMxmifRxYA=", **settings)

if __name__ == '__main__':
    http_server = tornado.httpserver.HTTPServer(application)
    http_server.listen(8888)
    tornado.ioloop.IOLoop.instance().start()
