# gen_dev_cert.py
import ipaddress
from datetime import datetime, timedelta
from cryptography import x509
from cryptography.x509.oid import NameOID, ExtendedKeyUsageOID
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa

CERT_PATH = r"C:\certs\dev.crt"
KEY_PATH = r"C:\certs\dev.key"

# 1) генеруємо RSA ключ
key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

# 2) створюємо самопідписаний сертифікат із SAN: лише 127.0.0.1
subject = issuer = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "127.0.0.1")])
san = x509.SubjectAlternativeName(
    [
        x509.IPAddress(ipaddress.IPv4Address("127.0.0.1")),
    ]
)

cert = (
    x509.CertificateBuilder()
    .subject_name(subject)
    .issuer_name(issuer)
    .public_key(key.public_key())
    .serial_number(x509.random_serial_number())
    .not_valid_before(datetime.utcnow() - timedelta(minutes=1))
    .not_valid_after(datetime.utcnow() + timedelta(days=365))
    .add_extension(san, critical=False)
    .add_extension(
        x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]),
        critical=False,
    )
    .add_extension(
        x509.KeyUsage(
            digital_signature=True,
            key_encipherment=True,
            key_cert_sign=False,
            crl_sign=False,
            content_commitment=False,
            data_encipherment=False,
            key_agreement=False,
            encipher_only=False,
            decipher_only=False,
        ),
        critical=False,
    )
    .sign(private_key=key, algorithm=hashes.SHA256())
)

# 3) записуємо приватний ключ (без пароля) і сертифікат у PEM
with open(KEY_PATH, "wb") as f:
    f.write(
        key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )

with open(CERT_PATH, "wb") as f:
    f.write(cert.public_bytes(serialization.Encoding.PEM))

print("OK:", CERT_PATH, KEY_PATH)
