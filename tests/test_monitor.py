import unittest
from monitor import parse_page, jsonld_product
from bs4 import BeautifulSoup

class TestStockDetection(unittest.TestCase):
    def page(self, text, extra=''):
        return f'<html><head><title>Physiolac Bio 1er âge 800g</title></head><body><h1>Physiolac Bio 1er âge 800g</h1>{text}<h2>Description</h2><p>Autres produits en stock</p>{extra}</body></html>'

    def test_clear_in_stock(self):
        result, _ = parse_page(self.page('<p>21,58€</p><p>Faible en stock</p><button>Ajouter au panier</button>'), 'pharmacieveau')
        self.assertEqual(result,'in_stock')

    def test_out_stock_over_other_product(self):
        result, _ = parse_page(self.page('<p>Article bientôt disponible</p><p>En stock</p>'), 'cocooncenter')
        self.assertEqual(result, 'out_of_stock')

    def test_gdd_out(self):
        result, _ = parse_page(self.page('<p>800 g Indisponible</p><button>M’avertir du retour en stock</button>'),'pharma_gdd')
        self.assertEqual(result,'out_of_stock')

    def test_bio_ar_excluded(self):
        result, _ = parse_page('<h1>Physiolac Bio AR 1er âge 800 g</h1><span>En stock</span>','newpharma')
        self.assertEqual(result,'unknown')

    def test_thick_formula_excluded(self):
        result, _ = parse_page('<h1>Physiolac Bio 1 formule épaissie 800 g</h1><span>En stock</span>', 'newpharma')
        self.assertEqual(result, 'unknown')

    def test_second_age_excluded(self):
        result, _ = parse_page('<h1>Physiolac Bio 2 800 g</h1><span>En stock</span>', 'newpharma')
        self.assertEqual(result, 'unknown')

    def test_400g_excluded(self):
        result, _ = parse_page('<h1>Physiolac Bio 1 400 g</h1><span>En stock</span>', 'newpharma')
        self.assertEqual(result, 'unknown')

    def test_non_bio_excluded(self):
        result, _ = parse_page('<h1>Physiolac lait 1er âge 800 g</h1><span>En stock</span>','newpharma')
        self.assertEqual(result,'unknown')

    def test_jsonld(self):
        html = '''<script type="application/ld+json">{"@type":"Product","name":"Physiolac Bio 1er âge 800 g","offers":{"availability":"https://schema.org/InStock"}}</script>'''
        self.assertEqual(jsonld_product(BeautifulSoup(html,'html.parser'))[0],'in_stock')

    def test_unknown(self):
        self.assertEqual(parse_page(self.page('<p>Fiche du lait en poudre</p>'),'atida')[0], 'unknown')

if __name__=='__main__': unittest.main()

class TestChannelsAndLocalCatalogs(unittest.TestCase):
    def test_catalog_never_confirms_stock(self):
        from monitor import fetch_shop
        shop = {'id':'lyon_test','name':'Catalogue local','url':'https://example.org','mode':'catalog','region':'Lyon / métropole'}
        result = fetch_shop(shop)
        self.assertEqual(result['status'], 'unknown')
        self.assertIn('Catalogue', result['reason'])

    def test_900g_excluded(self):
        result, _ = parse_page('<h1>Physiolac Bio 1er âge 900 g</h1><div>En stock</div>','lyon_partdieu')
        self.assertEqual(result, 'unknown')

    def test_jsonld_other_variant_ignored(self):
        html = '''<script type="application/ld+json">{"@type":"Product","name":"Physiolac Bio 2ème âge 800 g","offers":{"availability":"https://schema.org/InStock"}}</script>'''
        self.assertIsNone(jsonld_product(BeautifulSoup(html,'html.parser')))

    def test_no_alert_channel_without_configuration(self):
        from notifications import configured_channels
        from unittest.mock import patch
        with patch.dict('os.environ', {}, clear=True):
            self.assertEqual(configured_channels({}), [])

    def test_ntfy_is_only_configured_if_has_topic(self):
        from notifications import configured_channels
        from unittest.mock import patch
        with patch.dict('os.environ', {'NTFY_TOPIC':'physiolac_abc_123'}, clear=True):
            self.assertEqual(configured_channels({}), ['ntfy'])
