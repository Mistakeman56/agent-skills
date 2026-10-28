#!/usr/bin/env python3
"""Parse .torrent -> JSON (infohash / name / size / files / announce). stdlib only.

Usage: python3 parse_torrent.py file.torrent [more...] [--files N]

Rules:
- private=1: the announce URL embeds the account passkey; this script masks it.
  Never forward the raw .torrent or announce line outside the household.
- Multi-file torrents land on disk as <download-dir>/<info.name>/<paths...>,
  so compare info.name byte-for-byte with the on-disk folder BEFORE torrent-add,
  otherwise recheck flips to downloading (see references/pt-seeding-transfer.md).
"""
import sys, os, re, json, hashlib


def bdec(data, i=0):
    c = data[i:i + 1]
    if c == b'd':
        d, i = {}, i + 1
        while data[i:i + 1] != b'e':
            k, i = bdec(data, i)
            v, i = bdec(data, i)
            d[k] = v
        return d, i + 1
    if c == b'l':
        l, i = [], i + 1
        while data[i:i + 1] != b'e':
            v, i = bdec(data, i)
            l.append(v)
        return l, i + 1
    if c == b'i':
        j = data.index(b'e', i)
        return int(data[i + 1:j]), j + 1
    j = data.index(b':', i)
    n = int(data[i:j])
    s = j + 1
    return data[s:s + n], s + n


def benc(o):
    if isinstance(o, bool):
        return b'i%de' % int(o)
    if isinstance(o, int):
        return b'i%de' % o
    if isinstance(o, bytes):
        return b'%d:%s' % (len(o), o)
    if isinstance(o, str):
        return benc(o.encode())
    if isinstance(o, list):
        return b'l' + b''.join(benc(x) for x in o) + b'e'
    if isinstance(o, dict):
        return b'd' + b''.join(benc(k) + benc(o[k]) for k in sorted(o)) + b'e'
    raise TypeError(type(o))


def redact(url, private):
    url = re.sub(r'(?i)(passkey|auth|key|token|credential|password)=[^&/]+', r'\1=***', url)
    if private and len(url.rsplit('/', 1)[-1]) > 20 and '=' not in url.rsplit('/', 1)[-1]:
        url = url.rsplit('/', 1)[0] + '/***'
    return url


def main():
    args = list(sys.argv[1:])
    nfiles = 5
    if '--files' in args:
        k = args.index('--files')
        nfiles = int(args[k + 1])
        del args[k:k + 2]
    if not args:
        print(__doc__)
        sys.exit(1)
    for path in args:
        raw = open(path, 'rb').read()
        meta, _ = bdec(raw)
        info = meta[b'info']
        private = bool(info.get(b'private', 0))
        name = info[b'name'].decode('utf-8', 'replace')
        if b'length' in info:
            total, n, files = info[b'length'], 1, [name]
        else:
            fl = [(b'/'.join(f[b'path']).decode('utf-8', 'replace'), f[b'length']) for f in info[b'files']]
            total = sum(s for _, s in fl)
            n = len(fl)
            files = [f'{name}/{p}' for p, _ in fl]
        out = {
            'file': os.path.basename(path),
            'name': name,
            'infohash': hashlib.sha1(benc(info)).hexdigest(),
            'private': private,
            'announce': redact(meta.get(b'announce', b'').decode('utf-8', 'replace'), private),
            'nfiles': n,
            'total_GiB': round(total / 1024 ** 3, 2),
            'files_head': files[:nfiles],
        }
        if n > nfiles:
            out['files_tail'] = files[-1:]
        print(json.dumps(out, ensure_ascii=False))


if __name__ == '__main__':
    main()
