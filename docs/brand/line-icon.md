# Stargazer line icon

Editable canonical source: `apps/web/public/brand/adex-icon.svg`.
A back-view scholar outline with a hair knot and robe, three four-point stars and
three smaller star dots. Warm ivory background (#f6f2e9), ink blue (#253e4b).
No text, mountain detail, baked-in rounded corners, gradients or external imagery.

Export: render the SVG at 1024×1024 using macOS Quick Look, then encode as opaque
RGB PNG (Pillow RGB conversion without changing composition). Both Web icon and
AppIcon-512@2x.png contain identical exported pixels. iOS applies its own icon mask.
The source can be edited as vector paths without a generative image dependency.

Validation: visually inspected the raster output; dimensions 1024×1024 with no alpha.
iOS bundle and signed device build verify the asset catalog. No behavior tests needed
for replacing a static brand asset.
