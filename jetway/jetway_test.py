import os
import unittest
import jetway


TEST_BUILD_DIR = os.path.join(
    os.path.dirname(__file__), 'testdata', 'build')


class JetwayTestCase(unittest.TestCase):

  def test_create_fileset(self):
    req = {
        'fileset': {
            'name': 'test',
            'project': {
                'nickname': 'project',
                'owner': {'nickname': 'owner'},
            },
        },
    }
    client = jetway.Jetway(
        project='user@example.com/test',
        name='test',
        host='grow-prod.appspot.com',
        secure=True,)
    resp = client.upload(TEST_BUILD_DIR)
#    resp = client.rpc('filesets.create', req)
#    print resp



if __name__ == '__main__':
  unittest.main()
