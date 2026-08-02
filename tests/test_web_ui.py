"""Properties of the React UI that are worth pinning down.

The UI is a Vite build now, so there are two things to check: the source in
``ui/`` (where the rules about labels, ids and masking actually live) and the
build output in ``static/`` (what FastAPI serves and PyInstaller bundles).
"""

import json
import os
import re
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(REPO_ROOT)

STATIC = os.path.join(REPO_ROOT, 'static')
UI_SRC = os.path.join(REPO_ROOT, 'ui', 'src')


def read(*parts):
    with open(os.path.join(*parts), encoding='utf-8') as f:
        return f.read()


def read_index():
    return read(STATIC, 'index.html')


def read_css():
    return read(UI_SRC, 'index.css')


def source_files():
    """Every .ts/.tsx file under ui/src, as (relative path, text)."""
    out = []
    for root, _dirs, files in os.walk(UI_SRC):
        for name in sorted(files):
            if name.endswith(('.ts', '.tsx')):
                path = os.path.join(root, name)
                out.append((os.path.relpath(path, REPO_ROOT), read(path)))
    assert out, "no UI sources found"
    return out


def built_bundles():
    """The hashed JS/CSS the built index.html pulls in."""
    index = read_index()
    names = re.findall(r'/static/(assets/[^"\']+)', index)
    assert names, "index.html references no build assets"
    return [(name, read(STATIC, *name.split('/'))) for name in names]


# --- the build --------------------------------------------------------------

def test_the_ui_is_built_into_static():
    """PyInstaller bundles static/ verbatim - if it is stale or missing, the
    packaged app ships the wrong UI, and nothing else here would notice."""
    for name in ('index.html', 'manifest.webmanifest', 'sw.js', 'favicon.svg'):
        assert os.path.isfile(os.path.join(STATIC, name)), f"static/{name} is missing"
    assert built_bundles()


def test_every_static_reference_resolves():
    """A path that 404s in the packaged app is invisible until someone runs it."""
    for name, _text in built_bundles():
        pass  # built_bundles() already opened them

    index = read_index()
    for ref in set(re.findall(r'"(/static/[^"]+)"', index)):
        path = os.path.join(STATIC, *ref[len('/static/'):].split('/'))
        assert os.path.isfile(path), f"{ref} is referenced but not built"


def test_nothing_is_loaded_from_a_cdn():
    """The app runs on a laptop that may be offline, or on a locked-down
    network. Every byte has to come out of the bundle."""
    index = read_index()
    for url in re.findall(r'(?:src|href)="(https?://[^"]+)"', index):
        raise AssertionError(f"index.html loads {url} from the network")

    for name, text in built_bundles():
        if not name.endswith('.css'):
            continue
        for url in re.findall(r'url\(["\']?(https?://[^)"\']+)', text):
            raise AssertionError(f"{name} loads {url} from the network")


def test_fonts_are_bundled():
    """Montserrat is served from static/, not from Google Fonts."""
    css = read_css()
    assert '@font-face' in css
    for url in re.findall(r"url\(['\"]?([^)'\"]+)", css):
        assert url.startswith('/static/'), f"font {url} is not bundled"
        path = os.path.join(STATIC, *url[len('/static/'):].split('/'))
        assert os.path.isfile(path), f"font {url} is missing from the build"


# --- secrets ----------------------------------------------------------------

SECRET_IDS = ('vaultPasscode', 'vaultPasscodeConfirm', 'vaultPasscodeCurrent',
              'vaultPasscodeNew', 'vaultPasscodeNewConfirm',
              'credentialPassword', 'credentialPassphrase')


def test_every_secret_field_uses_the_masked_input():
    """One component owns masking, so there is no second path to get it wrong."""
    for path, text in source_files():
        for match in re.finditer(r'<(\w+)\s[^>]*id="([^"]+)"', text, re.S):
            component, ident = match.group(1), match.group(2)
            if ident in SECRET_IDS:
                assert component == 'SecretInput', \
                    f"{path}: {ident} is a <{component}>, not a SecretInput"


def test_secret_fields_are_masked_before_the_stylesheet_loads():
    """The field starts masked by the element itself - type=password when the
    browser cannot mask text, and the CSS mask on top either way. No window,
    however short, where a keystroke could be read."""
    ui = read(UI_SRC, 'components', 'ui.tsx')
    body = ui[ui.index('export function SecretInput'):]
    body = body[:body.index('// --- Badge')]

    assert "revealed ? 'text' : cssMasking ? 'text' : 'password'" in body, \
        "SecretInput must fall back to type=password"
    assert "'masked-input" in body, "SecretInput must carry the CSS mask"
    assert '-webkit-text-security: disc' in read_css()


