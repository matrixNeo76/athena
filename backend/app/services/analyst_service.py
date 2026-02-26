"""
ATHENA - Analyst Service
TODO-5: Pure local transformation layer — no LLM, no external calls.

Transforms ScoutResult into AnalystResult:
  - Flattens competitor/trend/segment data
  - Builds a GraphSpec (nodes + edges) for FalkorDB (TODO-9)
  - Generates analysis_summary for the Strategy Agent prompt
"""
import logging
import re
from datetime import datetime, timezone

from app.models.schemas import (
    ScoutResult,
    ScoutCompetitor,
    ScoutTrend,
    ScoutCustomerSegment,
    ConfidenceLevel,
    AnalystResult,
    AnalystCompetitorSummary,
    AnalystTrendSummary,
    AnalystSegmentSummary,
    GraphSpec,
    GraphNode,
    GraphEdge,
    GraphNodeType,
)

logger = logging.getLogger(__name__)

_CONFIDENCE_WEIGHT: dict[str, float] = {
    ConfidenceLevel.HIGH:   1.0,
    ConfidenceLevel.MEDIUM: 0.6,
    ConfidenceLevel.LOW:    0.3,
}


def _slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def _node_id(node_type: GraphNodeType, label: str) -> str:
    return f"{node_type.value}-{_slugify(label)}"


def _build_graph_spec(
    target: str,
    competitors: list[ScoutCompetitor],
    trends: list[ScoutTrend],
    segments: list[ScoutCustomerSegment],
) -> GraphSpec:
    nodes: list[GraphNode] = []
    edges: list[GraphEdge] = []

    target_id = _node_id(GraphNodeType.COMPANY, target)
    nodes.append(GraphNode(id=target_id, label=target, node_type=GraphNodeType.COMPANY, properties={"role": "analysis_target"}))

    market_label = f"{target} Market"
    market_id = _node_id(GraphNodeType.MARKET, market_label)
    nodes.append(GraphNode(id=market_id, label=market_label, node_type=GraphNodeType.MARKET, properties={"inferred": True}))
    edges.append(GraphEdge(source_id=target_id, target_id=market_id, relation="OPERATES_IN", weight=1.0))

    for comp in competitors:
        comp_id = _node_id(GraphNodeType.COMPETITOR, comp.name)
        weight = _CONFIDENCE_WEIGHT.get(comp.confidence, 0.6)
        nodes.append(GraphNode(id=comp_id, label=comp.name, node_type=GraphNodeType.COMPETITOR,
            properties={"description": comp.description, "market_position": comp.market_position,
                        "confidence": comp.confidence, "is_assumption": comp.is_assumption, "source_url": comp.source_url}))
        edges.append(GraphEdge(source_id=comp_id, target_id=market_id, relation="OPERATES_IN", weight=weight))
        edges.append(GraphEdge(source_id=target_id, target_id=comp_id, relation="COMPETES_WITH", weight=weight))

    for trend in trends:
        trend_id = _node_id(GraphNodeType.TREND, trend.title)
        weight = _CONFIDENCE_WEIGHT.get(trend.impact, 0.6)
        nodes.append(GraphNode(id=trend_id, label=trend.title, node_type=GraphNodeType.TREND,
            properties={"description": trend.description, "impact": trend.impact,
                        "timeframe": trend.timeframe, "is_assumption": trend.is_assumption}))
        edges.append(GraphEdge(source_id=trend_id, target_id=market_id, relation="SHAPES", weight=weight))

    for seg in segments:
        seg_id = _node_id(GraphNodeType.CUSTOMER_SEGMENT, seg.name)
        nodes.append(GraphNode(id=seg_id, label=seg.name, node_type=GraphNodeType.CUSTOMER_SEGMENT,
            properties={"description": seg.description, "pain_points": seg.pain_points,
                        "estimated_size": seg.estimated_size, "is_assumption": seg.is_assumption}))
        edges.append(GraphEdge(source_id=seg_id, target_id=target_id, relation="TARGETED_BY", weight=0.8))

    description = (f"Knowledge graph for '{target}': {len(nodes)} nodes, {len(edges)} edges.")
    return GraphSpec(nodes=nodes, edges=edges, description=description)


