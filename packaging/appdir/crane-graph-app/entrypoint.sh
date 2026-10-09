#! /bin/bash

exec "{{ python-executable }}" -m crane_graph.gui "$@"
