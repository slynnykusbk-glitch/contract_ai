"""Utilities for building the ParamGraph and evaluating legal constraints."""

from __future__ import annotations

from decimal import Decimal
from dataclasses import dataclass
import re
from types import SimpleNamespace
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple, Union

from contract_review_app.analysis.extract_summary import (
    _extract_cure_days,
    _extract_cross_refs,
    _extract_duration_from_text,
    _extract_notice_days,
    _extract_payment_term_days,
    _detect_numbering_gaps,
    _detect_order_of_precedence,
    _detect_undefined_terms,
)
from contract_review_app.core.lx_types import (
    Duration,
    LxDocFeatures,
    Money,
    ParamGraph,
    SourceRef,
)
from contract_review_app.legal_rules.cross_checks import _extract_survival_items

from pydantic import BaseModel, Field, PrivateAttr, ConfigDict
from typing import Literal

__all__ = [
    "build_param_graph",
    "Constraint",
    "InternalFinding",
    "load_constraints",
    "eval_constraints",
]


_ANNEX_RE = re.compile(r"\b(?P<prefix>annex|schedule)\s+(?P<label>[A-Z0-9]+)\b", re.IGNORECASE)
_LAW_PATTERN = re.compile(r"governed\s+by\s+the\s+law", re.IGNORECASE)
_JUR_PATTERN = re.compile(r"jurisdiction", re.IGNORECASE)
_CAP_PATTERN = re.compile(r"liability|cap", re.IGNORECASE)
_CURRENCY_PATTERN = re.compile(r"[$€£]|\bUSD\b|\bEUR\b|\bGBP\b", re.IGNORECASE)
_SURVIVE_PATTERN = re.compile(r"\bsurviv", re.IGNORECASE)
_NOTICE_PATTERN = re.compile(r"notice", re.IGNORECASE)
_CURE_PATTERN = re.compile(r"\b(cure|remedy)\b", re.IGNORECASE)
_PAYMENT_PATTERN = re.compile(r"\b(payment|invoice|fee|remit)\b", re.IGNORECASE)
_GRACE_PATTERN = re.compile(r"grace\s+period", re.IGNORECASE)
_CROSS_PATTERN = re.compile(r"\b(?:clause|section)\s+\d", re.IGNORECASE)
_PLACEHOLDER_PATTERN = re.compile(r"\bTBD\b|\?\?\?|\[.+?\]|<<.+?>>", re.IGNORECASE)

_COMPANY_EQUIVALENTS = {
    "LTD": "LIMITED",
    "LIMITED": "LIMITED",
    "PLC": "PLC",
    "CO": "COMPANY",
    "COMPANY": "COMPANY",
    "INC": "INCORPORATED",
    "INCORPORATED": "INCORPORATED",
    "LLC": "LIMITED LIABILITY COMPANY",
    "LLP": "LIMITED LIABILITY PARTNERSHIP",
}


def _normalize_company_name(name: Optional[str]) -> str:
    if not name or not isinstance(name, str):
        return ""
    tokens = re.findall(r"[A-Z0-9]+", name.upper())
    normalized: List[str] = []
    for token in tokens:
        if token == "THE":
            continue
        normalized.append(_COMPANY_EQUIVALENTS.get(token, token))
    return " ".join(normalized)


def _iter_addresses(party: Dict[str, Any]) -> Iterable[Dict[str, Any]]:
    address = party.get("address")
    if isinstance(address, dict):
        yield address
    addresses = party.get("addresses")
    if isinstance(addresses, list):
        for item in addresses:
            if isinstance(item, dict):
                yield item


def _is_address_complete(address: Dict[str, Any]) -> bool:
    if not isinstance(address, dict):
        return False
    line = address.get("line1") or address.get("street") or address.get("address1")
    city = address.get("city") or address.get("town")
    country = address.get("country")
    postal = address.get("postal_code") or address.get("postcode")
    components = [bool(line), bool(city or postal), bool(country)]
    return sum(1 for comp in components if comp) >= 2 and bool(country)


def _normalize_region(value: Optional[str]) -> Optional[str]:
    if not value or not isinstance(value, str):
        return None
    lowered = value.lower()
    if "england" in lowered and "wales" in lowered:
        return "england and wales"
    if "scotland" in lowered:
        return "scotland"
    if "northern ireland" in lowered:
        return "northern ireland"
    if "united kingdom" in lowered or "uk" in lowered:
        return "united kingdom"
    return lowered.strip() or None


def _has_placeholder_text(value: Optional[str]) -> bool:
    if not value or not isinstance(value, str):
        return False
    return bool(_PLACEHOLDER_PATTERN.search(value))


def _iter_segments(segments: Iterable[Any]) -> Iterable[Any]:
    for seg in segments or []:  # type: ignore[truthy-bool]
        yield seg


def _seg_attr(seg: Any, key: str, default: Any = None) -> Any:
    if isinstance(seg, dict):
        return seg.get(key, default)
    return getattr(seg, key, default)


def _combined_text(seg: Any) -> str:
    text = str(_seg_attr(seg, "text", "") or "")
    heading = _seg_attr(seg, "heading")
    if heading:
        return f"{heading}\n{text}" if text else str(heading)
    return text


def _clause_id(seg: Any) -> str:
    number = _seg_attr(seg, "number")
    if isinstance(number, str) and number:
        return number
    seg_id = _seg_attr(seg, "id")
    return str(seg_id) if seg_id is not None else "?"


def _seg_span(seg: Any) -> Optional[Tuple[int, int]]:
    start = _seg_attr(seg, "start")
    end = _seg_attr(seg, "end")
    if isinstance(start, int) and isinstance(end, int):
        return (start, end)
    return None


def _make_source(seg: Any, note: Optional[str] = None) -> SourceRef:
    return SourceRef(clause_id=_clause_id(seg), span=_seg_span(seg), note=note)


def _extract_grace_period(segments: Sequence[Any]) -> Optional[Duration]:
    for seg in segments:
        combined = _combined_text(seg)
        if combined and _GRACE_PATTERN.search(combined):
            lower = combined.lower()
            idx = lower.find("grace period")
            snippet = combined[idx:] if idx >= 0 else combined
            duration = _extract_duration_from_text(snippet)
            if duration:
                return duration
    return None


def _extract_contract_term(l0: Optional[LxDocFeatures]) -> Optional[Duration]:
    if not l0:
        return None
    for seg_id, features in (l0.by_segment or {}).items():
        labels = getattr(features, "labels", [])
        durations = getattr(features, "durations", {})
        if "Term" not in labels:
            continue
        days = durations.get("days")
        if isinstance(days, int) and days > 0:
            return Duration(days=days, kind="calendar")
    return None


def _normalize_currency(value: Optional[str]) -> Optional[str]:
    if not value or not isinstance(value, str):
        return None
    cleaned = value.strip()
    if cleaned in Money._symbol_map:
        return Money._symbol_map[cleaned]
    cleaned = cleaned.upper()
    if len(cleaned) == 3:
        return cleaned
    return None


