# word_addin_dev/gen_dev_certs.py
from datetime import datetime, timedelta
from ipaddress import ip_address
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization.pkcs12 import serialize_key_and_certificates
from cryptography.x509.oid import NameOID

BASE = Path(__file__).resolve().parent
CERTS = BASE / "certs"
CERTS.mkdir(exist_ok=True)

_LABEL = "local" + "host"
_LOOPBACK = "127.0.0.1"

key_path = CERTS / f"{_LABEL}-key.pem"
crt_path = CERTS / f"{_LABEL}.pem"
pfx_path = CERTS / f"{_LABEL}.pfx"
PFX_PASSWORD = "devpass"


def main():
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = issuer = x509.Name(
        [
            x509.NameAttribute(NameOID.COUNTRY_NAME, "UA"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Contract-AI Dev"),
            x509.NameAttribute(NameOID.COMMON_NAME, _LOOPBACK),
        ]
    )
    alt_names = x509.SubjectAlternativeName(
        [
            x509.DNSName(_LOOPBACK),
            x509.IPAddress(ip_address(_LOOPBACK)),
            x509.IPAddress(ip_address("::1")),
        ]
    )
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.utcnow() - timedelta(minutes=1))
        .not_valid_after(datetime.utcnow() + timedelta(days=3650))
        .add_extension(alt_names, critical=False)
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
        .sign(private_key=key, algorithm=hashes.SHA256())
    )
    # PEM/KEY
    key_bytes = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.TraditionalOpenSSL,
        serialization.NoEncryption(),
    )
    crt_bytes = cert.public_bytes(serialization.Encoding.PEM)
    key_path.write_bytes(key_bytes)
    crt_path.write_bytes(crt_bytes)
    # PFX (для імпорту у Windows)
    pfx = serialize_key_and_certificates(
        name=_LOOPBACK.encode("utf-8"),
        key=key,
        cert=cert,
        cas=None,
        encryption_algorithm=serialization.BestAvailableEncryption(PFX_PASSWORD.encode("utf-8")),
    )
    pfx_path.write_bytes(pfx)
    print(f"[OK] Wrote:\n  {crt_path}\n  {key_path}\n  {pfx_path}\nPFX password: {PFX_PASSWORD}")


if __name__ == "__main__":
    main()
