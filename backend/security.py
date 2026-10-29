"""Password scheme adapted from the existing bird-detection-web security module.

Sessions are opaque, revocable and stored only as hashes in SQLite.
"""
import hashlib
import hmac
import secrets
import time


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def hash_password(password, salt=None):
    salt = salt or secrets.token_hex(16)
    hashed = hashlib.pbkdf2_hmac('sha256', password.encode(), bytes.fromhex(salt), 600000)
    return f'{salt}${hashed.hex()}'


def verify_password(password, stored):
    salt, _ = stored.split('$')
    return hmac.compare_digest(hash_password(password, salt), stored)


def media_ticket(session_id, secret):
    body = f'{session_id}.{int(time.time()) + 300}'
    return body + '.' + hmac.new(secret.encode(), body.encode(), hashlib.sha256).hexdigest()


def check_media(ticket, secret):
    try:
        session_id, expires, signature = ticket.split('.')
        body = f'{session_id}.{expires}'
        expected = hmac.new(secret.encode(), body.encode(), hashlib.sha256).hexdigest()
        if int(expires) > time.time() and hmac.compare_digest(signature, expected):
            return session_id
    except (ValueError, AttributeError):
        pass
    return None
