
import sys
from lxml import etree
import json
import re
from abc import ABC, abstractmethod


STAXML_NS="http://www.fdsn.org/xml/station/1"

TEMP_NET_PATTERN = re.compile("[\dXYZ][A-Z\d]")

def createNetworkSid(netxml):
    code = netxml.get("code")
    sid = f"FDSN:{code}"
    if TEMP_NET_PATTERN.fullmatch(code):
        sid += netxml.get("startDate")[0:4]
    return sid

def createStationSid(xmlstation, xmlnetwork):
    code = xmlstation.get("code")
    netSid = createNetworkSid(xmlnetwork)
    sid = f"{netSid}_{code}"
    return sid

def createChannelSid(xmlchannel, xmlstation, xmlnetwork):
    code = xmlstation.get("code")
    locCode = xmlnetwork.get("locationCode")
    staSid = createStationSid(xmlstation, xmlnetwork)
    sid = f"{staSid}_{locCode}_{code[0]}_{code[1]}_{code[2]}"
    return sid


class AbstractStationJson(ABC):
    @abstractmethod
    def name(self):
        return "abstract_noname"

    def createNetwork(self, xmlnetwork):
        sid = createNetworkSid(xmlnetwork)
        net = {
            "sourceid": f"{sid}"
        }
        for name, value in sorted(xmlnetwork.items()):
            if name != "code":
                # do not copy code, use sid instead
                net[name] = value

        for child in xmlnetwork:
            tag = etree.QName(child)
            if tag.namespace == STAXML_NS:
                if tag.localname == "Identifier":
                    net["identifier"] = child.text

                if tag.localname == "Description":
                    net["description"] = child.text
                if tag.localname == "TotalNumberStations":
                    net["totalNumberStations"] = child.text
                if tag.localname == "SelectedNumberStations":
                    net["selectedNumberStations"] = child.text

            else:
                print(f"Non-staml namespace element found: {tag.text}")
        return net

    def createStation(self, xmlstation, xmlnetwork):
        sid = createStationSid(xmlstation, xmlnetwork)
        station = {
            "sourceid": f"{sid}",
            "startDate": xmlstation.get("startDate"),
            "placeholder": "much omitted"
        }
        if xmlstation.get("endDate"):
            station["endDate"] = xmlstation.get("endDate")
        return station

    def addStationToNetwork(self, station, net, envelope):
        if "station" not in net:
            net["station"] = []
        net["station"].append(station)

    def addNetworkToEnvelope(self, net, envelope):
        if "networks" not in envelope:
            envelope["networks"] = []
        envelope["networks"].append(net)

    def createEnvelope(self, staxml):
        envelope = {
        }
        return envelope

    def toJson(self, staxmlText):
        staxml = etree.fromstring(staxmlText)
        envelope = self.createEnvelope(staxml)

        for child in staxml:
            tag = etree.QName(child)
            if tag.namespace == STAXML_NS:
                if tag.localname == "Network":
                    net = self.createNetwork(child)
                    self.addNetworkToEnvelope(net, envelope)
                    for stachild in child:
                        statag = etree.QName(stachild)
                        if statag.namespace == STAXML_NS and statag.localname=="Station":
                            station = self.createStation(stachild, child)
                            self.addStationToNetwork(station, net, envelope)
        return envelope
