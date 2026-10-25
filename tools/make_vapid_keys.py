"""Makes the key pair that lets StyleSync send browser push notifications. Run it once and paste the 3 lines into .env.

    python tools/make_vapid_keys.py

The PUBLIC key is given to browsers. The PRIVATE key signs every push message: keep it secret and never commit it.
"""
import base64

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec

key = ec.generate_private_key(ec.SECP256R1())
b64 = lambda raw: base64.urlsafe_b64encode(raw).rstrip(b"=").decode()
print("VAPID_PUBLIC_KEY=" + b64(key.public_key().public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)))
print("VAPID_PRIVATE_KEY=" + b64(key.private_numbers().private_value.to_bytes(32, "big")))
print("VAPID_SUBJECT=mailto:you@example.com")