def test_the_plain_text_swap_is_gated_on_support():
    """Without -webkit-text-security a text field shows the passcode in clear,
    so the swap must never happen unsupported."""
    ui = read(UI_SRC, 'components', 'ui.tsx')
    body = ui[ui.index('export function SecretInput'):]
    body = body[:body.index('// --- Badge')]

    assert "CSS.supports?.('-webkit-text-security', 'disc')" in body

    guard = body.index("CSS.supports?.('-webkit-text-security', 'disc')")
    swap = body.index("cssMasking ? 'text'")
    assert swap > guard, "the swap happens after the check"


def test_no_secret_ever_reaches_local_storage():
    """Passcodes and the vault token live in memory for exactly as long as the
    tab does. Anything persisted survives the process and the screen lock."""
    for path, text in source_files():
        for match in re.finditer(r'(localStorage|sessionStorage)\.setItem\(([^)]*)', text):
            payload = match.group(2).lower()
            for word in ('pass', 'secret', 'token', 'credential'):
                assert word not in payload, \
                    f"{path}: {match.group(1)} stores {match.group(2).strip()}"


def test_the_vault_token_is_module_state_only():
    api = read(UI_SRC, 'lib', 'api.ts')
    assert 'let vaultToken' in api, "the token should be a module-level variable"
    assert 'Storage' not in api, "the token must never be persisted"


# --- WebKit AutoFill --------------------------------------------------------

AUTOFILL_BUTTONS = (
    '::-webkit-contacts-auto-fill-button',
    '::-webkit-credentials-auto-fill-button',
    '::-webkit-credit-card-auto-fill-button',
    '::-webkit-strong-password-auto-fill-button',
    '::-webkit-strong-confirmation-password-auto-fill-button',
    '::-webkit-strong-password-and-generate-button',
    '::-webkit-caps-lock-indicator',
    '::-webkit-list-button',
    '::-webkit-clear-button',
    '::-webkit-calendar-picker-indicator',
    '::-webkit-search-cancel-button',
    '::-webkit-search-decoration',
    '::-webkit-search-results-button',
    '::-webkit-search-results-decoration',
)


def test_webkits_autofill_buttons_are_hidden_one_rule_at_a_time():
    """WebKit draws a contact card on fields it reads as a person's name and a
    key on password fields, and in iTerm2's embedded browser they never go
    away. Each is hidden by its own rule: a browser that does not know one
    selector in a list throws the whole list away, which would take the
    others with it.
    """
    css = read_css()

    for pseudo in AUTOFILL_BUTTONS:
        assert pseudo in css, f"{pseudo} is not hidden"
        assert re.search(r'%s\s*,' % re.escape(pseudo), css) is None, \
            f"{pseudo} shares a selector list; split it out"


def test_the_autofill_rules_survive_into_the_build():
    """Tailwind's build could in principle drop them; it must not."""
    css = ''.join(text for name, text in built_bundles() if name.endswith('.css'))
    assert css, "no stylesheet was built"

    for pseudo in AUTOFILL_BUTTONS:
        assert pseudo in css, f"{pseudo} did not survive the build"
    assert '-webkit-text-security' in css


def test_the_decoration_container_is_left_alone():
    """Collapsing it renders a number input blank - the field's own text is
    laid out inside that container, so the port would show nothing while
    holding 22. The buttons are hidden one by one instead."""
    css = read_css()
    assert re.search(r'::-webkit-textfield-decoration-container\s*\{', css) is None, \
        "hiding this container blanks number fields"


# Measured in iTerm2's browser (Safari 26.5 WebKit) with tools/field-lab.html:
# AutoFill paints a contact card on a field whose *label* or *id* reads as a
# person, and a house when it reads as a place. Neither type="search", nor
# autocomplete, nor hiding the pseudo-elements shifted it. Different wording
# did - "Title" and "Endpoint" came back clean where "Display Name" and
# "Hostname / IP" did not.
FORBIDDEN_IN_IDS = ('name', 'address', 'user', 'phone', 'email')

