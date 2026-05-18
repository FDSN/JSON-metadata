# stationxml_to_json.py

Local converter from FDSN StationXML to JSON/JSON-LD metadata documents derived from the JSON metadata RFC-like proposal.

The parser uses only Python standard library modules and `xml.etree.ElementTree` for XML reading.

## Supported output profiles

- `machine-jsonld-flat`
- `machine-jsonld-bare`
- `human-flat-grouped`
- `human-tree-optional`
- `machine-json-bare`

## Supported levels

- `network`
- `station`
- `channel`

`response` is reserved and intentionally returns an error for now. Use `--level channel --include responseSummary` to extract a compact `ResponseSummary` from StationXML `InstrumentSensitivity`.

## Usage

```bash
python3 stationxml_to_json.py INGV_ACATE.xml \
  --level channel \
  --profile machine-jsonld-flat \
  --include provenance,responseSummary \
  --pretty \
  -o INGV_ACATE.machine-jsonld-flat.channel.json
```

Human tree view:

```bash
python3 stationxml_to_json.py INGV_ACATE.xml \
  --level channel \
  --profile human-tree-optional \
  --include responseSummary \
  --pretty
```

Bare JSON view:

```bash
python3 stationxml_to_json.py INGV_ACATE.xml \
  --level station \
  --profile machine-json-bare \
  --pretty
```

## Notes

- Network IDs are emitted as `FDSN:{network}`.
- Station IDs are emitted as `FDSN:{network}_{station}`.
- Channel IDs are emitted as `FDSN:{network}_{station}_{location}_{band}_{source}_{subsource}`.
- Empty StationXML `locationCode` is represented by the resulting double underscore, e.g. `FDSN:IV_ACATE__H_N_Z`.
- Channel epoch IDs append `/interval/{start}-{end}` where missing end dates become `open`.
