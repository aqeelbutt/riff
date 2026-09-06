#!/usr/bin/env python3
"""Phase 0 spike runner: drives the ACE-Step 1.5 sidecar over its REST API.

Stdlib only so it runs with any Python 3. Usage:

    python3 spike/run_spike.py text2music --name pop-turbo --lyrics spike/lyrics/pop.txt \
        --caption "..." --duration 150 --model acestep-v15-turbo
    python3 spike/run_spike.py cover --name pop-to-deephouse --src spike/out/pop-turbo_1.wav \
        --caption "deep house ..." --strength 0.45
    python3 spike/run_spike.py init --model acestep-v15-sft --slot 2

Every run appends a JSON line to spike/out/results.jsonl with wall-clock timing,
seed, model, and output paths, so the go/no-go doc is built from data not memory.
"""
from __future__ import annotations

import argparse
import json
import mimetypes
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

BASE = os.environ.get("ACESTEP_URL", "http://127.0.0.1:8001")
HERE = Path(__file__).resolve().parent
OUT = HERE / "out"
OUT.mkdir(exist_ok=True)
RESULTS = OUT / "results.jsonl"


def _req(path: str, body: dict | None = None, *, method: str = "POST", timeout: int = 600):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, method=method)
    if data is not None:
        req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def _multipart(path: str, fields: dict[str, str], files: dict[str, Path], timeout: int = 600):
    boundary = "----riff" + uuid.uuid4().hex
    body = bytearray()
    for k, v in fields.items():
        body += f"--{boundary}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n{v}\r\n".encode()
    for k, p in files.items():
        ctype = mimetypes.guess_type(p.name)[0] or "application/octet-stream"
        body += (
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"{k}\"; filename=\"{p.name}\"\r\n"
            f"Content-Type: {ctype}\r\n\r\n"
        ).encode()
        body += p.read_bytes() + b"\r\n"
    body += f"--{boundary}--\r\n".encode()
    req = urllib.request.Request(BASE + path, data=bytes(body), method="POST")
    req.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def _download(url_path: str, dest: Path) -> None:
    with urllib.request.urlopen(BASE + url_path, timeout=600) as r, open(dest, "wb") as f:
        f.write(r.read())


def _poll(task_id: str, started: float, quiet: bool = False) -> dict:
    last = ""
    while True:
        resp = _req("/query_result", {"task_id_list": [task_id]})
        items = resp.get("data") or []
        item = items[0] if items else {}
        status = item.get("status")
        if status == 1:
            return item
        if status == 2:
            raise SystemExit(f"task {task_id} FAILED: {json.dumps(item)[:800]}")
        line = f"  … {time.time() - started:6.0f}s status={status}"
        if line != last and not quiet:
            print(line, end="\r", flush=True)
            last = line
        time.sleep(3)


def _record(entry: dict) -> None:
    with open(RESULTS, "a") as f:
        f.write(json.dumps(entry) + "\n")


def _finish(name: str, item: dict, started: float, extra: dict) -> None:
    elapsed = time.time() - started
    result = item.get("result")
    if isinstance(result, str):
        result = json.loads(result)
    audios = result if isinstance(result, list) else [result]
    paths = []
    for i, a in enumerate(audios, 1):
        url = a.get("file")
        ext = Path(urllib.parse.parse_qs(urllib.parse.urlparse(url).query).get("path", [""])[0]).suffix or ".wav"
        dest = OUT / f"{name}_{i}{ext}"
        _download(url, dest)
        paths.append(str(dest))
    first = audios[0] if audios else {}
    entry = {
        "name": name,
        "elapsed_s": round(elapsed, 1),
        "outputs": paths,
        "seed_value": first.get("seed_value"),
        "dit_model": first.get("dit_model"),
        "lm_model": first.get("lm_model"),
        "metas": first.get("metas"),
        **extra,
    }
    _record(entry)
    print()
    print(f"✓ {name}: {elapsed:.0f}s → {', '.join(Path(p).name for p in paths)}  seed={entry['seed_value']} dit={entry['dit_model']} lm={entry['lm_model']}")


