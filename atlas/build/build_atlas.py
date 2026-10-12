"""Build the standalone atlas from its own content, graph, and app files."""

import base64
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ATLAS = ROOT / "atlas"
OUTPUT = ROOT / "outputs" / "Кольцо Всевластья — схема правил.html"


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def load_data():
    content = ATLAS / "content"
    graph = ATLAS / "graph"
    manifest = read_json(content / "manifest.json")
    layout = read_json(graph / "layout.json")
    documents = [read_json(path) for path in sorted((content / "sections").glob("*.json"))]
    sections_by_id = {doc["section"]["id"]: doc["section"] for doc in documents}
    nodes_by_id = {node["id"]: node for doc in documents for node in doc["nodes"]}
    if len(sections_by_id) != len(documents):
        raise ValueError("Duplicate section ID")
    if len(nodes_by_id) != sum(len(doc["nodes"]) for doc in documents):
        raise ValueError("Duplicate card ID")
    if set(sections_by_id) != set(manifest["sectionOrder"]):
        raise ValueError("Section manifest differs from content")
    if set(nodes_by_id) != set(manifest["nodeOrder"]):
        raise ValueError("Card manifest differs from content")
    if set(layout["nodes"]) != set(nodes_by_id) or set(layout["clusters"]) != set(sections_by_id):
        raise ValueError("Layout differs from content")

    sections = []
    for section_id in manifest["sectionOrder"]:
        section = dict(sections_by_id[section_id])
        section["clusters"] = layout["clusters"][section_id]
        sections.append(section)
    nodes = []
    for node_id in manifest["nodeOrder"]:
        node = dict(nodes_by_id[node_id])
        node["layout"] = layout["nodes"][node_id]
        nodes.append(node)
    data = {
        "sections": sections,
        "nodes": nodes,
        "edges": read_json(graph / "edges.json"),
    }
    validate(data)
    return data


def validate(data):
    sections = {section["id"] for section in data["sections"]}
    nodes = {node["id"] for node in data["nodes"]}
    edges = [edge["id"] for edge in data["edges"]]
    if len(edges) != len(set(edges)):
        raise ValueError("Duplicate link ID")
    part_ids = [part["id"] for node in data["nodes"] for part in node["parts"]]
    if len(part_ids) != len(set(part_ids)):
        raise ValueError("Duplicate card text ID")
    listed = [node_id for section in data["sections"] for node_id in section["nodes"]]
    if len(listed) != len(set(listed)) or set(listed) != nodes:
        raise ValueError("Each card must belong to exactly one section")
    for node in data["nodes"]:
        if node["section"] not in sections:
            raise ValueError(f"Unknown section for {node['id']}")
    for edge in data["edges"]:
        if edge["a"] not in nodes or edge["b"] not in nodes:
            raise ValueError(f"Broken link {edge['id']}")
        if edge.get("start") not in (None, "arrow") or edge.get("end") not in (None, "arrow"):
            raise ValueError(f"Invalid arrow direction {edge['id']}")


def build():
    data = load_data()
    app = ATLAS / "app"
    html = (app / "template.html").read_text(encoding="utf-8")
    replacements = {
        "/*BASE_CSS*/": (app / "base.css").read_text(encoding="utf-8").rstrip("\n"),
        "/*ATLAS_CSS*/": (app / "atlas.css").read_text(encoding="utf-8").rstrip("\n"),
        "/*APP_JS*/": (app / "atlas.js").read_text(encoding="utf-8").rstrip("\n"),
        "/*DATA*/": json.dumps(data, ensure_ascii=False).replace("</", "<\\/"),
        "/*LOGO_DATA*/": "data:image/png;base64," + base64.b64encode((app / "logo-ring.png").read_bytes()).decode("ascii"),
    }
    for marker, value in replacements.items():
        if html.count(marker) != 1:
            raise ValueError(f"Expected one {marker} marker")
        html = html.replace(marker, value)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(html, encoding="utf-8")
    print(f"{len(data['nodes'])} cards; {len(data['edges'])} arrows; {len(data['sections'])} chapters")


if __name__ == "__main__":
    build()