def _annex_refs(full_text: str) -> List[str]:
    refs = set()
    for match in _ANNEX_RE.finditer(full_text or ""):
        prefix = match.group("prefix") or "annex"
        label = match.group("label") or ""
        formatted = f"{prefix.title()} {label.upper()}" if label.isalpha() else f"{prefix.title()} {label}"
        refs.add(formatted)
    return sorted(refs)


def _first_segment_matching(segments: Sequence[Any], pattern: re.Pattern[str]) -> Optional[Any]:
    for seg in segments:
        combined = _combined_text(seg)
        if combined and pattern.search(combined):
            return seg
    return None


def _full_text_from_segments(segments: Sequence[Any]) -> str:
    parts: List[str] = []
    for seg in segments:
        combined = _combined_text(seg)
        if combined:
            parts.append(combined)
    return "\n".join(parts)


def _collect_survival_items(segments: Sequence[Any]) -> set[str]:
    items: set[str] = set()
    for seg in segments:
        combined = _combined_text(seg)
        if combined and _SURVIVE_PATTERN.search(combined):
            items.update(_extract_survival_items(combined))
    return items


def build_param_graph(
    snapshot: Any,
    segments: Sequence[Any],
    l0_features: Optional[LxDocFeatures],
) -> ParamGraph:
    segments_list = list(_iter_segments(segments))
    full_text = _full_text_from_segments(segments_list)
    parsed = SimpleNamespace(normalized_text=full_text, segments=segments_list)

    payment_term = _extract_payment_term_days(parsed, segments_list)
    notice_period = _extract_notice_days(parsed, segments_list)
    cure_period = _extract_cure_days(parsed, segments_list)
    cross_refs = _extract_cross_refs(parsed, segments_list)
    order_of_precedence = _detect_order_of_precedence(parsed, segments_list)
    undefined_terms = _detect_undefined_terms(parsed, segments_list)
    numbering_gaps = _detect_numbering_gaps(parsed, segments_list)
    grace_period = _extract_grace_period(segments_list)
    contract_term = _extract_contract_term(l0_features)
    survival_items = _collect_survival_items(segments_list)
    annex_refs = _annex_refs(full_text)

    parties = []
    try:
        for party in getattr(snapshot, "parties", []) or []:
            if hasattr(party, "model_dump"):
                parties.append(party.model_dump(exclude_none=True))
            elif isinstance(party, dict):
                parties.append({k: v for k, v in party.items() if v is not None})
    except Exception:
        parties = []

    signatures = []
    for sig in getattr(snapshot, "signatures", []) or []:
        if isinstance(sig, dict):
            signatures.append(sig)
        else:
            signatures.append({"raw": str(sig)})

    law = getattr(snapshot, "governing_law", None)
    juris = getattr(snapshot, "jurisdiction", None)

    cap = None
    liability = getattr(snapshot, "liability", None)
    if liability and getattr(liability, "has_cap", False):
        cap_value = getattr(liability, "cap_value", None)
        cap_currency = getattr(liability, "cap_currency", None)
        if cap_value is not None and cap_currency:
            try:
                amount = Decimal(str(cap_value))
                currency = _normalize_currency(cap_currency)
                if currency:
                    cap = Money(amount=amount, currency=currency)
            except Exception:
                cap = None

    contract_currency = _normalize_currency(getattr(snapshot, "currency", None))

    pg = ParamGraph(
        payment_term=payment_term,
        contract_term=contract_term,
        grace_period=grace_period,
        governing_law=law,
        jurisdiction=juris,
        cap=cap,
        contract_currency=contract_currency,
        notice_period=notice_period,
        cure_period=cure_period,
        survival_items=survival_items,
        cross_refs=cross_refs,
        parties=parties,
        signatures=signatures,
        annex_refs=annex_refs,
        order_of_precedence=order_of_precedence,
        undefined_terms=undefined_terms,
        numbering_gaps=numbering_gaps,
    )

    sources: Dict[str, SourceRef] = {}

    seg_payment = _first_segment_matching(segments_list, _PAYMENT_PATTERN)
    if payment_term and seg_payment:
        sources["payment_term"] = _make_source(seg_payment)

    seg_notice = _first_segment_matching(segments_list, _NOTICE_PATTERN)
    if notice_period and seg_notice:
        sources["notice_period"] = _make_source(seg_notice)

    seg_cure = _first_segment_matching(segments_list, _CURE_PATTERN)
    if cure_period and seg_cure:
        sources["cure_period"] = _make_source(seg_cure)

    seg_grace = _first_segment_matching(segments_list, _GRACE_PATTERN)
    if grace_period and seg_grace:
        sources["grace_period"] = _make_source(seg_grace)

    seg_law = _first_segment_matching(segments_list, _LAW_PATTERN)
    if law and seg_law:
        sources["governing_law"] = _make_source(seg_law)

    seg_jur = _first_segment_matching(segments_list, _JUR_PATTERN)
    if juris and seg_jur:
        sources["jurisdiction"] = _make_source(seg_jur)

    seg_cap = _first_segment_matching(segments_list, _CAP_PATTERN)
    if cap and seg_cap:
        sources["cap"] = _make_source(seg_cap)

    seg_currency = _first_segment_matching(segments_list, _CURRENCY_PATTERN)
    if contract_currency and seg_currency:
        sources["contract_currency"] = _make_source(seg_currency)

    seg_survival = _first_segment_matching(segments_list, _SURVIVE_PATTERN)
    if survival_items and seg_survival:
        sources["survival_items"] = _make_source(seg_survival)

    seg_cross = _first_segment_matching(segments_list, _CROSS_PATTERN)
    if cross_refs and seg_cross:
        sources["cross_refs"] = _make_source(seg_cross, note=f"{len(cross_refs)} cross-ref(s)")

    seg_annex = _first_segment_matching(segments_list, _ANNEX_RE)
    if annex_refs and seg_annex:
        sources["annex_refs"] = _make_source(seg_annex)

    if undefined_terms:
        term = undefined_terms[0]
        for seg in segments_list:
            combined = _combined_text(seg)
            if combined and term in combined:
                sources["undefined_terms"] = _make_source(seg, note=term)
                break

    if numbering_gaps:
        seg_numbering = None
        for seg in segments_list:
            if _seg_attr(seg, "number"):
                seg_numbering = seg
                break
        if seg_numbering:
            sources["numbering_gaps"] = _make_source(seg_numbering, note=", ".join(map(str, numbering_gaps)))

    if parties:
        seg_parties = None
        for seg in segments_list:
            combined = _combined_text(seg)
            if combined and "between" in combined.lower():
                seg_parties = seg
                break
        if seg_parties:
            sources["parties"] = _make_source(seg_parties)

    if signatures:
        seg_sign = None
        for seg in segments_list:
            combined = _combined_text(seg)
            if combined and "signed" in combined.lower():
                seg_sign = seg
                break
        if seg_sign:
            sources["signatures"] = _make_source(seg_sign)

    pg.sources = sources
    return pg


# ---------------------------------------------------------------------------
# Constraint DSL implementation
# ---------------------------------------------------------------------------


