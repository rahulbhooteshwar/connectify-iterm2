# Montserrat (vendored)

The web UI's typeface, bundled with Connectify so it renders offline without
depending on Google Fonts.

Source: `https://fonts.googleapis.com/css2?family=Montserrat:wght@300..700&display=swap`
(Google Fonts, Montserrat v31)

Contents:

| File | Purpose |
|------|---------|
| `css/montserrat.css` | `@font-face` rules pointing at the local files |
| `webfonts/montserrat-latin.woff2` | Latin subset (35 KB) |
| `webfonts/montserrat-latin-ext.woff2` | Latin Extended subset (68 KB) |

These are **variable** fonts covering weights 300-700 in a single file per
subset, so the whole UI needs just two files. The `unicode-range` rules are kept
from the original CSS, so a page that only uses basic Latin never loads the
extended file.

Only the Latin subsets are shipped. Text in Cyrillic, Greek or Vietnamese (e.g.
a host named in one of those scripts) falls back to the system sans-serif; add
the corresponding subset below if that ever matters.

## Updating

```bash
curl -A "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36" \
  "https://fonts.googleapis.com/css2?family=Montserrat:wght@300..700&display=swap"
```

That returns one `@font-face` block per subset. Download the `.woff2` for each
subset you want into `webfonts/`, then mirror its `unicode-range` into
`css/montserrat.css` with the `src:` rewritten to the local path. The browser
User-Agent matters - it's what makes Google serve woff2 variable fonts.

## License

Montserrat by Julieta Ulanovsky, Sol Matas, Juan Pablo del Peral, Jacques Le
Bailly.

Licensed under the SIL Open Font License 1.1:
https://openfontlicense.org

Available at https://fonts.google.com/specimen/Montserrat
