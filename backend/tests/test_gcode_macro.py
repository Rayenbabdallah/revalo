import math

import pytest

from revalo.engine.importers.common import ImportOptions
from revalo.engine.importers.gcode import import_gcode
from revalo.engine.importers.gcode_macro import expand
from revalo.engine.model import JobImportError


def words(program: str):
    return [w for w, _ in expand(program) if w]


def test_parameters_and_expressions():
    blocks = words("#1 = 50\n#<half> = [#1 / 2]\nG0 X[#1 + #<half> * 2] Y-#1 Z[SQRT[16]]\n")
    assert blocks[-1] == [("G", 0.0), ("X", 100.0), ("Y", -50.0), ("Z", 4.0)]


def test_operator_precedence_and_functions():
    blocks = words("G0 X[2 + 3 * 4 ** 2] Y[ATAN[1]/[1]] Z[10 MOD 3]\n")
    _, x, y, z = blocks[0]
    assert x == ("X", 50.0)
    assert y[1] == pytest.approx(45.0)
    assert z == ("Z", 1.0)


def test_repeat_loop():
    program = "#1 = 0\no100 repeat [3]\nG1 X#1\n#1 = [#1 + 10]\no100 endrepeat\nM2\n"
    xs = [w[1][1] for w in words(program) if w[0][0] == "G"]
    assert xs == [0.0, 10.0, 20.0]


def test_while_and_if_else():
    program = """
    #1 = 0
    o1 while [#1 LT 4]
      o2 if [#1 EQ 2]
        G1 X99
      o2 else
        G1 X#1
      o2 endif
      #1 = [#1 + 1]
    o1 endwhile
    """
    xs = [w[1][1] for w in words(program)]
    assert xs == [0.0, 1.0, 99.0, 3.0]


def test_subroutine_call_with_arguments():
    program = """
    o10 sub
      G1 X#1 Y#2
    o10 endsub
    o10 call [5] [7]
    o10 call [1] [2]
    """
    assert words(program) == [
        [("G", 1.0), ("X", 5.0), ("Y", 7.0)],
        [("G", 1.0), ("X", 1.0), ("Y", 2.0)],
    ]


def test_line_numbers_comments_and_spindle_selector():
    blocks = expand("N0010 G21 (metric)\nN0020 M3 $0 S1 ; torch on\nF#<_hal[plasmac.feed]>\n")
    assert blocks[0] == ([("G", 21.0)], "metric")
    assert blocks[1] == ([("M", 3.0), ("S", 1.0)], "torch on")
    assert blocks[2][0] == [("F", 0.0)]


def test_endless_loop_is_stopped():
    with pytest.raises(JobImportError):
        expand("o1 while [1]\nG1 X1\no1 endwhile\n")


def test_looped_concentric_circles_become_parts():
    # Same structure as the LinuxCNC plasma test program "metric circles".
    program = """
    #1 = 50
    #2 = 3
    #4 = 0.5
    #5 = [#1*#2*#4]
    G21
    o100 repeat [#2]
      G0 X[#5+-#4*#1] Y[#5+0]
      M3 $0 S1
      G2 I[#4*#1]
      M5 $0
      #4 = [#4+0.5]
    o100 endrepeat
    M2
    """
    job = import_gcode(program.encode(), "circles.ngc", ImportOptions())
    parts = sorted(job.sheets[0].parts, key=lambda p: p.area)
    # Three concentric circles: a disc, plus two rings once holes are paired up.
    assert len(parts) == 2
    assert parts[0].area == pytest.approx(math.pi * 25**2, rel=3e-3)
