#!/usr/bin/env python3
"""Summarize a UE CsvProfile CSV (frame/game/render/GPU times in ms).

Usage:
  Summarize-FrameTime.py <csv>
  Summarize-FrameTime.py --selftest

Exit: 0 PASS (p95 <= 16.7 ms), 1 FAIL, 2 error.
"""
import csv
import os
import sys
import tempfile

BUDGET_MS = 16.7
HITCH_MS = 33.0
COLS = {
    'frame': ['frametime', 'frame time', 'frame'],
    'game': ['gamethreadtime', 'game thread time', 'gamethread', 'game'],
    'render': ['renderthreadtime', 'render thread time', 'renderthread', 'render'],
    'gpu': ['gputime', 'gpu time', 'gpu'],
}


def pct(sorted_vals, p):
    """Nearest-rank percentile on a pre-sorted list."""
    n = len(sorted_vals)
    k = max(1, -((-p * n) // 100))  # ceil(p*n/100) with integer math
    return sorted_vals[k - 1]


def find_columns(header):
    norm = [h.strip().lower() for h in header]
    found = {}
    for key, names in COLS.items():
        for name in names:
            if name in norm:
                found[key] = norm.index(name)
                break
    return found


def load(path):
    """Return {key: [floats]} for every recognised column. Raises ValueError if no frame column."""
    with open(path, newline='', encoding='utf-8', errors='replace') as f:
        rows = list(csv.reader(f))
    header_idx = None
    cols = {}
    for i, row in enumerate(rows):
        cols = find_columns(row)
        if 'frame' in cols:
            header_idx = i
            break
    if header_idx is None:
        raise ValueError('no frame-time column found in header')
    data = {k: [] for k in cols}
    for row in rows[header_idx + 1:]:
        for key, idx in cols.items():
            if idx >= len(row):
                continue
            try:
                data[key].append(float(row[idx]))
            except ValueError:
                pass
    frames = data.get('frame', [])
    if not frames:
        raise ValueError('frame-time column has no numeric rows')
    # Keep only rows where frame time parsed; other columns may be shorter, which is fine.
    return data


def stats(vals):
    s = sorted(vals)
    return {
        'avg': sum(vals) / len(vals),
        'p50': pct(s, 50),
        'p95': pct(s, 95),
        'p99': pct(s, 99),
    }


def summarize(path):
    data = load(path)
    out = {'frames': len(data['frame']), 'frame': stats(data['frame'])}
    out['hitches'] = sum(1 for v in data['frame'] if v > HITCH_MS)
    for key in ('game', 'render', 'gpu'):
        if data.get(key):
            out[key] = stats(data[key])
    return out


def report(path):
    try:
        res = summarize(path)
    except (OSError, ValueError) as e:
        print(f'ERROR: {e}')
        return 2
    f = res['frame']
    print(f"frames: {res['frames']}")
    print(f"frame ms  avg {f['avg']:.2f}  p50 {f['p50']:.2f}  p95 {f['p95']:.2f}  p99 {f['p99']:.2f}")
    print(f"hitches (frame > {HITCH_MS:.0f} ms): {res['hitches']}")
    for key, label in (('game', 'game'), ('render', 'render'), ('gpu', 'gpu')):
        if key in res:
            s = res[key]
            print(f"{label} ms  avg {s['avg']:.2f}  p50 {s['p50']:.2f}  p95 {s['p95']:.2f}  p99 {s['p99']:.2f}")
        else:
            print(f'{label} ms  n/a (column absent)')
    ok = f['p95'] <= BUDGET_MS
    verdict = 'PASS' if ok else 'FAIL'
    print(f"RESULT: {verdict} (p95 {f['p95']:.2f} ms vs {BUDGET_MS} ms budget)")
    return 0 if ok else 1


def selftest():
    fail_csv = (
        'CsvProfile,ver1\n'
        'Frame,FrameTime,GameThreadTime,RenderThreadTime,GPUTime\n'
        + ''.join(f'{i},{20.0 if i < 10 else 10.0},5.0,4.0,8.0\n' for i in range(100))
    )
    pass_csv = (
        'Frame,FrameTime,GameThreadTime,RenderThreadTime\n'
        + ''.join(f'{i},12.0,6.0,5.0\n' for i in range(100))
    )
    with tempfile.TemporaryDirectory() as d:
        pf = os.path.join(d, 'fail.csv')
        ps = os.path.join(d, 'pass.csv')
        with open(pf, 'w', encoding='utf-8') as f:
            f.write(fail_csv)
        with open(ps, 'w', encoding='utf-8') as f:
            f.write(pass_csv)

        a = summarize(pf)
        assert a['frames'] == 100, a
        assert abs(a['frame']['avg'] - 11.0) < 1e-9, a
        assert abs(a['frame']['p50'] - 10.0) < 1e-9, a
        assert abs(a['frame']['p95'] - 20.0) < 1e-9, a
        assert abs(a['frame']['p99'] - 20.0) < 1e-9, a
        assert a['hitches'] == 0, a
        assert abs(a['gpu']['avg'] - 8.0) < 1e-9, a
        assert abs(a['game']['avg'] - 5.0) < 1e-9, a
        assert 'render' in a, a
        assert report(pf) == 1, 'fail case must return 1'

        b = summarize(ps)
        assert abs(b['frame']['p95'] - 12.0) < 1e-9, b
        assert 'gpu' not in b, 'gpu column absent must be omitted'
        assert report(ps) == 0, 'pass case must return 0'

    print('SELFTEST: PASS')
    return 0


def main(argv):
    if len(argv) == 2 and argv[1] == '--selftest':
        return selftest()
    if len(argv) != 2:
        print('usage: Summarize-FrameTime.py <csv> | --selftest')
        return 2
    return report(argv[1])


if __name__ == '__main__':
    sys.exit(main(sys.argv))
