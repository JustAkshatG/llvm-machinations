"""
C Reconstructor Module
======================
Translates LLVM IR into a human-readable pseudo-C representation for
educational visualization.  The output is **not** compilable C — it is
an approximation that helps students understand what the optimizer did
at the source-code level.

Key design choices:
  • SSA ``%name`` variables are rendered as C locals (``name``).
  • ``phi`` nodes are shown with a φ notation explaining the merge.
  • Labels are preserved as goto targets.
  • Dead / unreachable code is annotated with ``/* DEAD */``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field


# ═══════════════════════════════════════════════════════════════════════════
# IR type → C type mapping
# ═══════════════════════════════════════════════════════════════════════════

_TYPE_MAP: dict[str, str] = {
    "i1": "bool",
    "i8": "char",
    "i16": "short",
    "i32": "int",
    "i64": "long",
    "float": "float",
    "double": "double",
    "void": "void",
    "ptr": "void*",
    "i8*": "char*",
    "i32*": "int*",
    "i64*": "long*",
}

# Comparison predicate → C operator
_CMP_OPS: dict[str, str] = {
    "eq": "==", "ne": "!=",
    "sgt": ">",  "sge": ">=", "slt": "<",  "sle": "<=",
    "ugt": ">",  "uge": ">=", "ult": "<",  "ule": "<=",
    "oeq": "==", "one": "!=", "ogt": ">",  "oge": ">=",
    "olt": "<",  "ole": "<=",
}

# Arithmetic / logic opcode → C operator
_ARITH_OPS: dict[str, str] = {
    "add": "+",  "sub": "-",  "mul": "*",
    "sdiv": "/", "udiv": "/", "srem": "%", "urem": "%",
    "fadd": "+", "fsub": "-", "fmul": "*", "fdiv": "/", "frem": "%",
    "shl": "<<", "lshr": ">>", "ashr": ">>",
    "and": "&",  "or": "|",   "xor": "^",
}


# ═══════════════════════════════════════════════════════════════════════════
# Regex patterns for IR parsing
# ═══════════════════════════════════════════════════════════════════════════

# Function definition:  define dso_local i32 @name(i32 %a, i32 %b) ... {
_FUNC_DEF_RE = re.compile(
    r"define\s+(?:[\w]+\s+)*"           # optional linkage/attrs (dso_local etc.)
    r"([\w*]+)\s+"                       # return type
    r"@([\w.]+)\s*"                      # function name
    r"\(([^)]*)\)"                       # parameter list
    r"[^{]*\{"                           # attrs until opening brace
)

# Label:  entry:  or  if.then:  (possibly with preds comment)
_LABEL_RE = re.compile(r"^([\w.]+):\s*(?:;.*)?$")

# Assignment instruction:  %name = opcode ...
_ASSIGN_RE = re.compile(r"^\s+%([\w.]+)\s*=\s*(.*)")

# Standalone instruction (no assignment):  ret / br / store / unreachable
_STANDALONE_RE = re.compile(r"^\s+(ret|br|store|unreachable|switch|call|tail call|musttail call|notail call)\s*(.*)")

# Close brace
_CLOSE_BRACE_RE = re.compile(r"^\s*\}\s*$")


# ═══════════════════════════════════════════════════════════════════════════
# Helper functions
# ═══════════════════════════════════════════════════════════════════════════

def _c_type(ir_type: str) -> str:
    """Map an LLVM IR type string to an approximate C type."""
    ir_type = ir_type.strip()
    # Remove 'noundef', 'signext', 'zeroext' etc.
    ir_type = re.sub(r"\b(noundef|signext|zeroext|nonnull|dereferenceable\(\d+\))\b", "", ir_type).strip()
    return _TYPE_MAP.get(ir_type, ir_type)


def _clean_val(val: str) -> str:
    """Clean an IR value reference into a C-like name.

    ``%x``   → ``x``
    ``42``   → ``42``
    ``true`` → ``true``
    ``@func`` → ``func``
    """
    val = val.strip()
    if val.startswith("%"):
        return val[1:]
    if val.startswith("@"):
        return val[1:]
    return val


def _strip_ir_type_prefix(expr: str) -> tuple[str, str]:
    """Split 'i32 %x' into ('i32', '%x').

    Handles multi-token types like 'i32*', 'ptr', etc.
    """
    expr = expr.strip()
    # Handle 'ptr @name' or 'i32 %x' or 'i32 42'
    m = re.match(r"([\w*]+(?:\s*\*)*)\s+(.*)", expr)
    if m:
        return m.group(1).strip(), m.group(2).strip()
    return "", expr


# ═══════════════════════════════════════════════════════════════════════════
# Main Reconstructor
# ═══════════════════════════════════════════════════════════════════════════

class CReconstructor:
    """Translates LLVM IR into educational pseudo-C.

    Usage::

        r = CReconstructor()
        pseudo_c = r.reconstruct(ir_text)
    """

    def _resolve(self, name: str, is_ssa: bool = True) -> str:
        """Resolve a cleaned IR name, substituting parameter names.

        Also prefixes bare numeric SSA names with 't' so ``%3`` becomes ``t3``
        instead of the invalid-C ``3``.
        """
        if name in self._param_names:
            return self._param_names[name]
        # Prefix purely-numeric SSA names with 't' for readability
        if is_ssa and name.isdigit():
            return f"t{name}"
        return name

    def _clean(self, val: str) -> str:
        """Clean an IR value and resolve parameter names."""
        val = val.strip()
        is_ssa = val.startswith("%")
        cleaned = _clean_val(val)
        return self._resolve(cleaned, is_ssa=is_ssa)

    def _resolve_label(self, name: str) -> str:
        """Resolve a label name, prefixing numeric labels with 'lbl_'."""
        name = name.strip()
        if name.startswith("%"):
            name = name[1:]
        if name.isdigit():
            return f"lbl_{name}"
        return name

    def reconstruct(self, ir_text: str) -> str:
        """Reconstruct pseudo-C from LLVM IR text.

        Parameters
        ----------
        ir_text : str
            Raw LLVM IR (the output of ``opt -S``).

        Returns
        -------
        str
            A pseudo-C string for educational display.
        """
        self._param_names: dict[str, str] = {}
        lines = ir_text.splitlines()
        output: list[str] = []
        output.append("/* ═══ Reconstructed C (educational — not compilable) ═══ */")
        output.append("")

        i = 0
        while i < len(lines):
            line = lines[i]

            # Skip metadata, attributes, comments, empty lines at module level
            stripped = line.strip()
            if (
                not stripped
                or stripped.startswith(";")
                or stripped.startswith("!")
                or stripped.startswith("attributes")
                or stripped.startswith("source_filename")
                or stripped.startswith("target")
                or stripped.startswith("declare")
                or stripped.startswith("module")
            ):
                i += 1
                continue

            # Function definition
            m = _FUNC_DEF_RE.match(stripped)
            if m:
                ret_type, func_name, params_str = m.group(1), m.group(2), m.group(3)
                c_sig = self._reconstruct_signature(ret_type, func_name, params_str)
                output.append(f"{c_sig} {{")

                # Parse the function body until closing brace
                i += 1
                body_lines, i = self._collect_function_body(lines, i)
                body_c = self._reconstruct_body(body_lines)
                output.extend(body_c)
                output.append("}")
                output.append("")
                continue

            i += 1

        return "\n".join(output)

    # ── Signature reconstruction ──────────────────────────────────────

    def _reconstruct_signature(
        self, ret_type: str, func_name: str, params_str: str,
    ) -> str:
        """Build a C-style function signature."""
        c_ret = _c_type(ret_type)
        c_params: list[str] = []
        self._param_names: dict[str, str] = {}   # map %0 → arg0 etc.

        if params_str.strip():
            param_idx = 0
            for param in params_str.split(","):
                param = param.strip()
                if not param:
                    continue
                # Remove attributes like noundef, signext, etc.
                param = re.sub(
                    r"\b(noundef|signext|zeroext|nonnull|"
                    r"dereferenceable\(\d+\)|align\s+\d+|"
                    r"nocapture|readonly|writeonly)\b",
                    "", param,
                ).strip()
                parts = param.rsplit(None, 1)
                if len(parts) == 2:
                    ptype, pname = parts
                    clean = _clean_val(pname)
                    # If the name is just a number, make it readable
                    if clean.isdigit():
                        readable = f"arg{param_idx}"
                        self._param_names[clean] = readable
                        clean = readable
                    c_params.append(f"{_c_type(ptype)} {clean}")
                else:
                    c_params.append(_c_type(parts[0]))
                param_idx += 1

        return f"{c_ret} {func_name}({', '.join(c_params)})"

    # ── Body collection ───────────────────────────────────────────────

    def _collect_function_body(
        self, lines: list[str], start: int,
    ) -> tuple[list[str], int]:
        """Collect lines inside a function body until the closing '}'."""
        body: list[str] = []
        i = start
        depth = 1
        while i < len(lines):
            line = lines[i]
            if _CLOSE_BRACE_RE.match(line):
                depth -= 1
                if depth == 0:
                    return body, i + 1
            if "{" in line:
                depth += 1
            body.append(line)
            i += 1
        return body, i

    # ── Body reconstruction ───────────────────────────────────────────

    def _reconstruct_body(self, body_lines: list[str]) -> list[str]:
        """Reconstruct the function body as pseudo-C statements."""
        output: list[str] = []
        first_label = True   # skip printing 'entry:' label if it's the first

        for line in body_lines:
            stripped = line.strip()

            # Skip empty / comment / metadata lines
            if not stripped or stripped.startswith(";") or stripped.startswith("!"):
                continue

            # Label
            m = _LABEL_RE.match(stripped)
            if m:
                label_name = self._resolve_label(m.group(1))
                if first_label:
                    first_label = False
                    # Only add a comment for the entry block
                    output.append(f"    // entry block")
                else:
                    output.append("")
                    output.append(f"{label_name}:")
                continue

            first_label = False

            # Assignment instruction: %name = ...
            m = _ASSIGN_RE.match(line)
            if m:
                var_name = self._resolve(m.group(1))
                rhs = m.group(2).strip()
                c_stmt = self._reconstruct_assignment(var_name, rhs)
                output.append(f"    {c_stmt}")
                continue

            # Standalone instruction
            m = _STANDALONE_RE.match(line)
            if m:
                opcode = m.group(1).strip()
                rest = m.group(2).strip()
                c_stmt = self._reconstruct_standalone(opcode, rest)
                output.append(f"    {c_stmt}")
                continue

        return output

    # ── Assignment reconstruction ─────────────────────────────────────

    def _reconstruct_assignment(self, var_name: str, rhs: str) -> str:
        """Reconstruct a ``%var = ...`` instruction as C."""

        # ── alloca ──
        if rhs.startswith("alloca"):
            m = re.match(r"alloca\s+([\w*]+)", rhs)
            alloc_type = _c_type(m.group(1)) if m else "void"
            return f"{alloc_type} {var_name};    /* stack allocation */"

        # ── load ──
        if rhs.startswith("load"):
            m = re.match(r"load\s+([\w*]+)\s*,\s*\w+\s+(%?[\w.]+)", rhs)
            if m:
                load_type = _c_type(m.group(1))
                src = self._clean(m.group(2))
                return f"{load_type} {var_name} = *{src};"
            return f"auto {var_name} = /* load */;"

        # ── call ──
        if re.match(r"(?:tail\s+|musttail\s+|notail\s+)?call\s+", rhs):
            return self._reconstruct_call(var_name, rhs)

        # ── icmp / fcmp ──
        m = re.match(r"[if]cmp\s+(\w+)\s+([\w*]+)\s+(%?[\w.]+)\s*,\s*(%?[\w.]+)", rhs)
        if m:
            pred, _ty, lhs_val, rhs_val = m.group(1), m.group(2), m.group(3), m.group(4)
            op = _CMP_OPS.get(pred, pred)
            return f"bool {var_name} = ({self._clean(lhs_val)} {op} {self._clean(rhs_val)});"

        # ── phi ──
        if rhs.startswith("phi"):
            return self._reconstruct_phi(var_name, rhs)

        # ── select ──
        m = re.match(
            r"select\s+i1\s+(%?[\w.]+)\s*,\s*[\w*]+\s+(%?[\w.]+)\s*,\s*[\w*]+\s+(%?[\w.]+)",
            rhs,
        )
        if m:
            cond = self._clean(m.group(1))
            tv = self._clean(m.group(2))
            fv = self._clean(m.group(3))
            return f"auto {var_name} = {cond} ? {tv} : {fv};"

        # ── arithmetic / logic / bitwise ──
        for opcode, c_op in _ARITH_OPS.items():
            pattern = rf"^{opcode}\s+(?:nsw\s+|nuw\s+|exact\s+)*([\w*]+)\s+(%?[\w.]+)\s*,\s*(%?[\w.]+)"
            m = re.match(pattern, rhs)
            if m:
                ir_type = m.group(1)
                a = self._clean(m.group(2))
                b = self._clean(m.group(3))
                c_type = _c_type(ir_type)
                return f"{c_type} {var_name} = {a} {c_op} {b};"

        # ── sext / zext / trunc (type casts) ──
        m = re.match(r"(sext|zext|trunc)\s+[\w*]+\s+(%?[\w.]+)\s+to\s+([\w*]+)", rhs)
        if m:
            cast_op, src_val, dest_type = m.group(1), m.group(2), m.group(3)
            return f"{_c_type(dest_type)} {var_name} = ({_c_type(dest_type)}){self._clean(src_val)};"

        # ── bitcast / inttoptr / ptrtoint ──
        m = re.match(r"(bitcast|inttoptr|ptrtoint)\s+[\w*]+\s+(%?[\w.]+)\s+to\s+([\w*]+)", rhs)
        if m:
            _, src_val, dest_type = m.group(1), m.group(2), m.group(3)
            return f"{_c_type(dest_type)} {var_name} = ({_c_type(dest_type)}){self._clean(src_val)};"

        # ── getelementptr ──
        if rhs.startswith("getelementptr"):
            # Simplify GEP to pointer arithmetic
            m = re.match(r"getelementptr\s+(?:inbounds\s+)?[\w*]+\s*,\s*\w+\s+(%?[\w.]+)", rhs)
            if m:
                base = self._clean(m.group(1))
                return f"void* {var_name} = &{base}[...];    /* pointer arithmetic */"
            return f"void* {var_name} = /* getelementptr */;"

        # ── fallback ──
        # Try to at least show the opcode
        opcode_m = re.match(r"(\w+)", rhs)
        opcode = opcode_m.group(1) if opcode_m else "?"
        return f"auto {var_name} = /* {opcode}: {rhs[:60]} */;"

    # ── Call reconstruction ───────────────────────────────────────────

    def _reconstruct_call(self, var_name: str, rhs: str) -> str:
        """Reconstruct a call instruction."""
        # Match: [tail] call TYPE @func(args...)
        m = re.match(
            r"(?:tail\s+|musttail\s+|notail\s+)?call\s+"
            r"([\w*]+)\s+"                       # return type
            r"(?:[\w]+\s+)*"                     # optional attrs
            r"@([\w.]+)\s*"                       # function name
            r"\(([^)]*)\)",                       # arguments
            rhs,
        )
        if m:
            ret_type, func_name, args_str = m.group(1), m.group(2), m.group(3)
            c_args = self._reconstruct_call_args(args_str)
            c_ret = _c_type(ret_type)
            if c_ret == "void":
                return f"{func_name}({c_args});"
            return f"{c_ret} {var_name} = {func_name}({c_args});"

        # Fallback for indirect calls or complex signatures
        return f"auto {var_name} = /* call: {rhs[:60]} */;"

    def _reconstruct_call_args(self, args_str: str) -> str:
        """Parse call arguments like 'i32 10, i32 %x' into '10, x'."""
        if not args_str.strip():
            return ""
        args: list[str] = []
        # Split on commas but be careful with nested parens
        depth = 0
        current = ""
        for ch in args_str:
            if ch == "(":
                depth += 1
                current += ch
            elif ch == ")":
                depth -= 1
                current += ch
            elif ch == "," and depth == 0:
                args.append(current.strip())
                current = ""
            else:
                current += ch
        if current.strip():
            args.append(current.strip())

        c_args: list[str] = []
        for arg in args:
            arg = arg.strip()
            # Remove attributes
            arg = re.sub(
                r"\b(noundef|signext|zeroext|nonnull)\b", "", arg,
            ).strip()
            _, val = _strip_ir_type_prefix(arg)
            c_args.append(self._clean(val))
        return ", ".join(c_args)

    # ── PHI reconstruction ────────────────────────────────────────────

    def _reconstruct_phi(self, var_name: str, rhs: str) -> str:
        """Reconstruct a phi node as a φ-notation comment."""
        # Extract type
        m = re.match(r"phi\s+([\w*]+)\s+(.*)", rhs)
        if not m:
            return f"auto {var_name} = /* phi */;"

        ir_type = m.group(1)
        incoming = m.group(2)
        c_type = _c_type(ir_type)

        # Parse [ val, %label ] pairs
        pairs = re.findall(r"\[\s*(%?[\w.]+)\s*,\s*%?([\w.]+)\s*\]", incoming)
        if pairs:
            parts = [f"{self._clean(v)} from {self._resolve_label(lbl)}" for v, lbl in pairs]
            phi_desc = ", ".join(parts)
            return f"{c_type} {var_name} = φ({phi_desc});"

        return f"{c_type} {var_name} = /* phi */;"

    # ── Standalone instruction reconstruction ─────────────────────────

    def _reconstruct_standalone(self, opcode: str, rest: str) -> str:
        """Reconstruct instructions that don't assign to a variable."""

        # ── ret ──
        if opcode == "ret":
            m = re.match(r"([\w*]+)\s+(%?[\w.]+)", rest)
            if m:
                return f"return {self._clean(m.group(2))};"
            if "void" in rest:
                return "return;"
            return f"return {self._clean(rest)};"

        # ── br (conditional) ──
        if opcode == "br":
            # Conditional: br i1 %cond, label %t, label %f
            m = re.match(
                r"i1\s+(%?[\w.]+)\s*,\s*label\s+%?([\w.]+)\s*,\s*label\s+%?([\w.]+)",
                rest,
            )
            if m:
                cond = self._clean(m.group(1))
                true_lbl = self._resolve_label(m.group(2))
                false_lbl = self._resolve_label(m.group(3))
                return f"if ({cond}) goto {true_lbl}; else goto {false_lbl};"

            # Unconditional: br label %target
            m = re.match(r"label\s+%?([\w.]+)", rest)
            if m:
                return f"goto {self._resolve_label(m.group(1))};"

            return f"/* br {rest} */"

        # ── store ──
        if opcode == "store":
            m = re.match(
                r"([\w*]+)\s+(%?[\w.]+)\s*,\s*\w+\s+(%?[\w.]+)",
                rest,
            )
            if m:
                val = self._clean(m.group(2))
                dest = self._clean(m.group(3))
                return f"*{dest} = {val};"
            return f"/* store {rest[:50]} */;"

        # ── unreachable ──
        if opcode == "unreachable":
            return "/* UNREACHABLE */;"

        # ── call (standalone, void return) ──
        if "call" in opcode:
            m = re.match(
                r"(?:[\w*]+)\s+(?:[\w]+\s+)*@([\w.]+)\s*\(([^)]*)\)",
                rest,
            )
            if m:
                func_name = m.group(1)
                c_args = self._reconstruct_call_args(m.group(2))
                return f"{func_name}({c_args});"
            return f"/* {opcode} {rest[:50]} */;"

        # ── switch ──
        if opcode == "switch":
            return f"/* switch {rest[:60]} */;"

        return f"/* {opcode} {rest[:60]} */;"
