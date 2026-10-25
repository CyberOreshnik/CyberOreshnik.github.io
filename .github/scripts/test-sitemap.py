import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('sitemap_audit', Path(__file__).with_name('check-sitemap.py'))
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)

class SitemapSecurityTests(unittest.TestCase):
    def test_complete_expected_sitemap(self):
        xml = '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">' + ''.join('<url><loc>' + url + '</loc></url>' for url in sorted(audit.EXPECTED)) + '</urlset>'
        self.assertEqual(set(audit.check_xml(xml.encode())), audit.EXPECTED)

    def test_dtd_and_entities_are_rejected(self):
        for xml in [b'<!DOCTYPE urlset><urlset/>', b'<!DOCTYPE urlset [<!ENTITY x SYSTEM "file:///etc/passwd">]><urlset>&x;</urlset>']:
            with self.assertRaises(Exception):
                audit.check_xml(xml)

    def test_incomplete_and_oversized_sitemaps_are_rejected(self):
        for xml in [b'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"/>', b' ' * 4000001]:
            with self.assertRaises(ValueError):
                audit.check_xml(xml)

    def test_runtime_checks_survive_optimized_python(self):
        with self.assertRaises(ValueError):
            audit.require(False, 'must reject')

if __name__ == '__main__':
    unittest.main()
