# Offline figure database

`figures.json` is the canonical editable database, schema version 1. The lookup key
is the pair `(character_id, variant_id)`, stored as decimal integers. Character IDs
are read from the 3 bytes at 0x10; variant IDs from 2 bytes at 0x1C, little-endian.
Records are catalogue metadata, not a check that a dump has valid game save data.

Fields:

- `name`: display name of this edition; `character_name`: base character identity.
- `element`, `figure_type`, `variant_name`, `edition_game`: display/filter metadata.
- `swap_half`: Top or Bottom where applicable; two halves are separate dumps.
- `abilities`, `notes`: short gameplay guidance and uncertainties.
- `ps3_supported`: false for Nintendo-exclusive guest figures/vehicles, null when
  no platform verdict is recorded. Null must never be displayed as supported.
- `sources`: references into the file's source manifest.

An exact known pair in the browser yields `match=exact`. Otherwise the browser supplies
`match=character_only` or `match=unknown`. Character-only fallback does not guess
edition, release game or abilities. If editions have different types (Mini vs
Sidekick), an unknown variant's type remains Unknown.

The catalogue runs entirely offline. Correct or extend records locally, restart
skylanders-web, and rerun `python3 -m unittest discover -s tests`. JSON must have
unique ID pairs. See THIRD_PARTY.md for sources and attribution.

Edition game means the edition's release era, not the earliest game that accepts
its underlying character. Backward-compatible reposes, special items and vehicles
have exceptions; a universal game-compatibility filter is deliberately not inferred.
Identification metadata does not alter the USB portal protocol or figure IDs.

## Runtime in v0.5

The browser loads this file through /api/catalogue and builds its lookup map.
The Pi streams the JSON file as bytes and never runs a catalogue lookup during
portal operation. /api/identities reads up to 16 requested headers once; /api/state
is unchanged from the pre-catalogue version. catalogue.py is retained only as a
reference/test utility and is not imported by app.py or identity_api.py.