def _build_analysis_summary(
    target: str,
    competitors: list[ScoutCompetitor],
    trends: list[ScoutTrend],
    segments: list[ScoutCustomerSegment],
) -> str:
    high_comps  = [c.name for c in competitors if c.confidence == ConfidenceLevel.HIGH  and not c.is_assumption]
    med_comps   = [c.name for c in competitors if c.confidence == ConfidenceLevel.MEDIUM and not c.is_assumption]
    inferred    = [c.name for c in competitors if c.is_assumption]
    high_trends = [t.title for t in trends if t.impact == ConfidenceLevel.HIGH]
    seg_names   = [s.name for s in segments]

    lines: list[str] = [f"COMPETITIVE LANDSCAPE ANALYSIS — TARGET: {target}", ""]
    if high_comps:  lines.append(f"Confirmed primary competitors (high confidence): {', '.join(high_comps)}.")
    if med_comps:   lines.append(f"Secondary competitors (medium confidence): {', '.join(med_comps)}.")
    if inferred:    lines.append(f"Inferred competitors (assumptions): {', '.join(inferred)}.")
    if not competitors: lines.append("No competitors identified.")
    lines.append("")
    if high_trends: lines.append(f"High-impact trends: {', '.join(high_trends)}.")
    if trends:      lines.append(f"All trends ({len(trends)}): {', '.join(t.title for t in trends)}.")
    else:           lines.append("No trends identified.")
    lines.append("")
    if seg_names:   lines.append(f"Customer segments ({len(seg_names)}): {', '.join(seg_names)}.")
    else:           lines.append("No customer segments identified.")
    all_pp = [pp for s in segments for pp in s.pain_points]
    if all_pp:
        lines.append(f"Key pain points: {'; '.join(list(dict.fromkeys(all_pp))[:6])}.")
    return "\n".join(lines)


async def run_analyst(scout_result: ScoutResult) -> AnalystResult:
    logger.info("[ANALYST] run_analyst started — target='%s'", scout_result.target)

    competitors = [
        AnalystCompetitorSummary(
            name=c.name, description=c.description, market_position=c.market_position,
            strengths=c.strengths, weaknesses=c.weaknesses,
            confidence=c.confidence.value if hasattr(c.confidence, "value") else str(c.confidence),
            is_assumption=c.is_assumption,
        )
        for c in scout_result.competitors
    ]
    trends = [
        AnalystTrendSummary(
            title=t.title, description=t.description,
            impact=t.impact.value if hasattr(t.impact, "value") else str(t.impact),
            timeframe=t.timeframe, is_assumption=t.is_assumption,
        )
        for t in scout_result.trends
    ]
    segments = [
        AnalystSegmentSummary(
            name=s.name, description=s.description,
            pain_points=s.pain_points, estimated_size=s.estimated_size,
        )
        for s in scout_result.customer_segments
    ]
    high_confidence = [
        c.name for c in scout_result.competitors
        if c.confidence == ConfidenceLevel.HIGH and not c.is_assumption
    ]
    unique_pain_points = list(dict.fromkeys([pp for s in scout_result.customer_segments for pp in s.pain_points]))
    graph_spec = _build_graph_spec(scout_result.target, scout_result.competitors, scout_result.trends, scout_result.customer_segments)
    analysis_summary = _build_analysis_summary(scout_result.target, scout_result.competitors, scout_result.trends, scout_result.customer_segments)

    result = AnalystResult(
        target=scout_result.target, competitors=competitors, trends=trends, segments=segments,
        graph_spec=graph_spec, analysis_summary=analysis_summary,
        high_confidence_competitors=high_confidence, key_pain_points=unique_pain_points,
        analyzed_at=datetime.now(timezone.utc), source_scouted_at=scout_result.scouted_at,
    )
    logger.info("[ANALYST] complete — graph: %d nodes, %d edges", len(graph_spec.nodes), len(graph_spec.edges))
    return result
