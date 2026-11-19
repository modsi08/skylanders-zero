import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from flask import Flask
from identity_api import install_identity_routes


class TestIdentityAPI(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.data=bytearray(1024);self.data[:4]=b'TEST'
        self.data[16:19]=(112).to_bytes(3,'little');self.data[28:30]=(4614).to_bytes(2,'little')
        (self.root/'Tree.bin').write_bytes(self.data)
        app=Flask('test');install_identity_routes(app,self.root);self.client=app.test_client()
    def test_header_only_no_metadata_and_no_dump_change(self):
        r=self.client.post('/api/identities',json={'names':['Tree.bin']})
        self.assertEqual(r.status_code,200)
        self.assertEqual(r.json,{'identities':{'Tree.bin':{'character_id':112,'variant_id':4614,'blank':False}}})
        self.assertEqual((self.root/'Tree.bin').read_bytes(),self.data)
    def test_batch_limit_path_validation_missing_and_symlinks(self):
        for names in (None,['Tree.bin']*17,['../Tree.bin'],['/etc/passwd'],['x.original']):
            self.assertEqual(self.client.post('/api/identities',json={'names':names}).status_code,400)
        (self.root/'link.bin').symlink_to(self.root/'Tree.bin')
        r=self.client.post('/api/identities',json={'names':['missing.bin','link.bin']})
        self.assertTrue(all('error' in v for v in r.json['identities'].values()))
    def test_catalogue_is_streamed_not_reencoded_and_javascript_served(self):
        # Existing catalogue matching code must not be used by these routes.
        with patch('catalogue.Catalogue.identify',side_effect=AssertionError('No server lookup')):
            r=self.client.get('/api/catalogue');self.assertEqual(r.status_code,200)
            self.assertEqual(len(r.json['figures']),718);r.close()
            js=self.client.get('/catalogue.js');self.assertIn(b'class FigureCatalogue',js.data);js.close()

if __name__=='__main__':unittest.main()
