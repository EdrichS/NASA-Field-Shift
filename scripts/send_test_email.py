"""Send one test alert email, to check the SMTP setup end to end.

Usage:  make test-email TO=you@example.com
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.alerts.email import EmailError, mask, send_email  # noqa: E402

TEXT = """This is a test from SowSmart.

When something affects one of your saved fields, alerts will arrive like this one, for example:

  Heavy rain near "Rice field 1": rainfall in the last 3 days was far above normal.
  Source: JAXA GSMaP / NASA GPM. Open the app to see the details and what to check.

You can turn email alerts on or off for each field in the app."""

HTML = """<h2 style="color:#2a6f97">SowSmart test alert</h2>
<p>This is a test from SowSmart. When something affects one of your saved fields, alerts will
arrive like this one, for example:</p>
<blockquote style="border-left:4px solid #2a6f97;padding-left:12px">
<b>Heavy rain near "Rice field 1"</b>: rainfall in the last 3 days was far above normal.<br>
<small>Source: JAXA GSMaP / NASA GPM. Open the app to see the details and what to check.</small>
</blockquote>
<p>You can turn email alerts on or off for each field in the app.</p>"""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--to", required=True, help="recipient email address")
    args = parser.parse_args()
    try:
        send_email(args.to, "SowSmart test alert", TEXT, HTML)
    except EmailError as exc:
        print(f"❌ {exc}")
        return 1
    print(f"✅ Test email sent to {mask(args.to)}. Check the inbox (and spam) in a minute.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