class ConstraintSyntaxError(ValueError):
    """Raised when a constraint expression cannot be parsed."""


class ConstraintEvaluationError(RuntimeError):
    """Raised when a constraint expression fails at evaluation time."""


@dataclass
class Token:
    kind: str
    value: str


@dataclass
class ExprNode:
    """Base class for parsed expressions."""


@dataclass
class IdentifierNode(ExprNode):
    name: str


@dataclass
class LiteralNode(ExprNode):
    kind: str
    value: Any


@dataclass
class FunctionNode(ExprNode):
    name: str
    args: List[ExprNode]


@dataclass
class BinaryNode(ExprNode):
    left: ExprNode
    op: str
    right: ExprNode


@dataclass
class CompareNode(ExprNode):
    left: ExprNode
    op: str
    right: ExprNode


class _Tokenizer:
    _SINGLE = {"<", ">", "+", "-", "(", ")", ",", "{", "}"}

    def __init__(self, text: str):
        self.text = text
        self.length = len(text)
        self.pos = 0

    def tokenize(self) -> List[Token]:
        tokens: List[Token] = []
        while self.pos < self.length:
            ch = self.text[self.pos]
            if ch.isspace():
                self.pos += 1
                continue
            if ch in {'"', "'"}:
                tokens.append(self._read_string(ch))
                continue
            if ch.isalpha() or ch == "_":
                tokens.append(self._read_identifier())
                continue
            if ch.isdigit():
                tokens.append(self._read_number())
                continue
            if self.text.startswith("<=", self.pos) or self.text.startswith(">=", self.pos) or self.text.startswith("==", self.pos) or self.text.startswith("!=", self.pos):
                op = self.text[self.pos : self.pos + 2]
                tokens.append(Token("OP", op))
                self.pos += 2
                continue
            if ch in {"∈", "∉"}:
                tokens.append(Token("OP", ch))
                self.pos += 1
                continue
            if ch in self._SINGLE:
                tokens.append(Token(ch, ch))
                self.pos += 1
                continue
            raise ConstraintSyntaxError(f"Unexpected character '{ch}' in expression")
        return tokens

    def _read_string(self, quote: str) -> Token:
        self.pos += 1
        result: List[str] = []
        escaped = False
        while self.pos < self.length:
            ch = self.text[self.pos]
            if escaped:
                result.append(ch)
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == quote:
                self.pos += 1
                return Token("STRING", "".join(result))
            else:
                result.append(ch)
            self.pos += 1
        raise ConstraintSyntaxError("Unterminated string literal")

    def _read_identifier(self) -> Token:
        start = self.pos
        self.pos += 1
        while self.pos < self.length:
            ch = self.text[self.pos]
            if ch.isalnum() or ch == "_":
                self.pos += 1
                continue
            break
        return Token("IDENT", self.text[start:self.pos])

    def _read_number(self) -> Token:
        start = self.pos
        self.pos += 1
        has_dot = False
        while self.pos < self.length:
            ch = self.text[self.pos]
            if ch.isdigit():
                self.pos += 1
                continue
            if ch == "." and not has_dot:
                has_dot = True
                self.pos += 1
                continue
            break
        return Token("NUMBER", self.text[start:self.pos])


class _Parser:
    def __init__(self, tokens: List[Token]):
        self.tokens = tokens
        self.pos = 0

    def parse(self) -> ExprNode:
        expr = self._parse_comparison()
        if not self._at_end():
            raise ConstraintSyntaxError("Unexpected trailing tokens in expression")
        return expr

    def _parse_comparison(self) -> ExprNode:
        left = self._parse_sum()
        if self._match_op({"<", "<=", ">", ">=", "==", "!=", "∈", "∉"}):
            op_token = self._previous()
            right = self._parse_sum()
            return CompareNode(left=left, op=op_token.value, right=right)
        return left

    def _parse_sum(self) -> ExprNode:
        node = self._parse_factor()
        while self._match({"+", "-"}):
            op_token = self._previous()
            right = self._parse_factor()
            node = BinaryNode(left=node, op=op_token.value, right=right)
        return node

    def _parse_factor(self) -> ExprNode:
        if self._match({"("}):
            expr = self._parse_comparison()
            self._consume(")", "Expected ')' to close expression")
            return expr
        if self._match({"{"}):
            values: List[str] = []
            if not self._check("}"):
                while True:
                    token = self._consume("STRING", "Expected string literal inside set")
                    values.append(token.value)
                    if not self._match({","}):
                        break
            self._consume("}", "Expected '}' to close set literal")
            return LiteralNode(kind="set", value=set(values))
        if self._match({"IDENT"}):
            ident = self._previous()
            if self._match({"("}):
                args: List[ExprNode] = []
                if not self._check(")"):
                    while True:
                        args.append(self._parse_comparison())
                        if not self._match({","}):
                            break
                self._consume(")", "Expected ')' to close function call")
                return FunctionNode(name=ident.value, args=args)
            return IdentifierNode(name=ident.value)
        if self._match({"STRING"}):
            token = self._previous()
            return LiteralNode(kind="string", value=token.value)
        if self._match({"NUMBER"}):
            token = self._previous()
            value = Decimal(token.value)
            return LiteralNode(kind="number", value=value)
        raise ConstraintSyntaxError("Unexpected token in expression")

    def _match(self, kinds: set[str]) -> bool:
        if self._at_end():
            return False
        if self.tokens[self.pos].kind in kinds:
            self.pos += 1
            return True
        return False

    def _match_op(self, ops: set[str]) -> bool:
        if self._at_end():
            return False
        token = self.tokens[self.pos]
        if token.kind == "OP" and token.value in ops:
            self.pos += 1
            return True
        if token.kind in ops:
            self.pos += 1
            return True
        return False

    def _consume(self, kind: str, message: str) -> Token:
        if self._check(kind):
            self.pos += 1
            return self.tokens[self.pos - 1]
        raise ConstraintSyntaxError(message)

    def _check(self, kind: str) -> bool:
        if self._at_end():
            return False
        token = self.tokens[self.pos]
        if token.kind == kind:
            return True
        if kind in {"<", ">", "<=", ">=", "==", "!=", "∈", "∉"}:
            return token.kind == "OP" and token.value == kind
        return False

    def _previous(self) -> Token:
        return self.tokens[self.pos - 1]

    def _at_end(self) -> bool:
        return self.pos >= len(self.tokens)


def _parse_expression(text: str) -> ExprNode:
    tokens = _Tokenizer(text).tokenize()
    return _Parser(tokens).parse()


@dataclass
class EvalValue:
    kind: str
    value: Any


@dataclass
class EvaluationDetails:
    op: Optional[str] = None
    left: Optional[EvalValue] = None
    right: Optional[EvalValue] = None
    function: Optional[str] = None
    args: Optional[List[Optional[EvalValue]]] = None


_MISSING = object()


@dataclass(frozen=True)
class _Accessor:
    attr: str
    kind: str
    field: Optional[str] = None


