import os
import sys
from typing import List
from unittest.mock import patch

import pytest
import yaml
from i3ipc import Connection
from pyfakefs.fake_filesystem import FakeFilesystem

from dormer import CommandReply, OutputReply, WorkspaceReply, run


class MockI3(Connection):
    def __init__(self) -> None:
        self.commands_run: List[str] = []

    def get_workspaces(self) -> List[WorkspaceReply]:  # type: ignore[override]
        return [
            WorkspaceReply(num=1, output="foo", focused=True, visible=True),
            WorkspaceReply(num=2, output="foo", focused=False, visible=True),
        ]

    def get_outputs(self) -> List[OutputReply]:  # type: ignore[override]
        return [OutputReply(name="foo", active=True)]

    def command(self, cmd: str) -> List[CommandReply]:  # type: ignore[override]
        self.commands_run.append(cmd)
        return [CommandReply(success=True, error=None)]


path = "/home/bar/.config/dormer/2c26b46b68ffc68ff99b453c1d30413413422d706483bfa0f98a5e886266e7ae.yaml"  # noqa: E501


def test_no_args(capsys: pytest.CaptureFixture):
    with patch.object(sys, "argv", ["dormer"]):
        with pytest.raises(SystemExit):
            run(MockI3())

    res = capsys.readouterr()
    assert (
        res.err.find("error: the following arguments are required: command") != -1
    ), res.err
    assert res.out == ""


def test_save(capsys: pytest.CaptureFixture, fs: FakeFilesystem):
    with patch.object(sys, "argv", ["dormer", "save"]):
        with patch.dict(os.environ, {"HOME": "/home/bar"}, clear=True):
            run(MockI3())

    config_file = fs.get_object(path)
    config = yaml.safe_load(config_file.contents)
    assert config == {"outputs": ["foo"], "workspaces": {1: "foo", 2: "foo"}}

    res = capsys.readouterr()
    assert res.err == ""
    assert res.out == f"Saved to {path}\n"


def test_load_nothing(capsys: pytest.CaptureFixture, fs: FakeFilesystem):
    with patch.object(sys, "argv", ["dormer", "load"]):
        with patch.dict(os.environ, {"HOME": "/home/bar"}, clear=True):
            with pytest.raises(SystemExit):
                run(MockI3())

    res = capsys.readouterr()
    assert res.err == ""
    assert res.out == "No existing config for foo\n"


def test_load_identical(capsys: pytest.CaptureFixture, fs: FakeFilesystem):
    fs.create_file(
        path, contents=yaml.dump({"outputs": ["foo"], "workspaces": {1: "foo"}})
    )

    with patch.object(sys, "argv", ["dormer", "load"]):
        with patch.dict(os.environ, {"HOME": "/home/bar"}, clear=True):
            run(MockI3())

    res = capsys.readouterr()
    assert res.err == ""
    assert res.out == "No changes necessary\n"


def test_load_different(capsys: pytest.CaptureFixture, fs: FakeFilesystem):
    fs.create_file(
        path, contents=yaml.dump({"outputs": ["foo"], "workspaces": {1: "bar"}})
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
        "move workspace to output bar",
        "workspace 2",
        "workspace 1",
    ]


def test_load_failure(capsys: pytest.CaptureFixture, fs: FakeFilesystem):
    fs.create_file(
        path, contents=yaml.dump({"outputs": ["foo"], "workspaces": {1: "bar"}})
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
