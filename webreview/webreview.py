from googleapiclient import discovery
from googleapiclient import errors
from multiprocessing import pool
from oauth2client import client
from oauth2client import keyring_storage
from oauth2client import tools
from protorpc import messages
from protorpc import message_types
from protorpc import protojson
import base64
import httplib2
import json
import logging
import md5
import mimetypes
import os
import progressbar
import requests
import threading

# Google API details for a native/installed application for API project grow-prod.
CLIENT_ID = '578372381550-jfl3hdlf1q5rgib94pqsctv1kgkflu1a.apps.googleusercontent.com'
CLIENT_SECRET = 'XQKqbwTg88XVpaBNRcm_tYLf'  # Not so secret for installed apps.
REDIRECT_URI = 'urn:ietf:wg:oauth:2.0:oob'
OAUTH_SCOPES = [
    'https://www.googleapis.com/auth/plus.me',
    'https://www.googleapis.com/auth/userinfo.email',
]

requests_logger = logging.getLogger('requests')
requests_logger.setLevel(logging.WARNING)


class Error(Exception):
  pass


class Verb(object):
  GET = 'GET'
  PUT = 'PUT'
  DELETE = 'DELETE'


class AuthorMessage(messages.Message):
  name = messages.StringField(1)
  email = messages.StringField(2)


class CommitMessage(messages.Message):
  sha = messages.StringField(1)
  author = messages.MessageField(AuthorMessage, 2)
  date = message_types.DateTimeField(3)
  message = messages.StringField(4)
  has_unstaged_changes = messages.BooleanField(5)
  branch = messages.StringField(6)


class HttpWithApiKey(httplib2.Http):

  def __init__(self, *args, **kwargs):
    self.api_key = kwargs.pop('api_key', None)
    super(HttpWithApiKey, self).__init__(*args, **kwargs)

  def _request(self, conn, host, absolute_uri, request_uri, method, body, headers,
               redirections, cachekey):
    if headers is None:
      headers = {}
    if self.api_key is not None:
      headers['WebReview-Api-Key'] = self.api_key
    return super(HttpWithApiKey, self)._request(
        conn, host, absolute_uri, request_uri, method, body, headers,
        redirections, cachekey)


class RpcError(Error):

  def __init__(self, status, message=None, data=None):
    self.status = status
    self.message = data['error_message'] if data else message
    self.data = data

  def __repr__(self):
    return '{}: {}'.format(self.status, self.message)

  def __str__(self):
    return '{}: {}'.format(self.status, self.message)

  def __getitem__(self, name):
    return self.data[name]


class WebReviewRpcError(RpcError):
  pass


class GoogleStorageRpcError(RpcError, IOError):
  pass