# Every field the user types into, under the wording that measured clean
INPUT_IDS = ('searchBox', 'tagInput', 'hostTitle', 'hostEndpoint', 'hostLogin',
             'hostPort', 'hostGroup', 'hostCredential', 'itermProfile',
             'credentialTitle', 'credentialLogin', 'credentialDescription',
             'credentialKeyPath', 'vaultPasscode')


def test_no_field_id_reads_as_a_person_or_a_place():
    for path, text in source_files():
        for ident in re.findall(r'\bid="([^"]+)"', text):
            lowered = ident.lower()
            for word in FORBIDDEN_IN_IDS:
                assert word not in lowered, \
                    f'{path}: id="{ident}" contains "{word}" - AutoFill decorates it'


def test_no_visible_label_reads_as_a_person_or_a_place():
    """<Field label="..."> is the only thing that renders a <label>."""
    for path, text in source_files():
        for label in re.findall(r'<Field\s[^>]*label="([^"]+)"', text, re.S):
            lowered = label.lower()
            assert 'name' not in lowered, f"{path}: label {label!r} draws a contact card"
            assert 'host' not in lowered, f"{path}: label {label!r} draws a house"
            assert 'user' not in lowered, f"{path}: label {label!r} draws a contact card"


def test_placeholders_do_not_read_as_a_person_or_a_place():
    for path, text in source_files():
        for placeholder in re.findall(r'placeholder="([^"]+)"', text):
            lowered = placeholder.lower()
            assert 'name' not in lowered, f"{path}: placeholder {placeholder!r}"


def test_the_fields_are_present_under_their_safe_ids():
    sources = ''.join(text for _path, text in source_files())
    for ident in INPUT_IDS:
        assert f'id="{ident}"' in sources, f"{ident} is missing"


def test_the_shared_input_opts_out_of_autofill_and_autocapitalisation():
    """Hostnames and logins are identifiers, not prose - and the fewer hints
    AutoFill gets, the less it decorates. The shared Input sets all of it, so
    no caller can forget."""
    ui = read(UI_SRC, 'components', 'ui.tsx')
    body = ui[ui.index('export const Input ='):]
    body = body[:body.index('export function Field')]

    for attr in ('autoComplete="off"', 'autoCapitalize="off"',
                 'autoCorrect="off"', 'spellCheck={false}'):
        assert attr in body, f"the shared Input does not set {attr}"


def test_every_input_in_the_app_opts_out():
    """A handful of fields are hand-rolled rather than going through Input -
    the tag box, the combobox. They need the same four attributes, or the
    defences apply to some fields and not others."""
    for path, text in source_files():
        for element in re.findall(r'<input\b.*?/>', text, re.S):
            if re.search(r'type="(checkbox|radio|file)"', element):
                continue          # nothing is typed, so there is nothing to fill
            for attr in ('autoComplete="off"', 'autoCapitalize="off"',
                         'autoCorrect="off"', 'spellCheck={false}'):
                assert attr in element, \
                    f"{path}: an <input> is missing {attr}"


def test_the_body_opts_out_of_autocapitalisation():
    index = read_index()
    body = re.search(r'<body[^>]*>', index).group(0)
    assert 'autocapitalize="off"' in body
    assert 'autocorrect="off"' in body


# --- themes -----------------------------------------------------------------

def test_the_tile_themes_match_the_backend():
    """hosts.json stores these ids and main.py validates them; a theme the UI
    offers but the backend rejects fails only when a user picks it."""
    import main

    themes = read(UI_SRC, 'lib', 'themes.ts')
    ids = re.findall(r"\{\s*id:\s*'([^']+)'", themes)
    assert ids, "no themes found in ui/src/lib/themes.ts"
    assert ids == list(main.HOST_THEMES), \
        f"UI themes {ids} != backend {list(main.HOST_THEMES)}"


# --- PWA --------------------------------------------------------------------

def test_the_service_worker_never_caches_the_api():
    """Cached host data would be stale the moment anything changed, and a
    cached /api/vault response would outlive the lock."""
    sw = read(REPO_ROOT, 'static', 'sw.js')
    assert "startsWith('/static/assets/')" in sw, \
        "the service worker must only cache hashed build assets"

    code = re.sub(r'/\*.*?\*/|//[^\n]*', '', sw, flags=re.S)
    assert '/api' not in code, "the service worker touches the API"
    assert code.count("startsWith(") == 1, \
        "only one path prefix may be cached"


