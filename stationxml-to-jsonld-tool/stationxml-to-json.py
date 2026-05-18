#!/usr/bin/env python3
"""
Convert FDSN StationXML to JSON/JSON-LD documents derived from the
JSON metadata RFC-like proposal.

The parser intentionally uses only Python's standard library and
xml.etree.ElementTree for XML reading.

Supported output profiles:
  - machine-jsonld-flat
  - machine-jsonld-bare
  - human-flat-grouped
  - human-tree-optional
  - machine-json-bare

Full StationXML Response conversion is intentionally out of scope. When
requested with --include responseSummary, the tool extracts a compact
ResponseSummary from InstrumentSensitivity plus Sensor/DataLogger text
when available.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple
import xml.etree.ElementTree as ET

DEFAULT_CONTEXT_URL = "https://example.org/fdsn/context/station-metadata.jsonld"
SUPPORTED_PROFILES = {
    "machine-jsonld-flat",
    "machine-jsonld-bare",
    "human-flat-grouped",
    "human-tree-optional",
    "machine-json-bare",
}
SUPPORTED_LEVELS = {"network", "station", "channel", "response"}
SUPPORTED_CONTEXT_MODES = {"external", "inline", "none"}
SUPPORTED_INCLUDES = {"provenance", "responseSummary"}

INLINE_CONTEXT: Dict[str, Any] = {
    "@vocab": "https://example.org/fdsn/station-metadata#",
    "FDSN": "https://www.fdsn.org/networks/detail/",
    "Network": "https://example.org/fdsn/station-metadata#Network",
    "Station": "https://example.org/fdsn/station-metadata#Station",
    "Channel": "https://example.org/fdsn/station-metadata#Channel",
    "ChannelEpoch": "https://example.org/fdsn/station-metadata#ChannelEpoch",
    "ResponseSummary": "https://example.org/fdsn/station-metadata#ResponseSummary",
    "StationMetadataDocument": "https://example.org/fdsn/station-metadata#StationMetadataDocument",
    "AuthoritativeMetadataSource": "https://example.org/fdsn/station-metadata#AuthoritativeMetadataSource",
    "memberOfNetwork": {"@type": "@id"},
    "memberOfStation": {"@type": "@id"},
    "describesChannel": {"@type": "@id"},
    "hasResponseSummary": {"@type": "@id"},
    "authoritativeSource": {"@type": "@id"},
}


def local_name(tag: str) -> str:
    """Return the namespace-free XML local name."""
    if "}" in tag:
        return tag.rsplit("}", 1)[1]
    return tag


def children(element: ET.Element, name: Optional[str] = None) -> Iterable[ET.Element]:
    """Yield direct children, optionally filtered by local name."""
    for child in list(element):
        if name is None or local_name(child.tag) == name:
            yield child


def first_child(element: ET.Element, name: str) -> Optional[ET.Element]:
    return next(children(element, name), None)


def text_of(element: Optional[ET.Element]) -> Optional[str]:
    if element is None or element.text is None:
        return None
    value = element.text.strip()
    return value if value != "" else None


def child_text(element: ET.Element, name: str) -> Optional[str]:
    return text_of(first_child(element, name))


def to_number(value: Optional[str]) -> Optional[Any]:
    if value is None:
        return None
    value = value.strip()
    if value == "":
        return None
    try:
        if re.fullmatch(r"[-+]?\d+", value):
            return int(value)
        return float(value)
    except ValueError:
        return value


def put_if_present(target: Dict[str, Any], key: str, value: Any) -> None:
    if value is not None:
        target[key] = value


def compact_time(value: Optional[str]) -> str:
    """Compact an ISO-ish timestamp for stable interval ids."""
    if not value:
        return "open"
    value = value.strip()
    value = value.replace("-", "").replace(":", "")
    value = value.replace(".", "")
    return value


def stationxml_identifier_items(element: ET.Element) -> List[Dict[str, Any]]:
    """Collect StationXML Identifier children from any namespace."""
    items: List[Dict[str, Any]] = []
    for ident in children(element, "Identifier"):
        value = text_of(ident)
        if value is None:
            continue
        item: Dict[str, Any] = {"value": value}
        for k, v in ident.attrib.items():
            item[local_name(k)] = v
        items.append(item)
    return items


def channel_id(network_code: str, station_code: str, location_code: Optional[str], channel_code: str) -> str:
    loc = location_code or ""
    if len(channel_code) == 3:
        return f"FDSN:{network_code}_{station_code}_{loc}_{channel_code[0]}_{channel_code[1]}_{channel_code[2]}"
    return f"FDSN:{network_code}_{station_code}_{loc}_{channel_code}"


def epoch_id(channel_resource_id: str, start: Optional[str], end: Optional[str]) -> str:
    return f"{channel_resource_id}/interval/{compact_time(start)}-{compact_time(end)}"


def response_summary_id(epoch_resource_id: str) -> str:
    return f"{epoch_resource_id}/response-summary"


def parse_equipment_description(channel_el: ET.Element, equipment_name: str) -> Optional[str]:
    equipment = first_child(channel_el, equipment_name)
    if equipment is None:
        return None
    for tag in ("Description", "Type", "Manufacturer", "Model", "SerialNumber"):
        value = child_text(equipment, tag)
        if value:
            return value
    return None


def parse_units(units_el: Optional[ET.Element]) -> Optional[str]:
    if units_el is None:
        return None
    return child_text(units_el, "Name") or text_of(units_el)


def parse_response_summary(channel_el: ET.Element, epoch_resource_id: str) -> Optional[Dict[str, Any]]:
    response = first_child(channel_el, "Response")
    if response is None:
        return None
    sensitivity = first_child(response, "InstrumentSensitivity")
    if sensitivity is None:
        return None

    node: Dict[str, Any] = {
        "@id": response_summary_id(epoch_resource_id),
        "@type": "ResponseSummary",
    }
    put_if_present(node, "sensorDescription", parse_equipment_description(channel_el, "Sensor"))
    put_if_present(node, "dataLoggerDescription", parse_equipment_description(channel_el, "DataLogger"))
    put_if_present(node, "instrumentSensitivity", to_number(child_text(sensitivity, "Value")))
    put_if_present(node, "instrumentSensitivityFrequency", to_number(child_text(sensitivity, "Frequency")))
    put_if_present(node, "inputUnits", parse_units(first_child(sensitivity, "InputUnits")))
    put_if_present(node, "outputUnits", parse_units(first_child(sensitivity, "OutputUnits")))
    return node


def parse_stationxml(path: Path, *, include_response_summary: bool) -> Dict[str, Any]:
    tree = ET.parse(path)
    root = tree.getroot()

    header = {
        "source": child_text(root, "Source"),
        "sender": child_text(root, "Sender"),
        "module": child_text(root, "Module"),
        "moduleURI": child_text(root, "ModuleURI"),
        "created": child_text(root, "Created"),
        "schemaVersion": root.attrib.get("schemaVersion"),
    }

    result: Dict[str, Any] = {
        "header": header,
        "networks": [],
        "stations": [],
        "channels": [],
        "channelEpochs": [],
        "responseSummaries": [],
    }

    for network_el in children(root, "Network"):
        network_code = network_el.attrib.get("code", "")
        network_resource_id = f"FDSN:{network_code}"
        network: Dict[str, Any] = {
            "@id": network_resource_id,
            "@type": "Network",
        }
        put_if_present(network, "description", child_text(network_el, "Description"))
        put_if_present(network, "restrictedStatus", network_el.attrib.get("restrictedStatus"))
        put_if_present(network, "startDate", network_el.attrib.get("startDate"))
        put_if_present(network, "endDate", network_el.attrib.get("endDate"))
        put_if_present(network, "totalStations", to_number(child_text(network_el, "TotalNumberStations")))
        put_if_present(network, "selectedStations", to_number(child_text(network_el, "SelectedNumberStations")))
        identifiers = stationxml_identifier_items(network_el)
        if identifiers:
            network["identifiers"] = identifiers
        result["networks"].append(network)

        for station_el in children(network_el, "Station"):
            station_code = station_el.attrib.get("code", "")
            station_resource_id = f"FDSN:{network_code}_{station_code}"
            station: Dict[str, Any] = {
                "@id": station_resource_id,
                "@type": "Station",
                "memberOfNetwork": network_resource_id,
            }
            site_el = first_child(station_el, "Site")
            put_if_present(station, "stationName", child_text(site_el, "Name") if site_el is not None else None)
            put_if_present(station, "lat", to_number(child_text(station_el, "Latitude")))
            put_if_present(station, "lon", to_number(child_text(station_el, "Longitude")))
            put_if_present(station, "elevation", to_number(child_text(station_el, "Elevation")))
            put_if_present(station, "restrictedStatus", station_el.attrib.get("restrictedStatus"))
            put_if_present(station, "startDate", station_el.attrib.get("startDate"))
            put_if_present(station, "endDate", station_el.attrib.get("endDate"))
            put_if_present(station, "creationDate", child_text(station_el, "CreationDate"))
            put_if_present(station, "totalChannels", to_number(child_text(station_el, "TotalNumberChannels")))
            put_if_present(station, "selectedChannels", to_number(child_text(station_el, "SelectedNumberChannels")))
            identifiers = stationxml_identifier_items(station_el)
            if identifiers:
                station["identifiers"] = identifiers
            result["stations"].append(station)

            for channel_el in children(station_el, "Channel"):
                code = channel_el.attrib.get("code", "")
                location_code = channel_el.attrib.get("locationCode", "")
                ch_id = channel_id(network_code, station_code, location_code, code)
                channel: Dict[str, Any] = {
                    "@id": ch_id,
                    "@type": "Channel",
                    "memberOfStation": station_resource_id,
                }
                identifiers = stationxml_identifier_items(channel_el)
                if identifiers:
                    channel["identifiers"] = identifiers
                result["channels"].append(channel)

                start = channel_el.attrib.get("startDate")
                end = channel_el.attrib.get("endDate")
                ep_id = epoch_id(ch_id, start, end)
                epoch: Dict[str, Any] = {
                    "@id": ep_id,
                    "@type": "ChannelEpoch",
                    "describesChannel": ch_id,
                }
                put_if_present(epoch, "lat", to_number(child_text(channel_el, "Latitude")))
                put_if_present(epoch, "lon", to_number(child_text(channel_el, "Longitude")))
                put_if_present(epoch, "elevation", to_number(child_text(channel_el, "Elevation")))
                put_if_present(epoch, "depth", to_number(child_text(channel_el, "Depth")))
                put_if_present(epoch, "azimuth", to_number(child_text(channel_el, "Azimuth")))
                put_if_present(epoch, "dip", to_number(child_text(channel_el, "Dip")))
                put_if_present(epoch, "sampleRate", to_number(child_text(channel_el, "SampleRate")))
                put_if_present(epoch, "restrictedStatus", channel_el.attrib.get("restrictedStatus"))
                put_if_present(epoch, "startDate", start)
                put_if_present(epoch, "endDate", end)

                if include_response_summary:
                    summary = parse_response_summary(channel_el, ep_id)
                    if summary:
                        epoch["hasResponseSummary"] = summary["@id"]
                        result["responseSummaries"].append(summary)
                result["channelEpochs"].append(epoch)

    return result


def context_value(mode: str) -> Optional[Any]:
    if mode == "external":
        return DEFAULT_CONTEXT_URL
    if mode == "inline":
        return INLINE_CONTEXT
    if mode == "none":
        return None
    raise ValueError(f"Unsupported context mode: {mode}")


def nodes_for_level(data: Dict[str, Any], level: str, includes: set[str]) -> List[Dict[str, Any]]:
    if level == "response":
        raise NotImplementedError("Full StationXML Response conversion is not implemented; use --level channel --include responseSummary.")
    nodes: List[Dict[str, Any]] = []
    nodes.extend(data["networks"])
    if level in {"station", "channel"}:
        nodes.extend(data["stations"])
    if level == "channel":
        nodes.extend(data["channels"])
        nodes.extend(data["channelEpochs"])
        if "responseSummary" in includes:
            nodes.extend(data["responseSummaries"])
    return nodes


def provenance_nodes(path: Path, data: Dict[str, Any], level: str, profile: str) -> List[Dict[str, Any]]:
    raw = path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    source_id = "urn:fdsn:source:" + digest[:16]
    document_id = "urn:fdsn:station-metadata-document:" + digest[:16]
    header = data["header"]
    source_node = {
        "@id": source_id,
        "@type": "AuthoritativeMetadataSource",
    }
    put_if_present(source_node, "provider", header.get("sender") or header.get("source"))
    put_if_present(source_node, "service", header.get("moduleURI") or header.get("module"))
    put_if_present(source_node, "sourceFormat", "StationXML")
    put_if_present(source_node, "sourceFormatVersion", header.get("schemaVersion"))
    put_if_present(source_node, "retrievedAt", header.get("created"))

    document_node = {
        "@id": document_id,
        "@type": "StationMetadataDocument",
        "identifier": path.name,
        "profile": profile,
        "contentLevel": level,
        "authoritativeSource": source_id,
        "contentHash": "sha256:" + digest,
    }
    put_if_present(document_node, "generatedAt", header.get("created"))
    return [source_node, document_node]


def jsonld_document(path: Path, data: Dict[str, Any], *, level: str, profile: str, context_mode: str, includes: set[str]) -> Dict[str, Any]:
    graph: List[Dict[str, Any]] = []
    if profile == "machine-jsonld-flat" and "provenance" in includes:
        graph.extend(provenance_nodes(path, data, level, profile))
    graph.extend(nodes_for_level(data, level, includes))

    doc: Dict[str, Any] = {}
    ctx = context_value(context_mode)
    if ctx is not None:
        doc["@context"] = ctx
    doc["@graph"] = graph
    return doc


def strip_jsonld_fields(node: Dict[str, Any]) -> Dict[str, Any]:
    """Convert JSON-LD node keys to plain JSON keys, retaining stable ids."""
    out: Dict[str, Any] = {}
    for key, value in node.items():
        if key == "@id":
            out["id"] = value
        elif key == "@type":
            out["type"] = value
        else:
            out[key] = value
    return out


def network_code_from_id(resource_id: str) -> str:
    return resource_id.removeprefix("FDSN:")


def station_code_from_id(resource_id: str) -> str:
    value = resource_id.removeprefix("FDSN:")
    parts = value.split("_", 1)
    return parts[1] if len(parts) > 1 else value


def bare_document(data: Dict[str, Any], *, level: str, includes: set[str]) -> Dict[str, Any]:
    if level == "response":
        raise NotImplementedError("Full StationXML Response conversion is not implemented; use --level channel --include responseSummary.")
    doc: Dict[str, Any] = {
        "profile": "machine-json-bare",
        "level": level,
        "networks": [strip_jsonld_fields(n) for n in data["networks"]],
    }
    if level in {"station", "channel"}:
        doc["stations"] = [strip_jsonld_fields(n) for n in data["stations"]]
    if level == "channel":
        doc["channels"] = [strip_jsonld_fields(n) for n in data["channels"]]
        doc["channelEpochs"] = [strip_jsonld_fields(n) for n in data["channelEpochs"]]
        if "responseSummary" in includes:
            doc["responseSummaries"] = [strip_jsonld_fields(n) for n in data["responseSummaries"]]
    return doc


def human_flat_grouped(data: Dict[str, Any], *, level: str, includes: set[str]) -> Dict[str, Any]:
    if level == "response":
        raise NotImplementedError("Full StationXML Response conversion is not implemented; use --level channel --include responseSummary.")
    doc: Dict[str, Any] = {"profile": "human-flat-grouped", "level": level}
    doc["networks"] = [
        {
            "id": n["@id"],
            "code": network_code_from_id(n["@id"]),
            **{k: v for k, v in n.items() if not k.startswith("@") and k != "identifiers"},
        }
        for n in data["networks"]
    ]
    if level in {"station", "channel"}:
        doc["stations"] = [
            {
                "id": s["@id"],
                "code": station_code_from_id(s["@id"]),
                "network": s.get("memberOfNetwork"),
                **{k: v for k, v in s.items() if not k.startswith("@") and k not in {"memberOfNetwork", "identifiers"}},
            }
            for s in data["stations"]
        ]
    if level == "channel":
        summaries_by_id = {r["@id"]: r for r in data["responseSummaries"]}
        epochs = []
        for e in data["channelEpochs"]:
            item = {"id": e["@id"], "channel": e.get("describesChannel")}
            for k, v in e.items():
                if not k.startswith("@") and k not in {"describesChannel", "hasResponseSummary"}:
                    item[k] = v
            if "responseSummary" in includes and e.get("hasResponseSummary") in summaries_by_id:
                rs = summaries_by_id[e["hasResponseSummary"]]
                item["responseSummary"] = {k: v for k, v in rs.items() if not k.startswith("@")}
            epochs.append(item)
        doc["channels"] = [
            {
                "id": c["@id"],
                "station": c.get("memberOfStation"),
            }
            for c in data["channels"]
        ]
        doc["channelEpochs"] = epochs
    return doc


def human_tree_optional(data: Dict[str, Any], *, level: str, includes: set[str]) -> Dict[str, Any]:
    if level == "response":
        raise NotImplementedError("Full StationXML Response conversion is not implemented; use --level channel --include responseSummary.")
    summaries_by_id = {r["@id"]: r for r in data["responseSummaries"]}
    epochs_by_channel: Dict[str, List[Dict[str, Any]]] = {}
    for e in data["channelEpochs"]:
        ep = {"id": e["@id"]}
        for k, v in e.items():
            if not k.startswith("@") and k not in {"describesChannel", "hasResponseSummary"}:
                ep[k] = v
        if "responseSummary" in includes and e.get("hasResponseSummary") in summaries_by_id:
            rs = summaries_by_id[e["hasResponseSummary"]]
            ep["responseSummary"] = {k: v for k, v in rs.items() if not k.startswith("@")}
        epochs_by_channel.setdefault(e["describesChannel"], []).append(ep)

    channels_by_station: Dict[str, List[Dict[str, Any]]] = {}
    if level == "channel":
        for c in data["channels"]:
            item: Dict[str, Any] = {"id": c["@id"]}
            if c["@id"] in epochs_by_channel:
                item["epochs"] = epochs_by_channel[c["@id"]]
            channels_by_station.setdefault(c["memberOfStation"], []).append(item)

    stations_by_network: Dict[str, List[Dict[str, Any]]] = {}
    if level in {"station", "channel"}:
        for s in data["stations"]:
            item = {
                "id": s["@id"],
                "code": station_code_from_id(s["@id"]),
            }
            for k, v in s.items():
                if not k.startswith("@") and k not in {"memberOfNetwork", "identifiers"}:
                    item[k] = v
            if level == "channel":
                item["channels"] = channels_by_station.get(s["@id"], [])
            stations_by_network.setdefault(s["memberOfNetwork"], []).append(item)

    networks: List[Dict[str, Any]] = []
    for n in data["networks"]:
        item = {
            "id": n["@id"],
            "code": network_code_from_id(n["@id"]),
        }
        for k, v in n.items():
            if not k.startswith("@") and k != "identifiers":
                item[k] = v
        if level in {"station", "channel"}:
            item["stations"] = stations_by_network.get(n["@id"], [])
        networks.append(item)
    return {"profile": "human-tree-optional", "level": level, "networks": networks}


def build_document(path: Path, data: Dict[str, Any], *, level: str, profile: str, context_mode: str, includes: set[str]) -> Dict[str, Any]:
    if profile in {"machine-jsonld-flat", "machine-jsonld-bare"}:
        if profile == "machine-jsonld-bare":
            includes = set(includes)
            includes.discard("provenance")
        return jsonld_document(path, data, level=level, profile=profile, context_mode=context_mode, includes=includes)
    if profile == "machine-json-bare":
        return bare_document(data, level=level, includes=includes)
    if profile == "human-flat-grouped":
        return human_flat_grouped(data, level=level, includes=includes)
    if profile == "human-tree-optional":
        return human_tree_optional(data, level=level, includes=includes)
    raise ValueError(f"Unsupported profile: {profile}")


def parse_includes(raw_items: List[str]) -> set[str]:
    includes: set[str] = set()
    for raw in raw_items:
        for item in raw.split(","):
            value = item.strip()
            if value:
                includes.add(value)
    unknown = includes - SUPPORTED_INCLUDES
    if unknown:
        raise ValueError(f"Unsupported include option(s): {', '.join(sorted(unknown))}")
    return includes


def make_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Convert a local FDSN StationXML file to JSON/JSON-LD metadata profiles."
    )
    parser.add_argument("input", type=Path, help="Input StationXML file")
    parser.add_argument("-o", "--output", type=Path, help="Output JSON file. Defaults to stdout.")
    parser.add_argument(
        "--profile",
        choices=sorted(SUPPORTED_PROFILES),
        default="machine-jsonld-flat",
        help="Output profile",
    )
    parser.add_argument(
        "--level",
        choices=sorted(SUPPORTED_LEVELS),
        default="station",
        help="Content level. level=response is reserved and currently not implemented.",
    )
    parser.add_argument(
        "--context",
        choices=sorted(SUPPORTED_CONTEXT_MODES),
        default="external",
        help="JSON-LD context mode for JSON-LD profiles.",
    )
    parser.add_argument(
        "--include",
        action="append",
        default=[],
        help="Comma-separated include options: provenance,responseSummary. Can be repeated.",
    )
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON output")
    parser.add_argument("--compact", action="store_true", help="Compact JSON output, overrides --pretty")
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = make_arg_parser()
    args = parser.parse_args(argv)

    try:
        if not args.input.exists():
            raise FileNotFoundError(args.input)
        includes = parse_includes(args.include)
        if args.profile == "machine-jsonld-flat" and not args.include:
            includes.add("provenance")
        data = parse_stationxml(args.input, include_response_summary="responseSummary" in includes)
        document = build_document(
            args.input,
            data,
            level=args.level,
            profile=args.profile,
            context_mode=args.context,
            includes=includes,
        )
    except NotImplementedError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    indent = None if args.compact or not args.pretty else 2
    text = json.dumps(document, ensure_ascii=False, indent=indent)
    if args.output:
        args.output.write_text(text + "\n", encoding="utf-8")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
