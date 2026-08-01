"""Group metadata: the icon a group shows, and the order groups appear in.

Which group a host belongs to is a property of the host, and lives in
hosts.json with it. What a group *looks like* belongs to no single host, so it
lives beside them in ``~/.connectify/groups.json``:

    {"groups": [{"name": "Production", "emoji": "🚀"}],
     "order":  ["Production", "Databases"]}

The two are deliberately separate. "order" is the arrangement the user dragged
the groups into, and nothing else may change it - giving a group an icon must
not send it to the top of the sidebar. A group missing from "order" is not an
error: it sorts after the arranged ones, alphabetically, so a group created
today appears somewhere predictable rather than jumping the queue.
"""

import json
import os
from pathlib import Path

# A group icon is one emoji, but "one emoji" can be several codepoints: a flag
# is two, and a family with a skin tone can be seven or more. This is a sanity
# bound to keep a label out of the field, not a grapheme count.
MAX_EMOJI_CODEPOINTS = 16


def normalize_emoji(value):
    """Coerce a group icon to something safe to store and render.

    Returns '' for anything empty, over-long, or carrying control characters -
    a group simply has no icon rather than a broken one.
    """
    if not isinstance(value, str):
        return ''

    emoji = value.strip()
    if not emoji:
        return ''
    if any(ord(char) < 0x20 or ord(char) == 0x7F for char in emoji):
        return ''
    if len(emoji) > MAX_EMOJI_CODEPOINTS:
        return ''
    return emoji


class GroupStore:
    """Reads and writes groups.json, and answers questions about ordering."""

    def __init__(self, config_file="~/.connectify/hosts.json"):
        # Sits beside the host list, whatever the host list's path is, so a
        # test or a --config run keeps its metadata with its hosts
        self.path = Path(config_file).expanduser().parent / 'groups.json'

    # --- storage ------------------------------------------------------------

    def read(self):
        """The stored icons and arrangement, as ``(emoji_by_name, order)``.

        A missing or unreadable file means "nothing configured yet". Group
        metadata is decoration, and losing it must never stop the app from
        listing hosts.
        """
        if not self.path.exists():
            return {}, []

        try:
            with open(self.path, encoding='utf-8') as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            return {}, []
        if not isinstance(data, dict):
            return {}, []

        emoji = {}
        for entry in data.get('groups') or []:
            if not isinstance(entry, dict):
                continue
            name = str(entry.get('name', '')).strip()
            if name and name not in emoji:
                emoji[name] = normalize_emoji(entry.get('emoji'))

        order = []
        for name in data.get('order') or []:
            name = str(name).strip()
            if name and name not in order:
                order.append(name)

        return emoji, order

    def write(self, emoji, order):
        os.makedirs(self.path.parent, exist_ok=True)
        payload = {
            'groups': [
                {'name': name, 'emoji': normalize_emoji(value)}
                for name, value in emoji.items() if normalize_emoji(value)
            ],
            'order': list(order),
        }
        with open(self.path, 'w', encoding='utf-8') as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
        return True

    # --- reading ------------------------------------------------------------

    def emoji_for(self, name):
        emoji, _order = self.read()
        return emoji.get(name, '')

    def order_key(self, name):
        """Sort key: arranged groups in their order, the rest after, A-Z."""
        _emoji, order = self.read()
        if name in order:
            return (0, order.index(name), '')
        return (1, 0, name.lower())

    def metadata(self, names):
        """Metadata for ``names``, in the order they should be rendered.

        Names the store has never seen come back with no icon, so the UI can
        render every group it was given from one list.
        """
        emoji, _order = self.read()
        return [
            {'name': name, 'emoji': emoji.get(name, '')}
            for name in sorted(names, key=self.order_key)
        ]

    # --- writing ------------------------------------------------------------

    def set_emoji(self, name, value):
        """Give a group an icon - and only that. Where it sits in the sidebar
        is the user's arrangement, not a side effect of decorating it."""
        emoji, order = self.read()
        emoji[name] = normalize_emoji(value)
        self.write(emoji, order)

    def rename(self, old_name, new_name):
        """Carry a group's metadata across a rename.

        The hosts are moved by the caller - this only keeps the icon and the
        position, which would otherwise be silently lost.
        """
        emoji, order = self.read()

        carried = emoji.pop(old_name, '')
        if carried or old_name in emoji:
            emoji[new_name] = carried
        emoji.pop(old_name, None)

        if old_name in order:
            order[order.index(old_name)] = new_name
            # a rename onto a group already in the list must not list it twice
            order = [name for i, name in enumerate(order)
                     if name != new_name or i == order.index(new_name)]

        self.write(emoji, order)

    def set_order(self, names):
        """Arrange the groups. Names the caller did not mention keep their
        icons and follow behind, so a stale browser tab cannot drop anyone."""
        emoji, previous = self.read()

        order = []
        for name in names:
            name = str(name).strip()
            if name and name not in order:
                order.append(name)
        for name in previous:
            if name not in order:
                order.append(name)

        self.write(emoji, order)
        return self.metadata(set(order) | set(emoji))

    def forget(self, name):
        """Drop a group nobody uses any more."""
        emoji, order = self.read()
        emoji.pop(name, None)
        self.write(emoji, [n for n in order if n != name])