def test_the_service_worker_is_served_from_the_root():
    """A worker served from /static/ can only control /static/ - it would
    never see the app shell, and the PWA would not install."""
    import api_server

    routes = {getattr(r, 'path', None) for r in api_server.app.routes}
    assert '/sw.js' in routes, "the service worker needs a root-scoped route"


def test_the_manifest_installs_the_whole_app():
    manifest = json.loads(read(STATIC, 'manifest.webmanifest'))
    assert manifest['start_url'] == '/'
    assert manifest['scope'] == '/'
    assert manifest['display'] == 'standalone'
    for icon in manifest['icons']:
        src = icon['src']
        assert src.startswith('/static/'), src
        path = os.path.join(STATIC, *src[len('/static/'):].split('/'))
        assert os.path.isfile(path), f"{src} is missing from the build"

# --- the sidebar ------------------------------------------------------------

def test_the_sidebar_collapse_is_remembered():
    """A window that opens with the sidebar back out every time is worse than
    not having the toggle at all."""
    store = read(UI_SRC, 'store.tsx')

    assert "localStorage.getItem('connectify-sidebar')" in store, \
        "the collapsed state is not read back at startup"
    assert "localStorage.setItem('connectify-sidebar'" in store, \
        "the collapsed state is never saved"


def test_the_sidebar_has_a_keyboard_shortcut():
    """Cmd+B on macOS, Ctrl+B elsewhere - and never while the caret is in a
    field, where the browser and the caret have their own claim on it."""
    store = read(UI_SRC, 'store.tsx')
    handler = store[store.index('const onKeyDown = (e: KeyboardEvent)'):]
    handler = handler[:handler.index('window.addEventListener')]

    assert "e.key !== 'b'" in handler
    assert 'e.metaKey' in handler and 'e.ctrlKey' in handler
    assert 'HTMLInputElement' in handler, "the shortcut must yield to text fields"


# --- filters ----------------------------------------------------------------

def test_the_ungrouped_filter_uses_one_shared_sentinel():
    """The sidebar sets this filter and the hosts page reads it. Two hand-typed
    copies drifted apart once already - a filter that could never match, so
    clicking Ungrouped showed nothing at all."""
    types = read(UI_SRC, 'lib', 'types.ts')
    assert 'export const UNGROUPED' in types, "the sentinel should live in one place"

    for name in (('App.tsx',), ('pages', 'HostsPage.tsx')):
        text = read(UI_SRC, *name)
        path = '/'.join(name)
        assert 'UNGROUPED' in text, f"{path} does not use the sentinel"

        literal = re.search(r"groupFilter\s*===\s*'", text)
        assert literal is None, \
            f"{path} compares groupFilter to a hand-typed string"


def test_no_source_file_hides_a_control_character():
    """The sentinel above was once a raw NUL byte pasted into the source: it
    made grep call the file binary and hid the mismatch that broke the filter.
    Escapes are fine; the byte itself is not."""
    for path, text in source_files():
        for char in text:
            if char in '\t\n\r':
                continue
            assert ord(char) >= 0x20, \
                f"{path} contains a raw control character (0x{ord(char):02x})"

def test_a_field_caption_never_wraps_its_control():
    """A <label> forwards clicks to its first labelable descendant. Wrapping a
    field built from several controls therefore fired the first button from
    anywhere in it: clicking one tag's X deleted that tag and the first one,
    and clicking the caption deleted a tag on its own.
    """
    ui = read(UI_SRC, 'components', 'ui.tsx')
    field = ui[ui.index('export function Field'):]
    field = field[:field.index('/** A masked secret field')]

    assert '{children}' in field
    caption = field.index('htmlFor={htmlFor}')
    children = field.index('{children}')
    assert caption < children, "the caption must be a sibling of the control"
    assert '<label' in field and 'htmlFor={htmlFor}' in field, \
        "a caption that names one control should still be a real label"

    # the wrapper itself has to be a plain element
    wrapper = field[field.index('return ('):field.index('{children}')]
    assert '<label className' not in wrapper, "Field still wraps its children in a label"


def test_a_collapsed_group_shows_its_initial_and_its_name_on_hover():
    """Nine coloured dots in a row say nothing about which group is which."""
    app = read(UI_SRC, 'App.tsx')

    assert 'Array.from(name.trim())[0]' in app, \
        "take the initial codepoint-wise - half a surrogate pair renders as a box"


