import hashlib
from argparse import ArgumentParser
from dataclasses import dataclass
from pathlib import Path
from sys import exit
from typing import Dict, List, Literal, Optional, cast

import yaml
from i3ipc import Connection
from randrctl.xrandr import Xrandr
from typing_extensions import TypedDict


@dataclass
class OutputReply:
    name: str
    active: bool


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
    edids: list[str]
    workspaces: Dict[int, int]


def hash(value: str) -> str:
    hasher = hashlib.sha256()
    hasher.update(value.encode("utf-8"))
    return hasher.hexdigest()


def run(i3: Connection):
    workspaces = cast(List[WorkspaceReply], i3.get_workspaces())
    xrandr = Xrandr(None, None)

    parser = ArgumentParser()
    subparsers = parser.add_subparsers(title="commands", dest="command", required=True)
    subparsers.add_parser("save")
    subparsers.add_parser("load")

    ns = parser.parse_args()

    raw_edids: dict[str, str] = xrandr._get_verbose_fields("EDID")
    edids = sorted(raw_edids.values())
    key = hash(";".join(edids))
    path = Path(f"~/.config/dormer/{key}.yaml").expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)

    command = cast(Literal["save"] | Literal["load"], ns.command)

    if command == "save":
        data: Config = {"edids": edids, "workspaces": {}}

        for workspace in workspaces:
            index = edids.index(raw_edids[workspace.output])
            data["workspaces"][workspace.num] = index

        with path.open("w") as f:
            yaml.safe_dump(data, f)

        print(f"Saved to {path}")

    elif command == "load":
        if not path.exists():
            print(f"No existing config for {','.join(edids)}")
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
        edid_to_workspace = dict([(v, k) for (k, v) in raw_edids.items()])
        for name, output_id in config["workspaces"].items():
            output_name = edid_to_workspace[config["edids"][output_id]]
            if (
                name not in existing_workspaces
                or existing_workspaces[name] != output_name
            ):
                changes = True
                for i3_command in [
                    f"workspace {name}",
                    f"move workspace to output {output_name}",
                ]:
                    check_command(i3, i3_command)

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
