import hashlib
from argparse import ArgumentParser
from dataclasses import dataclass
from pathlib import Path
from sys import exit
from typing import Dict, List, Optional, cast

import yaml
from i3ipc import Connection
from typing_extensions import TypedDict


@dataclass
class OutputReply:
    name: str


@dataclass
class CommandReply:
    success: bool
    error: Optional[str]


@dataclass
class WorkspaceReply:
    num: int
    output: str
    focused: bool
    visible: bool


def check_command(i3: Connection, command: str):
    rets = cast(List[CommandReply], i3.command(command))
    for ret in rets:
        if ret.success:
            continue
        print(f"Failed to execute '{command}': {ret.error}")
        exit(-1)


class Config(TypedDict):
    outputs: List[str]
    workspaces: Dict[int, str]


def run(i3: Connection):
    workspaces = cast(List[WorkspaceReply], i3.get_workspaces())
    outputs = cast(List[OutputReply], i3.get_outputs())

    parser = ArgumentParser()
    subparsers = parser.add_subparsers(title="commands", dest="command", required=True)
    subparsers.add_parser("save")
    subparsers.add_parser("load")

    ns = parser.parse_args()

    output_names = sorted(
        [output.name for output in outputs if not output.name.startswith("xroot")]
    )
    hasher = hashlib.sha256()
    hasher.update(";".join(output_names).encode("utf-8"))
    key = hasher.hexdigest()
    path = Path(f"~/.config/dormer/{key}.yaml").expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)

    if ns.command == "save":
        data: Config = {"outputs": output_names, "workspaces": {}}

        for workspace in workspaces:
            data["workspaces"][workspace.num] = workspace.output

        with path.open("w") as f:
            yaml.safe_dump(data, f)

        print(f"Saved to {path}")

    elif ns.command == "load":
        if not path.exists():
            print(f"No existing config for {','.join(output_names)}")
            exit(-1)
        with path.open() as f:
            config = cast(Config, yaml.safe_load(f))

        existing_workspaces = dict(
            [(workspace.num, workspace.output) for workspace in workspaces]
        )
        focused_workspace = [
            workspace.num for workspace in workspaces if workspace.focused
        ][0]
        visible_workspaces = [
            workspace.num for workspace in workspaces if workspace.visible
        ]
        changes = False
        for name, output in config["workspaces"].items():
            if existing_workspaces[name] != output:
                changes = True
                for command in [
                    f"workspace {name}",
                    f"move workspace to output {output}",
                ]:
                    check_command(i3, command)

        if changes:
            for visible_workspace in visible_workspaces:
                if visible_workspace != focused_workspace:
                    check_command(i3, f"workspace {visible_workspace}")
            check_command(i3, f"workspace {focused_workspace}")
            print("Workspaces reset")
        else:
            print("No changes necessary")

    else:  # pragma: no cover - effectively impossible
        print(f"Unknown command: {ns.subparser}")
        exit(-1)


def main():  # pragma: no cover - can't seem to mock actual I3
    i3 = Connection()
    run(i3)


if __name__ == "__main__":  # pragma: no cover - can't seem to mock actual I3
    main()
