"""Properties of the single-page UI that are worth pinning down."""

import os
import re

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INDEX = os.path.join(REPO_ROOT, 'static', 'index.html')


def read_index():
    with open(INDEX, encoding='utf-8') as f:
        return f.read()


SECRET_FIELDS = ('vaultPasscode', 'vaultPasscodeConfirm',
                 'credentialPassword', 'credentialPassphrase')


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


def test_every_secret_field_is_masked_by_the_markup_itself():
    """No window, however short, where a keystroke could be read.

    The mask is a class in the HTML rather than something JavaScript adds
    later, so it applies as the field is parsed - and the field starts as a
    password input, which is masked even if the stylesheet never loads.
    """
    html = read_index()

    for ident in SECRET_FIELDS:
        field = re.search(r'<input[^>]*id="%s"[^>]*>' % ident, html)
        assert field, f"{ident} is missing"
        markup = field.group(0)
        assert 'masked-input' in markup, f"{ident} is not masked in the markup"
        assert 'type="password"' in markup, f"{ident} must start as a password field"


def test_no_secret_field_is_left_as_a_plain_input():
    """Anything that takes a secret has to be in the masked set above."""
    html = read_index()

    for match in re.finditer(r'<input\b[^>]*>', html, re.S):
        markup = match.group(0)
        looks_secret = any(word in markup.lower()
                           for word in ('passcode', 'password', 'passphrase'))
        if not looks_secret or 'placeholder' in markup and 'id=' not in markup:
            continue
        assert 'masked-input' in markup, f"unmasked secret field: {markup[:110]}"


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


AUTOFILL_BUTTONS = (
    '::-webkit-contacts-auto-fill-button',
    '::-webkit-credentials-auto-fill-button',
    '::-webkit-strong-password-auto-fill-button',
    '::-webkit-strong-password-and-generate-button',
    '::-webkit-caps-lock-indicator',
)


def test_webkits_autofill_buttons_are_hidden_one_rule_at_a_time():
    """WebKit draws a contact card on fields it reads as a person's name and a
    key on password fields, and in iTerm2's embedded browser they never go
    away. Each is hidden by its own rule: a browser that does not know one
    selector in a list throws the whole list away, which would take the
    others with it.
    """
    html = read_index()

    for pseudo in AUTOFILL_BUTTONS:
        assert pseudo in html, f"{pseudo} is not hidden"
        rule = re.search(r'input%s\s*,' % re.escape(pseudo), html)
        assert rule is None, f"{pseudo} shares a selector list; split it out"


def test_text_fields_opt_out_of_autofill():
    """Less to tempt the heuristics with in the first place."""
    html = read_index()

    for match in re.finditer(r'<input\b[^>]*>', html, re.S):
        markup = match.group(0)
        if 'type="text"' not in markup and 'type="password"' not in markup:
            continue
        assert 'autocomplete="off"' in markup, markup[:110]


def test_form_fields_do_not_autocapitalize():
    """Hostnames and usernames are identifiers, not prose."""
    html = read_index()

    inputs = re.findall(r'<input\b[^>]*>', html, re.S)
    typed = [i for i in inputs if 'type="text"' in i or 'type="password"' in i]
    assert typed, "there should be text inputs to check"

    for field in typed:
        assert 'autocapitalize="off"' in field, field[:120]
