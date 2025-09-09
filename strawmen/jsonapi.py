#!/usr/bin/env python

import sys
from lxml import etree
import json
import re
from util import STAXML_NS, createNetworkSid, createStationSid, AbstractStationJson
from abc import ABC
from mostBasic import MostBasic

class JsonApi(MostBasic):
    def name(self):
        return "jsonapi"

    def createEnvelope(self, staxml):
        envelope = {
            "meta": super().createEnvelope(staxml),
            "data":[]
        }
        return envelope

    def createNetwork(self, xmlnetwork):
        basicnetwork=  super().createNetwork(xmlnetwork)
        network = {
            "type": "network",
            "id": createNetworkSid(xmlnetwork),
            "attributes": basicnetwork
        }
        return network
    def createStation(self, xmlstation, xmlnetwork):
        basicstation=  super().createStation(xmlstation, xmlnetwork)
        station = {
            "type": "station",
            "id": createStationSid(xmlstation, xmlnetwork),
            "attributes": basicstation,
            "relationships": {
                "network": {
                    "data": {
                        "type": "network",
                        "id": createNetworkSid(xmlnetwork)
                    }
                }
            }
        }
        return station
    def addStationToNetwork(self, station, net, envelope):
        if "relationships" not in net:
            net["relationships"] = {
                "station": []
            }
        net["relationships"]["station"].append({
            "data": {
                "type": "station",
                "id": station["attributes"]["sourceid"]
            }
        })
        if "included" not in envelope:
            envelope["included"] = []
        envelope["included"].append(station)

    def addNetworkToEnvelope(self, net, envelope):
        if "data" not in envelope:
            envelope["data"] = []
        envelope["data"].append(net)

def main():
    converter = JsonApi()
    file = "CO_XD.staxml"
    if len(sys.argv) > 1:
        file = sys.argv[1]
    with open(file, "rb") as inxml:
        jsonObj = converter.toJson(inxml.read())

    with open(f"{converter.name()}.json", "w") as outjson:
        json.dump(jsonObj, outjson, indent=2)
    print(json.dumps(jsonObj, indent=2))

if __name__ == "__main__":
    sys.exit(main())
