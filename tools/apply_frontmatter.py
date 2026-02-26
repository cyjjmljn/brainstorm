#!/usr/bin/env python3
import os, json, re
from datetime import date
base=os.path.expanduser('~/research_project/brainstorm')
exported_path=os.path.join(base,'LOGS','exported.json')
icloud_base=os.path.expanduser('~/Library/Mobile Documents/iCloud~md~obsidian/research_project/brainstorm/sessions')
log_md=os.path.join(base,'LOGS','export_changes.md')
if not os.path.exists(exported_path):
    print('no exported.json')
    raise SystemExit(1)
exported=json.load(open(exported_path))
updated=[]
pattern=re.compile(r'[^0-9A-Za-z\u4e00-\u9fff]+')
for key in exported:
    sid,name=key.split('/',1)
    icloud_file=os.path.join(icloud_base,sid,name)
    if not os.path.exists(icloud_file):
        print('missing in icloud:', icloud_file)
        continue
    try:
        with open(icloud_file,'r',encoding='utf-8',errors='ignore') as f:
            text=f.read()
    except OSError as e:
        print('SKIP (read error):', icloud_file, '->', e)
        continue
    newtext=text
    # remove existing frontmatter
    stripped=newtext.lstrip()
    if stripped.startswith('---'):
        parts=stripped.split('---',2)
        if len(parts)>=3:
            newtext=parts[2].lstrip('\n')
        else:
            newtext=stripped
    # find title
    title=''
    for line in newtext.splitlines():
        s=line.strip()
        if not s: continue
        if s.startswith('#'):
            title=re.sub(r'^#+\s*','',s)
        else:
            title=s
        break
    if not title:
        title='Untitled'
    # slug tag: keep letters, numbers, chinese; replace others with underscore
    tag=pattern.sub('_', title.strip()).strip('_').lower()
    if not tag:
        tag='topic'
    created=date.today().isoformat()
    source=f'sessions/{sid}/{name}'
    title_esc=title.replace('"','\\"')
    fm_lines=[
        '---',
        f'title: "{title_esc}"',
        f'tags: [brainstorm, {tag}]',
        f'created: {created}',
        f'source: {source}',
        '---',
        ''
    ]
    fm='\n'.join(fm_lines)
    out=fm+newtext
    try:
        with open(icloud_file,'w',encoding='utf-8') as f:
            f.write(out)
    except OSError as e:
        print('SKIP (write error):', icloud_file, '->', e)
        continue
    updated.append(icloud_file)
# write change log
with open(log_md,'a',encoding='utf-8') as f:
    f.write(f'# Batch frontmatter update {date.today().isoformat()}\n')
    for p in updated:
        f.write(f'- {p}\n')
print('updated', len(updated), 'files')
