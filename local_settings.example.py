# copy and rename this to local_settings.py, and fill in the values 
local_settings = {
  'root_url' : "http://example.com",
  'static_path': os.path.join(os.path.dirname(__file__), "static"),
  'database' : 'mydatabase',
  'table' : 'mytab;e',
  'S3_BUCKET' : "http://mybucket.amazon.com",
  'S3_KEY' : "s3 key here",
  'S3_SECRET' : "s3 secret here"
}