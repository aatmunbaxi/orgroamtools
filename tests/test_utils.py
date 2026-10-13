import pytest

from orgroamtools._utils import (
    decode_lisp_string,
    extract_math_snippets,
    extract_src_blocks,
)


@pytest.mark.parametrize(
    "raw, expected",
    [
        ('"plain"', "plain"),
        ('"The \\"quoted\\" node"', 'The "quoted" node'),
        ('"back\\\\slash"', "back\\slash"),
        ('"a,b"', "a,b"),
        ('""', ""),
        ('"multi\nline"', "multi\nline"),
        (None, None),
        ("unquoted", "unquoted"),
        ('"', '"'),
    ],
)
def test_decode_lisp_string(raw, expected):
    assert decode_lisp_string(raw) == expected


@pytest.mark.parametrize(
    "text, expected",
    [
        (r"inline \(a+b\) math", ["a+b"]),
        ("\\[\nx^2\n\\]", ["x^2"]),
        ("\\begin{equation}\ne\n\\end{equation}", ["e\n"]),
        ("\\begin{align}\ne\n\\end{align}", ["e\n"]),
        ("#+begin_equation\ne\n#+end_equation", ["e\n"]),
        ("#+begin_latex\ne\n#+end_latex", ["e\n"]),
        ("no math here", []),
    ],
)
def test_extract_math_snippets(text, expected):
    assert extract_math_snippets(text) == expected


@pytest.mark.parametrize(
    "text, expected",
    [
        pytest.param(r"\[c+d\]", ["c+d"], id="display-one-line"),
        pytest.param("\\begin{equation*}\ne\n\\end{equation*}", ["e\n"], id="equation*"),
        pytest.param("\\begin{align*}\ne\n\\end{align*}", ["e\n"], id="align*"),
        pytest.param("\\begin{multline}\ne\n\\end{multline}", ["e\n"], id="multline"),
        pytest.param("\\begin{multline*}\ne\n\\end{multline*}", ["e\n"], id="multline*"),
        pytest.param("\\begin{equation}\ne\n\\end{align}", [], id="mismatched-env"),
        pytest.param("$x$", ["x"], id="dollar"),
    ],
)
@pytest.mark.xfail(strict=True, reason="phase 4: LaTeX regex")
def test_extract_math_snippets_known_gaps(text, expected):
    assert extract_math_snippets(text) == expected


@pytest.mark.parametrize(
    "text, expected",
    [
        ("#+begin_src python\nx = 1\n#+end_src\n", [("python", "x = 1")]),
        ("#+BEGIN_SRC emacs-lisp :results none\n(+ 1 2)\n#+END_SRC\n", [("emacs-lisp", "(+ 1 2)")]),
        ("  #+begin_src sh\nls\n  #+end_src\n", [("sh", "ls")]),
        ("#+begin_src c++ :includes <iostream>\nint x;\n#+end_src\n", [("c++", "int x;")]),
        (
            "#+begin_src a\n1\n#+end_src\n#+begin_src b\n2\n#+end_src\n",
            [("a", "1"), ("b", "2")],
        ),
        ("no blocks", []),
    ],
)
def test_extract_src_blocks(text, expected):
    assert extract_src_blocks(text) == expected


@pytest.mark.parametrize(
    "text, expected",
    [
        pytest.param("#+begin_src\nbare\n#+end_src\n", [(None, "bare")], id="no-language"),
    ],
)
@pytest.mark.xfail(strict=True, reason="phase 4: src block without a language")
def test_extract_src_blocks_known_gaps(text, expected):
    assert extract_src_blocks(text) == expected