class WebReview(object):
  _pool_size = 10

  def __init__(self, project=None, name=None, commit=None, host=None,
               secure=False, username='default', api='webreview',
               version='v0', api_key=None):
    if '/' not in project:
      raise ValueError('Project must be in format: <owner>/<project>')
    self.owner, self.project = project.split('/')
    self.name = name
    self.gs = GoogleStorageSigner()
    self.lock = threading.Lock()
    self.pool = pool.ThreadPool(processes=self._pool_size)
    self.commit = commit
    root = '{}://{}/_ah/api'.format('https' if secure else 'http', host)
    self.api_key = api_key
    self._api = api
    self._version = version
    self._url = '{}/discovery/v1/apis/{}/{}/rest'.format(root, api, version)
    self._service = None

  @property
  def fileset(self):
    commit = None
    if self.commit:
      commit = json.loads(protojson.encode_message(self.commit))
    return {
        'name': self.name,
        'commit': commit,
        'project': {
            'nickname': self.project,
            'owner': {
                'nickname': self.owner,
            },
        },
    }

  def get_service(self, username='default', reauth=False):
    http = HttpWithApiKey(api_key=self.api_key)
    if self.api_key is None:
      credentials = WebReview.get_credentials(username=username, reauth=reauth)
      credentials.authorize(http)
      if credentials.access_token_expired:
        credentials.refresh(http)
    return discovery.build(
        self._api,
        self._version,
        discoveryServiceUrl=self._url,
        http=http)

  def login(self, username='default', reauth=False):
    self._service = self.get_service(username=username, reauth=reauth)

  @property
  def service(self):
    if self._service is not None:
      return self._service
    self._service = self.get_service()
    return self._service

  @staticmethod
  def get_credentials(username, reauth=False):
    storage = keyring_storage.Storage('WebReview Client', username)
    credentials = storage.get()
    if credentials and not credentials.invalid:
      return credentials
    if credentials is None or reauth:
      parser = tools.argparser
      flags, _ = parser.parse_known_args([])
      flow = client.OAuth2WebServerFlow(CLIENT_ID, CLIENT_SECRET, OAUTH_SCOPES,
                                        redirect_uri=REDIRECT_URI)
      credentials = tools.run_flow(flow, storage, flags)
    return credentials

  def upload_dir(self, build_dir):
    paths_to_contents = WebReview._get_paths_to_contents_from_dir(build_dir)
    return self.write(paths_to_contents)

  def delete(self, paths):
    paths_to_contents = dict([(path, None) for path in paths])
    req = self.gs.create_sign_requests_request(Verb.DELETE, self.fileset, paths_to_contents)
    try:
      resp = self.service.sign_requests(body=req).execute()
    except errors.HttpError as e:
      raise WebReviewRpcError(e.resp.status, e._get_reason().strip())
    return self._execute_signed_requests(resp['signed_requests'], paths_to_contents)

  def read(self, paths):
    paths_to_contents = dict([(path, None) for path in paths])
    req = self.gs.create_sign_requests_request(Verb.GET, self.fileset, paths_to_contents)
    try:
      resp = self.service.sign_requests(body=req).execute()
    except errors.HttpError as e:
      raise WebReviewRpcError(e.resp.status, e._get_reason().strip())
    return self._execute_signed_requests(resp['signed_requests'], paths_to_contents)

  def write(self, paths_to_contents):
    req = self.gs.create_sign_requests_request(Verb.PUT, self.fileset, paths_to_contents)
    try:
      resp = self.service.sign_requests(body=req).execute()
    except errors.HttpError as e:
      raise WebReviewRpcError(e.resp.status, e._get_reason().strip())
    return self._execute_signed_requests(resp['signed_requests'], paths_to_contents)

  def finalize(self):
    try:
      req = {'fileset': self.fileset}
      return self.service.finalize(body=req).execute()
    except errors.HttpError as e:
      raise WebReviewRpcError(e.resp.status, e._get_reason().strip())

  def _execute(self, req, path, content, bar, resps, errors):
    error = None
    resp = None
    try:
      resp = self.gs.execute_signed_request(req, content)
    except GoogleStorageRpcError as e:
      error = e
    with self.lock:
      if resp is not None:
        resps[path] = resp
      if error is not None:
        errors[path] = e
    if bar is not None:
      bar.update(bar.currval + 1)

  def _execute_signed_requests(self, signed_requests, paths_to_contents):
    self.pool = pool.ThreadPool(processes=self._pool_size)
    resps = {}
    errors = {}
    num_files = len(signed_requests)
    text = 'Working: %(value)d/{} (in %(elapsed)s)'
    widgets = [progressbar.FormatLabel(text.format(num_files))]
    if num_files > 1:
      bar = progressbar.ProgressBar(widgets=widgets, maxval=num_files)
      bar.start()
      for req in signed_requests:
        path = req['path']
        args = (req, path, paths_to_contents[path], bar, resps, errors)
        self.pool.apply_async(self._execute, args=args)
      self.pool.close()
      self.pool.join()
      bar.finish()
    else:
      req = signed_requests[0]
      path = req['path']
      self._execute(req, path, paths_to_contents[path], None, resps, errors)
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