_IDENTIFIER_ACCESSORS: Dict[str, _Accessor] = {
    "PaymentTermDays": _Accessor("payment_term", "duration"),
    "ContractTermDays": _Accessor("contract_term", "duration"),
    "GraceDays": _Accessor("grace_period", "duration"),
    "NoticeDays": _Accessor("notice_period", "duration"),
    "CureDays": _Accessor("cure_period", "duration"),
    "GoverningLaw": _Accessor("governing_law", "string"),
    "Jurisdiction": _Accessor("jurisdiction", "string"),
    "Cap": _Accessor("cap", "money"),
    "CapAmount": _Accessor("cap", "money_amount"),
    "CapCurrency": _Accessor("cap", "money_currency"),
    "ContractCurrency": _Accessor("contract_currency", "string"),
    "SurvivalItems": _Accessor("survival_items", "string_set"),
}


def _collect_identifiers(node: ExprNode, bucket: set[str]) -> None:
    if isinstance(node, IdentifierNode):
        bucket.add(node.name)
    elif isinstance(node, (BinaryNode, CompareNode)):
        _collect_identifiers(node.left, bucket)
        _collect_identifiers(node.right, bucket)
    elif isinstance(node, FunctionNode):
        for arg in node.args:
            _collect_identifiers(arg, bucket)


def _get_accessor_value(pg: ParamGraph, accessor: _Accessor) -> Union[EvalValue, object]:
    value = getattr(pg, accessor.attr, None)
    if accessor.kind == "duration":
        if isinstance(value, Duration) and isinstance(value.days, int):
            return EvalValue("duration", value)
        return _MISSING
    if accessor.kind == "string":
        if isinstance(value, str) and value.strip():
            return EvalValue("string", value.strip())
        return _MISSING
    if accessor.kind == "string_set":
        if isinstance(value, set):
            filtered = {str(it) for it in value if isinstance(it, str) and it}
            if filtered:
                return EvalValue("string_set", filtered)
        return _MISSING
    if accessor.kind == "money":
        if isinstance(value, Money) and isinstance(value.amount, Decimal) and isinstance(value.currency, str):
            return EvalValue("money", value)
        return _MISSING
    if accessor.kind == "money_amount":
        if isinstance(value, Money) and isinstance(value.amount, Decimal):
            return EvalValue("decimal", value.amount)
        return _MISSING
    if accessor.kind == "money_currency":
        if isinstance(value, Money) and isinstance(value.currency, str):
            return EvalValue("string", value.currency)
        return _MISSING
    raise ConstraintEvaluationError(f"Unsupported accessor kind '{accessor.kind}'")


def _ensure_kind(value: EvalValue, expected: str) -> EvalValue:
    if value.kind != expected:
        raise ConstraintEvaluationError(f"Expected value of kind '{expected}', got '{value.kind}'")
    return value


def _duration_days(value: EvalValue) -> int:
    duration = _ensure_kind(value, "duration").value
    return int(duration.days)


def _combine_duration(left: EvalValue, right: EvalValue, op: str) -> EvalValue:
    left_days = _duration_days(left)
    right_days = _duration_days(right)
    days = left_days + right_days if op == "+" else left_days - right_days
    kind = getattr(left.value, "kind", "calendar") if isinstance(left.value, Duration) else "calendar"
    return EvalValue("duration", Duration(days=days, kind=kind))


def _combine_decimal(left: EvalValue, right: EvalValue, op: str) -> EvalValue:
    left_val = _ensure_kind(left, "decimal").value
    right_val = _ensure_kind(right, "decimal").value
    return EvalValue("decimal", left_val + right_val if op == "+" else left_val - right_val)


def _combine_money(left: EvalValue, right: EvalValue, op: str) -> EvalValue:
    money_left = _ensure_kind(left, "money").value
    money_right = _ensure_kind(right, "money").value
    if money_left.currency != money_right.currency:
        raise ConstraintEvaluationError("Cannot combine money values with different currencies")
    amount = money_left.amount + money_right.amount if op == "+" else money_left.amount - money_right.amount
    return EvalValue("money", Money(amount=amount, currency=money_left.currency))


def _format_eval_value(value: EvalValue) -> str:
    if value.kind == "duration":
        duration: Duration = value.value
        suffix = f" {duration.kind}" if getattr(duration, "kind", "calendar") != "calendar" else ""
        return f"{duration.days} days{suffix}"
    if value.kind == "money":
        money: Money = value.value
        return f"{money.amount} {money.currency}"
    if value.kind == "decimal":
        return str(value.value)
    if value.kind == "string":
        return f'"{value.value}"'
    if value.kind == "string_set":
        inner = ", ".join(sorted(value.value))
        return "{" + inner + "}"
    if value.kind == "bool":
        return "true" if value.value else "false"
    return str(value.value)


def _format_details(details: EvaluationDetails) -> str:
    if details.op:
        left = "?" if details.left is None else _format_eval_value(details.left)
        right = "?" if details.right is None else _format_eval_value(details.right)
        return f"{left} {details.op} {right}"
    if details.function:
        args = details.args or []
        formatted = ["?" if arg is None else _format_eval_value(arg) for arg in args]
        return f"{details.function}({', '.join(formatted)})"
    return ""


