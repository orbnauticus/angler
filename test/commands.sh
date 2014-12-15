#!/bin/sh

rm angler.manifest 2>/dev/null || true
export PYTHONPATH=.
bin/angler-setup
bin/angler-add package://bash install
bin/angler-add path:///home/user/bin/script file
bin/angler-add exec://run-script "bash bin/script"
bin/angler-add path:///home/user/.bashrc file --before exec://run-script
bin/angler-order package://bash exec://run-script
bin/angler-run

rm angler.manifest
