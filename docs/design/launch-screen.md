# Adex launch screen concept

![White launch screen with a sage ribbon path and morning sun](assets/adex-launch-concept.png)

White canvas, a restrained sage/ivory path toward morning light, charcoal Adex
wordmark, and “每一步，都算数。” (“Every step counts.”). The visual connects a
personal assistant's everyday actions with steady progress.

This AI-generated raster is a design concept, not an installed launch screen.
For implementation, keep system launch presentation brief, preserve safe areas,
use aspect-fit to avoid cropping the wordmark, and do not add an artificial delay.
Live text should be separate from illustration for accessibility/localization.

## Mountain sunrise revision

![Mountain sunrise concept with updated slogan](assets/adex-launch-mountain-v2.png)

A winding ivory trail through muted blue/green mountains blends into the white
canvas. The user-selected slogan is “让智能，成为日常。” (“Make intelligence part
of everyday life.”). This version is the selected app launch artwork (integration details below).
The original concept is retained for comparison.

## Implemented iOS identity

The mountain revision is now the iOS launch asset, fitted without cropping on a
white canvas. Native session bootstrap displays the same artwork, followed by a
180ms content reveal respecting Reduce Motion, with no artificial startup delay.
The system launch storyboard itself is static. The new simplified mountain/path/
sun icon is installed in the iOS asset catalog and used for Web favicon/sidebar.
Launch text remains baked into the approved illustration; the bootstrap wrapper
provides an accessible status label. Future translated variants need separate art.

![Simplified app icon](assets/adex-icon-mountain.png)
