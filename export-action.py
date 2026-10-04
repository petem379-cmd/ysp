#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ysp-live 静态导出 (GitHub Actions 版)

直接调用央视频 JCE/bkliveinfo 接口, 生成静态 m3u 文件。
在 GitHub Actions 里定时运行, 结果推送到本仓库, 由 GitHub Pages 对外服务。
"""
import os
import re
import sys
import time

# 导入 ysp-live.py 的协议函数 (不启动 HTTP 服务)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
_src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'ysp-live.py')).read()
_cut = _src.find('def refresh_loop')
_head = _src[:_cut]
_cstart = _src.find('CHANNELS = [')
_cend = _src.find(']', _cstart) + 1
_ns = {}
exec(_head + '\n' + _src[_cstart:_cend], _ns)

jce_fetch = _ns['jce_fetch']
bk_playurls = _ns['bk_playurls']
fetch_abs_playlist = _ns['fetch_abs_playlist']
CHANNELS = _ns['CHANNELS']

OUT = os.path.dirname(os.path.abspath(__file__))
PAGES_BASE = 'https://petem379-cmd.github.io/ysp'

class C:
    pass

def fetch_channel(slug, name, sid, pid, defn, retries=3):
    """取单个频道的 m3u8, 优先 JCE, 失败转 BK"""
    last = None
    for attempt in range(retries):
        try:
            # JCE
            ch = C()
            ch.pid, ch.sid, ch.defn = pid, sid, defn
            segs = jce_fetch(ch)
            if segs:
                return build_m3u8(segs), 'jce'
        except Exception as e:
            last = e
        try:
            # BK
            urls = bk_playurls(sid, pid, defn)
            for u in urls:
                try:
                    pl = fetch_abs_playlist(u)
                    if '#EXTM3U' in pl:
                        return strip_endlist(pl), 'bk'
                except Exception:
                    continue
        except Exception as e:
            last = e
        time.sleep(3)
    raise last or RuntimeError('all failed')

def build_m3u8(segs):
    lines = ['#EXTM3U', '#EXT-X-VERSION:3', '#EXT-X-TARGETDURATION:8',
             '#EXT-X-MEDIA-SEQUENCE:%d' % int(time.time())]
    for dur, pdt, url in segs[-60:]:
        if pdt:
            lines.append('#EXT-X-PROGRAM-DATE-TIME:' + pdt)
        lines.append('#EXTINF:%.3f,' % dur)
        lines.append(url)
    return '\n'.join(lines) + '\n'

def strip_endlist(pl):
    return re.sub(r'#EXT-X-ENDLIST\s*', '', pl)

def main():
    ok, fail = 0, []
    names = []
    for slug, name, sid, pid, defn in CHANNELS:
        try:
            pl, mode = fetch_channel(slug, name, sid, pid, defn)
            with open(os.path.join(OUT, slug + '.m3u8'), 'w') as f:
                f.write(pl)
            names.append((name, slug))
            ok += 1
            print('OK %s (%s)' % (slug, mode), flush=True)
        except Exception as e:
            fail.append((slug, '%s: %s' % (type(e).__name__, str(e)[:80])))
            print('FAIL %s %s' % (slug, str(e)[:80]), flush=True)
    with open(os.path.join(OUT, 'all.m3u'), 'w') as f:
        f.write('#EXTM3U\n')
        for name, slug in names:
            f.write('#EXTINF:-1,%s\n%s/%s.m3u8\n' % (name, PAGES_BASE, slug))
    print('done: ok=%d fail=%d' % (ok, len(fail)))
    return 0 if ok > 0 else 1

if __name__ == '__main__':
    sys.exit(main())
