"""Recovery email presentation must preserve accessibility and code safety."""

from __future__ import annotations

import re
from html.parser import HTMLParser

from backend.app.auth.email_templates import render_password_reset_email


class EmailParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.elements = []

    def handle_starttag(self, tag, attrs):
        self.elements.append((tag, dict(attrs)))


def test_leading_zero_code_and_security_guidance_survive_both_formats():
    plain, html = render_password_reset_email("012345")

    for body in (plain, html):
        assert "012345" in body
        assert "10 minutes" in body
        assert "share" in body.lower()
        assert "ignore" in body.lower()
        assert "app" in body.lower()
    assert "<html" not in plain.lower()


def test_html_uses_accessible_email_layout_without_external_resources():
    _, html = render_password_reset_email("123456")
    parser = EmailParser()
    parser.feed(html)

    assert any(tag == "html" and attrs.get("lang") == "en"
               for tag, attrs in parser.elements)
    assert any(tag == "h1" for tag, _ in parser.elements)
    assert any(tag == "meta" and attrs.get("name") == "viewport"
               for tag, attrs in parser.elements)
    tables = [attrs for tag, attrs in parser.elements if tag == "table"]
    assert tables
    assert all(attrs.get("role") == "presentation" for attrs in tables)
    assert not any(tag in {"script", "form", "iframe", "img", "link"}
                   for tag, _ in parser.elements)
    assert not re.search(r"(?:src|href)\s*=|url\s*\(|@import", html, re.I)


def test_dynamic_code_is_escaped_in_html():
    payload = '<img src=x onerror="alert(1)">'
    plain, html = render_password_reset_email(payload)
    assert payload in plain
    assert payload not in html
    assert "&lt;img" in html
    assert "&quot;" in html


def test_code_is_not_in_subject_or_hidden_preheader():
    _, html = render_password_reset_email("019283")
    preheader = re.search(r'<div style="display:none;[^>]*>(.*?)</div>', html, re.S)
    assert preheader is not None
    assert "019283" not in preheader.group(1)
    assert html.count("019283") == 1
