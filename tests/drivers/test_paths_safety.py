"""paths.py traversal defense + layout invariants."""

from __future__ import annotations

import os

import pytest

from src.drivers import paths

BUCKET = "storybook-assets"


def test_object_path_rejects_traversal(tmp_path):
    with pytest.raises(ValueError):
        paths.object_path(str(tmp_path), BUCKET, "../../etc/passwd")


def test_meta_path_rejects_traversal(tmp_path):
    with pytest.raises(ValueError):
        paths.meta_path(str(tmp_path), BUCKET, "../../../secret.json")


def test_object_path_valid_nested(tmp_path):
    p = paths.object_path(str(tmp_path), BUCKET, "humans/id1/uuid.png")
    assert p.startswith(os.path.join(str(tmp_path), BUCKET))


def test_new_tmp_under_root(tmp_path):
    tmp = paths.new_tmp_path(str(tmp_path))
    assert tmp.startswith(os.path.join(str(tmp_path), paths.TMP_DIR))
