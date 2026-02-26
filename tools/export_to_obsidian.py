#!/usr/bin/env python3
import os
import time
import json
import shutil
from datetime import datetime

BASE = os.path.expanduser('~/research_project/brainstorm')
SESSIONS = os.path.join(BASE, 'sessions')
LOGDIR = os.path.join(BASE, 'LOGS')
EXPORTED = os.path.join(LOGDIR, 'exported.json')
EXPORT_LOG = os.path.join(LOGDIR, 'export.log')

# iCloud target
ICLOUD_VAULT = os.path.expanduser('~/Library/Mobile Documents/iCloud~md~obsidian/research_project/brainstorm/sessions')

POLL_SECONDS = 10

os.makedirs(LOGDIR, exist_ok=True)
os.makedirs(ICLOUD_VAULT, exist_ok=True)

if os.path.exists(EXPORTED):
    with open(EXPORTED,'r') as f:
        exported = json.load(f)
else:
    exported = {}

def log(msg):
    ts = datetime.utcnow().isoformat() + 'Z'
    line = f"{ts} {msg}\n"
    with open(EXPORT_LOG,'a') as f:
        f.write(line)
    print(line, end='')


def add_frontmatter_if_missing(src_path, dest_path, session_id):
    with open(src_path,'r') as f:
        text = f.read()
    # check if has YAML frontmatter
    if text.startswith('---'):
        out = text
    else:
        fm = '---\n'
        fm += f"tags: [brainstorm,session_{session_id}]\n"
        fm += f"created: {datetime.utcnow().date()}\n"
        fm += f"source: {os.path.relpath(src_path, BASE)}\n"
        fm += '---\n\n'
        out = fm + text
    with open(dest_path,'w') as f:
        f.write(out)


def process():
    # iterate sessions
    if not os.path.isdir(SESSIONS):
        return
    for sid in os.listdir(SESSIONS):
        sdir = os.path.join(SESSIONS, sid)
        if not os.path.isdir(sdir):
            continue
        target_folder = os.path.join(ICLOUD_VAULT, sid)
        os.makedirs(target_folder, exist_ok=True)
        # scan for md files of interest
        for name in os.listdir(sdir):
            if not name.lower().endswith('.md'):
                continue
            src = os.path.join(sdir, name)
            dest = os.path.join(target_folder, name)
            key = f"{sid}/{name}"
            mtime = os.path.getmtime(src)
            prev = exported.get(key, 0)
            if mtime <= prev:
                continue
            try:
                add_frontmatter_if_missing(src, dest, sid)
                exported[key] = mtime
                log(f"exported {key} -> {dest}")
            except Exception as e:
                log(f"ERROR exporting {key}: {e}")
    # write exported state
    with open(EXPORTED,'w') as f:
        json.dump(exported, f)


if __name__=='__main__':
    log('export_to_obsidian watcher started')
    try:
        while True:
            process()
            time.sleep(POLL_SECONDS)
    except KeyboardInterrupt:
        log('export_to_obsidian watcher stopped')
