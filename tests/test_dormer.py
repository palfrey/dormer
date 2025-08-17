import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, List
from unittest.mock import patch

import pytest
import yaml
from i3ipc import Connection
from pyfakefs.fake_filesystem import FakeFilesystem
from pyfakefs.fake_filesystem_unittest import Pause

from dormer import CommandReply, OutputReply, WorkspaceReply, run


class MockI3(Connection):
    def __init__(self) -> None:
        self.commands_run: List[str] = []

    def get_workspaces(self) -> List[WorkspaceReply]:  # type: ignore[override]
        return [
            WorkspaceReply(num=1, output="eDP-1", focused=True, visible=True),
            WorkspaceReply(num=2, output="DP-1", focused=False, visible=True),
        ]

    def get_outputs(self) -> List[OutputReply]:  # type: ignore[override]
        return [OutputReply(name="eDP-1", active=True)]

    def command(self, cmd: str) -> List[CommandReply]:  # type: ignore[override]
        self.commands_run.append(cmd)
        return [CommandReply(success=True, error=None)]


path = "/home/bar/.config/dormer/5833e7fabae0829a6c3a810549de97a2e8eae776e4452d2e42b5c1e335db42ab.yaml"  # noqa: E501


def mock_xrandr(monkeypatch: pytest.MonkeyPatch, fs: FakeFilesystem):
    def mock_run(*args: str, **kwargs: Any):
        if args == (["xrandr", "-q", "--verbose"],):
            with Pause(fs):
                with Path(__file__).parent.joinpath("xrandr.test_output").open(
                    "rb"
                ) as f:

                    @dataclass
                    class MockRun:
                        stdout: bytes
                        stderr: bytes

                    return MockRun(stdout=f.read(), stderr=b"")
        else:
            raise Exception((args, kwargs))

    monkeypatch.setattr(subprocess, "run", mock_run)


def test_no_args(capsys: pytest.CaptureFixture):
    with patch.object(sys, "argv", ["dormer"]):
        with pytest.raises(SystemExit):
            run(MockI3())

    res = capsys.readouterr()
    assert (
        res.err.find("error: the following arguments are required: command") != -1
    ), res.err
    assert res.out == ""


def test_save(
    capsys: pytest.CaptureFixture, fs: FakeFilesystem, monkeypatch: pytest.MonkeyPatch
):
    mock_xrandr(monkeypatch, fs)
    with patch.object(sys, "argv", ["dormer", "save"]):
        with patch.dict(os.environ, {"HOME": "/home/bar"}, clear=True):
            run(MockI3())

    config_file = fs.get_object(path)
    assert config_file.contents is not None
    config = yaml.safe_load(config_file.contents)
    assert config == {
        "edids": [
            "00ffffffffffff000459982401010101",
            "00ffffffffffff000469982401010101",
            "00ffffffffffff004d10d01400000000",
        ],
        "workspaces": {1: 2, 2: 1},
    }

    res = capsys.readouterr()
    assert res.err == ""
    assert res.out == f"Saved to {path}\n"


def test_load_nothing(
    capsys: pytest.CaptureFixture, fs: FakeFilesystem, monkeypatch: pytest.MonkeyPatch
):
    mock_xrandr(monkeypatch, fs)
    with patch.object(sys, "argv", ["dormer", "load"]):
        with patch.dict(os.environ, {"HOME": "/home/bar"}, clear=True):
            with pytest.raises(SystemExit):
                run(MockI3())

    res = capsys.readouterr()
    assert res.err == ""
    assert (
        res.out
        == "No existing config for 00ffffffffffff000459982401010101,00ffffffffffff000469982401010101,00ffffffffffff004d10d01400000000\n"  # noqa: E501
    )


def test_load_identical(
    capsys: pytest.CaptureFixture, fs: FakeFilesystem, monkeypatch: pytest.MonkeyPatch
):
    mock_xrandr(monkeypatch, fs)
    fs.create_file(
        path,
        contents=yaml.dump(
            {"edids": ["00ffffffffffff004d10d01400000000"], "workspaces": {1: 0}}
        ),
    )

    with patch.object(sys, "argv", ["dormer", "load"]):
        with patch.dict(os.environ, {"HOME": "/home/bar"}, clear=True):
            run(MockI3())

    res = capsys.readouterr()
    assert res.err == ""
    assert res.out == "No changes necessary\n"


def test_load_different(
    capsys: pytest.CaptureFixture, fs: FakeFilesystem, monkeypatch: pytest.MonkeyPatch
):
    mock_xrandr(monkeypatch, fs)
    fs.create_file(
        path,
        contents=yaml.dump(
            {"edids": ["00ffffffffffff000469982401010101"], "workspaces": {1: 0}}
        ),
    )

    mock_i3 = MockI3()
    with patch.object(sys, "argv", ["dormer", "load"]):
        with patch.dict(os.environ, {"HOME": "/home/bar"}, clear=True):
            run(mock_i3)

    res = capsys.readouterr()
    assert res.err == ""
    assert res.out == "Workspaces reset\n"

    assert mock_i3.commands_run == [
        "workspace 1",
        "move workspace to output DP-1",
        "workspace 2",
        "workspace 1",
    ]


def test_load_failure(
    capsys: pytest.CaptureFixture, fs: FakeFilesystem, monkeypatch: pytest.MonkeyPatch
):
    mock_xrandr(monkeypatch, fs)
    fs.create_file(
        path,
        contents=yaml.dump(
            {"edids": ["00ffffffffffff000469982401010101"], "workspaces": {1: 0}}
        ),
    )

    class FailingMockI3(MockI3):
        def command(self, cmd: str) -> List[CommandReply]:  # type: ignore[override]
            super().command(cmd)
            return [CommandReply(success=False, error="some error")]

    mock_i3 = FailingMockI3()
    with patch.object(sys, "argv", ["dormer", "load"]):
        with patch.dict(os.environ, {"HOME": "/home/bar"}, clear=True):
            with pytest.raises(SystemExit):
                run(mock_i3)

    res = capsys.readouterr()
    assert res.err == ""
    assert res.out == "Failed to execute 'workspace 1': some error\n"

    assert mock_i3.commands_run == ["workspace 1"]