class _Evaluator:
    def __init__(self, pg: ParamGraph):
        self.pg = pg

    def _get_party(self, index: int) -> Dict[str, Any]:
        parties = self.pg.parties or []
        if 0 <= index < len(parties):
            party = parties[index]
            if isinstance(party, dict):
                return party
        return {}

    def _party_ch_consistent(self, index: int) -> bool:
        party = self._get_party(index)
        if not party:
            return True
        name = party.get("name")
        ch_number = party.get("ch_number") or party.get("company_number")
        registry_name = (
            party.get("ch_name")
            or party.get("registered_name")
            or party.get("company_name")
        )
        if not name or not ch_number:
            return True
        if not registry_name:
            return True
        return _normalize_company_name(name) == _normalize_company_name(registry_name)

    def _addresses_coherent(self) -> bool:
        for party in self.pg.parties or []:
            if not isinstance(party, dict):
                continue
            addresses = list(_iter_addresses(party))
            if not addresses:
                continue
            if not any(_is_address_complete(addr) for addr in addresses):
                return False
        return True

    def _signatures_match_parties(self) -> bool:
        if not self.pg.signatures:
            return True
        normalized_parties = {
            _normalize_company_name(party.get("name"))
            for party in self.pg.parties or []
            if isinstance(party, dict) and party.get("name")
        }
        normalized_parties.discard("")
        if not normalized_parties:
            return True
        for signature in self.pg.signatures:
            if not isinstance(signature, dict):
                continue
            entity = signature.get("entity") or signature.get("for") or signature.get("on_behalf_of")
            if not entity:
                continue
            if _normalize_company_name(entity) not in normalized_parties:
                return False
        return True

    def _signatures_dated(self) -> bool:
        for signature in self.pg.signatures or []:
            if not isinstance(signature, dict):
                continue
            date = signature.get("date") or signature.get("signed_date")
            if not date:
                return False
        return True

    def _get_flag(self, name: str) -> bool:
        value = self.pg.doc_flags.get(name)
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return bool(value)
        if isinstance(value, str):
            lowered = value.strip().lower()
            if lowered in {"yes", "true", "1"}:
                return True
            if lowered in {"no", "false", "0"}:
                return False
        return bool(value)

    def _flag_absent(self, name: str) -> bool:
        return not self._get_flag(name)

    def _flag_present(self, name: str) -> bool:
        return self._get_flag(name)

    def _governing_law_matches_jurisdiction(self) -> bool:
        law_region = _normalize_region(self.pg.governing_law)
        jur_region = _normalize_region(self.pg.jurisdiction)
        if not law_region or not jur_region:
            return True
        if law_region == jur_region:
            return True
        if law_region == "england and wales" and ("england" in jur_region or "wales" in jur_region or "london" in jur_region):
            return True
        return False

    def _no_mixed_exclusivity(self) -> bool:
        jurisdiction = self.pg.jurisdiction or ""
        lowered = jurisdiction.lower()
        return not ("exclusive" in lowered and "non-exclusive" in lowered)

    def _jurisdiction_requires_governing_law(self) -> bool:
        if not self.pg.jurisdiction:
            return True
        return bool(self.pg.governing_law)

    def _jurisdiction_has_no_placeholder(self) -> bool:
        return not _has_placeholder_text(self.pg.jurisdiction)

    def _no_mixed_day_kinds(self) -> bool:
        kinds: set[str] = set()
        for duration in [
            self.pg.payment_term,
            self.pg.contract_term,
            self.pg.grace_period,
            self.pg.notice_period,
            self.pg.cure_period,
        ]:
            if isinstance(duration, Duration):
                kinds.add(duration.kind)
        return len(kinds) <= 1

    def _annexes_have_order_of_precedence(self) -> bool:
        annexes = self.pg.annex_refs or []
        if not annexes:
            return True
        return bool(self.pg.order_of_precedence)

    def _no_undefined_terms(self) -> bool:
        return not (self.pg.undefined_terms or self._get_flag("undefined_terms_present"))

    def _numbering_coherent(self) -> bool:
        if self.pg.numbering_gaps:
            return False
        return not self._get_flag("dangling_or")

    def _survival_baseline_complete(self) -> bool:
        items = {item.lower() for item in (self.pg.survival_items or set())}
        if not items:
            return False
        baseline = {"confidentiality", "intellectual property", "liability"}
        return baseline.issubset(items)

    def _arg_to_int(self, arg: Optional[EvalValue]) -> Optional[int]:
        if arg is None:
            return None
        if arg.kind == "decimal":
            try:
                return int(arg.value)
            except Exception as exc:  # pragma: no cover - defensive
                raise ConstraintEvaluationError("Invalid integer argument") from exc
        raise ConstraintEvaluationError("Expected numeric argument")

    def evaluate(self, node: ExprNode) -> Tuple[Optional[bool], EvaluationDetails]:
        if isinstance(node, CompareNode):
            result, left_val, right_val = self._evaluate_compare(node)
            details = EvaluationDetails(op=node.op, left=left_val, right=right_val)
            return result, details
        if isinstance(node, FunctionNode):
            value, args = self._eval_function_node(node)
            details = EvaluationDetails(function=node.name, args=args)
            if value is _MISSING:
                return None, details
            if value.kind != "bool":
                raise ConstraintEvaluationError("Function did not produce a boolean result")
            return bool(value.value), details
        value = self._eval_value(node)
        if value is _MISSING:
            return None, EvaluationDetails()
        if not isinstance(value, EvalValue) or value.kind != "bool":
            raise ConstraintEvaluationError("Constraint expression must evaluate to a boolean")
        return bool(value.value), EvaluationDetails()

    def _eval_value(self, node: ExprNode) -> Union[EvalValue, object]:
        if isinstance(node, LiteralNode):
            if node.kind == "string":
                return EvalValue("string", node.value)
            if node.kind == "set":
                return EvalValue("string_set", set(node.value))
            if node.kind == "number":
                return EvalValue("decimal", node.value)
            raise ConstraintEvaluationError(f"Unsupported literal kind '{node.kind}'")
        if isinstance(node, IdentifierNode):
            accessor = _IDENTIFIER_ACCESSORS.get(node.name)
            if not accessor:
                raise ConstraintEvaluationError(f"Unknown identifier '{node.name}'")
            return _get_accessor_value(self.pg, accessor)
        if isinstance(node, BinaryNode):
            left = self._eval_value(node.left)
            right = self._eval_value(node.right)
            if left is _MISSING or right is _MISSING:
                return _MISSING
            if not isinstance(left, EvalValue) or not isinstance(right, EvalValue):
                raise ConstraintEvaluationError("Invalid operands for arithmetic operator")
            if left.kind == "duration" and right.kind == "duration":
                return _combine_duration(left, right, node.op)
            if left.kind == "decimal" and right.kind == "decimal":
                return _combine_decimal(left, right, node.op)
            if left.kind == "money" and right.kind == "money":
                return _combine_money(left, right, node.op)
            raise ConstraintEvaluationError(
                f"Unsupported operand types for '{node.op}': {left.kind} and {right.kind}"
            )
        if isinstance(node, CompareNode):
            result, _, _ = self._evaluate_compare(node)
            if result is None:
                return _MISSING
            return EvalValue("bool", result)
        if isinstance(node, FunctionNode):
            value, _ = self._eval_function_node(node)
            return value
        raise ConstraintEvaluationError("Unsupported expression node")

    def _eval_function_node(
        self, node: FunctionNode
    ) -> Tuple[Union[EvalValue, object], List[Optional[EvalValue]]]:
        evaluated_args: List[Optional[EvalValue]] = []
        for arg in node.args:
            value = self._eval_value(arg)
            evaluated_args.append(None if value is _MISSING else value)
        return self._call_function(node.name, evaluated_args), evaluated_args

    def _evaluate_compare(
        self, node: CompareNode
    ) -> Tuple[Optional[bool], Optional[EvalValue], Optional[EvalValue]]:
        left = self._eval_value(node.left)
        right = self._eval_value(node.right)
        left_val = None if left is _MISSING else left
        right_val = None if right is _MISSING else right
        if left is _MISSING or right is _MISSING:
            return None, left_val, right_val
        if not isinstance(left, EvalValue) or not isinstance(right, EvalValue):
            raise ConstraintEvaluationError("Comparison operands must be values")
        op = node.op
        if op in {"==", "!="}:
            return self._compare_equality(op, left, right), left, right
        if op in {"<", "<=", ">", ">="}:
            return self._compare_order(op, left, right), left, right
        if op in {"∈", "∉"}:
            return self._compare_membership(op, left, right), left, right
        raise ConstraintEvaluationError(f"Unsupported comparison operator '{op}'")

    def _compare_equality(self, op: str, left: EvalValue, right: EvalValue) -> bool:
        if left.kind != right.kind:
            raise ConstraintEvaluationError("Cannot compare values of different kinds")
        if left.kind == "duration":
            result = _duration_days(left) == _duration_days(right)
            return result if op == "==" else not result
        if left.kind == "money":
            money_left: Money = left.value
            money_right: Money = right.value
            if op == "==":
                return money_left.currency == money_right.currency and money_left.amount == money_right.amount
            return money_left.currency != money_right.currency or money_left.amount != money_right.amount
        if left.kind in {"string", "decimal", "bool", "string_set"}:
            return (left.value == right.value) if op == "==" else (left.value != right.value)
        raise ConstraintEvaluationError(f"Equality not supported for kind '{left.kind}'")

    def _compare_order(self, op: str, left: EvalValue, right: EvalValue) -> bool:
        if left.kind == "duration" and right.kind == "duration":
            lval = _duration_days(left)
            rval = _duration_days(right)
        elif left.kind == "decimal" and right.kind == "decimal":
            lval = left.value
            rval = right.value
        elif left.kind == "money" and right.kind == "money":
            money_left: Money = left.value
            money_right: Money = right.value
            if money_left.currency != money_right.currency:
                raise ConstraintEvaluationError("Cannot compare money values with different currencies")
            lval = money_left.amount
            rval = money_right.amount
        else:
            raise ConstraintEvaluationError(
                f"Ordering operator not supported for kinds '{left.kind}' and '{right.kind}'"
            )
        if op == "<":
            return lval < rval
        if op == "<=":
            return lval <= rval
        if op == ">":
            return lval > rval
        if op == ">=":
            return lval >= rval
        raise ConstraintEvaluationError(f"Unsupported ordering operator '{op}'")

    def _compare_membership(self, op: str, left: EvalValue, right: EvalValue) -> bool:
        if right.kind != "string_set":
            raise ConstraintEvaluationError("Membership requires a set of strings on the right-hand side")
        if left.kind != "string":
            raise ConstraintEvaluationError("Membership is only supported for string values")
        membership = left.value in right.value
        return membership if op == "∈" else not membership

    def _call_function(self, name: str, args: List[Optional[EvalValue]]) -> Union[EvalValue, object]:
        lname = name.lower()
        if lname == "present":
            if len(args) != 1:
                raise ConstraintEvaluationError("present() expects exactly one argument")
            arg = args[0]
            if arg is None:
                return EvalValue("bool", False)
            return EvalValue("bool", self._is_present(arg))
        if lname == "same_currency":
            if len(args) != 2:
                raise ConstraintEvaluationError("same_currency() expects exactly two arguments")
            if any(arg is None for arg in args):
                return _MISSING
            currencies = {self._extract_currency(arg) for arg in args if arg is not None}
            return EvalValue("bool", len(currencies) <= 1)
        if lname == "non_negative":
            if len(args) != 1:
                raise ConstraintEvaluationError("non_negative() expects exactly one argument")
            arg = args[0]
            if arg is None:
                return _MISSING
            return EvalValue("bool", self._is_non_negative(arg))
        if lname == "all_present":
            if not args:
                raise ConstraintEvaluationError("all_present() expects at least one argument")
            if any(arg is None for arg in args):
                return EvalValue("bool", False)
            return EvalValue("bool", all(self._is_present(arg) for arg in args))
        if lname == "implies":
            if len(args) != 2:
                raise ConstraintEvaluationError("implies() expects exactly two arguments")
            if any(arg is None for arg in args):
                return _MISSING
            left, right = args
            if left.kind != "bool" or right.kind != "bool":
                raise ConstraintEvaluationError("implies() arguments must be boolean expressions")
            return EvalValue("bool", (not bool(left.value)) or bool(right.value))
        if lname == "party_ch_consistent":
            if len(args) != 1:
                raise ConstraintEvaluationError("party_ch_consistent() expects one argument")
            index = self._arg_to_int(args[0])
            if index is None:
                return EvalValue("bool", True)
            return EvalValue("bool", self._party_ch_consistent(index))
        if lname == "addresses_coherent":
            if args:
                raise ConstraintEvaluationError("addresses_coherent() expects no arguments")
            return EvalValue("bool", self._addresses_coherent())
        if lname == "signatures_match_parties":
            if args:
                raise ConstraintEvaluationError("signatures_match_parties() expects no arguments")
            return EvalValue("bool", self._signatures_match_parties())
        if lname == "signatures_dated":
            if args:
                raise ConstraintEvaluationError("signatures_dated() expects no arguments")
            return EvalValue("bool", self._signatures_dated())
        if lname == "flag_absent":
            if len(args) != 1:
                raise ConstraintEvaluationError("flag_absent() expects one argument")
            flag_name = args[0]
            if flag_name is None:
                return EvalValue("bool", True)
            if flag_name.kind != "string":
                raise ConstraintEvaluationError("flag_absent() expects a string argument")
            return EvalValue("bool", self._flag_absent(flag_name.value))
        if lname == "flag_present":
            if len(args) != 1:
                raise ConstraintEvaluationError("flag_present() expects one argument")
            flag_name = args[0]
            if flag_name is None:
                return EvalValue("bool", False)
            if flag_name.kind != "string":
                raise ConstraintEvaluationError("flag_present() expects a string argument")
            return EvalValue("bool", self._flag_present(flag_name.value))
        if lname == "governing_law_coherent":
            if args:
                raise ConstraintEvaluationError("governing_law_coherent() expects no arguments")
            return EvalValue("bool", self._governing_law_matches_jurisdiction())
        if lname == "no_mixed_exclusivity":
            if args:
                raise ConstraintEvaluationError("no_mixed_exclusivity() expects no arguments")
            return EvalValue("bool", self._no_mixed_exclusivity())
        if lname == "jurisdiction_requires_law":
            if args:
                raise ConstraintEvaluationError("jurisdiction_requires_law() expects no arguments")
            return EvalValue("bool", self._jurisdiction_requires_governing_law())
        if lname == "jurisdiction_has_no_placeholder":
            if args:
                raise ConstraintEvaluationError("jurisdiction_has_no_placeholder() expects no arguments")
            return EvalValue("bool", self._jurisdiction_has_no_placeholder())
        if lname == "no_mixed_day_kinds":
            if args:
                raise ConstraintEvaluationError("no_mixed_day_kinds() expects no arguments")
            return EvalValue("bool", self._no_mixed_day_kinds())
        if lname == "annexes_have_order":
            if args:
                raise ConstraintEvaluationError("annexes_have_order() expects no arguments")
            return EvalValue("bool", self._annexes_have_order_of_precedence())
        if lname == "no_undefined_terms":
            if args:
                raise ConstraintEvaluationError("no_undefined_terms() expects no arguments")
            return EvalValue("bool", self._no_undefined_terms())
        if lname == "numbering_coherent":
            if args:
                raise ConstraintEvaluationError("numbering_coherent() expects no arguments")
            return EvalValue("bool", self._numbering_coherent())
        if lname == "survival_baseline_complete":
            if args:
                raise ConstraintEvaluationError("survival_baseline_complete() expects no arguments")
            return EvalValue("bool", self._survival_baseline_complete())
        raise ConstraintEvaluationError(f"Unknown function '{name}' in constraint expression")

    def _is_present(self, value: EvalValue) -> bool:
        if value.kind in {"duration", "money"}:
            return True
        if value.kind == "string":
            return bool(value.value)
        if value.kind == "decimal":
            return True
        if value.kind == "string_set":
            return len(value.value) > 0
        if value.kind == "bool":
            return True
        return value.value is not None

    def _extract_currency(self, value: EvalValue) -> str:
        if value.kind == "money":
            return value.value.currency
        if value.kind == "string":
            return value.value.upper()
        raise ConstraintEvaluationError("Unsupported value for currency extraction")

    def _is_non_negative(self, value: EvalValue) -> bool:
        if value.kind == "decimal":
            return value.value >= 0
        if value.kind == "money":
            return value.value.amount >= 0
        raise ConstraintEvaluationError("non_negative() expects a money amount")