def cmd_text2music(a: argparse.Namespace) -> None:
    lyrics = Path(a.lyrics).read_text() if a.lyrics else ""
    body = {
        "prompt": a.caption,
        "lyrics": lyrics,
        "audio_duration": a.duration,
        "inference_steps": a.steps,
        "thinking": a.thinking,
        "batch_size": a.batch,
        "audio_format": "wav",
        "use_random_seed": a.seed is None,
        "instrumental": a.instrumental,
    }
    if a.seed is not None:
        body["seed"] = a.seed
    if a.model:
        body["model"] = a.model
    if a.shift is not None:
        body["shift"] = a.shift
    if a.bpm:
        body["bpm"] = a.bpm
    if a.lang:
        body["vocal_language"] = a.lang
    print(f"▶ {a.name}: text2music model={a.model or 'default'} steps={a.steps} thinking={a.thinking} batch={a.batch} dur={a.duration} lang={a.lang or 'en'}")
    started = time.time()
    resp = _req("/release_task", body)
    task_id = resp["data"]["task_id"]
    item = _poll(task_id, started)
    _finish(a.name, item, started, {"task": "text2music", "steps": a.steps, "thinking": a.thinking,
                                     "batch": a.batch, "duration_req": a.duration, "caption": a.caption})


def cmd_cover(a: argparse.Namespace) -> None:
    fields = {
        "prompt": a.caption,
        "task_type": "cover",
        "audio_cover_strength": str(a.strength),
        "inference_steps": str(a.steps),
        "batch_size": str(a.batch),
        "audio_format": "wav",
        "thinking": "false",
    }
    if a.lyrics:
        fields["lyrics"] = Path(a.lyrics).read_text()
    if a.model:
        fields["model"] = a.model
    if a.shift is not None:
        fields["shift"] = str(a.shift)
    if a.bpm:
        fields["bpm"] = str(a.bpm)
    if a.lang:
        fields["vocal_language"] = a.lang
    print(f"▶ {a.name}: cover src={Path(a.src).name} strength={a.strength} steps={a.steps} lang={a.lang or 'en'}")
    started = time.time()
    resp = _multipart("/release_task", fields, {"src_audio": Path(a.src)})
    task_id = resp["data"]["task_id"]
    item = _poll(task_id, started)
    _finish(a.name, item, started, {"task": "cover", "src": a.src, "strength": a.strength,
                                     "steps": a.steps, "batch": a.batch, "caption": a.caption})


def cmd_init(a: argparse.Namespace) -> None:
    body = {"model": a.model, "slot": a.slot, "init_llm": a.init_llm}
    if a.lm:
        body["lm_model_path"] = a.lm
    started = time.time()
    print(json.dumps(_req("/v1/init", body, timeout=1800)["data"], indent=1))
    print(f"init took {time.time() - started:.0f}s")


def cmd_status(_: argparse.Namespace) -> None:
    for p in ("/health", "/v1/models", "/v1/stats"):
        try:
            print(p, json.dumps(_req(p, method="GET"), indent=1)[:1200])
        except urllib.error.URLError as e:
            print(p, "ERROR", e)


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)

    t = sub.add_parser("text2music")
    t.add_argument("--name", required=True)
    t.add_argument("--caption", required=True)
    t.add_argument("--lyrics")
    t.add_argument("--duration", type=float, default=150)
    t.add_argument("--steps", type=int, default=8)
    t.add_argument("--shift", type=float, default=None)
    t.add_argument("--thinking", action="store_true")
    t.add_argument("--instrumental", action="store_true")
    t.add_argument("--batch", type=int, default=1)
    t.add_argument("--seed", type=int)
    t.add_argument("--model")
    t.add_argument("--bpm", type=int)
    t.add_argument("--lang", help="vocal_language code, e.g. en, hi, ur, pa (default en)")
    t.set_defaults(fn=cmd_text2music)

    c = sub.add_parser("cover")
    c.add_argument("--name", required=True)
    c.add_argument("--src", required=True)
    c.add_argument("--caption", required=True)
    c.add_argument("--lyrics")
    c.add_argument("--strength", type=float, default=0.5)
    c.add_argument("--steps", type=int, default=8)
    c.add_argument("--shift", type=float, default=None)
    c.add_argument("--batch", type=int, default=1)
    c.add_argument("--model")
    c.add_argument("--bpm", type=int)
    c.add_argument("--lang", help="vocal_language code for regenerated vocals")
    c.set_defaults(fn=cmd_cover)

    i = sub.add_parser("init")
    i.add_argument("--model", required=True)
    i.add_argument("--slot", type=int, default=1)
    i.add_argument("--init-llm", action="store_true")
    i.add_argument("--lm")
    i.set_defaults(fn=cmd_init)

    s = sub.add_parser("status")
    s.set_defaults(fn=cmd_status)

    a = ap.parse_args()
    try:
        a.fn(a)
    except urllib.error.HTTPError as e:
        print("HTTP", e.code, e.read().decode()[:1500], file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
