dormer
========
[![codecov](https://codecov.io/gh/palfrey/dormer/branch/main/graph/badge.svg?token=FJUKT8PO95)](https://codecov.io/gh/palfrey/dormer)

dormer is a tool for saving/restoring [i3](https://i3wm.org/) Workspace -> Output mappings. In theory, [i3 does it for itself](https://i3wm.org/docs/userguide.html#workspace_screen) but this doesn't seem to work when plugging/unplugging screens. This is intended for setups where you've got a computer linked to multiple screens, but periodically want to unplug it from them temporarily. The canonical use-case is a laptop that's normally tethered to some screens, but that every so often you want to use it elsewhere for a bit before plugging it back in. It's intended for use together with tools like [randrctl](https://github.com/koiuo/randrctl) which stores/restores your screen resolutions.

There are two modes: "load" and "save". In "save" mode, dormer stores the current set of workspace -> screen mappings as the canonical wanted config for a given set of screen outputs. Note that we currently pay no attention to the actual monitors, and instead make the assumption that a particular set of output imports implies what they are.

In "load", dormer tries to find an existing "save" config and set the workspaces to be on the relevant monitors. If it can't find a config, it says so and quits.