"""Canaux de notifications sans Telegram. Paramètres privés: variables d'environnement / config.json.

Seule une confirmation « in_stock » de la fiche produit exacte peut déclencher
une alerte. Les erreurs de livraison ne sont pas interprétées comme un succès.
"""
from __future__ import annotations

from email.message import EmailMessage
import os
import re
import smtplib
from urllib.parse import urlparse

import requests


def value(name, settings=None):
    settings = settings or {}
    return str(os.environ.get(name, '') or settings.get(name.lower(), '') or '').strip()


def configured_channels(settings=None):
    providers = []
    if value('NTFY_TOPIC', settings): providers.append('ntfy')
    if value('EMAIL_TO', settings) and value('SMTP_HOST', settings) and value('SMTP_USER', settings) and value('SMTP_PASSWORD', settings):
        providers.append('e-mail')
    if value('DISCORD_WEBHOOK_URL', settings): providers.append('Discord')
    if value('PUSHOVER_TOKEN', settings) and value('PUSHOVER_USER', settings): providers.append('Pushover')
    return providers


def send_ntfy(title, body, link, settings=None):
    topic = value('NTFY_TOPIC', settings)
    if not re.fullmatch(r'[A-Za-z0-9_-]{8,64}', topic):
        raise ValueError('NTFY_TOPIC doit contenir 8 à 64 lettres, chiffres, _ ou -')
    base = value('NTFY_BASE_URL', settings) or 'https://ntfy.sh'
    if base != 'https://ntfy.sh' and not (base.startswith('https://') and urlparse(base).hostname):
        raise ValueError('NTFY_BASE_URL doit être une adresse HTTPS valide')
    headers = {'Title': 'Physiolac Bio 1 - ' + ('TEST' if 'test' in title else 'EN STOCK'), 'Priority': 'high', 'Tags': 'baby_bottle', 'Content-Type': 'text/plain; charset=utf-8'}
    if link: headers['Click'] = link
    token = value('NTFY_ACCESS_TOKEN', settings)
    if token: headers['Authorization'] = 'Bearer ' + token
    resp = requests.post(f'{base.rstrip("/")}/{topic}', data=body.encode('utf-8'), headers=headers, timeout=15)
    resp.raise_for_status()


def send_email(title, body, link, settings=None):
    host = value('SMTP_HOST', settings)
    port = int(value('SMTP_PORT', settings) or '587')
    user, password = value('SMTP_USER', settings), value('SMTP_PASSWORD', settings)
    sender = value('EMAIL_FROM', settings) or user
    recipient = value('EMAIL_TO', settings)
    msg = EmailMessage()
    msg['Subject'] = title
    msg['From'] = sender
    msg['To'] = recipient
    msg.set_content(body + (f'\n\nOuvrir la fiche : {link}' if link else ''))
    if port == 465:
        with smtplib.SMTP_SSL(host, port, timeout=18) as smtp:
            smtp.login(user, password)
            smtp.send_message(msg)
    else:
        with smtplib.SMTP(host, port, timeout=18) as smtp:
            smtp.ehlo()
            smtp.starttls()
            smtp.ehlo()
            smtp.login(user, password)
            smtp.send_message(msg)


def send_discord(title, body, link, settings=None):
    url = value('DISCORD_WEBHOOK_URL', settings)
    p = urlparse(url)
    if p.scheme != 'https' or p.hostname not in ('discord.com', 'discordapp.com') or not p.path.startswith('/api/webhooks/'):
        raise ValueError('DISCORD_WEBHOOK_URL non valide')
    r = requests.post(url, json={'content': f'**{title}**\n{body}' + (f'\n{link}' if link else '')}, timeout=15)
    r.raise_for_status()


def send_pushover(title, body, link, settings=None):
    r = requests.post('https://api.pushover.net/1/messages.json', data={
        'token': value('PUSHOVER_TOKEN', settings), 'user': value('PUSHOVER_USER', settings),
        'title': title, 'message': body, 'url': link, 'priority': '1',
    }, timeout=15)
    r.raise_for_status()
    if r.json().get('status') != 1:
        raise ValueError('Pushover a refusé le message')


def notify(shops=None, settings=None, test=False):
    """Return {sent: [], errors: []}, sans exposer les identifiants secrets."""
    shops = shops or []
    title = 'Physiolac Bio 1er âge 800 g — ' + ('test' if test else 'EN STOCK !')
    body = ('Ceci est un test des alertes Physiolac.' if test else '\n'.join(f"✅ {shop['name']}\n{shop['url']}" for shop in shops))
    link = '' if test or not shops else shops[0]['url']
    providers = [('ntfy', 'ntfy', send_ntfy), ('e-mail', 'email', send_email),
                 ('Discord', 'discord', send_discord), ('Pushover', 'pushover', send_pushover)]
    active = set(configured_channels(settings))
    result = {'sent': [], 'errors': []}
    for name, _key, fn in providers:
        if name not in active: continue
        try:
            fn(title, body, link, settings)
            result['sent'].append(name)
        except Exception as exc:
            result['errors'].append(f'{name}: {type(exc).__name__}')
    return result