def test_collapsed_sidebar_items_use_a_real_tooltip_not_the_native_title():
    """The native title attribute has a browser-controlled delay, and in
    iTerm2's embedded WebKit browser it sometimes never renders at all - which
    is exactly the failure mode for a collapsed icon with no other label. Both
    NavItem and GroupItem must render through the shared Tooltip component
    when collapsed, and never fall back to title=.
    """
    app = read(UI_SRC, 'App.tsx')

    assert 'return <Tooltip content=' in app, \
        "collapsed items must render through the Tooltip component"
    assert re.search(r'\btitle=\{', app) is None, \
        "a native title= crept back in - it must be the Tooltip, not this"


def test_the_tooltip_shows_immediately():
    """A default hover delay defeats the point - the icon is the only thing on
    screen, so the name has to appear as soon as the pointer arrives."""
    ui = read(UI_SRC, 'components', 'ui.tsx')
    # Tooltip is the last export in the file, so everything from here to the
    # end of the file is its body
    tooltip = ui[ui.index('export function Tooltip'):]

    assert 'delayDuration={0}' in tooltip


# --- groups ------------------------------------------------------------------

def test_the_emoji_picker_renders_native_glyphs_not_cdn_images():
    """emoji-mart defaults to fetching a PNG per emoji from a CDN
    (cdn.jsdelivr.net) unless told otherwise. set="native" renders the actual
    Unicode character through a <span> instead, so nothing is ever fetched -
    that string appearing dead in the vendored library source is fine; what
    matters is our own component never asks for anything else."""
    picker = read(UI_SRC, 'components', 'EmojiMartPicker.tsx')
    assert 'set="native"' in picker


def test_the_emoji_dataset_is_bundled_not_fetched():
    """Left to its default, @emoji-mart/data's own picker prop fetches its
    dataset over the network on first open. Importing it as a module bundles
    the ~200KB JSON instead, so the picker works with no server reachable."""
    picker = read(UI_SRC, 'components', 'EmojiMartPicker.tsx')
    assert "@emoji-mart/data" in picker


def test_the_emoji_picker_escapes_the_dialogs_scroll_container():
    """Rendered in place, the panel was clipped by the dialog body's
    `overflow-y: auto` - and no z-index lifts a box out of an ancestor that
    clips it. It has to be portalled out and positioned itself."""
    picker = read(UI_SRC, 'components', 'EmojiMartPicker.tsx')

    assert 'createPortal(' in picker, "the panel must be portalled out of the scroll container"
    assert 'getBoundingClientRect()' in picker, "a portalled panel has to position itself"


def test_the_panel_is_positioned_against_its_containing_block():
    """The dialog is centred with a CSS transform, and a transformed ancestor
    becomes the containing block for `position: fixed` children - so "fixed"
    inside one is fixed to *it*, not the window. Viewport coordinates have to
    be rebased onto the container, or the panel lands somewhere else."""
    picker = read(UI_SRC, 'components', 'EmojiMartPicker.tsx')

    assert 'container.getBoundingClientRect()' in picker, \
        "coordinates must be rebased onto the positioned container"
    assert "position.fixed ? 'fixed' : 'absolute'" in picker, \
        "fixed only when anchored to the viewport itself"


def test_the_pickers_hard_coded_height_is_overridden():
    """emoji-mart ships `height: 435px` on its own host element, which is
    taller than the space under a field in an 85vh dialog. Document styles
    beat a shadow-DOM :host rule, which is how this is bounded."""
    css = read_css()
    picker = read(UI_SRC, 'components', 'EmojiMartPicker.tsx')

    assert '.emoji-popover em-emoji-picker' in css, "nothing overrides the picker's own height"
    assert '--emoji-picker-height' in css and '--emoji-picker-height' in picker, \
        "the measured height has to reach the picker element"


def test_clicking_the_panel_does_not_dismiss_the_dialog_under_it():
    """Portalled out, the panel is outside the dialog in the DOM - Radix would
    otherwise read a click on an emoji as a click outside and close the form."""
    ui = read(UI_SRC, 'components', 'ui.tsx')
    content = ui[ui.index('export function DialogContent'):ui.index('export function DialogBody')]

    assert 'emoji-popover' in content, "interactions inside the panel must not count as outside"


