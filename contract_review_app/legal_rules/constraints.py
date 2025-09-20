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
        if lname == "implies":
            if len(args) != 2:
                raise ConstraintEvaluationError("implies() expects exactly two arguments")
            if any(arg is None for arg in args):
                return _MISSING
            left, right = args
            if left.kind != "bool" or right.kind != "bool":
                raise ConstraintEvaluationError("implies() arguments must be boolean expressions")
            return EvalValue("bool", (not bool(left.value)) or bool(right.value))
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
    specs = [
        Constraint(
            id="payment_term_vs_term",
            expr="PaymentTermDays <= ContractTermDays + GraceDays",
            severity="medium",
            message_tmpl="Payment term should not exceed the contract term plus any grace period.",
            scope="doc",
            anchors=["payment_term", "contract_term", "grace_period"],
        ),
        Constraint(
            id="governing_law_jurisdiction_alignment",
            expr=(
                "implies(GoverningLaw == \"England and Wales\", "
                "Jurisdiction ∈ {\"England and Wales courts\", \"LCIA London\"})"
            ),
            severity="medium",
            message_tmpl="When governing law is England and Wales, jurisdiction should be aligned.",
            scope="doc",
            anchors=["governing_law", "jurisdiction"],
        ),
        Constraint(
            id="cap_non_negative",
            expr="non_negative(CapAmount)",
            severity="high",
            message_tmpl="Liability cap amount must be non-negative.",
            scope="doc",
            anchors=["cap"],
        ),
        Constraint(
            id="cap_currency_alignment",
            expr="same_currency(Cap, ContractCurrency)",
            severity="medium",
            message_tmpl="Liability cap currency should match the contract currency.",
            scope="doc",
            anchors=["cap", "contract_currency"],
        ),
        Constraint(
            id="notice_vs_cure",
            expr="NoticeDays <= CureDays",
            severity="medium",
            message_tmpl="Notice period should not exceed the cure period.",
            scope="doc",
            anchors=["notice_period", "cure_period"],
        ),
    ]
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
