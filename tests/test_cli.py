# -*- coding: utf-8 -*-
"""cli：被测项目独立 pipenv 环境路由 + shell 命令"""
import os
import sys
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cli  # noqa: E402


class FakeResult:
    def __init__(self, returncode=0, stdout="", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def _mk_project(tmp_path, with_pipfile=True):
    proj = tmp_path / "demo"
    proj.mkdir()
    if with_pipfile:
        (proj / "Pipfile").write_text("[packages]\njust-go = \"*\"\n", encoding="utf-8")
    return proj


def test_project_venv_path_ok(tmp_path, monkeypatch):
    """项目有 Pipfile 且 pipenv venv 存在时返回 venv 路径"""
    proj = _mk_project(tmp_path)
    venv = tmp_path / "venvs" / "demo"
    venv.mkdir(parents=True)
    monkeypatch.setattr(cli.shutil, "which", lambda name: "pipenv")
    monkeypatch.setattr(cli.subprocess, "run", lambda *a, **k: FakeResult(stdout=str(venv)))
    assert cli._project_venv_path(str(proj)) == str(venv)


def test_project_venv_path_no_pipfile(tmp_path, monkeypatch):
    """项目无 Pipfile 时不查询（返回 None）"""
    proj = _mk_project(tmp_path, with_pipfile=False)
    calls = []
    monkeypatch.setattr(cli.shutil, "which", lambda name: "pipenv")
    monkeypatch.setattr(
        cli.subprocess, "run", lambda *a, **k: calls.append(a) or FakeResult(stdout="x")
    )
    assert cli._project_venv_path(str(proj)) is None
    assert calls == []


def test_project_venv_path_no_venv(tmp_path, monkeypatch):
    """pipenv --venv 无结果/目录不存在时返回 None"""
    proj = _mk_project(tmp_path)
    monkeypatch.setattr(cli.shutil, "which", lambda name: "pipenv")
    monkeypatch.setattr(cli.subprocess, "run", lambda *a, **k: FakeResult(returncode=1))
    assert cli._project_venv_path(str(proj)) is None


def test_cmd_run_uses_project_venv(tmp_path, monkeypatch):
    """被测项目有 venv：用 pipenv run 执行，不注入框架源码"""
    proj = _mk_project(tmp_path)
    calls = []
    monkeypatch.setattr(cli, "_project_venv_path", lambda root: str(tmp_path / "venv"))
    monkeypatch.setattr(
        cli.shutil, "which", lambda name: "pipenv" if name == "pipenv" else None
    )
    monkeypatch.setattr(cli.subprocess, "run", lambda *a, **k: calls.append((a, k)) or FakeResult())
    args = SimpleNamespace(target=str(proj), output=None, pytest_args=[])
    cli.cmd_run(args)
    pos_args, kwargs = calls[0]
    cmd = pos_args[0]
    assert cmd[0] == "pipenv" and cmd[1] == "run" and cmd[3] == "-m" and cmd[4] == "pytest"
    assert "-p" in cmd
    assert kwargs["cwd"] == str(proj)
    # 独立环境模式：不注入框架根到 PYTHONPATH
    env = kwargs["env"]
    assert env["JUSTGO_PROJECT_ROOT"] == str(proj)
    assert env["JUSTGO_PROJECT_NAME"] == "demo"
    assert "PYTHONPATH" not in env or cli.FRAMEWORK_ROOT not in env["PYTHONPATH"]


def test_cmd_run_fallback_to_framework(tmp_path, monkeypatch):
    """被测项目无 venv：回退框架环境（sys.executable + 注入框架根）"""
    proj = _mk_project(tmp_path, with_pipfile=False)
    calls = []
    monkeypatch.setattr(cli, "_project_venv_path", lambda root: None)
    monkeypatch.setattr(cli.subprocess, "run", lambda *a, **k: calls.append((a, k)) or FakeResult())
    args = SimpleNamespace(target=str(proj), output=None, pytest_args=[])
    cli.cmd_run(args)
    pos_args, kwargs = calls[0]
    cmd = pos_args[0]
    assert cmd[0] == sys.executable
    env = kwargs["env"]
    assert cli.FRAMEWORK_ROOT in env["PYTHONPATH"].split(os.pathsep)


def test_cmd_shell_auto_creates_env(tmp_path, monkeypatch):
    """shell：旧项目自动生成 Pipfile、创建环境后进入 shell"""
    proj = _mk_project(tmp_path, with_pipfile=False)
    calls = []
    monkeypatch.setattr(cli, "_project_venv_path", lambda root: None)
    monkeypatch.setattr(
        cli.shutil, "which", lambda name: "pipenv" if name == "pipenv" else None
    )
    monkeypatch.setattr(cli.subprocess, "call", lambda *a, **k: calls.append(a[0]) or 0)
    args = SimpleNamespace(target=str(proj))
    assert cli.cmd_shell(args) == 0
    assert (proj / "Pipfile").exists()
    assert "just-go" in (proj / "Pipfile").read_text(encoding="utf-8")
    assert calls == [["pipenv", "install", "--skip-lock"], ["pipenv", "shell"]]
    assert "shell" in calls[-1]


def test_cmd_shell_existing_env_skips_install(tmp_path, monkeypatch):
    """shell：项目已有 venv 时不重复安装，直接进入"""
    proj = _mk_project(tmp_path)
    calls = []
    monkeypatch.setattr(cli, "_project_venv_path", lambda root: str(tmp_path / "venv"))
    monkeypatch.setattr(
        cli.shutil, "which", lambda name: "pipenv" if name == "pipenv" else None
    )
    monkeypatch.setattr(cli.subprocess, "call", lambda *a, **k: calls.append(a[0]) or 0)
    args = SimpleNamespace(target=str(proj))
    cli.cmd_shell(args)
    assert calls == [["pipenv", "shell"]]
