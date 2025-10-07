#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
StationXML to JSON-LD via external mappings (robust + where filters + extra lookups)
- Step 1: XML to ICDM using yaml mapping (xml-to-icdm.yaml)
- Step 2: ICDM to JSON-LD using yaml/json mapping (icdm-to-owl.yaml or .json) + @context
Requirements:
  - Python 3.9+
  - PyYAML  (pip install pyyaml)
"""

import argparse
import json
import os
import re
import xml.etree.ElementTree as ET

try:
    import yaml
except ImportError as e:
    raise SystemExit("PyYAML is required. Install with: pip install pyyaml") from e


# ---------------------------
# Helpers
# ---------------------------

def text_of(elem):
    return (elem.text or "").strip() if elem is not None else None


def get_attr(elem, expr):
    # expr like '@code'
    return elem.get(expr[1:]) if expr.startswith("@") else None


def find_with_ns_chain(elem, path, ns_prefix_map):
    """
    Resolve a multi-step path like 'sta:Site/sta:Name' where each step can have a namespace prefix.
    Iterate segment by segment and build Clark-notation {uri}local for .find().
    """
    current = elem
    for segment in path.split("/"):
        if not segment:
            return None
        if ":" in segment:
            pfx, local = segment.split(":", 1)
            uri = ns_prefix_map.get(pfx)
            if not uri:
                # last-resort: try raw
                current = current.find(segment)
            else:
                qname = f"{{{uri}}}{local}"
                current = current.find(qname)
        else:
            current = current.find(segment)
        if current is None:
            return None
    return current


def extract_field(elem, field_expr, ns_prefix_map):
    """
    Supports:
      - '@attr'
      - 'sta:Tag/text()'
      - 'sta:Parent/sta:Child/text()' (multi-step)
    """
    expr = field_expr.strip()
    if expr.startswith("@"):
        return get_attr(elem, expr)

    if expr.endswith("/text()"):
        path = expr[:-7]
        node = find_with_ns_chain(elem, path, ns_prefix_map)
        return text_of(node)

    return None


def render_iri(template, env):
    def repl(m): return str(env.get(m.group(1), ""))
    return re.sub(r"\${([^}]+)}", repl, template)


def build_period(start, end):
    node = {"@type": "time:ProperInterval"}
    if start:
        node["time:hasBeginning"] = {"@type": "time:Instant", "time:inXSDDateTime": start}
    if end:
        node["time:hasEnd"] = {"@type": "time:Instant", "time:inXSDDateTime": end}
    return node


# ---- WHERE evaluation helpers ----

def _eval_exists(item, fields):
    for f in fields or []:
        key = f.split('.')[-1]  # "ICDM.Network.code" -> "code"
        if key not in item or item.get(key) in (None, "", []):
            return False
    return True

def _eval_equals(item, mapping):
    for f, expected in (mapping or {}).items():
        key = f.split('.')[-1]
        if str(item.get(key)) != str(expected):
            return False
    return True

def _eval_regex(item, mapping):
    for f, pattern in (mapping or {}).items():
        key = f.split('.')[-1]
        val = item.get(key)
        if val is None:
            return False
        try:
            if not re.search(pattern, str(val)):
                return False
        except re.error:
            return False
    return True

def _passes_where(item, where_def):
    if not where_def:
        return True
    if "exists" in where_def and not _eval_exists(item, where_def.get("exists")):
        return False
    if "equals" in where_def and not _eval_equals(item, where_def.get("equals")):
        return False
    if "regex" in where_def and not _eval_regex(item, where_def.get("regex")):
        return False
    return True


# ---------------------------
# Step 1: XML to ICDM
# ---------------------------

def extract_icdm(xml_path, xml_map_path):
    cfg = yaml.safe_load(open(xml_map_path, "r", encoding="utf-8"))
    ns = cfg.get("namespaces", {}) or {}

    tree = ET.parse(xml_path)
    root = tree.getroot()

    out = {"Network": [], "Station": []}

    # Networks
    net_path = cfg["network"]["path"]
    net_fields = cfg["network"]["fields"]
    for net in root.findall(net_path):
        row = {}
        for key, expr in net_fields.items():
            row[key] = extract_field(net, expr, ns) if not expr.startswith("@") else get_attr(net, expr)
        out["Network"].append(row)

    # Stations
    sta_path = cfg["station"]["path"]
    sta_fields = cfg["station"]["fields"]
    for st in root.findall(sta_path):
        row = {}
        for key, expr in sta_fields.items():
            row[key] = extract_field(st, expr, ns) if not expr.startswith("@") else get_attr(st, expr)
        out["Station"].append(row)

    return out


# ---------------------------
# Step 2: ICDM to JSON-LD
# ---------------------------

def load_mapping(owl_map_path):
    if owl_map_path.endswith(".json"):
        return json.load(open(owl_map_path, "r", encoding="utf-8"))
    return yaml.safe_load(open(owl_map_path, "r", encoding="utf-8"))


def apply_mapping(icdm, owl_map_path, context, compact=True, extra_lookups=None):
    cfg = load_mapping(owl_map_path)

    iri_policy = cfg.get("iriPolicy", {})
    baseId = iri_policy.get("baseId", "")
    net_tpl = iri_policy.get("networkIri", "${baseId}network/${ICDM.Network.code}")
    sta_tpl = iri_policy.get("stationIri",  "${baseId}station/${ICDM.Network.code}_${ICDM.Station.code}")

    net_map = cfg.get("networkMapping", {})
    sta_map = cfg.get("stationMapping", {})

    out = {"@context": context["@context"] if compact else None, "@graph": []}

    # lookups (merge extra if provided)
    lookups = cfg.get("lookups", {})
    if extra_lookups:
        for k, v in (extra_lookups or {}).items():
            if isinstance(v, dict):
                lookups.setdefault(k, {}).update(v)
            else:
                lookups[k] = v

    # Networks
    net_where = (net_map or {}).get("where")
    for net in icdm.get("Network", []):
        if not _passes_where(net, net_where):
            continue

        env = {
            "baseId": baseId,
            "ICDM.Network.code": net.get("code", "")
        }
        net_id = render_iri(net_tpl, env)
        net_node = {"@id": net_id, "@type": net_map.get("type", "fdsn:Network")}

        for prop, rule in (net_map.get("properties") or {}).items():
            if not isinstance(rule, dict):
                continue

            cond = rule.get("when")
            if cond:
                key = cond.split(".")[-1]
                if not net.get(key):
                    continue

            if "from" in rule:
                key = rule["from"].split(".")[-1]
                val = net.get(key)
                if val is None or val == "":
                    continue

                if rule.get("lookup"):
                    table = lookups.get(rule["lookup"], {})
                    mapped = table.get(val) or table.get(str(val).lower()) or table.get(str(val).capitalize())
                    if mapped:
                        net_node.setdefault(prop, []).append({"@id": mapped})
                        continue

                if rule.get("type") == "iriOrLiteral" and (isinstance(val, str) and (val.startswith("http://") or val.startswith("https://"))):
                    net_node.setdefault(prop, []).append({"@id": val})
                elif "datatype" in rule:
                    net_node.setdefault(prop, []).append({"@value": val, "@type": rule["datatype"]})
                else:
                    net_node.setdefault(prop, []).append(val)

            elif rule.get("build") == "period":
                args = rule.get("args", [])
                start = net.get(args[0].split(".")[-1]) if len(args) > 0 else None
                end   = net.get(args[1].split(".")[-1]) if len(args) > 1 else None
                period_node = build_period(start, end)
                net_node.setdefault(prop, []).append(period_node)

        out["@graph"].append(net_node)

        # Stations (simple pairing; in real life link by explicit parent)
        sta_where = (sta_map or {}).get("where")
        for st in icdm.get("Station", []):
            if not _passes_where(st, sta_where):
                continue

            env2 = {
                "baseId": baseId,
                "ICDM.Network.code": net.get("code", ""),
                "ICDM.Station.code": st.get("code", "")
            }
            st_id = render_iri(sta_tpl, env2)
            st_node = {"@id": st_id, "@type": sta_map.get("type", "fdsn:Station")}

            for prop, rule in (sta_map.get("properties") or {}).items():
                if not isinstance(rule, dict):
                    continue

                if "fromIri" in rule:
                    st_node.setdefault(prop, []).append({"@id": render_iri(rule["fromIri"], env2)})

                elif "from" in rule:
                    key = rule["from"].split(".")[-1]
                    val = st.get(key)
                    if not val:
                        continue

                    if rule.get("lookup"):
                        table = lookups.get(rule["lookup"], {})
                        mapped = table.get(val) or table.get(str(val).lower()) or table.get(str(val).capitalize())
                        if mapped:
                            st_node.setdefault(prop, []).append({"@id": mapped})
                            continue

                    if rule.get("type") == "iriOrLiteral" and (val.startswith("http://") or val.startswith("https://")):
                        st_node.setdefault(prop, []).append({"@id": val})
                    elif "datatype" in rule:
                        st_node.setdefault(prop, []).append({"@value": val, "@type": rule["datatype"]})
                    else:
                        st_node.setdefault(prop, []).append(val)

            out["@graph"].append(st_node)

    if not compact:
        out.pop("@context", None)
    return out


# ---------------------------
# CLI
# ---------------------------

def main():
    ap = argparse.ArgumentParser(description="StationXML to JSON-LD via external mappings")
    ap.add_argument("--xml", default="examples/sample.stationxml")
    ap.add_argument("--xml-map", default="mappings/xml-to-icdm.yaml")
    ap.add_argument("--owl-map", default="mappings/icdm-to-owl.yaml",
                    help="Can be YAML or JSON")
    ap.add_argument("--context", default="contexts/context-strict-v1.jsonld")
    ap.add_argument("--expanded", action="store_true", help="Emit expanded (no @context)")
    ap.add_argument("--extra-lookups", help="Path to a JSON file with additional lookups to merge", default=None)
    ap.add_argument("--out", default="build/output.jsonld")
    args = ap.parse_args()

    with open(args.context, "r", encoding="utf-8") as f:
        ctx = json.load(f)

    icdm = extract_icdm(args.xml, args.xml_map)

    extra = None
    if args.extra_lookups:
        with open(args.extra_lookups, "r", encoding="utf-8") as f:
            extra = json.load(f)

    data = apply_mapping(icdm, args.owl_map, ctx, compact=(not args.expanded), extra_lookups=extra)

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print("Wrote", args.out)


if __name__ == "__main__":
    main()
