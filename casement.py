import hashlib
from pathlib import Path
from i3ipc import Connection
from argparse import ArgumentParser
import yaml
from sys import exit

i3 = Connection()
workspaces = i3.get_workspaces()
outputs = i3.get_outputs()

parser = ArgumentParser()
subparsers = parser.add_subparsers(title="command", dest="subparser", required=True)
subparsers.add_parser("save")
subparsers.add_parser("load")

ns = parser.parse_args()

output_names = sorted([output.name for output in outputs if not output.name.startswith("xroot")])
hasher = hashlib.sha256()
hasher.update(";".join(output_names).encode("utf-8"))
key = hasher.hexdigest()
path = Path(f"~/.config/casement/{key}.yaml").expanduser()
path.parent.mkdir(parents=True, exist_ok=True)

def check_command(command: str):
    rets = i3.command(command)
    for ret in rets:
        if not ret.success:
            print(f"Failed to execute '{command}': {ret.error}")
            exit(-1)    

if ns.subparser == "save":
    data = {"outputs": output_names, "workspaces": {}}        

    for workspace in workspaces:
        data["workspaces"][workspace.num] = workspace.output

    print(data)

    with path.open("w") as f:
        yaml.safe_dump(data, f)

    print(f"Saved to {path}")

elif ns.subparser == "load":
    if not path.exists():
        print(f"No existing config for {','.join(output_names)}")
        exit(-1)
    with path.open() as f:
        config = yaml.safe_load(f)
    
    existing_workspaces = dict([(workspace.num, workspace.output) for workspace in workspaces])
    focused_workspace = [workspace.num for workspace in workspaces if workspace.focused][0]
    visible_workspaces = [workspace.num for workspace in workspaces if workspace.visible]
    changes = False
    for name, output in config["workspaces"].items():
        if existing_workspaces[name] != output:
            changes = True
            for command in [
                f"workspace {name}", f"move workspace to output {output}"]:
                check_command(command)

    if changes:
        for visible_workspace in visible_workspaces:
            check_command(f"workspace {visible_workspace}")
        check_command(f"workspace {focused_workspace}")
        print("Workspaces reset")
    else:
        print("No changes necessary")

else:
    print(f"Unknown command: {ns.subparser}")
    exit(-1)