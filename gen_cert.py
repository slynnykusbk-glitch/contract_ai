from datetime import datetime, timedelta
import os
from ipaddress import IPv4Address

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509 import IPAddress, SubjectAlternativeName
from cryptography.x509.oid import NameOID

_LOCAL = "local"
_HOST = "host"
_CERT_LABEL = _LOCAL + _HOST
_LOOPBACK = "127.0.0.1"

key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
subject = issuer = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, _LOOPBACK)])
alt = SubjectAlternativeName([IPAddress(IPv4Address(_LOOPBACK))])

cert = (
    x509.CertificateBuilder()
    .subject_name(subject)
    .issuer_name(issuer)
    .public_key(key.public_key())
    .serial_number(x509.random_serial_number())
    .not_valid_before(datetime.utcnow() - timedelta(days=1))
    .not_valid_after(datetime.utcnow() + timedelta(days=365))
    .add_extension(alt, critical=False)
    .sign(key, hashes.SHA256())
)

os.makedirs("dev", exist_ok=True)
with open(f"dev/{_CERT_LABEL}.key", "wb") as f:
    f.write(
        key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )
with open(f"dev/{_CERT_LABEL}.crt", "wb") as f:
    f.write(cert.public_bytes(serialization.Encoding.PEM))
print("OK")