def test_the_emoji_picker_is_code_split():
    """emoji-mart plus its dataset is real weight - nobody looking at a host
    list should pay for it until they actually open a picker."""
    picker = read(UI_SRC, 'components', 'EmojiMartPicker.tsx')
    assert 'React.lazy(' in picker
    assert 'React.Suspense' in picker


def test_the_same_picker_is_used_for_hosts_and_groups():
    """One component, not two copies that could drift."""
    host_dialog = read(UI_SRC, 'components', 'HostDialog.tsx')
    group_dialog = read(UI_SRC, 'components', 'GroupDialog.tsx')
    assert 'EmojiMartPicker' in host_dialog
    assert 'EmojiMartPicker' in group_dialog


def test_a_host_can_carry_its_own_icon():
    types = read(UI_SRC, 'lib', 'types.ts')
    host_dialog = read(UI_SRC, 'components', 'HostDialog.tsx')
    hosts_page = read(UI_SRC, 'pages', 'HostsPage.tsx')

    interface = types[types.index('export interface Host'):types.index('export interface Credential')]
    assert 'emoji: string' in interface, "the Host type is missing its icon field"
    assert 'id="hostEmoji"' in host_dialog
    assert 'host.emoji &&' in hosts_page, "the tile must not render an empty icon slot"


def test_group_rename_and_icon_go_through_one_endpoint():
    """A group is a label repeated on every host that carries it - renaming
    it has to be a single request the backend applies atomically, not the UI
    looping over hosts and calling updateHost per host."""
    api = read(UI_SRC, 'lib', 'api.ts')
    assert "/api/groups/${encodeURIComponent(name)}" in api
    assert "method: 'PUT'" in api


def test_the_tooltip_does_not_linger_over_the_next_item():
    """Radix keeps a tooltip open while the pointer might be travelling into
    it - a "grace area" meant for tooltips you can hover and click. These are
    plain labels, and the grace area meant a tooltip never closed on leave: the
    next icon you hovered was blocked from opening its own, so it kept showing
    the previous group's name at the new position.
    """
    app = read(UI_SRC, 'App.tsx')
    assert 'disableHoverableContent' in app, \
        "without this a label tooltip stays open and blocks the next one"


def test_reordering_uses_a_drag_library_not_hand_rolled_pointer_maths():
    """Sliding the neighbours out of the way as you drag is most of what makes
    a reorder feel like one, and is not worth reimplementing. dnd-kit is also
    pointer-event based, so unlike native HTML5 drag-and-drop it works in
    iTerm2's embedded WebKit view."""
    app = read(UI_SRC, 'App.tsx')

    assert '@dnd-kit/sortable' in app
    assert 'useSortable(' in app
    assert 'onPointerMove={onDragMove}' not in app, "the hand-rolled drag is still here"


def test_a_click_on_a_group_is_not_swallowed_by_the_drag():
    """Press-and-release on a group has to filter, not count as a zero-length
    drag - hence an activation distance before dragging begins."""
    app = read(UI_SRC, 'App.tsx')
    sensors = app[app.index('const sensors = useSensors('):]
    sensors = sensors[:sensors.index(')\n\n')]

    assert 'activationConstraint' in sensors
    assert 'distance' in sensors


def test_copying_falls_back_when_the_clipboard_api_refuses():
    """navigator.clipboard is absent without a secure context (the UI reached
    over the LAN with --share) and WebKit rejects it outright whenever the
    document is not focused - which, embedded in an iTerm2 tab beside a
    terminal, it often is not. execCommand has neither restriction, so it is
    the fallback rather than the error message."""
    clip = read(UI_SRC, 'lib', 'clipboard.ts')

    assert 'navigator.clipboard' in clip
    assert "execCommand('copy')" in clip, "there has to be a second route"
    assert 'isSecureContext' in clip, "the async API is simply absent without one"

    # the function body, not the comment above it that names both routes
    body = clip[clip.index('export async function copyText'):]
    api_call = body.index('navigator.clipboard')
    fallback = body.index('legacyCopy(')
    assert api_call < fallback, "the modern API should be tried first"


def test_every_copy_goes_through_the_one_helper():
    """A second call site writing to navigator.clipboard directly would fail
    in exactly the cases the helper exists to survive."""
    for path, text in source_files():
        if path.endswith('lib/clipboard.ts'):
            continue
        assert 'clipboard.writeText' not in text, \
            f"{path} writes to the clipboard without the fallback"


