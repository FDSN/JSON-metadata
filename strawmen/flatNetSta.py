#!/usr/bin/env python

import sys
from lxml import etree
import json
import re
from util import STAXML_NS, createNetworkSid, createStationSid, AbstractStationJson
from abc import ABC
from mostBasic import MostBasic

class FlatNetSta(MostBasic):
    def name(self):
        return "flat_net_sta"
    def addStationToNetwork(self, station, net, envelope):
        if "station" not in envelope:
            envelope["station"] = []
        envelope["station"].append(station)

    def addNetworkToEnvelope(self, net, envelope):
        if "network" not in envelope:
            envelope["network"] = []
        envelope["network"].append(net)

def main():
    converter = FlatNetSta()
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
