"""Tests for the fail-closed sanitized Xiaohongshu import boundary."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from mom_index.collectors import SourceResult
from mom_index.collectors.xhs_import import import_xhs_file
from mom_index.config import SECTOR_KEYS


def _record(
    *,
    post_id: str = "xhs_1",
    title: str = "纳指小白求带",
    content: str = "第一次买美股ETF，现在入手会不会太高？",
    url: str = "https://www.xiaohongshu.com/explore/abc123",
    sector: str = "nasdaq",
    published_at: str | None = "2026-07-30T10:00:00+08:00",
    collected_at: str = "2026-07-30T12:00:00+00:00",
    extra: dict | None = None,
) -> dict:
    record = {
        "id": post_id,
        "title": title,
        "content": content,
        "url": url,
        "sector": sector,
        "published_at": published_at,
        "collected_at": collected_at,
    }
    if extra:
        record.update(extra)
    return record


def _write_json(tmp_path: Path, name: str, data) -> Path:
    path = tmp_path / name
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return path


def _write_jsonl(tmp_path: Path, name: str, records: list) -> Path:
    path = tmp_path / name
    path.write_text(
        "\n".join(json.dumps(item, ensure_ascii=False) for item in records),
        encoding="utf-8",
    )
    return path


class TestSanitizedImport:
    """Sanitized JSON and JSONL import successfully with imported mode."""

    def test_json_array_imports(self, tmp_path):
        path = _write_json(
            tmp_path,
            "in.json",
            [_record(post_id="xhs_a"), _record(post_id="xhs_b", sector="gold")],
        )
        result = import_xhs_file(path)
        assert isinstance(result, SourceResult)
        assert result.source_id == "xiaohongshu"
        assert result.mode == "imported"
        assert result.collected_at is not None
        assert result.post_count == 2
        assert len(result.posts["nasdaq"]) == 1
        assert len(result.posts["gold"]) == 1
        post = result.posts["nasdaq"][0]
        assert post["platform"] == "xiaohongshu"
        assert post["id"] == "xhs_a"
        assert post["published_at"] == "2026-07-30T10:00:00+08:00"

    def test_json_sector_map_imports(self, tmp_path):
        data = {
            "nasdaq": [_record(post_id="n1", sector="nasdaq")],
            "gold": [_record(post_id="g1", sector="gold")],
        }
        path = _write_json(tmp_path, "sector.json", data)
        result = import_xhs_file(path)
        assert result.mode == "imported"
        assert result.post_count == 2
        assert result.posts["nasdaq"][0]["id"] == "n1"
        assert result.posts["gold"][0]["id"] == "g1"

    def test_jsonl_imports(self, tmp_path):
        path = _write_jsonl(
            tmp_path,
            "in.jsonl",
            [_record(post_id="l1"), _record(post_id="l2", sector="semiconductor")],
        )
        result = import_xhs_file(path)
        assert result.mode == "imported"
        assert result.post_count == 2
        assert result.posts["semiconductor"][0]["id"] == "l2"

    def test_jsonl_skips_blank_lines(self, tmp_path):
        path = tmp_path / "blank.jsonl"
        path.write_text(
            json.dumps(_record(post_id="x1"), ensure_ascii=False)
            + "\n\n"
            + json.dumps(_record(post_id="x2"), ensure_ascii=False)
            + "\n",
            encoding="utf-8",
        )
        result = import_xhs_file(path)
        assert result.mode == "imported"
        assert result.post_count == 2

    def test_published_at_null_accepted(self, tmp_path):
        path = _write_json(
            tmp_path, "null.json", [_record(post_id="p1", published_at=None)]
        )
        result = import_xhs_file(path)
        assert result.mode == "imported"
        assert result.posts["nasdaq"][0]["published_at"] is None

    def test_all_four_sectors_accepted(self, tmp_path):
        records = [
            _record(post_id=f"r_{sector}", sector=sector)
            for sector in SECTOR_KEYS
        ]
        path = _write_json(tmp_path, "all.json", records)
        result = import_xhs_file(path)
        assert result.mode == "imported"
        assert result.post_count == 4
        for sector in SECTOR_KEYS:
            assert len(result.posts[sector]) == 1


class TestFailClosed:
    """Identity and credential fields abort the entire import."""

    @pytest.mark.parametrize(
        "field",
        [
            "cookie",
            "cookies",
            "author",
            "author_id",
            "followers",
            "follower_count",
            "session",
            "session_token",
            "access_token",
            "api_key",
            "authorization",
            "password",
            "secret",
            "token",
            "browser_profile",
            "nickname",
            "display_name",
        ],
    )
    def test_banned_identity_field_aborts(self, tmp_path, field):
        records = [
            _record(post_id="good"),
            _record(post_id="bad", extra={field: "leak"}),
        ]
        path = _write_json(tmp_path, "banned.json", records)
        result = import_xhs_file(path)
        assert result.mode == "unavailable"
        assert result.collected_at is None
        assert result.post_count == 0
        assert any("banned identity/credential" in error for error in result.errors)

    def test_banned_field_aborts_even_if_first_record_valid(self, tmp_path):
        path = _write_json(
            tmp_path,
            "mixed.json",
            [_record(post_id="ok"), _record(post_id="bad", extra={"token": "abc"})],
        )
        result = import_xhs_file(path)
        assert result.mode == "unavailable"
        # Fail closed must not leak the otherwise-valid first record.
        assert result.post_count == 0

    def test_secret_like_value_aborts(self, tmp_path):
        path = _write_json(
            tmp_path,
            "secret.json",
            [_record(post_id="s1", content="Authorization: Bearer abc123def456")],
        )
        result = import_xhs_file(path)
        assert result.mode == "unavailable"
        assert result.post_count == 0
        assert any("secret-like" in error for error in result.errors)

    def test_secret_token_pattern_aborts(self, tmp_path):
        path = _write_json(
            tmp_path,
            "sk.json",
            [_record(post_id="s2", title="leaked sk-" + "a" * 24)],
        )
        result = import_xhs_file(path)
        assert result.mode == "unavailable"
        assert result.post_count == 0

    def test_secret_in_otherwise_invalid_record_still_aborts(self, tmp_path):
        path = _write_json(
            tmp_path,
            "invalid-secret.json",
            [
                _record(post_id="good"),
                _record(
                    post_id="bad",
                    url="https://evil.example.com/?token=abc123def456",
                ),
            ],
        )
        result = import_xhs_file(path)
        assert result.mode == "unavailable"
        assert result.post_count == 0
        assert any("secret-like" in error for error in result.errors)

    def test_nested_banned_field_still_aborts(self, tmp_path):
        path = _write_json(
            tmp_path,
            "nested-private.json",
            [
                _record(post_id="good"),
                _record(
                    post_id="bad",
                    extra={"metadata": {"author": "private identity"}},
                ),
            ],
        )
        result = import_xhs_file(path)
        assert result.mode == "unavailable"
        assert result.post_count == 0
        assert any("banned identity/credential" in error for error in result.errors)

    def test_secret_scalar_record_still_aborts(self, tmp_path):
        path = _write_json(
            tmp_path,
            "scalar-secret.json",
            [_record(post_id="good"), "token=abc123def456"],
        )
        result = import_xhs_file(path)
        assert result.mode == "unavailable"
        assert result.post_count == 0
        assert any("secret-like" in error for error in result.errors)


class TestZeroValidRecords:
    """Zero valid records returns unavailable."""

    def test_empty_json_array(self, tmp_path):
        path = _write_json(tmp_path, "empty.json", [])
        result = import_xhs_file(path)
        assert result.mode == "unavailable"
        assert result.post_count == 0
        assert any("zero" in error.lower() for error in result.errors)

    def test_empty_jsonl(self, tmp_path):
        path = tmp_path / "empty.jsonl"
        path.write_text("\n  \n", encoding="utf-8")
        result = import_xhs_file(path)
        assert result.mode == "unavailable"

    def test_all_records_invalid(self, tmp_path):
        records = [
            _record(post_id="bad1", url="http://evil.example.com/x"),
            _record(post_id="bad2", sector="bonds"),
        ]
        path = _write_json(tmp_path, "all_bad.json", records)
        result = import_xhs_file(path)
        assert result.mode == "unavailable"
        assert result.post_count == 0
        assert len(result.errors) == 2


class TestSchemaRejections:
    """Invalid individual records are rejected explicitly; valid ones survive."""

    def test_bad_url_rejected_others_kept(self, tmp_path):
        records = [
            _record(post_id="ok1"),
            _record(post_id="bad", url="https://evil.example.com/x"),
            _record(post_id="ok2", sector="gold"),
        ]
        path = _write_json(tmp_path, "mixed.json", records)
        result = import_xhs_file(path)
        assert result.mode == "imported"
        assert result.post_count == 2
        assert any("url" in error for error in result.errors)

    def test_missing_required_field_rejected(self, tmp_path):
        record = _record()
        del record["title"]
        path = _write_json(tmp_path, "missing.json", [record])
        result = import_xhs_file(path)
        assert result.mode == "unavailable"
        assert any("missing required" in error for error in result.errors)

    def test_invalid_sector_rejected(self, tmp_path):
        path = _write_json(
            tmp_path,
            "badsector.json",
            [_record(post_id="s1", sector="bonds")],
        )
        result = import_xhs_file(path)
        assert result.mode == "unavailable"
        assert any("sector" in error for error in result.errors)

    def test_non_xhs_url_rejected(self, tmp_path):
        path = _write_json(
            tmp_path,
            "http.json",
            [_record(post_id="h1", url="http://www.xiaohongshu.com/x")],
        )
        result = import_xhs_file(path)
        assert result.mode == "unavailable"
        assert any("url" in error for error in result.errors)

    def test_url_with_whitespace_rejected(self, tmp_path):
        path = _write_json(
            tmp_path,
            "whitespace-url.json",
            [
                _record(
                    post_id="h2",
                    url="https://www.xiaohongshu.com/explore/abc 123",
                )
            ],
        )
        result = import_xhs_file(path)
        assert result.mode == "unavailable"
        assert any("url" in error for error in result.errors)

    def test_naive_timestamp_rejected(self, tmp_path):
        path = _write_json(
            tmp_path,
            "naive.json",
            [_record(post_id="t1", collected_at="2026-07-30T12:00:00")],
        )
        result = import_xhs_file(path)
        assert result.mode == "unavailable"
        assert any("timezone" in error for error in result.errors)

    def test_malformed_timestamp_rejected(self, tmp_path):
        path = _write_json(
            tmp_path,
            "bad.json",
            [_record(post_id="t2", collected_at="not-a-timestamp")],
        )
        result = import_xhs_file(path)
        assert result.mode == "unavailable"
        assert any("ISO timestamp" in error for error in result.errors)

    def test_unknown_field_rejected(self, tmp_path):
        path = _write_json(
            tmp_path,
            "unknown.json",
            [_record(post_id="u1", extra={"unrelated": "x"})],
        )
        result = import_xhs_file(path)
        assert result.mode == "unavailable"
        assert any("unknown field" in error for error in result.errors)

    @pytest.mark.parametrize(
        ("field", "value"),
        [
            ("id", 123),
            ("title", ["not", "a", "string"]),
            ("content", {"text": "not a string"}),
            ("url", 123),
            ("sector", True),
        ],
    )
    def test_non_string_fields_rejected(self, tmp_path, field, value):
        record = _record()
        record[field] = value
        path = _write_json(tmp_path, "wrong-type.json", [record])
        result = import_xhs_file(path)
        assert result.mode == "unavailable"
        assert result.post_count == 0
        assert any(f".{field} must be a string" in error for error in result.errors)

    def test_oversized_title_rejected(self, tmp_path):
        path = _write_json(
            tmp_path,
            "long.json",
            [_record(post_id="l1", title="x" * 301)],
        )
        result = import_xhs_file(path)
        assert result.mode == "unavailable"
        assert any("title" in error for error in result.errors)

    def test_empty_title_rejected(self, tmp_path):
        path = _write_json(
            tmp_path,
            "blank.json",
            [_record(post_id="e1", title="")],
        )
        result = import_xhs_file(path)
        assert result.mode == "unavailable"

    def test_non_object_record_rejected(self, tmp_path):
        path = _write_json(
            tmp_path,
            "nonobj.json",
            ["not a record", _record(post_id="ok1")],
        )
        result = import_xhs_file(path)
        assert result.mode == "imported"
        assert result.post_count == 1
        assert any("must be a JSON object" in error for error in result.errors)

    def test_sector_map_mismatch_rejected(self, tmp_path):
        data = {
            "nasdaq": [_record(post_id="m1", sector="gold")],
        }
        path = _write_json(tmp_path, "mismatch.json", data)
        result = import_xhs_file(path)
        assert result.mode == "unavailable"
        assert any("mismatched" in error for error in result.errors)

    def test_sector_map_unknown_key_rejected(self, tmp_path):
        data = {"bonds": [_record(post_id="u1", sector="bonds")]}
        path = _write_json(tmp_path, "badmap.json", data)
        result = import_xhs_file(path)
        assert result.mode == "unavailable"


class TestFileErrors:
    """Missing and unparseable files return unavailable."""

    def test_missing_file(self, tmp_path):
        missing_path = tmp_path / "does_not_exist.json"
        result = import_xhs_file(missing_path)
        assert result.mode == "unavailable"
        assert any("not found" in error for error in result.errors)
        assert all(str(missing_path) not in error for error in result.errors)

    def test_invalid_json(self, tmp_path):
        path = tmp_path / "broken.json"
        path.write_text("{not valid json", encoding="utf-8")
        result = import_xhs_file(path)
        assert result.mode == "unavailable"
        assert any("invalid JSON" in error for error in result.errors)

    def test_invalid_utf8(self, tmp_path):
        path = tmp_path / "invalid-utf8.json"
        path.write_bytes(b"\xff")
        result = import_xhs_file(path)
        assert result.mode == "unavailable"
        assert any("cannot read import file" in error for error in result.errors)
        assert all(str(path) not in error for error in result.errors)

    def test_invalid_jsonl_line(self, tmp_path):
        path = tmp_path / "broken.jsonl"
        path.write_text(
            json.dumps(_record(post_id="ok1"), ensure_ascii=False) + "\n{broken\n",
            encoding="utf-8",
        )
        result = import_xhs_file(path)
        assert result.mode == "unavailable"
        assert any("JSONL line" in error for error in result.errors)

    def test_non_array_non_map_json(self, tmp_path):
        path = _write_json(tmp_path, "scalar.json", "just a string")
        result = import_xhs_file(path)
        assert result.mode == "unavailable"
