#!/bin/sh

debug () { echo '**' "$@"; "$@"; }

rm angler.manifest 2>/dev/null || true
PYTHONPATH=. bin/angler-shell <<EOF
add package:///bash install
add path:///home/user/bin/script file
add path:///home/user/bin/script?permission exact mode=0755
add process:///run-script once command="bash bin/script"
add path:///home/user/.bashrc file --before process:///run-script
order package:///bash exec:///run-script
run
run --swap
EOF
rm angler.manifest
