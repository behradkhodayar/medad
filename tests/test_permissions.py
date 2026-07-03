from medad.permissions import PermissionEngine, command_matches_prefix


def test_prefix_word_boundary():
    assert command_matches_prefix("git status", "git status")
    assert command_matches_prefix("git status -sb", "git status")
    assert not command_matches_prefix("git status-foo", "git status")
    assert not command_matches_prefix("git stash", "git status")
    assert not command_matches_prefix("git status", "")


def test_execute_allowlist():
    engine = PermissionEngine(allow_commands=["git status", "ls"])
    assert engine.is_auto_approved("execute", {"command": "git status -sb"})
    assert engine.is_auto_approved("execute", {"command": "ls -la src"})
    assert not engine.is_auto_approved("execute", {"command": "rm -rf /"})
    assert not engine.is_auto_approved("execute", {"command": "git push"})


def test_edits_gated_by_default():
    engine = PermissionEngine()
    assert not engine.is_auto_approved("write_file", {"file_path": "a.py"})
    assert not engine.is_auto_approved("edit_file", {"file_path": "a.py"})
    assert PermissionEngine(auto_approve_edits=True).is_auto_approved(
        "write_file", {"file_path": "a.py"}
    )


def test_allow_always_execute_grants_two_word_prefix():
    engine = PermissionEngine()
    engine.allow_always("execute", {"command": "npm test -- --watch=false"})
    assert engine.is_auto_approved("execute", {"command": "npm test"})
    assert engine.is_auto_approved("execute", {"command": "npm test --ci"})
    assert not engine.is_auto_approved("execute", {"command": "npm install"})


def test_allow_always_tool():
    engine = PermissionEngine()
    engine.allow_always("edit_file", {})
    assert engine.is_auto_approved("edit_file", {"file_path": "x"})
    assert not engine.is_auto_approved("write_file", {"file_path": "x"})
