# Doctor v2 Migration

The doctor collects diagnostics and a 14-block maturity matrix.

## Running

```bash
python tools/doctor.py --out reports/latest/analysis --json --html
```

This writes `reports/latest/analysis.json`, `reports/latest/analysis.html` and a `state.log` in the same folder.

## Reading the report

- `generated_at_utc` – UTC ISO8601 timestamp.
- `overall_score` – average of all block scores.
- `blocks` – 14 items (`B0`..`B13`) with `status` (`OK`, `WARN`, `MISSING`), `score`, `metrics` and `notes`.

## CLI help

```
$ python tools/doctor.py --help
usage: doctor.py --out OUT [--json] [--html]

Collect project diagnostics

optional arguments:
  --out OUT   Output file prefix for the report
  --json      Write JSON report
  --html      Write HTML report
```
