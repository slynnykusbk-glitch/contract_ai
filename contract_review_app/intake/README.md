# Intake module

Utilities for preparing raw contract text for downstream processing.

## Normalization

* Windows (``\r\n``) and legacy Mac (``\r``) line endings are converted to
  ``\n``.
* Curly quotes, various dashes and non‑breaking spaces are replaced with their
  ASCII equivalents.
* Zero‑width characters are stripped.

The normalization step builds a strict offset map so every character in the
normalized text can be traced back to the original position.

## Splitting

``splitter.split_into_candidate_blocks`` segments the normalized text using a
set of heuristics:

1. paragraphs are split on double new lines;
2. numbered or alphabetical list items and headings start new blocks;
3. very long paragraphs are further divided into sentences;
4. short blocks and adjacent headings may be merged;
5. lines that break a sentence mid‑way are merged back together.

The resulting spans are non‑overlapping and aim to cover at least 99.5% of the
non‑whitespace characters in the normalized text.
