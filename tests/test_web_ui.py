"""Properties of the single-page UI that are worth pinning down."""

import os
import re

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INDEX = os.path.join(REPO_ROOT, 'static', 'index.html')


def read_index():
    with open(INDEX, encoding='utf-8') as f:
        return f.read()


def test_secret_fields_are_masked_and_undecorated():
    """iTerm2's embedded browser floats an AutoFill key over password fields.

    Two defences, and both have to stay: hide the decorations, and swap in a
    text field the browser masks itself so there is nothing to decorate.
    """
    html = read_index()

    assert '::-webkit-credentials-auto-fill-button' in html
    assert '-webkit-text-security: disc' in html
    assert 'maskSecretFields' in html
    assert 'this.maskSecretFields();' in html, "run before anything can be typed"


def test_the_plain_text_swap_is_gated_on_support():
    """Without -webkit-text-security a text field shows the passcode in clear.

    The swap must therefore never happen unsupported - this test exists so
    that check cannot quietly disappear.
    """
    html = read_index()
    body = html[html.index('maskSecretFields(root = document) {'):]
    body = body[:body.index('\n      }')]

    assert "CSS.supports('-webkit-text-security', 'disc')" in body
    assert 'if (!supported) return false;' in body

    guard = body.index('if (!supported) return false;')
    assert body.index("input.type = 'text'") > guard, "the swap happens after the check"


def test_form_fields_do_not_autocapitalize():
    """Hostnames and usernames are identifiers, not prose."""
    html = read_index()

    inputs = re.findall(r'<input\b[^>]*>', html, re.S)
    typed = [i for i in inputs if 'type="text"' in i or 'type="password"' in i]
    assert typed, "there should be text inputs to check"

    for field in typed:
        assert 'autocapitalize="off"' in field, field[:120]
