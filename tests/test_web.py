import io
import tempfile
import unittest
from pathlib import Path
import app as web
from portal import Portal
from modes import Modes

class TestWeb(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.old=(web.DATA,web.portal,web.TOKEN,web.modes)
        web.DATA=Path(self.temp.name);web.portal=Portal(self.temp.name);web.TOKEN='';web.modes=None
        self.addCleanup(self.restore);self.client=web.app.test_client()
    def restore(self):web.DATA,web.portal,web.TOKEN,web.modes=self.old
    def upload(self,data=bytes(1024),name='spyro.bin'):
        return self.client.post('/api/upload',data={'file':(io.BytesIO(data),name)})
    def test_upload_load_write_save_unload_download(self):
        self.assertEqual(self.upload().status_code,200)
        self.assertEqual(self.upload().status_code,409)
        self.assertEqual(self.client.post('/api/load',json={'name':'spyro.bin'}).status_code,200)
        web.portal.command(b'W\x10\x04'+bytes(range(16)))
        self.assertEqual(self.client.post('/api/save').status_code,200)
        response=self.client.get('/api/download/spyro.bin');self.assertEqual(response.data[64:80],bytes(range(16)));response.close()
        self.assertEqual(self.client.post('/api/delete',json={'name':'spyro.bin'}).status_code,409)
        self.assertEqual(self.client.post('/api/unload',json={'slot':1}).status_code,200)
        self.assertEqual(self.client.post('/api/delete',json={'name':'spyro.bin'}).status_code,200)
    def test_invalid_requests_and_offline_status(self):
        self.assertEqual(self.upload(bytes(1025)).status_code,400)
        self.assertEqual(self.client.post('/api/unload',json={}).status_code,400)
        self.assertEqual(self.client.post('/api/load',json={'name':None}).status_code,400)
        self.assertEqual(self.client.get('/api/state').json['usb_connected'],False)
    def test_mode_api_rejects_unavailable_controller_and_protects_writes(self):
        web.modes=Modes(web.portal,web.DATA/'mode.json',prepare=lambda:None)
        self.assertEqual(self.client.post('/api/mode',json={'mode':'controller'}).status_code,400)
        self.assertEqual(self.client.post('/api/mode',json={'mode':'idle'}).status_code,200)
        self.assertEqual(self.client.get('/api/state').json['mode'],'idle')
        self.upload()
        self.assertEqual(self.client.post('/api/load',json={'name':'spyro.bin'}).status_code,409)
        web.TOKEN='test'
        self.assertEqual(self.client.post('/api/mode',json={'mode':'idle'}).status_code,401)

    def test_token_protects_mutations(self):
        web.TOKEN='test';self.assertEqual(self.upload().status_code,401)
        self.assertEqual(self.client.post('/api/save',headers={'X-Portal-Token':'test'}).status_code,200)

if __name__=='__main__':unittest.main()
