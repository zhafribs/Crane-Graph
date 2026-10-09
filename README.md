# Crane Graph

A dynamic crane **working-range diagram**: boom, jib and crane position drawn on an
XY axis, with the tip envelope and the derived readouts updating as you drag.

Drag the boom tip on the graph to set the boom angle; drag the crane marker to move
the crane on the axis. The diagram, the inputs and the readouts all stay in step.

## Requirements

- Python 3.9 or newer
- The packages in `requirements.txt` — PyQt5 to run it, `python-appimage` only to
  build the AppImage

## Setup

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

## Run

```bash
.venv/bin/python run.py
```

## Build the AppImage

```bash
./build-appimage.sh
```

The result lands in `dist/`. Note that the script expects the icon to **already
exist** at `packaging/appdir/crane-graph-app/crane-graph-app.png` — see below.

## Layout

```
run.py                          development entry point
crane_graph/
    geometry.py                 the maths: pure Python, no Qt, unit-testable
    gui.py                      the PyQt5 window, controls and interactive canvas
    theme.py                    the Qt stylesheet
packaging/
    appdir/crane-graph-app/     the AppDir skeleton, including the icon
build-appimage.sh               builds the AppImage
```

`geometry.py` deliberately imports nothing from Qt. Everything the diagram computes
can be exercised from a plain interpreter, which is where its tests belong:

```bash
python3 -c "from crane_graph import geometry as g; print(g.readouts(dict(g.DEFAULT_STATE)))"
```

## About the icon, and a lost file

This project's source tree was lost once — the working copy was left with only an
empty `__pycache__` — and everything here was recovered from `dist/crane-graph-V1.0.0.appimage`,
which still carried the program.

An AppImage bundles what the program *runs*. That recovered all four modules, and
the icon. It did **not** recover `packaging/make_icon.py`, because a build script is
never executed from inside the built image.

So:

- The icon is checked in and is **source** now, not build output. It cannot be
  regenerated, and a clone without it cannot build.
- `tests/` was not recovered either; its `__pycache__` was empty. Any tests worth
  having would have to be written again.
- `dist/` is ignored, but the AppImage in it is worth keeping somewhere outside the
  repository's history as a last-resort backup of a release.

## Related

The same diagram also ships as a **Graph tab** inside an Android lifting-plan app,
where `geometry.py` was ported to Kotlin and is covered by unit tests pinned to this
module's own output. The two agree: at 45° on a 30 m boom both put the tip at
(21.2132, 21.2132).
