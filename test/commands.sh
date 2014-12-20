#!/bin/sh

debug () { echo '**' "$@"; "$@"; }

rm angler.manifest 2>/dev/null || true
export PYTHONPATH=.
export PATH="bin:$PATH"
debug angler-setup
debug angler-add package://bash install
debug angler-add path:///home/user/bin/script file
debug angler-add path:///home/user/bin/script?permission 0755
debug angler-add exec://run-script "bash bin/script"
debug angler-add path:///home/user/.bashrc file --before exec://run-script
debug angler-order package://bash exec://run-script
debug angler-run
debug angler-run --swap
rm angler.manifest
