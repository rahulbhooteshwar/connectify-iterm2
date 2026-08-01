#!/usr/bin/env python3
"""
What the tab shows while ssh authenticates.

Authentication happens before the remote end paints anything, so the tab would
otherwise sit blank. This draws a centred, bordered card - host, login, which
credential is answering - with a spinner underneath, in the colour of the
host's tile theme.

It is deliberately *not* an alternate-screen takeover. Everything written to
an alternate screen is discarded when you leave it, which would swallow ssh's
own error output on a failed connection - exactly the text you need. Rich's
transient Live erases only what it drew, so on success the card disappears
without a trace and the session output flows into a clean screen, while
anything ssh printed stays where it is.

Run as ``connectify session-splash`` by the session launcher; it exits when
the marker file appears (ssh's LocalCommand touches it once the session is
up), when it is asked to stop, or when it gives up waiting.
"""

import argparse
import signal
import sys
import time
from pathlib import Path

# Matches the tile themes in the web UI, so a red tile opens a red card
THEME_COLOURS = {
    'red': '#f87171',
    'green': '#34d399',
    'orange': '#fbbf24',
    'default': '#818cf8',
}

POLL_SECONDS = 0.02
DEFAULT_TIMEOUT = 120.0


def colour_for(theme):
    return THEME_COLOURS.get(str(theme or '').strip().lower(), THEME_COLOURS['default'])


def build_parser():
    parser = argparse.ArgumentParser(
        prog='connectify session-splash',
        description="Internal: the connecting card shown in an iTerm2 tab",
    )
    parser.add_argument('--name', default='', help='Host name to show')
    parser.add_argument('--target', default='', help='user@host:port')
    parser.add_argument('--auth', default='', help='How the session authenticates')
    parser.add_argument('--theme', default='default', help='Tile theme: red/green/orange/default')
    parser.add_argument('--marker', required=True, help='File that appears once connected')
    parser.add_argument('--yield-on', dest='yield_on', default=None,
                        help='File that appears when something else needs the terminal')
    parser.add_argument('--timeout', type=float, default=DEFAULT_TIMEOUT,
                        help='Give up drawing after this many seconds')
    return parser


def run(argv=None):
    args = build_parser().parse_args(argv)
    marker = Path(args.marker)
    # The askpass helper touches this when it has to ask the user whether to
    # trust an unknown host: the card has to stop drawing over the question
    yielded = Path(args.yield_on) if args.yield_on else None

    try:
        from rich.align import Align
        from rich.console import Console, Group
        from rich.live import Live
        from rich.panel import Panel
        from rich.spinner import Spinner
        from rich.text import Text
    except ImportError:
        # No Rich here for some reason: say the one thing that matters
        print(f"Connecting to {args.name or args.target}...")
        return 0

    console = Console()
    if not console.is_terminal:
        return 0

    # Asked to stop (ssh exited, usually): let the context manager erase the
    # card on the way out instead of leaving it painted on the screen
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
    signal.signal(signal.SIGINT, lambda *_: sys.exit(0))

    colour = colour_for(args.theme)
    # One spinner instance, reused: Rich animates it from the clock, so a fresh
    # one on every refresh would freeze on the first frame
    spinner = Spinner('dots', style=colour)

    def card(elapsed):
        lines = [Align.center(Text(args.name or args.target, style=f"bold {colour}"))]
        if args.target and args.name:
            lines.append(Align.center(Text(args.target, style="dim")))
        if args.auth:
            lines.append(Align.center(Text(args.auth, style="dim")))
        lines.append(Text(""))

        spinner.text = Text(f" connecting… {int(elapsed)}s", style="dim")
        lines.append(Align.center(spinner))

        panel = Panel(
            Group(*lines),
            border_style=colour,
            style="on grey11",
            padding=(1, 6),
            expand=False,
        )
        # Centred both ways. Height keeps the card in the middle of the screen
        # without an alternate screen buffer.
        return Align.center(panel, vertical="middle", height=max(console.size.height - 1, 6))

    started = time.time()
    with Live(card(0), console=console, refresh_per_second=12.5,
              transient=True, screen=False) as live:
        while time.time() - started < args.timeout:
            if marker.exists() or (yielded is not None and yielded.exists()):
                break
            live.update(card(time.time() - started))
            time.sleep(POLL_SECONDS)

    return 0


if __name__ == '__main__':
    sys.exit(run())
