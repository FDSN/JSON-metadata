# StationXML → JSON-LD Mapping Kit 

Convert FDSN StationXML to JSON-LD using external mappings, with **WHERE filters** and **extra lookup merging**.

## Structure
- `src/convert.py` — Converter (YAML/JSON mapping; supports where & extra-lookups).
- `mappings/xml-to-icdm.yaml` — StationXML → ICDM field extraction.
- `mappings/icdm-to-owl.json` — ICDM → Ontology mapping.
- `mappings/extra-lookups.json` — Extra lookup tables to merge at runtime.
- `contexts/context-strict-v1.jsonld` — Strict JSON-LD context.
- `shapes/network-open-has-station.ttl` — SHACL example.
- `tools/ontology_to_mapping_template.py` — Generate mapping template from OWL.
- `examples/sample.stationxml` — Sample input.
- `build/` — Output folder.

## Requirements
- Python 3.9+
- PyYAML: `pip install pyyaml`
- (Optional) rdflib: `pip install rdflib` (for the template generator)

## Quick start
```bash
python3 src/convert.py   --xml examples/sample.stationxml   --xml-map mappings/xml-to-icdm.yaml   --owl-map mappings/icdm-to-owl.json   --context contexts/context-strict-v1.jsonld   --out build/output.jsonld
```

### Expanded (no @context)
```bash
python3 src/convert.py --xml examples/sample.stationxml --expanded --out build/output-expanded.jsonld
```

## WHERE filters
Add in `networkMapping` / `stationMapping`:
```json
"where": {
  "exists": ["ICDM.Network.code"],
  "equals": { "ICDM.Network.restricted": "open" },
  "regex":  { "ICDM.Network.code": "^[A-Z0-9]+$" }
}
```
- `exists`: all listed fields must be present (non-empty).
- `equals`: exact match (string compare).
- `regex`: Python regex applied to the string value.

## Extra lookups (runtime merge)
```bash
python3 src/convert.py   --xml examples/sample.stationxml   --owl-map mappings/icdm-to-owl.json   --extra-lookups mappings/extra-lookups.json   --out build/output.jsonld
```

## Generate mapping template from OWL
```bash
python3 tools/ontology_to_mapping_template.py   --owl path/to/ontology.ttl   --base-id https://webservices.example.org/id/   --out mappings/icdm-to-owl.template.json   --sparql-where-out tools/where-templates.sparql
```

## Check for errors in ontology
```bash
python tools/ontology_linter.py your_ontology.ttl --apply-fixes --base https://example.org/ontology/
# or with SHACL
python tools/ontology_linter.py your_ontology.ttl --apply-fixes --shapes shapes.ttl
```

## Troubleshooting
- Install `PyYAML` (and `rdflib` for the template tool).
- If output is empty, check `where` clauses and your mapping field names.
- Namespaces in `xml-to-icdm.yaml` must match StationXML 1.x.
- Multi-step XML paths like `sta:Site/sta:Name/text()` are supported.

## License
TODO

---
### Tooling: Context Lint
Run a consistency check between mapping and JSON-LD context:
```bash
python3 tools/validate_context.py --context contexts/context-strict-v1.jsonld --mapping mappings/icdm-to-owl.json
# or fail CI on warnings:
python3 tools/validate_context.py --fail-on-warn
```
The linter flags missing prefixes and ensures `fdsn:memberOfNetwork` is `@id`-typed.

---
### Reminder: Service base for resource IDs
Resource IRIs can be served from a distinct base using `iriPolicy.resourceBaseId`.
Example:
```json
{
  "iriPolicy": {
    "baseId": "https://webservices.example.org/id/",
    "resourceBaseId": "https://webservices.example.org/resource/",
    "networkIri": "${resourceBaseId}FDSN:${ICDM.Network.code}",
    "stationIri": "${resourceBaseId}FDSN:${ICDM.Network.code}_${ICDM.Station.code}"
  }
}
```

