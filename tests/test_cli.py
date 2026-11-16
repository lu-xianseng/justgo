# -*- coding: utf-8 -*-
"""cli：被测项目独立 pipenv 环境路由 + shell 命令"""
import os
import sys
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from just_go import cli  # noqa: E402


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
    """被测项目无 venv：用当前 Python 环境直接执行"""
    proj = _mk_project(tmp_path, with_pipfile=False)
    calls = []
    monkeypatch.setattr(cli, "_project_venv_path", lambda root: None)
    monkeypatch.setattr(cli.subprocess, "run", lambda *a, **k: calls.append((a, k)) or FakeResult())
    args = SimpleNamespace(target=str(proj), output=None, pytest_args=[])
    cli.cmd_run(args)
    pos_args, kwargs = calls[0]
    cmd = pos_args[0]
    assert cmd[0] == sys.executable
    assert "PYTHONPATH" not in kwargs["env"] or cli.FRAMEWORK_ROOT not in kwargs["env"].get("PYTHONPATH", "")


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


def test_save_registry_is_atomic(tmp_path, monkeypatch):
    """注册表先写临时文件再替换：不残留半成品，写坏时旧文件也不受影响"""
    monkeypatch.setattr(cli, "REGISTRY_DIR", str(tmp_path))
    monkeypatch.setattr(cli, "REGISTRY_FILE", str(tmp_path / "projects.json"))
    cli.save_registry({"demo": "/x"})
    assert cli.load_registry() == {"demo": "/x"}
    # 临时文件不残留在 ~/.just-go
    assert [p.name for p in tmp_path.iterdir()] == ["projects.json"]


def test_load_registry_reports_corrupted_file(tmp_path, monkeypatch, capsys):
    """注册表 JSON 损坏时给出提示，而不是静默当成“没有注册项目”"""
    broken = tmp_path / "projects.json"
    broken.write_text("{oops", encoding="utf-8")
    monkeypatch.setattr(cli, "REGISTRY_FILE", str(broken))
    assert cli.load_registry() == {}
    assert "注册表读取失败" in capsys.readouterr().out


def test_cmd_init_creates_images_dir(tmp_path, monkeypatch):
    """init 骨架要预建 images/：IMAGE_PATH 就是项目根，用户需要明确的放图位置"""
    monkeypatch.setattr(cli.shutil, "which", lambda name: None)  # 跳过 pipenv
    target = tmp_path / "proj"
    assert cli.cmd_init(SimpleNamespace(target=f"{target}[gui]")) == 0
    assert (target / "images").is_dir()
    assert (target / "pages" / "base_page.py").is_file()


def test_cmd_init_does_not_generate_config_ini(tmp_path, monkeypatch):
    """init 不生成 config.ini：常改的项都在 conftest.py，路径类的项按需自建"""
    monkeypatch.setattr(cli.shutil, "which", lambda name: None)  # 跳过 pipenv
    target = tmp_path / "proj"
    assert cli.cmd_init(SimpleNamespace(target=f"{target}[all]")) == 0
    assert not (target / "config.ini").exists()
    # conftest 里保留 config.run.* 的覆盖示例
    conftest = (target / "conftest.py").read_text(encoding="utf-8")
    assert "config.run.slow_time" in conftest


def test_cmd_init_scaffold_collects(tmp_path, monkeypatch):
    """init 生成的骨架必须能被 pytest 收集：CaseControl 要求方法名含用例文件名"""
    import subprocess

    monkeypatch.setattr(cli.shutil, "which", lambda name: None)  # 跳过 pipenv
    target = tmp_path / "proj"
    assert cli.cmd_init(SimpleNamespace(target=f"{target}[all]")) == 0

    r = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q"],
        cwd=str(target),
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONPATH": cli.FRAMEWORK_ROOT},
    )
    assert r.returncode == 0, r.stdout + r.stderr
    assert "test_login_1" in r.stdout
    assert "test_login_2" in r.stdout


def test_template_cases_do_not_share_file_name_rule():
    """模板里每个用例文件只能放同 ID 的用例，否则收集阶段 CaseError"""
    templates, _ = cli._build_templates("gui")
    for rel, content in templates.items():
        if not rel.startswith("cases/login/test_"):
            continue
        stem = os.path.splitext(os.path.basename(rel))[0]
        for line in content.splitlines():
            line = line.strip()
            if not line.startswith("def test_"):
                continue
            method = line.split("(")[0].removeprefix("def ")
            assert stem == method or stem.startswith(method + "_") or method in stem, (
                f"{rel}: 方法 {method} 与文件名 {stem} 不匹配"
            )
