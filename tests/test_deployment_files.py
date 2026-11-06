"""Static consistency checks; not a substitute for installing native services."""
from pathlib import Path
import struct
import tomllib
import unittest
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parent.parent

class DeploymentFilesTests(unittest.TestCase):
    def test_templates_are_parseable_consistent_and_include_windows_icon(self):
        for platform in ('linux','windows'):
            with (ROOT/'deployment'/platform/'corevia.toml.example').open('rb') as src:config=tomllib.load(src)
            self.assertEqual(config['environment'],'production');self.assertEqual(config['host'],'127.0.0.1')
            self.assertTrue(config['allowed_hosts']);self.assertTrue(config['allowed_networks'])
        service=ET.parse(ROOT/'deployment/windows/CoreviaServicio.xml.example').getroot()
        self.assertEqual(service.findtext('name'),'Corevia');self.assertEqual(service.findtext('startmode'),'Manual')
        ET.parse(ROOT/'deployment/windows/web.config.example')
        self.assertIn('run_server.py',(ROOT/'deployment/linux/corevia.service').read_text())
        self.assertIn('manage.py backup',(ROOT/'deployment/linux/corevia-backup.service').read_text())
        reserved,kind,count=struct.unpack('<HHH',(ROOT/'static/brand/corevia.ico').read_bytes()[:6])
        self.assertEqual((reserved,kind,count),(0,1,6))

if __name__=='__main__':unittest.main()
