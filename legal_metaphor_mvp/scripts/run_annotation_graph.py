"""Run the optional LangGraph annotation workflow on a sample legal text."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from utils import read_json

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_DIR))

try:
    from dotenv import load_dotenv  # noqa: E402
except ImportError:  # pragma: no cover - optional at runtime
    def load_dotenv(*_args: object, **_kwargs: object) -> bool:
        return False
from graph.annotation_graph import run_annotation_graph  # noqa: E402

SAMPLE_TEXT = (
    "지방자치법 제192조 제8항에 근거한 이 사건 소송은, 조례가 헌법 및 법률 등 상위 법규와의 관계에서 "
    "효력을 갖는지 여부를 다툴 수 있도록 마련된 것으로 일종의 추상적 규범통제의 성격을 가진다. "
    "그리고 그 취지는 조례에 대한 관계에서 법령의 우위 내지 조례의 적법성을 관철함으로써 "
    "헌법이 상정하고 있는 전체 법질서의 통일성을 확보하기 위한 것으로 볼 수 있다."
)

def _load_contextual_lookup(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}

    payload = read_json(path, default={})
    if not isinstance(payload, dict):
        return {}

    lemma_groups = payload.get("lemma_groups")
    if not isinstance(lemma_groups, list):
        return {}

    lookup: dict[str, str] = {}
    for group in lemma_groups:
        if not isinstance(group, dict):
            continue
        lemma = str(group.get("lemma", "")).strip()
        if not lemma:
            continue
        contextual_meaning = str(group.get("contextual_meaning", "")).strip()
        if contextual_meaning:
            lookup[lemma] = contextual_meaning
    return lookup


def main() -> None:
    load_dotenv(PROJECT_ROOT / ".env")
    contextual_lookup = _load_contextual_lookup(PROJECT_ROOT / "data/output/pos_nodes_contextualized.json")
    state = run_annotation_graph(SAMPLE_TEXT, contextual_meaning_by_lemma=contextual_lookup)

    annotations_dir = PROJECT_ROOT / "outputs" / "annotations"
    rdf_dir = PROJECT_ROOT / "outputs" / "rdf"
    annotations_dir.mkdir(parents=True, exist_ok=True)
    rdf_dir.mkdir(parents=True, exist_ok=True)

    annotation_path = annotations_dir / "graph_annotation.json"
    rdf_path = rdf_dir / "metaphors.ttl"
    annotation_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    rdf_path.write_text(state.get("rdf_output", ""), encoding="utf-8")

    print("LangGraph annotation workflow finished.")
    print(f"candidates: {len(state.get('candidates', []))}")
    print(f"mipvu_annotations: {len(state.get('mipvu_annotations', []))}")
    print(f"metaphor_annotations: {len(state.get('metaphor_annotations', []))}")
    print(f"rdf_mappings: {len(state.get('rdf_mappings', []))}")
    print(f"annotation_output: {annotation_path}")
    print(f"rdf_output: {rdf_path}")
    if state.get("errors"):
        print("errors:")
        for error in state["errors"]:
            print(f"- {error}")


if __name__ == "__main__":
    main()
