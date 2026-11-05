import ast
import io
import sys
import tokenize

WORD = "_\"'"
JOIN = {"**", "//", "<<", ">>", "<=", ">=", "==", "!=", "->", ":=", "+=", "-=", "*=", "/=", "%=", "&=", "|=", "^=", "@=", ".."}
NEED = {"body"}


def noop(s):
    return isinstance(s, ast.Pass) or isinstance(s, ast.Expr) and isinstance(s.value, ast.Constant)


def merge(body):
    out = []
    for s in body:
        p = out[-1] if out else None
        if isinstance(s, ast.Import) and isinstance(p, ast.Import):
            p.names += s.names
        elif (isinstance(s, ast.ImportFrom) and isinstance(p, ast.ImportFrom) and s.module == p.module
              and s.level == p.level and s.module != "__future__" and "*" not in [a.name for a in s.names + p.names]):
            p.names += s.names
        else:
            out.append(s)
    return out


def transform(tree):
    for node in ast.walk(tree):
        if isinstance(node, ast.Return) and isinstance(node.value, ast.Constant) and node.value.value is None:
            node.value = None
        for field in ("body", "orelse", "finalbody"):
            body = getattr(node, field, None)
            if not isinstance(body, list) or not body or not isinstance(body[0], ast.stmt):
                continue
            body = merge([s for s in body if not noop(s)])
            if not body and not isinstance(node, ast.Module) and (
                    field in NEED or field == "finalbody" and not node.handlers):
                body = [ast.Expr(ast.Constant(0))]
            setattr(node, field, body)
    return tree


def spans(src):
    lines = io.StringIO(src).readlines()

    def cut(a, b):
        if a[0] == b[0]:
            return lines[a[0] - 1][a[1]:b[1]]
        return lines[a[0] - 1][a[1]:] + "".join(lines[a[0]:b[0] - 1]) + lines[b[0] - 1][:b[1]]

    toks = list(tokenize.generate_tokens(io.StringIO(src).readline))
    i = 0
    while i < len(toks):
        t = toks[i]
        if tokenize.tok_name[t.type].endswith("STRING_START"):
            depth, j = 0, i
            while True:
                n = tokenize.tok_name[toks[j].type]
                if n.endswith("STRING_START"):
                    depth += 1
                elif n.endswith("STRING_END"):
                    depth -= 1
                    if not depth:
                        break
                j += 1
            yield tokenize.STRING, cut(t.start, toks[j].end)
            i = j + 1
            continue
        yield t.type, t.string
        i += 1


def space(a, b, ta):
    x, y = a[-1], b[0]
    if (x.isalnum() or x in WORD) and (y.isalnum() or y in WORD):
        return True
    if ta == tokenize.NUMBER and y == ".":
        return True
    return x + y in JOIN


def logical(src):
    depth, line = 0, []
    for t, text in spans(src):
        if t in (tokenize.COMMENT, tokenize.NL, tokenize.ENDMARKER):
            continue
        if t == tokenize.INDENT:
            depth += 1
        elif t == tokenize.DEDENT:
            depth -= 1
        elif t == tokenize.NEWLINE:
            s, prev = "", None
            for tt, x in line:
                if prev and space(prev[1], x, prev[0]):
                    s += " "
                s += x
                prev = (tt, x)
            kind = "head" if line[-1] == (tokenize.OP, ":") else "deco" if s[0] == "@" else "simple"
            yield [depth, s, kind]
            line = []
        else:
            line.append((t, text))


def compact(src):
    lines = list(logical(src))
    out = []
    i = 0
    while i < len(lines):
        d, s, kind = lines[i]
        if kind == "head":
            j = i + 1
            while j < len(lines) and lines[j][0] > d:
                j += 1
            suite = lines[i + 1:j]
            if suite and all(x[0] == d + 1 and x[2] == "simple" for x in suite):
                out.append([d, s + ";".join(x[1] for x in suite), "inline"])
                i = j
                continue
        if kind == "simple" and out and out[-1][2] == "simple" and out[-1][0] == d:
            out[-1][1] += ";" + s
        else:
            out.append([d, s, kind])
        i += 1
    return "".join(" " * d + s + "\n" for d, s, _ in out)


def minify(src):
    tree = transform(ast.parse(src))
    head = src.split("\n", 1)[0] + "\n" if src.startswith("#!") else ""
    new = head + compact(ast.unparse(tree))
    if ast.dump(ast.parse(new)) != ast.dump(tree):
        raise ValueError("ast mismatch")
    return new


def main():
    for path in sys.argv[1:]:
        with tokenize.open(path) as f:
            src = f.read()
        try:
            new = minify(src)
        except Exception as e:
            print("pymin: %s: %s" % (path, e), file=sys.stderr)
            continue
        if len(new.encode()) < len(src.encode()):
            with open(path, "w", encoding="utf-8") as f:
                f.write(new)


if __name__ == "__main__":
    main()
