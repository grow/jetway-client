import base64
import json
import logging
import md5
import mimetypes
import os
import requests
import threading


class Error(Exception):
  pass


class RpcError(Error):

  def __init__(self, status, data):
    self.status = status
    self.text = data['error_message']
    self.data = data

  def __str__(self):
    return self.text

  def __getitem__(self, name):
    return self.data[name]


class Jetway(object):

  def __init__(self, host, secure=False):
    self.host = host
    self.scheme = 'https' if secure else 'http'
    self.gs = GoogleStorageSigningSession()

  def rpc(self, path, body=None):
    if body is None:
      body = {}
    headers = {'Content-Type': 'application/json'}
    url = '{}://{}/_api/{}'.format(self.scheme, self.host, path)
    resp = requests.post(url, data=json.dumps(body), headers=headers)
    if not (resp.status_code >= 200 and resp.status_code < 205):
      data = resp.json()
      raise RpcError(resp.status_code, data=data)
    return resp.json()

  def upload(self, build_dir):
    fileset = {
        'name': 'test',
        'project': {'ident': '5066549580791808'},
    }
    print build_dir
    paths_to_contents = Jetway._get_paths_to_contents_from_build(build_dir)
    print paths_to_contents
    req = self.gs.create_sign_requests_request(fileset, paths_to_contents)
    resp = self.rpc('filesets.sign_requests', req)
    self._upload_build(resp['signed_requests'], paths_to_contents)

  def _upload_build(self, signed_requests, paths_to_contents):
     # TODO(jeremydw): Thread pool.
     print 'Uploading files...'
     threads = []
     for req in signed_requests:
       file_path = req['path']
       thread = threading.Thread(
           target=self.gs.execute_signed_upload,
           args=(req, paths_to_contents[file_path]))
       threads.append(thread)
       logging.info('Uploading: {}'.format(file_path))
       thread.start()
     for thread in threads:
       thread.join()

  @classmethod
  def _get_paths_to_contents_from_build(cls, build_dir):
    paths_to_contents = {}
    for pre, _, files in os.walk(build_dir):
      for f in files:
        path = os.path.join(pre, f)
        fp = open(path)
        path = path.replace(build_dir, '')
        if not path.startswith('/'):
          path = '/{}'.format(path)
        content = fp.read()
        fp.close()
        if isinstance(content, unicode):
          content = content.encode('utf-8')
        paths_to_contents[path] = content
    return paths_to_contents


class GoogleStorageSigningSession(object):

  @staticmethod
  def create_unsigned_request(verb, path, content=None):
    req = {
      'path': path,
      'verb': verb,
    }
    if verb == 'PUT':
      if path.endswith('/'):
        mimetype = 'text/html'
      else:
        mimetype = mimetypes.guess_type(path)[0]
        mimetype = mimetype or 'application/octet-stream'
      md5_digest = base64.b64encode(md5.new(content).digest())
      req['headers'] = {}
      req['headers']['content_length'] = str(len(content))
      req['headers']['content_md5'] = md5_digest
      req['headers']['content_type'] = mimetype
    return req

  def create_sign_requests_request(self, fileset, paths_to_contents):
    unsigned_requests = []
    for path, content in paths_to_contents.iteritems():
      req = self.create_unsigned_request('PUT', path, content)
      unsigned_requests.append(req)
    return {
        'fileset': fileset,
        'unsigned_requests': unsigned_requests,
    }

  @staticmethod
  def execute_signed_upload(signed_request, content):
    req = signed_request
    params = {
        'GoogleAccessId': req['params']['google_access_id'],
        'Signature': req['params']['signature'],
        'Expires': req['params']['expires'],
    }
    headers = {
        'Content-Type': req['headers']['content_type'],
        'Content-MD5': req['headers']['content_md5'],
        'Content-Length': req['headers']['content_length'],
    }
    resp = requests.put(req['url'], params=params, headers=headers, data=content)
    if not (resp.status_code >= 200 and resp.status_code < 205):
      raise Exception(resp.text)
    return resp
