#!/usr/bin/env python3
"""Debug playlist structure"""
import sys, json, re
sys.path.insert(0, '/home/ubuntu/Yt')

from aytube.fetcher import fetch_page

html = fetch_page('PLRqw7-VrqV5vAQAIEKpefyO99kLA9fSm5',
                  cookies_file='/home/ubuntu/Yt/cookies_file', timeout=30)
print(f'HTML length: {len(html)}')

# Extract ytInitialData
m = re.search(r'ytInitialData\s*=\s*', html)
brace = html.find('{', m.end())
depth = 0
in_str = False
esc = False
for i in range(brace, len(html)):
    c = html[i]
    if esc: esc = False; continue
    if c == '\\' and in_str: esc = True; continue
    if c == '"' and not esc: in_str = not in_str; continue
    if in_str: continue
    if c == '{': depth += 1
    elif c == '}':
        depth -= 1
        if depth == 0:
            data = json.loads(html[brace:i+1])
            break

contents = data.get('contents', {})
print(f'\nTop keys: {list(contents.keys())[:10]}')

# Browse results
browse = contents.get('twoColumnBrowseResults', contents.get('twoColumnBrowseResultsRenderer', {}))
print(f'\nbrowse keys: {list(browse.keys())[:10]}')
tabs = browse.get('tabs', [])
print(f'tabs count: {len(tabs)}')

for idx, tab in enumerate(tabs):
    tr = tab.get('tabRenderer', {})
    print(f'\n  Tab {idx}: title="{tr.get("title","")}" selected={tr.get("selected")}')
    content = tr.get('content', {})
    print(f'  content keys: {list(content.keys())[:10]}')

    # sectionListRenderer
    slr = content.get('sectionListRenderer', {})
    secs = slr.get('contents', [])
    print(f'  sections: {len(secs)}')
    for si, sec in enumerate(secs[:3]):
        print(f'    section[{si}] keys: {list(sec.keys())[:10]}')
        # Look for itemSectionRenderer
        isr = sec.get('itemSectionRenderer', {})
        isr_contents = isr.get('contents', [])
        print(f'    itemSection contents: {len(isr_contents)}')
        for ci, ic in enumerate(isr_contents[:2]):
            print(f'      content[{ci}] keys: {list(ic.keys())[:15]}')
            # Look for playlistVideoListRenderer
            pvlr = ic.get('playlistVideoListRenderer', {})
            pvlr_contents = pvlr.get('contents', [])
            print(f'      playlistVideoList contents: {len(pvlr_contents)}')
            for pi, pvc in enumerate(pvlr_contents[:2]):
                print(f'        playlistVideo[{pi}] keys: {list(pvc.keys())[:10]}')
                if 'playlistVideoRenderer' in pvc:
                    pvr = pvc['playlistVideoRenderer']
                    vid = pvr.get('videoId','')
                    title_runs = pvr.get('title',{}).get('runs',[])
                    title = title_runs[0].get('text','') if title_runs else ''
                    print(f'          -> videoId={vid} title={title[:40]}')

# Also check for grid items
grid = content.get('gridRenderer', {})
print(f'\ngrid items: {len(grid.get("items",[]))}')
