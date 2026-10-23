"""T047: the consumer inventory loader, compliance mapping and `corpus consumers`."""

from __future__ import annotations

import json
from collections import Counter

import pytest
import yaml
from typer.testing import CliRunner

from mneme.corpus import cli as ccli
from mneme.corpus import consumers as cons

CLI = CliRunner()


def _entry(**over):
    e = {"name": "x", "repo": "r", "entry": "a.py:1", "kinds": ["grounding"],
         "mode": "independent"}
    e.update(over)
    return e


def _write(tmp_path, entries, schema=1):
    p = tmp_path / "consumers.yaml"
    p.write_text(yaml.safe_dump({"schema": schema, "consumers": entries}))
    return p


def test_shipped_file_parses_with_52_entries_and_split():
    rows = cons.load()
    assert len(rows) == 52
    assert Counter(c.mode for c in rows) == {"independent": 49, "palace": 2, "partial": 1}


def test_valid_optional_fields_round_trip(tmp_path):
    p = _write(tmp_path, [_entry(reads=["docs/party.md"], kinds_toc=["party"], other="o",
                                 note="n", issue=None, via="v")])
    (c,) = cons.load(p)
    assert c.reads == ("docs/party.md",) and c.kinds_toc == ("party",) and c.issue is None


@pytest.mark.parametrize("over, needle", [
    ({"mode": "bogus"}, "mode"),
    ({"kinds": ["nope"]}, "kinds"),
    ({"surprise": 1}, "surprise: unknown field"),
    ({"reads": "docs/party.md"}, "reads"),
    ({"kinds_toc": ["nope"]}, "kinds_toc"),
    ({"issue": 5}, "issue"),
])
def test_validation_table(tmp_path, over, needle):
    with pytest.raises(cons.ConsumersError) as ei:
        cons.load(_write(tmp_path, [_entry(**over)]))
    assert any(needle in p and "(x)" in p
               for p in ei.value.problems)


@pytest.mark.parametrize("field", ["name", "repo", "entry", "kinds", "mode"])
def test_missing_required_field(tmp_path, field):
    e = _entry()
    del e[field]
    with pytest.raises(cons.ConsumersError) as ei:
        cons.load(_write(tmp_path, [e]))
    assert any(f".{field}: required" in p for p in ei.value.problems)


def test_bad_schema(tmp_path):
    with pytest.raises(cons.ConsumersError, match="schema"):
        cons.load(_write(tmp_path, [_entry()], schema=2))


@pytest.mark.parametrize("mode, expected", [
    ("palace", "compliant"), ("toc", "compliant"),
    ("partial", "partial"), ("independent", "non-compliant"),
])
def test_compliance_mapping(mode, expected):
    c = cons.Consumer("n", "r", "e", ("grounding",), mode)
    assert cons.compliance(c) == expected


def test_noncompliant_filters():
    rows = [cons.Consumer("a", "r", "e", ("party",), m)
            for m in ("palace", "toc", "partial", "independent")]
    assert [c.mode for c in cons.noncompliant(rows)] == ["partial", "independent"]


def test_cli_lists_and_filters(tmp_path, monkeypatch):
    p = _write(tmp_path, [_entry(name="a", mode="palace"), _entry(name="b", mode="partial"),
                          _entry(name="c", mode="independent")])
    monkeypatch.setattr(cons, "DEFAULT", p)
    res = CLI.invoke(ccli.app, ["consumers", "--json"])
    assert res.exit_code == 0
    assert [r["name"] for r in json.loads(res.output)] == ["a", "b", "c"]
    res = CLI.invoke(ccli.app, ["consumers", "--noncompliant", "--json"])
    rows = json.loads(res.output)
    assert [(r["name"], r["compliance"]) for r in rows] == [
        ("b", "partial"), ("c", "non-compliant")]
    res = CLI.invoke(ccli.app, ["consumers", "--noncompliant"])
    assert res.exit_code == 0 and "a [" not in res.output and "c [" in res.output


def test_cli_exit_2_when_invalid(tmp_path, monkeypatch):
    monkeypatch.setattr(cons, "DEFAULT", _write(tmp_path, [_entry(mode="bogus")]))
    res = CLI.invoke(ccli.app, ["consumers"])
    assert res.exit_code == 2


def test_empty_kinds_is_valid(tmp_path):
    (c,) = cons.load(_write(tmp_path, [_entry(kinds=[])]))
    assert c.kinds == ()
