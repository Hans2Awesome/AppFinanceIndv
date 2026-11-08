"""Ledger-styled plain-text and HTML password-reset email template."""

from __future__ import annotations

import html

_SERIF_STACK = "Georgia, 'Times New Roman', Times, serif"
_SANS_STACK = (
    "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif"
)
_MONO_STACK = (
    "ui-monospace, SFMono-Regular, 'SF Mono', Menlo, Consolas, 'Liberation Mono', monospace"
)


def render_password_reset_email(code: str) -> tuple[str, str]:
    """Return (plain_text, html_body) for a password-reset verification code.

    The dynamic code is HTML-escaped and never included in the hidden preheader.
    """

    raw_code = str(code).strip()
    safe_code = html.escape(raw_code, quote=True)

    plain_text = (
        "Bot04 / Finance App - Password reset\n"
        "----------------------------------------\n\n"
        f"Your password reset code is: {raw_code}\n\n"
        "Enter this 6-digit code on the password reset screen in Finance App.\n"
        "This code expires in 10 minutes and can only be used once.\n\n"
        "Security notice:\n"
        "- Never share this code with anyone.\n"
        "- If you did not request a password reset, you can safely ignore this email. "
        "Requesting a code does not change your password.\n"
    )

    html_body = f"""<!DOCTYPE html>
<html lang="en" xmlns="http://www.w3.org/1999/xhtml">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <meta http-equiv="X-UA-Compatible" content="IE=edge">
  <meta name="x-apple-disable-message-reformatting">
  <meta name="format-detection" content="telephone=no,address=no,email=no,date=no,url=no">
  <title>Finance App password reset</title>
</head>
<body style="margin:0;padding:0;background-color:#F2F0E9;color:#171A16;-webkit-text-size-adjust:100%;-ms-text-size-adjust:100%;">
  <div style="display:none;max-height:0;max-width:0;overflow:hidden;opacity:0;font-size:1px;line-height:1px;color:#F2F0E9;mso-hide:all;">
    Password reset request for your Bot04 / Finance App account. Valid for 10 minutes.
  </div>
  <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%" style="width:100%;border-collapse:collapse;background-color:#F2F0E9;margin:0;padding:0;">
    <tr>
      <td align="center" style="padding:32px 16px;">
        <!--[if mso]>
        <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="560" align="center">
        <tr>
        <td>
        <![endif]-->
        <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%" style="width:100%;max-width:560px;border-collapse:collapse;background-color:#FBFAF5;border:1px solid #DAD5C7;">
          <tr>
            <td style="padding:24px 32px 16px 32px;border-bottom:1px solid #DAD5C7;">
              <p style="margin:0;font-family:{_SANS_STACK};font-size:12px;line-height:16px;font-weight:600;color:#64685E;letter-spacing:0.06em;text-transform:uppercase;">
                Bot04 &middot; Finance App
              </p>
            </td>
          </tr>
          <tr>
            <td style="padding:28px 32px 24px 32px;">
              <h1 style="margin:0 0 12px 0;font-family:{_SERIF_STACK};font-size:28px;line-height:34px;font-weight:400;color:#171A16;letter-spacing:-0.01em;">
                Password reset code
              </h1>
              <p style="margin:0 0 24px 0;font-family:{_SANS_STACK};font-size:15px;line-height:22px;font-weight:400;color:#565A52;">
                Enter this verification code on the password reset screen in Finance App to set a new password.
              </p>
              <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%" style="width:100%;border-collapse:collapse;background-color:#EBE8DE;border:1px solid #DAD5C7;">
                <tr>
                  <td align="center" style="padding:20px 24px;">
                    <div style="margin:0 0 6px 0;font-family:{_SANS_STACK};font-size:11px;line-height:14px;font-weight:600;color:#64685E;letter-spacing:0.08em;text-transform:uppercase;">
                      Verification code
                    </div>
                    <div style="margin:0;font-family:{_MONO_STACK};font-size:34px;line-height:40px;font-weight:600;color:#171A16;letter-spacing:0.18em;font-variant-numeric:tabular-nums;">
                      {safe_code}
                    </div>
                  </td>
                </tr>
              </table>
              <p style="margin:16px 0 0 0;font-family:{_SANS_STACK};font-size:13px;line-height:19px;font-weight:500;color:#171A16;">
                This code expires in 10 minutes and works once.
              </p>
            </td>
          </tr>
          <tr>
            <td style="padding:20px 32px 24px 32px;border-top:1px solid #DAD5C7;">
              <p style="margin:0 0 8px 0;font-family:{_SANS_STACK};font-size:13px;line-height:19px;font-weight:600;color:#171A16;">
                Never share this code with anyone.
              </p>
              <p style="margin:0;font-family:{_SANS_STACK};font-size:13px;line-height:19px;font-weight:400;color:#64685E;">
                If you did not request a password reset, you can safely ignore this email. Requesting a code does not change your password.
              </p>
            </td>
          </tr>
        </table>
        <!--[if mso]>
        </td>
        </tr>
        </table>
        <![endif]-->
      </td>
    </tr>
  </table>
</body>
</html>"""

    return plain_text, html_body
