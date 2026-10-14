"""One run of this graph per booking. The risk score arrives in the state, worked out for the whole
morning's bookings in one TabPFN call (see desk.py). A flagged booking pauses twice for the owner:
first Draft or Leave (no model runs until Draft), then Send or Reject once the draft is checked."""
from typing import Callable, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from noshow.check import check_draft
from noshow.draft import facts_brief, write_draft
from noshow.facts import work_out_facts

MAX_DRAFTS = 2    # one redraft if the check finds a wrong fact, then the owner sees it flagged


class Desk(TypedDict, total=False):
    booking: dict
    risk: float
    flagged: bool        # set by the morning run: risk at or over the line
    reasons: list[dict]
    facts: dict
    draft: str
    problems: list[str]
    attempts: int
    final: str
    sent: dict           # what the sender reported: channel, address, time
    outcome: str         # "left" | "sent" | "rejected"


def build(sender: Callable[[dict, str], dict], writer: Callable[[str], str] = write_draft, checkpointer=None):
    # Nodes with a pause re-run from their top on resume, so they do nothing before interrupt().
    def choose(s: Desk) -> dict:
        answer = interrupt({"stage": "choose"})          # "draft" | "leave"
        return {"outcome": "left"} if answer == "leave" else {}

    def facts(s: Desk) -> dict:
        return {"facts": work_out_facts(s["booking"])}

    def draft(s: Desk) -> dict:
        text = writer(facts_brief(s["facts"]))
        return {"draft": text, "attempts": s.get("attempts", 0) + 1}

    def check(s: Desk) -> dict:
        return {"problems": check_draft(s["draft"], s["facts"])}

    def review(s: Desk) -> dict:
        answer = interrupt({"stage": "review"})          # "send" | "reject" | {"decision": "send", "text": ...}
        if isinstance(answer, dict):
            answer, text = answer["decision"], answer.get("text") or s["draft"]
        else:
            text = s["draft"]
        return {"outcome": "rejected"} if answer == "reject" else {"final": text}

    def send(s: Desk) -> dict:
        return {"sent": sender(s["booking"], s["final"]), "outcome": "sent"}

    g = StateGraph(Desk)
    for name, node in [("choose", choose), ("facts", facts), ("draft", draft), ("check", check),
                       ("review", review), ("send", send)]:
        g.add_node(name, node)
    g.add_conditional_edges(START, lambda s: "choose" if s.get("flagged") else END)
    g.add_conditional_edges("choose", lambda s: END if s.get("outcome") == "left" else "facts")
    g.add_edge("facts", "draft")
    g.add_edge("draft", "check")
    g.add_conditional_edges("check", lambda s: "review" if not s["problems"] or s["attempts"] >= MAX_DRAFTS
                            else "draft")
    g.add_conditional_edges("review", lambda s: END if s.get("outcome") == "rejected" else "send")
    g.add_edge("send", END)
    return g.compile(checkpointer=checkpointer)
