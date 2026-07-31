# Font Awesome Free 6.0.0 (vendored)

Bundled with Connectify so the web UI renders its icons offline, without
depending on a CDN.

Source: https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/

Contents:

| File | Purpose |
|------|---------|
| `css/fontawesome.min.css` | Core styles and icon glyph definitions |
| `css/solid.min.css` | `fas` / `fa-solid` family |
| `css/regular.min.css` | `far` / `fa-regular` family |
| `css/brands.min.css` | `fab` / `fa-brands` family (the GitHub link in the footer) |
| `webfonts/fa-solid-900.woff2` | Solid font |
| `webfonts/fa-regular-400.woff2` | Regular font |
| `webfonts/fa-brands-400.woff2` | Brands font |

The solid, regular and brands families are shipped. The `.ttf` fallbacks were removed from the two `@font-face` rules since only the
`.woff2` files are vendored; every browser Connectify runs in supports woff2.

## Updating

```bash
BASE=https://cdnjs.cloudflare.com/ajax/libs/font-awesome/<version>
for f in css/fontawesome.min.css css/solid.min.css css/regular.min.css css/brands.min.css \
         webfonts/fa-solid-900.woff2 webfonts/fa-regular-400.woff2 webfonts/fa-brands-400.woff2; do
  curl -fL "$BASE/$f" -o "static/vendor/fontawesome/$f"
done
# then drop the ".ttf" entries from the src: lines in solid/regular.min.css
```

## License

Font Awesome Free by @fontawesome - https://fontawesome.com
License: https://fontawesome.com/license/free

- Icons: CC BY 4.0
- Fonts: SIL OFL 1.1
- Code: MIT

Copyright 2022 Fonticons, Inc.
