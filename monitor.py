"""Physiolac Stock Alert - scrute les fiches en restant conservateur.

Statuts : in_stock, out_of_stock, unknown (le blocage ou l'ambiguïté ne valent
jamais une disponibilité). Pas de contournement de captcha/anti-bot.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import tempfile
from threading import Lock
import time
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup
from notifications import configured_channels, notify

ROOT = Path(__file__).resolve().parent
DATA = ROOT / 'data' / 'status.json'
SHOPS = ROOT / 'shops.json'
CONFIG = ROOT / 'config.json'
EAN = '3518646124167'
TIMEOUT = 18
UA = 'PhysiolacStockAlert/1.0 (personal availability checker; reasonable polling)'
RUN_LOCK = Lock()

NEGATIVE = [
    # Attention aux expressions contenant « en stock » / « disponible » sous
    # une négation : ce sont des ruptures, jamais des preuves de disponibilité.
    r'nous n.avons pas ce produit en stock',
    r'ce produit (?:n.est pas|n.est plus|est non) (?:en stock|disponible)',
    r'(?:pas|plus|non) (?:en stock|disponible)',
    r'aucun(?:e)? (?:produit )?en stock',
    r'ce produit n.est plus disponible', r'article bient[oô]t disponible',
    r'en cours de r[eé]approvisionnement', r'm.alerter du retour en stock',
    r'm.avertir du retour en stock', r'plus disponible [aà] la vente',
    r'rupture de stock', r'[ée]puis[ée]', r'\bindisponible\b',
    r'hors stock', r'out of stock', r'me pr[eé]venir',
]
POSITIVE = [
    r'faible en stock', r'\ben stock\b', r'disponible en ligne',
    r'ajouter au panier', r'\bcommander\b'
]
# Rules for high-confidence text from the primary product block, NOT related products.
SHOP_NEGATIVE = {
    'pharmashopdiscount': [r'ce produit n.est plus disponible'],
    'pharma_gdd': [r'800\s*g\s*indisponible', r'm.avertir du retour en stock'],
    'cocooncenter': [r'article bient[oô]t disponible'],
    'easypara': [r'm.alerter du retour en stock', r'rupture de stock', r'plus disponible [aà] la vente'],
    'lyon_partdieu': [r'nous n.avons pas ce produit en stock'],
}


def utcnow():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def load_json(path, default):
    try:
        return json.loads(Path(path).read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return default


def save_json(path, value):
    path = Path(path)
    path.parent.mkdir(exist_ok=True, parents=True)
    # Atomic replace avoids a half-written API response.
    fd, p = tempfile.mkstemp(dir=path.parent, suffix='.tmp')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump(value, f, ensure_ascii=False, indent=2)
        os.replace(p, path)
    finally:
        if os.path.exists(p):
            os.unlink(p)


def clean(text):
    return re.sub(r'\s+', ' ', text or '').strip()


def jsonld_product(soup):
    """Find stock data belonging to a Product in JSON-LD, not breadcrumbs/cards."""
    def walk(v):
        if isinstance(v, list):
            for x in v:
                yield from walk(x)
        elif isinstance(v, dict):
            t = v.get('@type', '')
            if (isinstance(t, str) and 'Product' in t) or (isinstance(t, list) and 'Product' in t):
                yield v
            for nested in ('@graph', 'mainEntity'):
                if nested in v:
                    yield from walk(v[nested])

    for script in soup.find_all('script', type=re.compile('ld\\+json', re.I)):
        try:
            doc = json.loads(script.string or script.get_text())
        except (ValueError, TypeError):
            continue
        for product in walk(doc):
            title = clean(str(product.get('name', ''))).lower()
            if 'physiolac' not in title or 'bio' not in title:
                continue
            if re.search(r'\bar\b|anti.regurg|[ée]paiss|bio\s*[23]\b|2[eè]me|3[eè]me|2e age|croissance|400\s*g|900\s*g', title, re.I):
                continue
            if not re.search(r'\b1\b|1er|premier|0\s*(?:-|à)\s*6', title) or not re.search(r'800\s*g|800\s*grammes', title):
                continue
            offers = product.get('offers', [])
            if isinstance(offers, dict): offers = [offers]
            for offer in offers:
                if not isinstance(offer, dict): continue
                stock = str(offer.get('availability', '')).lower()
                if 'outofstock' in stock or 'soldout' in stock or 'discontinued' in stock:
                    return 'out_of_stock', 'Donnée structurée du vendeur : rupture'
                if 'instock' in stock or 'limitedavailability' in stock:
                    return 'in_stock', 'Donnée structurée du vendeur : disponible'
    return None


def extract_main_text(soup):
    # Keep content closest to primary product title; cross-sells farther down
    # are not trustworthy for this exact item's availability.
    heading = soup.find('h1')
    if heading:
        chunks = []
        for el in heading.next_elements:
            if getattr(el, 'name', None) in ('h2', 'h3') and ('description' in clean(el.get_text(' ', strip=True)).lower() or 'avis' == clean(el.get_text(' ', strip=True)).lower()):
                break
            if isinstance(el, str) and getattr(el, 'parent', None) and el.parent.name not in ('script', 'style'):
                chunks.append(str(el))
            if len(' '.join(chunks)) >= 2200:
                break
        return clean(' '.join(chunks))[:2200]
    for sel in ('main', '[itemtype*="schema.org/Product"]', '.product-info-main'):
        el = soup.select_one(sel)
        if el: return clean(el.get_text(' ', strip=True))[:2300]
    return clean(soup.get_text(' ', strip=True))[:2200]


def parse_page(html, shop_id):
    soup = BeautifulSoup(html, 'html.parser')
    for element in soup(['script','style','noscript','footer','nav']):
        # Preserve JSON-LD: parse before dropping it.
        if element.name == 'script' and element.get('type', '').lower() == 'application/ld+json':
            continue
        element.decompose()
    title = clean(soup.title.get_text(' ', strip=True)) if soup.title else ''
    h1 = soup.find('h1')
    primary_title = clean(h1.get_text(' ', strip=True)) if h1 else title
    if 'physiolac' not in (primary_title + ' ' + title).lower():
        return 'unknown', 'La fiche produit n’est pas identifiable'
    # Exclude anti-reflux, thickened, second-stage, and regular non-organic variants.
    low = primary_title.lower()
    if re.search(r'\b(?:ar|anti.r[eé]gurg|[ée]paiss|bio\s*[23]\b|2[eè]me|3[eè]me|2e\W*âge|2[èe]me\W*âge|croissance|400\s*g|900\s*g)', low):
        return 'unknown', 'Variante du lait non conforme à la cible'
    if not re.search(r'\bbio\b', low):
        return 'unknown', 'La fiche ne confirme pas la variante Bio'
    if not re.search(r'\b1\b|1er|premier|0\s*(?:-|à)\s*6', low):
        return 'unknown', 'La fiche ne confirme pas le 1er âge'
    if not re.search(r'800\s*g|800\s*grammes', primary_title + ' ' + title, re.I):
        return 'unknown', 'La fiche ne confirme pas la boîte de 800 g'
    ld = jsonld_product(soup)
    body = extract_main_text(soup)
    low_body = body.lower()
    # Seller-specific explicit negative signals outrank generic « en stock »,
    # including the phrase « nous n'avons pas ce produit en stock ».
    for pattern in SHOP_NEGATIVE.get(shop_id, []):
        if re.search(pattern, low_body):
            return 'out_of_stock', 'Rupture indiquée sur la fiche produit'
    # The visible product page can contradict stale JSON-LD availability.
    # Resolve visible, product-scoped negative messages BEFORE considering JSON-LD.
    neg = [p for p in NEGATIVE if re.search(p, low_body)]
    if neg:
        return 'out_of_stock', 'Rupture indiquée sur la fiche produit'
    if ld:
        return ld
    # Without an actual stock phrase, a generic cart button is not sufficient
    # evidence (buttons may remain on sold-out sites).
    pos = [p for p in POSITIVE[:3] if re.search(p, low_body)]
    if pos:
        return 'in_stock', 'Disponibilité mentionnée sur la fiche produit'
    return 'unknown', 'Aucune indication de stock suffisamment fiable'


def fetch_shop(shop):
    result = {**shop, 'status': 'unknown', 'reason': 'Non vérifié', 'checked_at': utcnow()}
    if shop.get('mode') == 'catalog':
        result['reason'] = 'Catalogue local à consulter : stock du produit exact non vérifiable automatiquement'
        return result
    try:
        response = requests.get(shop['url'], timeout=TIMEOUT, headers={
            'User-Agent': 'Mozilla/5.0 (compatible; PhysiolacStockAlert/1.0; personal stock tracker)',
            'Accept-Language': 'fr-FR,fr;q=0.9,en;q=0.5',
            'Accept': 'text/html,application/xhtml+xml',
        }, allow_redirects=True)
        if response.status_code in (403, 429, 503):
            result['reason'] = f'Accès refusé ou limité (HTTP {response.status_code})'
        elif not response.ok:
            result['reason'] = f'Erreur du vendeur (HTTP {response.status_code})'
        elif 'text/html' not in response.headers.get('Content-Type','text/html').lower():
            result['reason'] = 'Réponse inattendue du site'
        else:
            result['status'], result['reason'] = parse_page(response.text, shop['id'])
    except requests.RequestException as exc:
        result['reason'] = f'Connexion impossible : {str(exc)[:110]}'
    return result


def check_all(notify_enabled=True):
    if not RUN_LOCK.acquire(blocking=False):
        return None
    try:
        previous = load_json(DATA, {})
        shops = load_json(SHOPS, [])
        results = []
        with ThreadPoolExecutor(max_workers=4) as pool:
            futures = {pool.submit(fetch_shop, shop): shop for shop in shops}
            for future in as_completed(futures):
                results.append(future.result())
        order = {s['id']: i for i, s in enumerate(shops)}
        results.sort(key=lambda s: order[s['id']])
        # Etat mémorisé même lorsque la fiche passe temporairement à "unknown".
        # Réarmement uniquement après une vraie rupture confirmée.
        latched = previous.get('alerts_latched', {}).copy()
        fresh = []
        for shop in results:
            if shop['status'] == 'out_of_stock':
                latched[shop['id']] = False
            elif shop['status'] == 'in_stock' and not latched.get(shop['id'], False):
                fresh.append(shop)
        checked = utcnow()
        history = previous.get('history', [])
        counts = {s: sum(x['status'] == s for x in results) for s in ('in_stock','out_of_stock','unknown')}
        history.append({'at': checked, **counts})
        settings = load_json(CONFIG, {})
        active = configured_channels(settings)
        last_alert = previous.get('last_alert')
        if notify_enabled and fresh and active:
            sent = notify(fresh, settings=settings)
            last_alert = {'at': checked, 'sent': sent['sent'], 'errors': sent['errors'],
                          'shops': [s['id'] for s in fresh]}
            # Si tous les canaux échouent, le prochain cycle réessaiera.
            if sent['sent']:
                for shop in fresh:
                    latched[shop['id']] = True
        state = {'product': 'Physiolac Bio 1er âge 800 g', 'ean': EAN,
                 'last_check': checked, 'shops': results, 'history': history[-100:],
                 'interval_minutes': 30, 'notification_channels': active,
                 'last_alert': last_alert, 'alerts_latched': latched}
        save_json(DATA, state)
        return state
    finally:
        RUN_LOCK.release()

def main():
    p = argparse.ArgumentParser()
    p.add_argument('--once', action='store_true', help='Effectue une vérification et termine')
    p.add_argument('--test-alert', action='store_true', help='Teste les canaux configurés sans contrôler les stocks')
    args = p.parse_args()
    if args.test_alert:
        report = notify(test=True, settings=load_json(CONFIG, {}))
        print(json.dumps(report, ensure_ascii=False, indent=2))
        if not report['sent']:
            raise SystemExit('Aucune notification de test délivrée. Vérifier les secrets et les journaux.')
        return
    if args.once:
        result = check_all()
        print(json.dumps({'last_check': result['last_check'],
                          'shops': [{'name': s['name'], 'status': s['status'], 'reason': s['reason']} for s in result['shops']]},
                         ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