def test_a_failed_copy_still_shows_the_value():
    """If every route is blocked there is nothing to be done about it, but the
    value can at least be put on screen to be read off."""
    page = read(UI_SRC, 'pages', 'HostsPage.tsx')
    handler = page[page.index('const copy = async'):]
    handler = handler[:handler.index('\n  }')]

    assert '${text}' in handler, "the failure message should carry the value"


def test_host_tiles_reorder_within_their_group():
    """Same library as the sidebar, and the order is persisted server-side -
    hosts.json is the order, so it cannot live in the browser."""
    page = read(UI_SRC, 'pages', 'HostsPage.tsx')

    assert 'SortableHostTile' in page
    assert 'api.setHostOrder(' in page, "the new order has to reach hosts.json"
    assert 'rectSortingStrategy' in page and 'verticalListSortingStrategy' in page, \
        "a grid and a list need different strategies or the gap opens sideways"


def test_dragging_a_tile_does_not_eat_the_launch_click():
    """The drag listeners are on the whole card, so Launch and the hover
    actions are inside the draggable - only an activation distance keeps them
    clickable."""
    page = read(UI_SRC, 'pages', 'HostsPage.tsx')
    sensors = page[page.index('const sensors = useSensors('):]
    sensors = sensors[:sensors.index(')\n\n')]

    assert 'activationConstraint' in sensors and 'distance' in sensors


def test_group_order_is_persisted_through_the_api_not_local_storage_alone():
    """The ask was for the order to persist under ~/.connectify - that only
    happens if the sidebar actually calls the ordering endpoint rather than
    keeping the arrangement in the browser alone."""
    app = read(UI_SRC, 'App.tsx')
    assert 'api.setGroupOrder(' in app


def test_the_entry_animation_does_not_hold_its_last_frame():
    """A filled animation outranks every normal declaration, inline styles
    included. ``animation: fade-up ... both`` therefore went on asserting
    ``opacity: 1`` long after it finished, and silently beat the ``opacity-40``
    that marks the tile a drag left behind. The final keyframe is the resting
    state anyway, so only the ``backwards`` half is worth keeping."""
    css = read_css()
    rule = re.search(r'\.animate-fade-up\s*\{([^}]*)\}', css)

    assert rule, "the fade-up utility should still exist"
    assert 'backwards' in rule.group(1)
    assert 'forwards' not in rule.group(1) and 'both' not in rule.group(1)


def test_tiles_are_measured_before_they_start_moving():
    """The sortable strategy works out where each tile belongs by comparing the
    layout it started from with the order it would land in. Re-measuring every
    frame hands it rects that already carry the shift, and it settles on "stay
    put" - the tiles stop making room for the card being dragged."""
    page = read(UI_SRC, 'pages', 'HostsPage.tsx')

    assert 'MeasuringStrategy.Always' not in page


def test_the_card_under_the_pointer_is_not_the_one_left_behind():
    """A drag should look like carrying the card: a full-strength copy travels
    with the pointer while the tile it came from stays put as a faded gap."""
    page = read(UI_SRC, 'pages', 'HostsPage.tsx')

    assert 'DragOverlay' in page, "the carried copy is what makes the drag read as a drag"
    assert 'opacity-40' in page, "and the tile it came from should read as a gap"


def test_the_emoji_list_can_be_scrolled_inside_a_dialog():
    """The list scrolls inside the picker's shadow root, and a wheel crossing
    that boundary is retargeted to the host element. The dialog's scroll lock
    then sees a wheel over something with no scrollable ancestor it can find and
    cancels it, so nothing moves - the delta has to be applied by hand."""
    picker = read(UI_SRC, 'components', 'EmojiMartPicker.tsx')

    assert "addEventListener('wheel'" in picker
    assert 'passive: false' in picker, "preventDefault needs a non-passive listener"
    assert 'shadowRoot' in picker and 'scrollTop' in picker, \
        "the scroll container is behind the shadow boundary"


def test_each_group_is_drawn_on_its_own_surface():
    """Spacing alone let one group run into the next down a long listing. Each
    section is a panel now - a border and a tint the tiles sit on."""
    page = read(UI_SRC, 'pages', 'HostsPage.tsx')
    section = re.search(r'<section\s+key=\{section\.name[^>]*?className="([^"]*)"', page, re.S)

    assert section, "the group section should carry a literal className"
    classes = section.group(1)
    assert 'border' in classes and 'bg-' in classes and 'rounded' in classes, classes
