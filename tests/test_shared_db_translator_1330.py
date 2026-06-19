"""Unit-Tests für den SQL-Translator + Schema-Ableitung des PG-Kompat-Layers (#1330).

Rein Python, ohne psycopg/Datenbank — verifiziert die kritische ``?``→``%s`` /
``%``→``%%`` Quote-aware-Übersetzung, auf der alle Modul-Ports aufsetzen.
"""
from shared.db import schema_for, translate_sql


def test_simple_placeholders():
    assert translate_sql("SELECT ?") == "SELECT %s"
    assert translate_sql("WHERE a=? AND b=?") == "WHERE a=%s AND b=%s"
    assert translate_sql("VALUES(?,?,?)") == "VALUES(%s,%s,%s)"


def test_literal_percent_is_doubled():
    assert translate_sql("WHERE name LIKE '%foo%'") == "WHERE name LIKE '%%foo%%'"
    assert translate_sql("SELECT '50%'") == "SELECT '50%%'"


def test_mixed_like_and_param():
    assert (translate_sql("WHERE name LIKE ? AND x LIKE '%y%'")
            == "WHERE name LIKE %s AND x LIKE '%%y%%'")


def test_question_mark_inside_string_preserved():
    assert translate_sql("SELECT '?' , ?") == "SELECT '?' , %s"
    assert translate_sql("WHERE s='who?' AND a=?") == "WHERE s='who?' AND a=%s"


def test_escaped_single_quote_inside_string():
    assert translate_sql("WHERE s='can''t' AND a=?") == "WHERE s='can''t' AND a=%s"
    # ? nach escaptem Quote weiterhin als Platzhalter
    assert translate_sql("SELECT 'a''b', ?") == "SELECT 'a''b', %s"


def test_no_placeholders_unchanged_except_percent():
    assert translate_sql("SELECT 1") == "SELECT 1"
    assert translate_sql("CREATE TABLE t(id BIGINT)") == "CREATE TABLE t(id BIGINT)"


def test_percent_inside_and_outside_string_both_doubled():
    assert translate_sql("a % b LIKE '%z%'") == "a %% b LIKE '%%z%%'"


def test_schema_for():
    assert schema_for("data/db/soc.sqlite") == "soc"
    assert schema_for("data/db/ai_act.sqlite") == "ai_act"
    assert schema_for("soc.sqlite") == "soc"
    assert schema_for("data/db/pytest_soc_1254.sqlite") == "pytest_soc_1254"
    assert schema_for("data/db/users.sqlite") == "users"
    # Sanitisierung
    assert schema_for("data/db/Weird-Name.sqlite") == "weird_name"


def test_schema_for_leading_digit():
    assert schema_for("123abc.sqlite").startswith("s_")
