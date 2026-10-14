"""One run of this graph per flagged booking. The risk score arrives in the state, worked out
for the whole morning's bookings in one TabPFN call (see desk.py)."""
from typing import Callable, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from noshow.check import check_draft
from noshow.draft import facts_brief, write_draft
from noshow.facts import work_out_facts

RISK_LINE = 0.5   # above this, the owner gets a draft to approve
MAX_DRAFTS = 2    # one redraft if the check finds a wrong fact, then the owner sees it flagged


class Desk(TypedDict, total=False):
    booking: dict
    risk: float
    facts: dict
    draft: str
    problems: list[str]
    attempts: int
    decision: str        # "approve" | "reject" | "edit"
    final: str


def build(writer: Callable[[str], str] = write_draft, checkpointer=None):
    def facts(s: Desk) -> dict:
        return {"facts": work_out_facts(s["booking"])}

    def draft(s: Desk) -> dict:
        text = writer(facts_brief(s["facts"]))
        return {"draft": text, "attempts": s.get("attempts", 0) + 1}

    def check(s: Desk) -> dict:
        return {"problems": check_draft(s["draft"], s["facts"])}

    def approve(s: Desk) -> dict:
        # Everything above this line re-runs on resume, so this node does nothing else.
        answer = interrupt({"guest": s["booking"]["guest"], "risk": round(s["risk"], 2),
                           "draft": s["draft"], "problems": s["problems"]})
        if isinstance(answer, dict):           # {"decision": "edit", "text": "..."}
            return {"decision": answer["decision"], "final": answer.get("text", s["draft"])}
        return {"decision": answer, "final": s["draft"] if answer == "approve" else ""}

    def triage(s: Desk) -> str:
        return "facts" if s["risk"] >= RISK_LINE else END

    def after_check(s: Desk) -> str:
        return "approve" if not s["problems"] or s["attempts"] >= MAX_DRAFTS else "draft"

    g = StateGraph(Desk)
    g.add_node("facts", facts)
    g.add_node("draft", draft)
    g.add_node("check", check)
    g.add_node("approve", approve)
    g.add_conditional_edges(START, triage)
    g.add_edge("facts", "draft")
    g.add_edge("draft", "check")
    g.add_conditional_edges("check", after_check)
    g.add_edge("approve", END)
    return g.compile(checkpointer=checkpointer)
