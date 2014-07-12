import base64
import json
import logging
import md5
import mimetypes
import os
import requests
import threading

requests_logger = logging.getLogger('requests')
requests_logger.setLevel(logging.WARNING)


class Error(Exception):
  pass


class Verb(object):
  GET = 'GET'
  PUT = 'PUT'
  DELETE = 'DELETE'


class RpcError(Error):

  def __init__(self, status, message=None, data=None):
    self.status = status
    self.message = data['error_message'] if data else message
    self.data = data

  def __str__(self):
    return self.message

  def __getitem__(self, name):
    return self.data[name]


class GoogleStorageRpcError(RpcError):
  pass


class Jetway(object):

  def __init__(self, project, name, host, secure=False):
    if '/' not in project:
      raise ValueError('Project must be in format: <owner>/<project>')
    self.owner, self.project = project.split('/')
    self.name = name
    self.host = host
    self.scheme = 'https' if secure else 'http'
    self.gs = GoogleStorageSigner()

  @property
  def fileset(self):
    return {
        'name': self.name,
        'project': {'owner': {'nickname': self.owner}, 'nickname': self.project},
    }

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

  def upload_dir(self, build_dir):
    paths_to_contents = Jetway._get_paths_to_contents_from_dir(build_dir)
    return self.write(paths_to_contents)

  def delete(self, paths):
    paths_to_contents = dict([(path, None) for path in paths])
    req = self.gs.create_sign_requests_request(Verb.DELETE, self.fileset, paths_to_contents)
    resp = self.rpc('filesets.sign_requests', req)
    return self._execute_signed_requests(resp['signed_requests'], paths_to_contents)

  def read(self, paths):
    paths_to_contents = dict([(path, None) for path in paths])
    req = self.gs.create_sign_requests_request(Verb.GET, self.fileset, paths_to_contents)
    resp = self.rpc('filesets.sign_requests', req)
    return self._execute_signed_requests(resp['signed_requests'], paths_to_contents)

  def write(self, paths_to_contents):
    req = self.gs.create_sign_requests_request(Verb.PUT, self.fileset, paths_to_contents)
    resp = self.rpc('filesets.sign_requests', req)
    return self._execute_signed_requests(resp['signed_requests'], paths_to_contents)

  def _execute_signed_requests(self, signed_requests, paths_to_contents):
    resps = {}
    errors = {}
    threads = []
    lock = threading.Lock()  # TODO(jeremydw): Thread pool.

    def _execute_signed_request(req, path, content):
      with lock:
        try:
          resps[path] = self.gs.execute_signed_request(req, content)
        except GoogleStorageRpcError as e:
          errors[path] = e

    for req in signed_requests:
      path = req['path']
      thread = threading.Thread(target=_execute_signed_request,
                                args=(req, path, paths_to_contents[path]))
      thread.start()
      threads.append(thread)

    for thread in threads:
      thread.join()

    return resps, errors

  @classmethod
  def _get_paths_to_contents_from_dir(cls, build_dir):
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


class GoogleStorageSigner(object):

  @staticmethod
  def create_unsigned_request(verb, path, content=None):
    req = {
      'path': path,
      'verb': verb,
    }
    if verb == Verb.PUT:
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

  def create_sign_requests_request(self, verb, fileset, paths_to_contents):
    unsigned_requests = []
    for path, content in paths_to_contents.iteritems():
      req = self.create_unsigned_request(verb, path, content)
      unsigned_requests.append(req)
    return {
        'fileset': fileset,
        'unsigned_requests': unsigned_requests,
    }

  @staticmethod
  def execute_signed_request(signed_request, content=None):
    req = signed_request
    params = {
        'GoogleAccessId': req['params']['google_access_id'],
        'Signature': req['params']['signature'],
        'Expires': req['params']['expires'],
    }

    if signed_request['verb'] == Verb.PUT:
      headers = {
          'Content-Type': req['headers']['content_type'],
          'Content-MD5': req['headers']['content_md5'],
          'Content-Length': req['headers']['content_length'],
      }
      resp = requests.put(req['url'], params=params, headers=headers, data=content)

    elif signed_request['verb'] == Verb.GET:
      resp = requests.get(req['url'], params=params)

    elif signed_request['verb'] == Verb.DELETE:
      resp = requests.delete(req['url'], params=params)

    if not (resp.status_code >= 200 and resp.status_code < 205):
      raise GoogleStorageRpcError(resp.status_code, message=resp.content)

    return resp.content
