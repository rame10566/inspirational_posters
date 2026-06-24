"""
SSL certificate helper for the Morning Poster approval server.

Generates a self-signed certificate that covers your Mac's current local IP
so the approval server can run on HTTPS and be reached from any device on
your home network.

The cert is regenerated automatically whenever your local IP changes
(e.g. after a router restart assigns a different address).

One-time setup per device:
  Mac    — double-click output/ssl/cert.pem → add to Keychain → mark as "Always Trust"
  iPhone — AirDrop output/ssl/cert.pem to your phone → Settings → General →
           VPN & Device Management → install → then Settings → General →
           About → Certificate Trust Settings → enable full trust
  iPad   — same as iPhone
  Other  — share the cert file and install as a trusted CA
"""

import os
import socket
import subprocess
import tempfile

SSL_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "output", "ssl"
)
CERT_PATH = os.path.join(SSL_DIR, "cert.pem")
KEY_PATH  = os.path.join(SSL_DIR, "key.pem")
IP_PATH   = os.path.join(SSL_DIR, "cert_ip.txt")   # stores the IP the cert was made for


def get_local_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        # Network not available yet (e.g. early boot via launchd).
        # Fall back to the last known IP from the saved cert so we don't
        # trigger a pointless regeneration.
        if os.path.exists(IP_PATH):
            with open(IP_PATH) as f:
                return f.read().strip()
        return "127.0.0.1"


def _cert_is_valid(local_ip: str) -> bool:
    """Return True if the cert exists and was made for the current IP."""
    if not os.path.exists(CERT_PATH) or not os.path.exists(KEY_PATH):
        return False
    if not os.path.exists(IP_PATH):
        return False
    with open(IP_PATH) as f:
        cached_ip = f.read().strip()
    return cached_ip == local_ip


def generate_cert(local_ip: str) -> bool:
    """
    Generate a self-signed certificate that covers:
      • the Mac's current local IP (e.g. 192.168.1.10)
      • 127.0.0.1
      • localhost
    Returns True on success.
    """
    os.makedirs(SSL_DIR, exist_ok=True)

    # Write a temporary OpenSSL config that includes Subject Alternative Names
    config = f"""[req]
default_bits       = 2048
prompt             = no
default_md         = sha256
distinguished_name = dn
x509_extensions    = v3_req

[dn]
CN = MorningPoster

[v3_req]
subjectAltName  = @alt_names
basicConstraints = CA:TRUE
keyUsage         = critical, digitalSignature, keyCertSign, cRLSign

[alt_names]
IP.1  = {local_ip}
IP.2  = 127.0.0.1
DNS.1 = localhost
"""

    with tempfile.NamedTemporaryFile(mode="w", suffix=".cnf", delete=False) as tf:
        tf.write(config)
        config_file = tf.name

    try:
        result = subprocess.run(
            [
                "openssl", "req",
                "-x509",
                "-newkey", "rsa:2048",
                "-keyout", KEY_PATH,
                "-out",    CERT_PATH,
                "-days",   "825",
                "-nodes",
                "-config", config_file,
            ],
            capture_output=True, text=True
        )
        if result.returncode != 0:
            print(f"⚠️  openssl error:\n{result.stderr}")
            return False

        # Save the IP so we know when to regenerate
        with open(IP_PATH, "w") as f:
            f.write(local_ip)

        print(f"🔐  SSL certificate generated for {local_ip}")
        return True

    except FileNotFoundError:
        print("⚠️  openssl not found — cannot generate SSL certificate.")
        return False
    finally:
        os.unlink(config_file)


def ensure_cert() -> tuple[str, str] | None:
    """
    Ensure a valid SSL cert exists for the current local IP.
    Regenerates if the IP has changed or the cert is missing.

    Returns (cert_path, key_path) on success, or None if generation failed.
    """
    local_ip = get_local_ip()

    if not _cert_is_valid(local_ip):
        print(f"🔐  Generating SSL certificate for {local_ip} …")
        if not generate_cert(local_ip):
            return None

    return CERT_PATH, KEY_PATH


def print_trust_instructions(local_ip: str):
    """Print one-time setup instructions for trusting the cert on each device."""
    cert_display = CERT_PATH.replace(
        os.path.expanduser("~"), "~"
    )
    print(f"""
╔══════════════════════════════════════════════════════════════╗
║  One-time SSL trust setup (only needed once per device)      ║
╠══════════════════════════════════════════════════════════════╣
║                                                              ║
║  The cert file is at:                                        ║
║  {cert_display:<60}║
║                                                              ║
║  Mac (this computer):                                        ║
║    1. Double-click the cert.pem file above                   ║
║    2. Keychain Access opens — find "MorningPoster"           ║
║    3. Double-click it → Trust → "Always Trust"               ║
║                                                              ║
║  iPhone / iPad:                                              ║
║    1. AirDrop cert.pem to your device                        ║
║    2. Settings → General → VPN & Device Management          ║
║       → install the profile                                  ║
║    3. Settings → General → About →                          ║
║       Certificate Trust Settings → enable "MorningPoster"   ║
║                                                              ║
║  After trusting once, all future approval links work         ║
║  without any warnings.                                       ║
╚══════════════════════════════════════════════════════════════╝
""")
