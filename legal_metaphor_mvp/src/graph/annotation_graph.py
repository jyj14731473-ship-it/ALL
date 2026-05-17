"""LangGraph orchestration for the legal metaphor annotation workflow."""

from __future__ import annotations

import os
from typing import Any

from nodes.metaphor_classify import metaphor_classify_node
from nodes.mipvu_judge import mipvu_judge_node
from nodes.rdf_convert import rdf_convert_node
from nodes.rdf_mapping import rdf_mapping_node
from nodes.validation_check import validation_check_node
from schemas.annotation import AnnotationState, create_empty_state


def build_annotation_graph() -> Any:
    """Build the LangGraph workflow."""
    try:
        from langgraph.graph import END, StateGraph
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(
            "LangGraph가 설치되어 있지 않습니다. `pip install -r requirements.txt` 후 다시 실행하세요."
        ) from exc

    graph = StateGraph(AnnotationState)
    graph.add_node("mipvu_judge", mipvu_judge_node)
    graph.add_node("metaphor_classify", metaphor_classify_node)
    graph.add_node("rdf_mapping", rdf_mapping_node)
    graph.add_node("validation_check", validation_check_node)
    graph.add_node("rdf_convert", rdf_convert_node)

    graph.set_entry_point("mipvu_judge")
    graph.add_edge("mipvu_judge", "metaphor_classify")
    graph.add_edge("metaphor_classify", "rdf_mapping")
    graph.add_edge("rdf_mapping", "validation_check")
    graph.add_edge("validation_check", "rdf_convert")
    graph.add_edge("rdf_convert", END)
    return graph.compile()


def run_annotation_graph(
    raw_text: str,
    document_id: str = "sample-doc",
    case_id: str = "sample-case",
    contextual_meaning_by_lemma: dict[str, str] | None = None,
    contextual_candidates: list[dict] | None = None,
) -> AnnotationState:
    """Run the full graph and return the final state."""
    state = create_empty_state(document_id=document_id, case_id=case_id, raw_text=raw_text)
    contextual_lookup = contextual_meaning_by_lemma or {}
    contextual_candidates = list(contextual_candidates or [])
    state["candidates"] = contextual_candidates
    if contextual_candidates:
        sentence_ids: list[str] = []
        for item in contextual_candidates:
            sid = str(item.get("sentence_id", "")).strip()
            if sid and sid not in sentence_ids:
                sentence_ids.append(sid)
        if sentence_ids:
            state["sentences"] = sentence_ids
    state["contextual_meaning_by_lemma"] = contextual_lookup
    state["metadata"] = {
        "pipeline": "graph",
        "prompt_directory": "src/prompts",
        "llm_available": bool(os.getenv("OPENAI_API_KEY", "").strip()),
        "contextual_meaning_lookup_available": bool(contextual_lookup),
        "contextual_meaning_lookup_size": len(contextual_lookup),
        "candidate_count": len(contextual_candidates),
    }
    if not contextual_candidates:
        state["errors"].append(
            "[graph] contextualized 후보 생성 결과가 비어 있습니다. pos_nodes_contextualized.json을 확인하세요."
        )
    if not state["metadata"]["llm_available"]:
        state["errors"].append(
            "[graph] OPENAI_API_KEY가 없어 LLM 기반 노드는 빈 결과 또는 fallback 결과를 반환할 수 있습니다."
        )

    try:
        app = build_annotation_graph()
    except RuntimeError as exc:
        state["errors"].append(f"[graph] {exc}")
        state["metadata"]["validation_status"] = "needs_repair"
        return state

    result = app.invoke(state)
    if "metadata" not in result:
        result["metadata"] = state["metadata"]
    else:
        result["metadata"].update(state["metadata"])
    if "status" not in result:
        result["status"] = "completed"
    return result
