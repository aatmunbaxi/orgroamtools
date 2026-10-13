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
        # \( \) and \[ \]
        pytest.param(r"inline \(a+b\) math", ["a+b"], id="inline"),
        pytest.param("\\[\nx^2\n\\]", ["x^2"], id="display"),
        pytest.param(r"\[c+d\]", ["c+d"], id="display-one-line"),
        pytest.param(r"\\[2pt] \(x\)", ["x"], id="latex-linebreak-not-display"),
        # environments
        pytest.param("\\begin{equation}\ne\n\\end{equation}", ["e"], id="equation"),
        pytest.param("\\begin{equation*}\ne\n\\end{equation*}", ["e"], id="equation*"),
        pytest.param("\\begin{align}\ne\n\\end{align}", ["e"], id="align"),
        pytest.param("\\begin{align*}\ne\n\\end{align*}", ["e"], id="align*"),
        pytest.param("\\begin{multline}\ne\n\\end{multline}", ["e"], id="multline"),
        pytest.param("\\begin{multline*}\ne\n\\end{multline*}", ["e"], id="multline*"),
        pytest.param("\\begin{gather*}\ne\n\\end{gather*}", ["e"], id="gather*"),
        pytest.param("\\begin{equation}\ne\n\\end{align}", [], id="mismatched-env"),
        pytest.param("\\begin{itemize}\n\\item a\n\\end{itemize}", [], id="non-math-env"),
        pytest.param(
            "\\begin{align*}\na \\\\[2pt] \\(b\\)\n\\end{align*}",
            ["a \\\\[2pt] \\(b\\)"],
            id="env-contents-not-split",
        ),
        # org blocks
        pytest.param("#+begin_equation\ne\n#+end_equation", ["e"], id="equation-block"),
        pytest.param("#+BEGIN_EQUATION\ne\n#+END_EQUATION", ["e"], id="equation-block-upper"),
        pytest.param("#+begin_latex\ne\n#+end_latex", ["e"], id="latex-block"),
        # dollars
        pytest.param("$x$", ["x"], id="dollar-single-char"),
        pytest.param("so $a + b$, then", ["a + b"], id="dollar"),
        pytest.param("$$\\sum_i x_i$$", ["\\sum_i x_i"], id="double-dollar"),
        pytest.param("It costs $5 and $6 today", [], id="currency"),
        pytest.param("$ x$ and $x $", [], id="dollar-space-inside"),
        pytest.param("$x$y", [], id="dollar-followed-by-letter"),
        pytest.param(r"\$x\$", [], id="escaped-dollar"),
        pytest.param("$a\nb\nc$", ["a\nb\nc"], id="dollar-two-newlines"),
        pytest.param("$a\nb\nc\nd$", [], id="dollar-three-newlines"),
        # general
        pytest.param(
            "first \\(a\\), then $b$, then\n\\begin{equation}\nc\n\\end{equation}",
            ["a", "b", "c"],
            id="document-order",
        ),
        pytest.param(
            "#+begin_src sh\necho $HOME $x$\n#+end_src\n\\(y\\)",
            ["y"],
            id="ignores-src-blocks",
        ),
        pytest.param("no math here", [], id="none"),
    ],
)
def test_extract_math_snippets(text, expected):
    assert extract_math_snippets(text) == expected


@pytest.mark.parametrize(
    "text, expected",
    [
        ("#+begin_src python\nx = 1\n#+end_src\n", [("python", "x = 1")]),
        (
            "#+BEGIN_SRC emacs-lisp :results none\n(+ 1 2)\n#+END_SRC\n",
            [("emacs-lisp", "(+ 1 2)")],
        ),
        ("  #+begin_src sh\nls\n  #+end_src\n", [("sh", "ls")]),
        (
            "#+begin_src c++ :includes <iostream>\nint x;\n#+end_src\n",
            [("c++", "int x;")],
        ),
        ("#+begin_src python -n :results output\nx\n#+end_src", [("python", "x")]),
        ("#+begin_src\nbare\n#+end_src\n", [(None, "bare")]),
        ("#+begin_src   \nbare\n#+end_src\n", [(None, "bare")]),
        (
            "#+begin_src a\n1\n#+end_src\n#+begin_src b\n2\n#+end_src\n",
            [("a", "1"), ("b", "2")],
        ),
        ("text #+begin_src python\nx\n#+end_src", []),
        ("no blocks", []),
    ],
)
def test_extract_src_blocks(text, expected):
    assert extract_src_blocks(text) == expected
