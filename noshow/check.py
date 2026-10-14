"""Plain-Python check: every amount, date and night count in a draft must match the facts."""
import re

MONTHS = ["january", "february", "march", "april", "may", "june", "july", "august",
          "september", "october", "november", "december"]
_M = "(?:" + "|".join(MONTHS + ["sept"] + [m[:3] for m in MONTHS]) + r")\b\.?"   # March, Mar, Mar., Sept
_ORD = r"(?:st|nd|rd|th)?"
DAY_MONTH = re.compile(rf"\b(\d{{1,2}}){_ORD}(?:\s+of)?\s+({_M})(?![a-z])", re.I)
MONTH_DAY = re.compile(rf"\b({_M})\s+(?:the\s+)?(\d{{1,2}}){_ORD}\b", re.I)
ISO = re.compile(r"\b\d{4}-(\d{1,2})-(\d{1,2})\b")
SLASH = re.compile(r"(?<![\d/])(\d{1,2})/(\d{1,2})(?:/\d{2,4})?(?![\d/])")   # read as month/day, as Gemma writes
AMOUNT = re.compile(r"\$\s?\d[\d,]*(?:\.\d{1,2})?")
BARE_NUMBER = re.compile(r"(?<![\d$/.-])\d[\d,]*(?:\.\d{1,2})?(?![\d/])")
WORDS = {w: i for i, w in enumerate("zero one two three four five six seven eight nine ten "
                                    "eleven twelve thirteen fourteen".split())}
NIGHTS = re.compile(r"\b(\d+|" + "|".join(WORDS) + r")\s+nights?\b", re.I)


def _money(s: str) -> float:
    return float(s.replace("$", "").replace(",", "").strip())


def _month(name: str) -> int:
    return [m[:3] for m in MONTHS].index(name[:3].lower()) + 1


def _dates(text: str) -> list[tuple[int, int]]:
    found = [(int(d), _month(m)) for d, m in DAY_MONTH.findall(text)]
    found += [(int(d), _month(m)) for m, d in MONTH_DAY.findall(text)]
    found += [(int(d), int(m)) for m, d in ISO.findall(text) + SLASH.findall(text)]
    return found


def check_draft(text: str, facts: dict) -> list[str]:
    problems = []
    total = facts["total"]
    amounts = AMOUNT.findall(text)
    problems += [f"amount {a.strip()} is not the total {total}" for a in amounts if _money(a) != _money(total)]
    if not amounts and _money(total) not in {_money(n) for n in BARE_NUMBER.findall(text)}:
        problems.append(f"total {total} not mentioned")

    allowed = {(d.day, d.month) for d in (facts["arrival"], facts["departure"], facts["free_cancel_until"]) if d}
    for day, month in _dates(text):
        if (day, month) not in allowed:
            label = f"{day} {MONTHS[month - 1].title()}" if 1 <= month <= 12 else f"{month}/{day}"
            problems.append(f"date {label} is not arrival, departure or free-cancel date")
    a = facts["arrival"]
    if (a.day, a.month) not in _dates(text):
        problems.append(f"arrival {a.day} {a:%B} not mentioned")

    for n in NIGHTS.findall(text):
        said = int(n) if n.isdigit() else WORDS[n.lower()]
        if said != facts["nights"]:
            problems.append(f"says {said} nights, booking is {facts['nights']}")
    return problems
