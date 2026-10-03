#!/bin/bash
BACKUP_DIR="backup"
mkdir -p "$BACKUP_DIR"

for project_dir in projects/*/; do
    project_name=$(basename "$project_dir")
    manifest="$project_dir/manifest.json"
    if [ -f "$manifest" ]; then
        mkdir -p "$BACKUP_DIR/$project_name"
        cp "$manifest" "$BACKUP_DIR/$project_name/"
        echo "✔ $project_name"
    fi
done