class InternalFinding(BaseModel):
    rule_id: str
    message: str
    severity: Literal["low", "medium", "high", "critical"]
    scope: Literal["doc", "clause"]
    anchors: List[SourceRef] = Field(default_factory=list)


class Constraint(BaseModel):
    id: str
    expr: str
    severity: Literal["low", "medium", "high", "critical"]
    message_tmpl: str
    scope: Literal["doc", "clause"] = "doc"
    anchors: List[str] = Field(default_factory=list)

    model_config = ConfigDict(arbitrary_types_allowed=True)

    _ast: ExprNode = PrivateAttr()

    def model_post_init(self, __context: Any) -> None:
        self._ast = _parse_expression(self.expr)
        identifiers: set[str] = set()
        _collect_identifiers(self._ast, identifiers)
        missing = [name for name in identifiers if name not in _IDENTIFIER_ACCESSORS]
        if missing:
            raise ConstraintSyntaxError(
                f"Unknown identifiers in constraint '{self.id}': {', '.join(sorted(missing))}"
            )

    def evaluate(self, pg: ParamGraph) -> Tuple[Optional[bool], EvaluationDetails]:
        evaluator = _Evaluator(pg)
        return evaluator.evaluate(self._ast)


_CONSTRAINTS_CACHE: Optional[List[Constraint]] = None


