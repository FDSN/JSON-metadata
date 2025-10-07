#!/usr/bin/env python3
import json, sys, re, argparse, pathlib

def prefixes_in_terms(terms):
    return {t.split(":")[0] for t in terms if isinstance(t,str) and ":" in t}

def load_json(p): 
    with open(p, "r", encoding="utf-8") as f: 
        return json.load(f)

def main():
    ap = argparse.ArgumentParser(description="Lint JSON-LD context against mapping usage")
    ap.add_argument("--context", default="contexts/context-strict-v1.jsonld")
    ap.add_argument("--mapping", default="mappings/icdm-to-owl.json")
    ap.add_argument("--fail-on-warn", action="store_true")
    args = ap.parse_args()

    ctx = load_json(args.context)
    mp  = load_json(args.mapping)
    ctxc = ctx.get("@context", {})
    ctx_prefixes = {k for k,v in ctxc.items() if isinstance(v, str)}
    explicit = {k for k,v in ctxc.items() if isinstance(v, dict) and "@id" in v}

    used = set()
    for section in ("networkMapping","stationMapping"):
        props = (mp.get(section, {}) or {}).get("properties", {}) or {}
        used.update(props.keys())
        typ = (mp.get(section, {}) or {}).get("type")
        if typ: used.add(typ)

    needed = prefixes_in_terms(used)

    missing = sorted([p for p in needed if p not in ctx_prefixes and p not in explicit])
    warnings = []
    if missing:
        warnings.append(f"Missing prefixes in context: {', '.join(missing)}")

    # Check that fdsn:memberOfNetwork, if used, is typed as @id
    mon_key = None
    for k,v in ctxc.items():
        if isinstance(v, dict) and v.get("@id") == "fdsn:memberOfNetwork":
            mon_key = k
            break
    if "fdsn:memberOfNetwork" in used and not mon_key:
        warnings.append("Property fdsn:memberOfNetwork should be present in context with @type '@id' (add: \"memberOfNetwork\": {\"@id\": \"fdsn:memberOfNetwork\", \"@type\": \"@id\"})")

    # Check wgs lat/long availability
    for req in ("wgs",):
        if req not in ctx_prefixes:
            warnings.append("Prefix 'wgs' is required for WGS84 latitude/longitude properties.")

    if warnings:
        print("Context Lint: WARN")
        for w in warnings:
            print("-", w)
        if args.fail_on_warn:
            sys.exit(2)
    else:
        print("Context Lint: OK")

if __name__ == "__main__":
    main()
