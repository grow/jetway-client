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
    client = jetway.Jetway('jetway.dev.example.com:8080')
    resp = client.upload(TEST_BUILD_DIR)
#    resp = client.rpc('filesets.create', req)
#    print resp



if __name__ == '__main__':
  unittest.main()