def load_constraints() -> List[Constraint]:
    global _CONSTRAINTS_CACHE
    if _CONSTRAINTS_CACHE is not None:
        return _CONSTRAINTS_CACHE
    specs_data = [
        {
            "id": "L2-001",
            "expr": "party_ch_consistent(0)",
            "severity": "high",
            "message_tmpl": "Party A name / company number mismatch.",
            "anchors": ["parties"],
        },
        {
            "id": "L2-002",
            "expr": "addresses_coherent()",
            "severity": "medium",
            "message_tmpl": "Party address information is inconsistent.",
            "anchors": ["parties", "parties/addrs"],
        },
        {
            "id": "L2-003",
            "expr": "signatures_match_parties()",
            "severity": "high",
            "message_tmpl": "Signature entity does not match the preamble parties.",
            "anchors": ["signatures", "preamble"],
        },
        {
            "id": "L2-004",
            "expr": "signatures_dated()",
            "severity": "medium",
            "message_tmpl": "Execution block lacks signing dates.",
            "anchors": ["signatures"],
        },
        {
            "id": "L2-005",
            "expr": "party_ch_consistent(1)",
            "severity": "high",
            "message_tmpl": "Party B name / company number mismatch.",
            "anchors": ["parties"],
        },
        {
            "id": "L2-010",
            "expr": "governing_law_coherent()",
            "severity": "high",
            "message_tmpl": "Governing law and jurisdiction are inconsistent.",
            "anchors": ["governing_law", "jurisdiction"],
        },
        {
            "id": "L2-011",
            "expr": "no_mixed_exclusivity()",
            "severity": "medium",
            "message_tmpl": "Jurisdiction clause mixes exclusive and non-exclusive language.",
            "anchors": ["dispute"],
        },
        {
            "id": "L2-012",
            "expr": "jurisdiction_requires_law()",
            "severity": "medium",
            "message_tmpl": "Jurisdiction provided without governing law reference.",
            "anchors": ["governing_law", "jurisdiction"],
        },
        {
            "id": "L2-013",
            "expr": "jurisdiction_has_no_placeholder()",
            "severity": "medium",
            "message_tmpl": "Jurisdiction clause contains placeholder text.",
            "anchors": ["jurisdiction"],
        },
        {
            "id": "L2-020",
            "expr": "PaymentTermDays <= ContractTermDays + GraceDays",
            "severity": "high",
            "message_tmpl": "Payment term exceeds the contract term plus grace period.",
            "anchors": ["payment_term", "contract_term", "grace_period"],
        },
        {
            "id": "L2-021",
            "expr": "implies(all_present(NoticeDays, CureDays), NoticeDays <= CureDays)",
            "severity": "medium",
            "message_tmpl": "Notice period should not exceed the cure period when both are defined.",
            "anchors": ["notice_period", "cure_period"],
        },
        {
            "id": "L2-022",
            "expr": "no_mixed_day_kinds()",
            "severity": "low",
            "message_tmpl": "Mixed calendar and business day concepts detected in related periods.",
            "anchors": ["durations"],
        },
        {
            "id": "L2-023",
            "expr": "implies(present(PaymentTermDays), present(ContractTermDays))",
            "severity": "medium",
            "message_tmpl": "Payment terms defined but contract term missing.",
            "anchors": ["payment_term", "contract_term"],
        },
        {
            "id": "L2-024",
            "expr": "implies(present(NoticeDays), present(CureDays))",
            "severity": "medium",
            "message_tmpl": "Notice period referenced without a corresponding cure period.",
            "anchors": ["notice_period", "cure_period"],
        },
        {
            "id": "L2-030",
            "expr": "non_negative(CapAmount)",
            "severity": "high",
            "message_tmpl": "Liability cap amount must be non-negative.",
            "anchors": ["cap"],
        },
        {
            "id": "L2-031",
            "expr": "same_currency(Cap, ContractCurrency)",
            "severity": "medium",
            "message_tmpl": "Liability cap currency should match the contract currency.",
            "anchors": ["cap", "contract_currency"],
        },
        {
            "id": "L2-032",
            "expr": "flag_absent(\"indemnity_unlimited_no_carveout\")",
            "severity": "high",
            "message_tmpl": "Unlimited indemnity without carve-outs detected.",
            "anchors": ["indemnity"],
        },
        {
            "id": "L2-033",
            "expr": "flag_absent(\"fraud_exclusion_detected\")",
            "severity": "critical",
            "message_tmpl": "Liability carve-outs improperly exclude fraud.",
            "anchors": ["liability"],
        },
        {
            "id": "L2-034",
            "expr": "flag_absent(\"cap_amount_missing\")",
            "severity": "medium",
            "message_tmpl": "Liability cap referenced without a stated amount.",
            "anchors": ["cap"],
        },
        {
            "id": "L2-040",
            "expr": "flag_absent(\"public_domain_by_recipient\")",
            "severity": "medium",
            "message_tmpl": "Confidentiality exception allows disclosures caused by the recipient.",
            "anchors": ["confidentiality"],
        },
        {
            "id": "L2-041",
            "expr": "flag_absent(\"illegal_possession_exception\")",
            "severity": "medium",
            "message_tmpl": "Exception for information illegally in the recipient's possession is present.",
            "anchors": ["confidentiality"],
        },
        {
            "id": "L2-042",
            "expr": "flag_absent(\"purpose_overbreadth\")",
            "severity": "medium",
            "message_tmpl": "Purpose clause allows \"any other purpose whatsoever\".",
            "anchors": ["confidentiality"],
        },
        {
            "id": "L2-043",
            "expr": "flag_absent(\"return_delete_broken_ref\")",
            "severity": "medium",
            "message_tmpl": "Return/delete obligations reference missing or broken cross-references.",
            "anchors": ["confidentiality"],
        },
        {
            "id": "L2-044",
            "expr": "flag_absent(\"missing_return_timeline\")",
            "severity": "medium",
            "message_tmpl": "Confidential information return or destruction lacks a defined timeline.",
            "anchors": ["confidentiality"],
        },
        {
            "id": "L2-050",
            "expr": "flag_absent(\"notify_notwithstanding_law\")",
            "severity": "critical",
            "message_tmpl": "Obligation to notify regulators applies even when prohibited by law.",
            "anchors": ["regulatory"],
        },
        {
            "id": "L2-051",
            "expr": "flag_absent(\"overbroad_regulator_disclosure\")",
            "severity": "high",
            "message_tmpl": "Regulator disclosure not limited to the minimum necessary information.",
            "anchors": ["regulatory"],
        },
        {
            "id": "L2-052",
            "expr": "flag_absent(\"regulator_notice_requires_consent\")",
            "severity": "medium",
            "message_tmpl": "Regulatory disclosures require prior consent, impeding compliance.",
            "anchors": ["regulatory"],
        },
        {
            "id": "L2-053",
            "expr": "flag_absent(\"aml_obligations_missing\")",
            "severity": "medium",
            "message_tmpl": "AML obligations missing despite regulatory triggers.",
            "anchors": ["aml"],
        },
        {
            "id": "L2-060",
            "expr": "flag_absent(\"fm_no_payment_carveout\")",
            "severity": "medium",
            "message_tmpl": "Force majeure clause lacks a payment obligation carve-out.",
            "anchors": ["force_majeure"],
        },
        {
            "id": "L2-061",
            "expr": "flag_absent(\"fm_financial_hardship\")",
            "severity": "medium",
            "message_tmpl": "Force majeure excuses performance for financial hardship or internal failures.",
            "anchors": ["force_majeure"],
        },
        {
            "id": "L2-070",
            "expr": "flag_absent(\"pd_without_dp_obligations\")",
            "severity": "high",
            "message_tmpl": "Personal data processing mentioned without UK GDPR obligations.",
            "anchors": ["data_protection"],
        },
        {
            "id": "L2-071",
            "expr": "flag_absent(\"data_transfer_without_safeguards\")",
            "severity": "high",
            "message_tmpl": "International data transfers lack safeguard obligations.",
            "anchors": ["data_protection"],
        },
        {
            "id": "L2-080",
            "expr": "no_undefined_terms()",
            "severity": "medium",
            "message_tmpl": "Undefined capitalised terms are used in the contract.",
            "anchors": ["definitions"],
        },
        {
            "id": "L2-081",
            "expr": "numbering_coherent()",
            "severity": "low",
            "message_tmpl": "Numbering gaps or dangling '; or' detected.",
            "anchors": ["definitions"],
        },
        {
            "id": "L2-082",
            "expr": "annexes_have_order()",
            "severity": "medium",
            "message_tmpl": "Annexes referenced without an order of precedence clause.",
            "anchors": ["annexes"],
        },
        {
            "id": "L2-083",
            "expr": "flag_absent(\"annex_reference_unresolved\")",
            "severity": "medium",
            "message_tmpl": "Schedule or annex references cannot be resolved.",
            "anchors": ["annexes"],
        },
        {
            "id": "L2-084",
            "expr": "flag_absent(\"broken_cross_references\")",
            "severity": "high",
            "message_tmpl": "Broken internal cross-references detected.",
            "anchors": ["cross_refs"],
        },
        {
            "id": "L2-090",
            "expr": "flag_absent(\"companies_act_1985_reference\")",
            "severity": "medium",
            "message_tmpl": "Contract cites the Companies Act 1985 instead of the 2006 Act.",
            "anchors": ["statutes"],
        },
        {
            "id": "L2-091",
            "expr": "flag_absent(\"outdated_ico_reference\")",
            "severity": "low",
            "message_tmpl": "Outdated UK data protection authority name detected.",
            "anchors": ["statutes"],
        },
        {
            "id": "L2-092",
            "expr": "flag_absent(\"outdated_fsa_reference\")",
            "severity": "medium",
            "message_tmpl": "Outdated UK regulator name (e.g., FSA) referenced.",
            "anchors": ["statutes"],
        },
        {
            "id": "L2-100",
            "expr": "flag_absent(\"fee_for_nda\")",
            "severity": "medium",
            "message_tmpl": "Fee-for-NDA commercial anomaly detected.",
            "anchors": ["commercial"],
        },
        {
            "id": "L2-101",
            "expr": "flag_absent(\"shall_be_avoided_wording\")",
            "severity": "low",
            "message_tmpl": "Clause uses 'shall be avoided' where 'void' or 'invalid' is expected.",
            "anchors": ["commercial"],
        },
        {
            "id": "L2-102",
            "expr": "survival_baseline_complete()",
            "severity": "medium",
            "message_tmpl": "Survival clause missing confidentiality/IP/liability baseline.",
            "anchors": ["survival"],
        },
    ]
    specs = [Constraint(**data) for data in specs_data]
    _CONSTRAINTS_CACHE = specs
    return specs


def _anchors_for(constraint: Constraint, pg: ParamGraph) -> List[SourceRef]:
    anchors: List[SourceRef] = []
    for anchor in constraint.anchors:
        source = pg.sources.get(anchor)
        if source:
            anchors.append(source)
    return anchors


def eval_constraints(pg: ParamGraph, findings_in: List[InternalFinding]) -> List[InternalFinding]:
    findings = list(findings_in)
    for constraint in load_constraints():
        try:
            result, details = constraint.evaluate(pg)
        except ConstraintEvaluationError:
            continue
        if result is None or result:
            continue
        detail_text = _format_details(details)
        message = constraint.message_tmpl
        if detail_text:
            message = f"{message} ({detail_text})"
        findings.append(
            InternalFinding(
                rule_id=f"L2::{constraint.id}",
                message=message,
                severity=constraint.severity,
                scope=constraint.scope,
                anchors=_anchors_for(constraint, pg),
            )
        )
    return findings
