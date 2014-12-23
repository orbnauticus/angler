#!/bin/sh

debug () { echo '**' "$@"; "$@"; }

rm angler.manifest 2>/dev/null || true
export PYTHONPATH=.
export PATH="bin:$PATH"
debug angler-setup
debug angler-add package:///bash install
debug angler-add path:///home/user/bin/script file
debug angler-add path:///home/user/bin/script?permission exact mode=0755
debug angler-add process:///run-script once command="bash bin/script"
debug angler-add path:///home/user/.bashrc file --before process:///run-script
debug angler-order package:///bash exec:///run-script
debug angler-run -n
debug angler-run -n --swap
rm angler.manifest
