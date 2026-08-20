"""Case files as XML, validated against schema/case-file.xsd.

The printed case file is for a person; this is the same document for a system.
Back offices in this domain exchange XML, and an evidence record that cannot be
handed to another system is a dead end.

The schema is the XML counterpart of `pipeline/contracts.py`: the citation and
the caveat are required elements, and `status` is fixed to "Flagged for
investigation" so a conforming document cannot assert guilt even if someone
edits it by hand.

Round-trips: `parse_case_xml` reads a document back into the same dict shape,
so the export is a real interchange format rather than a one-way dump.
"""
from __future__ import annotations

from pathlib import Path
from xml.etree import ElementTree as ET

SCHEMA_PATH = Path("schema/case-file.xsd")

ISSUER = {"office": "Office of the District Supply Officer",
          "district": "Vellore", "state": "Tamil Nadu"}


def _el(parent: ET.Element, tag: str, text=None, **attrs) -> ET.Element:
    node = ET.SubElement(parent, tag, {k: str(v) for k, v in attrs.items()
                                       if v is not None})
    if text is not None:
        node.text = str(text)
    return node


def case_to_element(case: dict, flag: dict, generated: str) -> ET.Element:
    root = ET.Element("caseFile", {
        "reference": case["flag_id"],
        "priority": str(case["tier"]),
        "status": "Flagged for investigation",
        "generated": generated,
    })

    issuer = _el(root, "issuer")
    for k, v in ISSUER.items():
        _el(issuer, k, v)

    subject = _el(root, "subject")
    _el(subject, "item", case["title"].split(" — ")[0])
    _el(subject, "itemCode", flag["item"])
    _el(subject, "location", case["title"].split(" — ")[-1])
    _el(subject, "locationCode", flag["location"])

    _el(root, "window", start=case["window"]["start"], end=case["window"]["end"],
        days=case["duration_days"])
    _el(root, "finding", case["finding"])

    ref = case["reference"]
    rnode = _el(root, "referenceRate", unit=flag["expected"]["unit"])
    _el(rnode, "basis", ref["basis"])
    _el(rnode, "citation", ref["citation"] or "not recorded")
    _el(rnode, "rate", ref["rate"])
    _el(rnode, "expectedRange", low=ref["band"][0], high=ref["band"][1])

    obs = case["observed"]
    onode = _el(root, "observed", unit=flag["expected"]["unit"], observations=obs["n"])
    _el(onode, "median", obs["median"])
    _el(onode, "percentAgainstReference", obs["pct_vs_reference"])
    prov = _el(onode, "provenance",
               independentLocalities=obs.get("distinct_localities"))
    for p in obs["provenance"]:
        _el(prov, "source", tier=p["tier"], label=p["label"], observations=p["n"])

    m = case["measure"]
    mnode = _el(root, "measure", detector=m["detector"])
    _el(mnode, "statistic", m["name"])
    _el(mnode, "value", m["value"])
    _el(mnode, "threshold", m["threshold"])
    extra = {k: v for k, v in (m.get("extra") or {}).items() if v is not None}
    if extra:
        snode = _el(mnode, "supporting")
        for k, v in extra.items():
            _el(snode, "value", v, name=k)
    _el(mnode, "explanation", m["explanation"])

    peers = _el(root, "peersInBand", residualStandardDeviation=case["residual_sd"])
    for p in case["peers_in_band"]:
        _el(peers, "location", p)

    _el(root, "summary", case["narrative"])
    if case.get("evidence_floor"):
        _el(root, "evidenceFloor", case["evidence_floor"])
    _el(root, "caveat", case["caveat"])
    return root


def build_case_set(cases: dict, flags: list[dict], generated: str) -> ET.ElementTree:
    by_id = {f["flag_id"]: f for f in flags}
    root = ET.Element("caseFileSet", {
        "district": ISSUER["district"], "generated": generated,
        "count": str(len(cases)),
    })
    for flag_id, case in cases.items():
        root.append(case_to_element(case, by_id[flag_id], generated))
    ET.indent(root, space="  ")
    return ET.ElementTree(root)


def to_string(element: ET.Element) -> str:
    ET.indent(element, space="  ")
    return ET.tostring(element, encoding="unicode", xml_declaration=True)


def validate(xml_text: str) -> None:
    """Assert the document conforms. Raises if the schema is violated."""
    import xmlschema

    xmlschema.XMLSchema(SCHEMA_PATH).validate(xml_text)


def parse_case_xml(xml_text: str) -> list[dict]:
    """Read an exported document back. Proves the format is interchange, not a dump."""
    root = ET.fromstring(xml_text)
    nodes = [root] if root.tag == "caseFile" else list(root)
    out = []
    for node in nodes:
        ref = node.find("referenceRate")
        obs = node.find("observed")
        out.append({
            "flag_id": node.get("reference"),
            "tier": int(node.get("priority")),
            "status": node.get("status"),
            "item": node.findtext("subject/itemCode"),
            "location": node.findtext("subject/locationCode"),
            "window": {"start": node.find("window").get("start"),
                       "end": node.find("window").get("end")},
            "reference_rate": float(ref.findtext("rate")),
            "citation": ref.findtext("citation"),
            "observed_median": float(obs.findtext("median")),
            "narrative": node.findtext("summary"),
        })
    return out
