"""Expand G-code into plain blocks of (letter, value) words.

Most CAM output is plain coordinates, but LinuxCNC, Mach3 and many hand-written
programs use parameters (#1, #<name>), bracketed expressions, and O-word
control flow (repeat, while, do, if, subroutines). This module runs that
logic and hands the importer a flat list of blocks with numbers only.

Only the RS274/NGC subset needed to recover geometry is supported. Unknown
parameters (such as HAL pins) read as 0, and execution is capped so a program
cannot loop forever.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field

from revalo.engine.model import JobImportError

MAX_STEPS = 2_000_000

Block = tuple[list[tuple[str, float]], str]

_PAREN_COMMENT = re.compile(r"\(([^)]*)\)")
_LINE_NUMBER = re.compile(r"^\s*N\s*\d+(\.\d+)?")
_OWORD = re.compile(
    r"^\s*O\s*(\d+|<[^>]*>)\s*"
    r"(SUB|ENDSUB|CALL|DO|WHILE|ENDWHILE|IF|ELSEIF|ELSE|ENDIF|REPEAT|ENDREPEAT|BREAK|CONTINUE"
    r"|RETURN)\b(.*)$"
)
_NUMBER = re.compile(r"[-+]?(?:\d+\.?\d*|\.\d+)")
_FUNCTIONS = {
    "ABS": abs,
    "SQRT": lambda v: math.sqrt(max(v, 0.0)),
    "SIN": lambda v: math.sin(math.radians(v)),
    "COS": lambda v: math.cos(math.radians(v)),
    "TAN": lambda v: math.tan(math.radians(v)),
    "ASIN": lambda v: math.degrees(math.asin(max(-1.0, min(1.0, v)))),
    "ACOS": lambda v: math.degrees(math.acos(max(-1.0, min(1.0, v)))),
    "EXP": math.exp,
    "LN": lambda v: math.log(v) if v > 0 else 0.0,
    "ROUND": lambda v: float(round(v)),
    "FIX": lambda v: float(math.floor(v)),
    "FUP": lambda v: float(math.ceil(v)),
}
# Binary operators by precedence (lowest first).
_PRECEDENCE = [
    ("AND", "OR", "XOR"),
    ("EQ", "NE", "GT", "GE", "LT", "LE"),
    ("+", "-"),
    ("*", "/", "MOD"),
    ("**",),
]


@dataclass
class _Line:
    code: str
    comment: str
    label: str | None = None
    keyword: str | None = None
    rest: str = ""


@dataclass
class _Structure:
    close: dict[int, int] = field(default_factory=dict)
    open_of: dict[int, int] = field(default_factory=dict)
    branches: dict[int, list[int]] = field(default_factory=dict)
    subs: dict[str, int] = field(default_factory=dict)
    do_closers: set[int] = field(default_factory=set)


class _Parser:
    """Recursive-descent evaluator for values and bracketed expressions."""

    def __init__(self, text: str, params: dict[str, float]):
        self.s = text
        self.i = 0
        self.params = params

    def skip(self) -> None:
        while self.i < len(self.s) and self.s[self.i] in " \t":
            self.i += 1

    def peek(self) -> str:
        self.skip()
        return self.s[self.i] if self.i < len(self.s) else ""

    def done(self) -> bool:
        return self.peek() == ""

    def param_name(self) -> str:
        self.skip()
        if self.s[self.i] != "#":
            raise ValueError("expected #")
        self.i += 1
        self.skip()
        if self.i < len(self.s) and self.s[self.i] == "<":
            end = self.s.index(">", self.i)
            name = self.s[self.i + 1 : end].strip().lower()
            self.i = end + 1
            return name
        if self.peek() == "[":
            return str(int(round(self.bracket())))
        match = re.compile(r"\d+").match(self.s, self.i)
        if not match:
            raise ValueError("bad parameter")
        self.i = match.end()
        return str(int(match.group()))

    def value(self) -> float:
        c = self.peek()
        if c == "[":
            return self.bracket()
        if c == "#":
            return self.params.get(self.param_name(), 0.0)
        if c in "+-":
            self.i += 1
            v = self.value()
            return -v if c == "-" else v
        if c.isalpha():
            match = re.compile(r"[A-Z]+").match(self.s, self.i)
            name = match.group() if match else ""
            if name == "ATAN":
                self.i = match.end()
                y = self.bracket()
                self.skip()
                if self.peek() == "/":
                    self.i += 1
                    x = self.bracket()
                    return math.degrees(math.atan2(y, x))
                return math.degrees(math.atan(y))
            if name in _FUNCTIONS:
                self.i = match.end()
                return _FUNCTIONS[name](self.bracket())
            if name == "EXISTS":
                self.i = match.end()
                self.skip()
                self.i += 1  # [
                key = self.param_name()
                self.skip()
                self.i += 1  # ]
                return 1.0 if key in self.params else 0.0
            raise ValueError(f"unexpected {name}")
        match = _NUMBER.match(self.s, self.i)
        if not match:
            raise ValueError("expected a number")
        self.i = match.end()
        return float(match.group())

    def bracket(self) -> float:
        if self.peek() != "[":
            raise ValueError("expected [")
        self.i += 1
        v = self.expr(0)
        if self.peek() != "]":
            raise ValueError("expected ]")
        self.i += 1
        return v

    def _operator(self, level: int) -> str | None:
        self.skip()
        for op in sorted(_PRECEDENCE[level], key=len, reverse=True):
            if self.s.startswith(op, self.i):
                if op == "*" and self.s.startswith("**", self.i):
                    continue
                return op
        return None

    def expr(self, level: int) -> float:
        if level == len(_PRECEDENCE):
            return self.value()
        left = self.expr(level + 1)
        while (op := self._operator(level)) is not None:
            self.i += len(op)
            right = self.expr(level + 1)
            left = _apply(op, left, right)
        return left


def _apply(op: str, a: float, b: float) -> float:
    if op == "+":
        return a + b
    if op == "-":
        return a - b
    if op == "*":
        return a * b
    if op == "/":
        return a / b if b else 0.0
    if op == "MOD":
        return math.fmod(a, b) if b else 0.0
    if op == "**":
        try:
            return float(a**b)
        except (OverflowError, ValueError, ZeroDivisionError):
            return 0.0
    comparisons = {
        "EQ": a == b,
        "NE": a != b,
        "GT": a > b,
        "GE": a >= b,
        "LT": a < b,
        "LE": a <= b,
        "AND": bool(a) and bool(b),
        "OR": bool(a) or bool(b),
        "XOR": bool(a) != bool(b),
    }
    return 1.0 if comparisons[op] else 0.0


def _split_comments(raw: str) -> tuple[str, str]:
    comments = _PAREN_COMMENT.findall(raw)
    code = _PAREN_COMMENT.sub(" ", raw)
    if ";" in code:
        code, semi = code.split(";", 1)
        comments.append(semi)
    text = " ".join(c.strip() for c in comments if c.strip())
    return code.upper(), text


def _preparse(text: str) -> tuple[list[_Line], _Structure]:
    lines: list[_Line] = []
    for raw in text.splitlines():
        code, comment = _split_comments(raw)
        code = code.strip().lstrip("/").strip()
        if code.startswith("%"):
            code = ""
        code = _LINE_NUMBER.sub("", code)
        match = _OWORD.match(code)
        if match:
            lines.append(_Line("", comment, match.group(1), match.group(2), match.group(3)))
        else:
            lines.append(_Line(code, comment))

    st = _Structure()
    stack: list[tuple[str, str, int]] = []
    for idx, line in enumerate(lines):
        kw, label = line.keyword, line.label
        if kw is None:
            continue
        if kw == "WHILE" and stack and stack[-1][0] == label and stack[-1][1] == "DO":
            _, _, start = stack.pop()
            st.close[start] = idx
            st.open_of[idx] = start
            st.do_closers.add(idx)
        elif kw in ("SUB", "DO", "WHILE", "IF", "REPEAT"):
            stack.append((label, kw, idx))
            if kw == "SUB":
                st.subs[label] = idx
            if kw == "IF":
                st.branches[idx] = []
        elif kw in ("ELSEIF", "ELSE"):
            for lab, k, start in reversed(stack):
                if lab == label and k == "IF":
                    st.branches[start].append(idx)
                    st.open_of[idx] = start
                    break
        elif kw in ("ENDSUB", "ENDWHILE", "ENDIF", "ENDREPEAT"):
            for pos in range(len(stack) - 1, -1, -1):
                if stack[pos][0] == label:
                    _, _, start = stack.pop(pos)
                    st.close[start] = idx
                    st.open_of[idx] = start
                    break
        elif kw in ("BREAK", "CONTINUE"):
            for lab, _k, start in reversed(stack):
                if lab == label:
                    st.open_of[idx] = start
                    break
    return lines, st


def _eval_rest(rest: str, params: dict[str, float]) -> float:
    rest = rest.strip()
    if not rest:
        return 0.0
    try:
        return _Parser(rest, params).value()
    except (ValueError, IndexError, ZeroDivisionError):
        return 0.0


def _run_line(code: str, params: dict[str, float]) -> list[tuple[str, float]]:
    """Evaluate one line: assignments update params, words are returned."""
    p = _Parser(code, params)
    words: list[tuple[str, float]] = []
    pending: list[tuple[str, float]] = []
    while not p.done():
        c = p.peek()
        try:
            if c == "#":
                name = p.param_name()
                if p.peek() == "=":
                    p.i += 1
                    pending.append((name, p.value()))
                continue
            if c == "$":  # spindle selector, e.g. M3 $0
                p.i += 1
                number = _NUMBER.match(p.s, p.i)
                if number:
                    p.i = number.end()
                continue
            if c.isalpha():
                p.i += 1
                words.append((c, p.value()))
                continue
        except (ValueError, IndexError):
            pass
        p.i += 1  # skip anything unparseable
    # Parameters set on a line take effect after the line is read (RS274/NGC).
    for name, value in pending:
        params[name] = value
    return words


def expand(text: str) -> list[Block]:
    lines, st = _preparse(text)
    params: dict[str, float] = {}
    blocks: list[Block] = []
    repeat_left: dict[int, int] = {}
    calls: list[tuple[int, dict[str, float]]] = []
    pc = 0
    steps = 0
    n = len(lines)

    while pc < n:
        steps += 1
        if steps > MAX_STEPS:
            raise JobImportError("G-code program runs too long (endless loop?).")
        line = lines[pc]
        kw = line.keyword
        if kw is None:
            words = _run_line(line.code, params) if line.code else []
            if words or line.comment:
                blocks.append((words, line.comment))
            if any(w == ("M", 2.0) or w == ("M", 30.0) for w in words):
                break
            pc += 1
            continue

        if kw == "SUB":
            pc = st.close.get(pc, pc) + 1
        elif kw in ("ENDSUB", "RETURN"):
            if calls:
                pc, saved = calls.pop()
                params.update(saved)
            else:
                pc += 1
        elif kw == "CALL":
            start = st.subs.get(line.label)
            if start is None or len(calls) > 50:
                pc += 1
                continue
            args = re.findall(r"\[[^\]]*\]", line.rest)
            saved = {str(i): params.get(str(i), 0.0) for i in range(1, 31)}
            for i, arg in enumerate(args, start=1):
                params[str(i)] = _eval_rest(arg, params)
            calls.append((pc + 1, saved))
            pc = start + 1
        elif kw == "REPEAT":
            if pc not in repeat_left:
                repeat_left[pc] = int(_eval_rest(line.rest, params))
            if repeat_left[pc] <= 0:
                del repeat_left[pc]
                pc = st.close.get(pc, pc) + 1
            else:
                pc += 1
        elif kw == "ENDREPEAT":
            start = st.open_of.get(pc)
            if start is not None and start in repeat_left:
                repeat_left[start] -= 1
                pc = start
            else:
                pc += 1
        elif kw == "DO":
            pc += 1
        elif kw == "WHILE":
            cond = _eval_rest(line.rest, params)
            if pc in st.do_closers:
                pc = st.open_of[pc] + 1 if cond else pc + 1
            else:
                pc = pc + 1 if cond else st.close.get(pc, pc) + 1
        elif kw == "ENDWHILE":
            pc = st.open_of.get(pc, pc + 1)
        elif kw == "IF":
            if _eval_rest(line.rest, params):
                pc += 1
            else:
                pc = _next_branch(pc, pc, st, lines, params)
        elif kw in ("ELSEIF", "ELSE"):
            # Reached by falling out of a taken branch: skip to ENDIF.
            start = st.open_of.get(pc)
            pc = st.close.get(start, pc) + 1 if start is not None else pc + 1
        elif kw == "ENDIF":
            pc += 1
        elif kw in ("BREAK", "CONTINUE"):
            start = st.open_of.get(pc)
            if start is None:
                pc += 1
            elif kw == "BREAK":
                repeat_left.pop(start, None)
                pc = st.close.get(start, pc) + 1
            else:
                pc = st.close.get(start, pc)
        else:
            pc += 1
    return blocks


def _next_branch(start: int, current: int, st: _Structure, lines, params) -> int:
    """After a false IF/ELSEIF, find the branch to run, or the line after ENDIF."""
    for idx in st.branches.get(start, []):
        if idx <= current:
            continue
        if lines[idx].keyword == "ELSE":
            return idx + 1
        if _eval_rest(lines[idx].rest, params):
            return idx + 1
    return st.close.get(start, current) + 1
