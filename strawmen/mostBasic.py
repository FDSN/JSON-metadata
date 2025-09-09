#!/usr/bin/env python

import sys
from lxml import etree
import json
import re
from util import STAXML_NS, createNetworkSid, createStationSid, AbstractStationJson
from abc import ABC

class MostBasic(AbstractStationJson):
    def name(self):
        return "mostbasic"
    def addStationToNetwork(self, station, net, envelope):
        if "station" not in net:
            net["station"] = []
        net["station"].append(station)

    def addNetworkToEnvelope(self, net, envelope):
        if "network" not in envelope:
            envelope["network"] = []
        envelope["network"].append(net)

    def createEnvelope(self, staxml):
        envelope = {
        }

        for child in staxml:
            tag = etree.QName(child)
            if tag.namespace == STAXML_NS:
                if tag.localname == "Source":
                    envelope["source"] = child.text

                if tag.localname == "Sender":
                    envelope["sender"] = child.text

                if tag.localname == "Module":
                    envelope["module"] = child.text

                if tag.localname == "ModuleURI":
                    envelope["moduleUri"] = child.text

                if tag.localname == "Created":
                    envelope["created"] = child.text

            else:
                print(f"Non-staml namespace element found: {tag.text}")
        return envelope



def main():
    converter = MostBasic()
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
