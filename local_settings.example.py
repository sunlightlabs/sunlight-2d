import os

# copy and rename this to local_settings.py, and fill in the values 
local_settings = {
    'root_url' : "http://example.com",
    'static_path': os.path.join(os.path.dirname(__file__), "static"),
    # set printing value to 'enabled' to enable
    'printing' : 'disabled',
    'database' : 'mydatabase',
    'table' : 'mytable',
    'S3_BUCKET' : "http://mybucket.amazon.com",
    'S3_KEY' : "s3 key here",
    'S3_SECRET' : "s3 secret here"
}
