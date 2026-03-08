#!/usr/bin/env python3
"""Punjabi Gurmukhi OCR app with segmentation, correction loop, and adaptive training.

Requirements:
- Python 3.11+
- tesseract executable in PATH with Punjabi language data (pan)
"""

from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import os
import pathlib
import re
import shutil
import subprocess
import textwrap
import uuid
import zipfile
from collections import Counter
from dataclasses import dataclass
from email.parser import BytesParser
from email.policy import default
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from io import BytesIO
from urllib.parse import parse_qs, urlparse
from xml.sax.saxutils import escape

ROOT_DIR = pathlib.Path(__file__).resolve().parent
DATA_DIR = ROOT_DIR / "app_data"
UPLOADS_DIR = DATA_DIR / "uploads"
OUTPUTS_DIR = DATA_DIR / "outputs"
MODEL_DIR = DATA_DIR / "model"

CORRECTIONS_FILE = MODEL_DIR / "corrections.json"
VOCAB_FILE = MODEL_DIR / "vocab_counts.json"
TRAINING_LOG = MODEL_DIR / "training_log.jsonl"

ALLOWED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".webp"}
GURMUKHI_TOKEN_RE = re.compile(r"[\u0A00-\u0A7F]+", re.UNICODE)


def ensure_dirs() -> None:
    for directory in (DATA_DIR, UPLOADS_DIR, OUTPUTS_DIR, MODEL_DIR):
        directory.mkdir(parents=True, exist_ok=True)
    if not CORRECTIONS_FILE.exists():
        CORRECTIONS_FILE.write_text("{}", encoding="utf-8")
    if not VOCAB_FILE.exists():
        VOCAB_FILE.write_text("{}", encoding="utf-8")


def bootstrap_model_if_empty() -> None:
    vocab = load_json_dict(VOCAB_FILE)
    if vocab:
        return

    trainer = OCRTrainer()
    seed_files = [
        ROOT_DIR / "punjabi_corpus" / "punjabi_corpus.txt",
        ROOT_DIR / "corrections" / "corrected_text.txt",
    ]
    total_tokens = 0
    for seed_file in seed_files:
        if not seed_file.exists():
            continue
        text = seed_file.read_text(encoding="utf-8", errors="ignore")
        counts = Counter(tokenize_gurmukhi(text))
        for token, amount in counts.items():
            trainer.vocab_counts[token] = int(trainer.vocab_counts.get(token, 0)) + int(amount)
        total_tokens += sum(counts.values())

    trainer._save()
    if total_tokens:
        print(f"Bootstrapped vocabulary with {total_tokens} tokens from existing Punjabi corpus files.")


def now_stamp() -> str:
    return dt.datetime.now().strftime("%Y%m%d_%H%M%S")


def load_json_dict(path: pathlib.Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_json_dict(path: pathlib.Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def tokenize_gurmukhi(text: str) -> list[str]:
    return GURMUKHI_TOKEN_RE.findall(text)


def levenshtein(a: str, b: str) -> int:
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)

    prev_row = list(range(len(b) + 1))
    for i, ca in enumerate(a, start=1):
        curr = [i]
        for j, cb in enumerate(b, start=1):
            ins = curr[j - 1] + 1
            dele = prev_row[j] + 1
            sub = prev_row[j - 1] + (ca != cb)
            curr.append(min(ins, dele, sub))
        prev_row = curr
    return prev_row[-1]


def is_valid_image(filename: str) -> bool:
    return pathlib.Path(filename).suffix.lower() in ALLOWED_EXTENSIONS


@dataclass
class OCRResult:
    raw_text: str
    segmented_words: list[dict]


class OCRTrainer:
    def __init__(self) -> None:
        self.corrections = load_json_dict(CORRECTIONS_FILE)
        self.vocab_counts = load_json_dict(VOCAB_FILE)

    def _save(self) -> None:
        save_json_dict(CORRECTIONS_FILE, self.corrections)
        save_json_dict(VOCAB_FILE, self.vocab_counts)

    def _best_vocab_candidate(self, word: str) -> str | None:
        if word in self.vocab_counts:
            return word

        candidates = []
        for token, count in self.vocab_counts.items():
            if abs(len(token) - len(word)) > 2:
                continue
            dist = levenshtein(word, token)
            if dist <= 2:
                candidates.append((dist, -int(count), token))

        if not candidates:
            return None
        candidates.sort()
        return candidates[0][2]

    def apply_corrections(self, text: str) -> str:
        def replace_token(match: re.Match[str]) -> str:
            token = match.group(0)
            if token in self.corrections:
                return self.corrections[token]
            candidate = self._best_vocab_candidate(token)
            return candidate if candidate else token

        return GURMUKHI_TOKEN_RE.sub(replace_token, text)

    def train_from_pair(self, noisy_text: str, corrected_text: str, source_file: str) -> dict:
        noisy_tokens = tokenize_gurmukhi(noisy_text)
        corrected_tokens = tokenize_gurmukhi(corrected_text)

        replaced = 0
        for wrong, right in zip(noisy_tokens, corrected_tokens):
            if wrong != right and right:
                self.corrections[wrong] = right
                replaced += 1

        counts = Counter(corrected_tokens)
        for token, amount in counts.items():
            self.vocab_counts[token] = int(self.vocab_counts.get(token, 0)) + int(amount)

        self._save()
        log_item = {
            "timestamp": dt.datetime.now().isoformat(timespec="seconds"),
            "source_file": source_file,
            "pairs_seen": min(len(noisy_tokens), len(corrected_tokens)),
            "new_or_updated_rules": replaced,
            "vocab_total": len(self.vocab_counts),
        }
        with TRAINING_LOG.open("a", encoding="utf-8") as f:
            f.write(json.dumps(log_item, ensure_ascii=False) + "\n")
        return log_item


def run_tesseract_text(image_path: pathlib.Path, lang: str = "pan") -> str:
    command = ["tesseract", str(image_path), "stdout", "-l", lang, "--psm", "6", "--oem", "1"]
    completed = subprocess.run(command, check=True, capture_output=True, text=True)
    return completed.stdout


def run_tesseract_tsv(image_path: pathlib.Path, lang: str = "pan") -> list[dict]:
    command = ["tesseract", str(image_path), "stdout", "-l", lang, "--psm", "6", "--oem", "1", "tsv"]
    completed = subprocess.run(command, check=True, capture_output=True, text=True)
    rows = completed.stdout.splitlines()
    if not rows:
        return []

    headers = rows[0].split("\t")
    segments = []
    for row in rows[1:]:
        values = row.split("\t")
        if len(values) != len(headers):
            continue
        rec = dict(zip(headers, values))
        text_val = rec.get("text", "").strip()
        if rec.get("level") == "5" and text_val:
            segments.append(
                {
                    "text": text_val,
                    "left": int(rec.get("left", "0") or 0),
                    "top": int(rec.get("top", "0") or 0),
                    "width": int(rec.get("width", "0") or 0),
                    "height": int(rec.get("height", "0") or 0),
                    "conf": float(rec.get("conf", "-1") or -1),
                }
            )
    return segments


def do_ocr(image_path: pathlib.Path, lang: str) -> OCRResult:
    text = run_tesseract_text(image_path, lang=lang)
    segments = run_tesseract_tsv(image_path, lang=lang)
    return OCRResult(raw_text=text, segmented_words=segments)


def write_docx(text: str, out_path: pathlib.Path) -> None:
    content_types = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
</Types>
"""

    rels = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>
"""

    lines = text.splitlines() or [""]
    paragraphs = "".join(
        f"<w:p><w:r><w:t xml:space=\"preserve\">{escape(line)}</w:t></w:r></w:p>" for line in lines
    )

    document_xml = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:wpc="http://schemas.microsoft.com/office/word/2010/wordprocessingCanvas"
 xmlns:mc="http://schemas.openxmlformats.org/markup-compatibility/2006"
 xmlns:o="urn:schemas-microsoft-com:office:office"
 xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"
 xmlns:m="http://schemas.openxmlformats.org/officeDocument/2006/math"
 xmlns:v="urn:schemas-microsoft-com:vml"
 xmlns:wp14="http://schemas.microsoft.com/office/word/2010/wordprocessingDrawing"
 xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"
 xmlns:w10="urn:schemas-microsoft-com:office:word"
 xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"
 xmlns:w14="http://schemas.microsoft.com/office/word/2010/wordml"
 xmlns:wpg="http://schemas.microsoft.com/office/word/2010/wordprocessingGroup"
 xmlns:wpi="http://schemas.microsoft.com/office/word/2010/wordprocessingInk"
 xmlns:wne="http://schemas.microsoft.com/office/2006/wordml"
 xmlns:wps="http://schemas.microsoft.com/office/word/2010/wordprocessingShape"
 mc:Ignorable="w14 wp14">
  <w:body>
    {paragraphs}
    <w:sectPr><w:pgSz w:w="12240" w:h="15840"/><w:pgMar w:top="1440" w:right="1440" w:bottom="1440" w:left="1440"/></w:sectPr>
  </w:body>
</w:document>
"""

    with zipfile.ZipFile(out_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", content_types.strip())
        zf.writestr("_rels/.rels", rels.strip())
        zf.writestr("word/document.xml", document_xml.strip())


def sanitize_filename(name: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", name)
    return cleaned[:100] or "upload"


def parse_multipart(
    handler: BaseHTTPRequestHandler,
) -> tuple[dict[str, str], dict[str, list[tuple[str, bytes]]]]:
    content_type = handler.headers.get("Content-Type", "")
    content_length = int(handler.headers.get("Content-Length", "0"))
    raw_body = handler.rfile.read(content_length)

    message_bytes = (
        f"Content-Type: {content_type}\r\nMIME-Version: 1.0\r\n\r\n".encode("utf-8") + raw_body
    )
    msg = BytesParser(policy=default).parsebytes(message_bytes)

    fields: dict[str, str] = {}
    files: dict[str, list[tuple[str, bytes]]] = {}

    for part in msg.iter_parts():
        cd = part.get("Content-Disposition", "")
        if "form-data" not in cd:
            continue
        name = part.get_param("name", header="Content-Disposition")
        filename = part.get_filename()
        payload = part.get_payload(decode=True) or b""

        if not name:
            continue
        if filename:
            files.setdefault(name, []).append((filename, payload))
        else:
            fields[name] = payload.decode("utf-8", errors="replace")

    return fields, files


def html_page(body: str) -> bytes:
    page = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>Punjabi Gurmukhi OCR Trainer</title>
<style>
:root {{
  --bg: #f6f7ef;
  --ink: #202419;
  --card: #ffffff;
  --accent: #2e5e3e;
  --muted: #66715f;
  --line: #d8ddcf;
}}
* {{ box-sizing: border-box; }}
body {{ margin: 0; font-family: "Palatino Linotype", "Noto Sans Gurmukhi", serif; background: radial-gradient(circle at top, #f4f8ea 0%, var(--bg) 65%); color: var(--ink); }}
main {{ max-width: 980px; margin: 2rem auto; padding: 1rem; }}
.card {{ background: var(--card); border: 1px solid var(--line); border-radius: 14px; padding: 1rem 1.2rem; box-shadow: 0 6px 22px rgba(0,0,0,0.05); margin-bottom: 1rem; }}
label {{ display: block; margin: 0.6rem 0 0.25rem; font-weight: 600; }}
input[type=file], input[type=number], textarea, select {{ width: 100%; padding: 0.6rem; border: 1px solid #cfd7c3; border-radius: 8px; font: inherit; }}
textarea {{ min-height: 120px; }}
button {{ margin-top: 0.8rem; padding: 0.62rem 1rem; background: var(--accent); color: white; border: none; border-radius: 9px; cursor: pointer; font-weight: 700; }}
small, .muted {{ color: var(--muted); }}
code {{ background: #edf2e4; padding: 0.15rem 0.35rem; border-radius: 5px; }}
pre {{ white-space: pre-wrap; background: #f3f5ef; border: 1px solid #dfe6d4; border-radius: 8px; padding: 0.8rem; }}
.table {{ overflow:auto; border:1px solid #dde3d4; border-radius: 8px; }}
table {{ width:100%; border-collapse: collapse; font-size: 0.95rem; }}
th, td {{ border-bottom:1px solid #e8ece1; text-align:left; padding:0.35rem 0.5rem; }}
</style>
</head>
<body>
<main>
{body}
</main>
</body>
</html>
"""
    return page.encode("utf-8")


def render_home(message: str = "") -> bytes:
    msg_html = f'<p class="muted">{html.escape(message)}</p>' if message else ""
    body = f"""
<div class="card">
<h1>Punjabi Gurmukhi OCR with Training Loop</h1>
<p>Pipeline stages: <code>Input</code> -> <code>Segmentation</code> -> <code>Reading</code> -> <code>Correction + Training</code> -> <code>Output</code>. Loop count runs stages repeatedly to improve corrections model.</p>
{msg_html}
</div>
<div class="card">
<form method="POST" action="/process" enctype="multipart/form-data">
<label>Upload Punjabi Image(s)</label>
<input type="file" name="images" accept=".png,.jpg,.jpeg,.tif,.tiff,.bmp,.webp" multiple required />

<label>Loops (1-5)</label>
<input type="number" name="loops" min="1" max="5" value="2" />

<label>OCR Language</label>
<select name="lang">
<option value="pan" selected>Punjabi (pan)</option>
<option value="pan+eng">Punjabi + English</option>
<option value="pan+hin+eng">Punjabi + Hindi + English</option>
</select>

<label>Optional Human-Corrected Text (feeds training)</label>
<textarea name="corrected_text" placeholder="Paste corrected Punjabi text here to train the correction model."></textarea>

<button type="submit">Run OCR Pipeline</button>
</form>
<p><small>Exports created: <code>.txt</code> and <code>.docx</code>. Requires local <code>tesseract</code> install.</small></p>
</div>
"""
    return html_page(body)


def render_result(result: dict) -> bytes:
    segmented_rows = "".join(
        f"<tr><td>{html.escape(str(i + 1))}</td><td>{html.escape(seg['text'])}</td><td>{seg['left']}</td><td>{seg['top']}</td><td>{seg['width']}</td><td>{seg['height']}</td><td>{seg['conf']:.1f}</td></tr>"
        for i, seg in enumerate(result["segmented_words"][:250])
    )

    training_note = ""
    if result.get("training"):
        t = result["training"]
        training_note = (
            f"<p><b>Training update:</b> pairs seen={t['pairs_seen']}, new/updated rules={t['new_or_updated_rules']}, vocabulary size={t['vocab_total']}.</p>"
        )

    body = f"""
<div class="card">
<h2>Pipeline Completed</h2>
<p><b>Input file:</b> {html.escape(result['source_file'])}</p>
<p><b>Loops executed:</b> {result['loops']}</p>
<p><b>Total segmented words:</b> {len(result['segmented_words'])}</p>
{training_note}
<p><a href="/download/{result['txt_file']}">Download TXT</a> | <a href="/download/{result['docx_file']}">Download DOCX</a></p>
<p><a href="/">Run another file</a></p>
</div>

<div class="card">
<h3>Final OCR Output (post-correction)</h3>
<pre>{html.escape(result['final_text'])}</pre>
</div>

<div class="card">
<h3>Segmentation (word boxes from TSV)</h3>
<div class="table">
<table>
<tr><th>#</th><th>Word</th><th>Left</th><th>Top</th><th>Width</th><th>Height</th><th>Conf</th></tr>
{segmented_rows}
</table>
</div>
<p><small>Showing up to first 250 segmented words.</small></p>
</div>
"""
    return html_page(body)


class OCRHandler(BaseHTTPRequestHandler):
    server_version = "PunjabiOCR/1.0"

    def _send_bytes(self, status: HTTPStatus, body: bytes, content_type: str = "text/html; charset=utf-8") -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path == "/":
            self._send_bytes(HTTPStatus.OK, render_home())
            return

        if parsed.path.startswith("/download/"):
            filename = parsed.path.removeprefix("/download/")
            safe = sanitize_filename(filename)
            file_path = OUTPUTS_DIR / safe
            if not file_path.exists() or not file_path.is_file():
                self._send_bytes(HTTPStatus.NOT_FOUND, html_page("<div class='card'><p>File not found.</p></div>"))
                return

            ctype = "application/octet-stream"
            if safe.endswith(".txt"):
                ctype = "text/plain; charset=utf-8"
            elif safe.endswith(".docx"):
                ctype = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            body = file_path.read_bytes()
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Disposition", f'attachment; filename="{safe}"')
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        self._send_bytes(HTTPStatus.NOT_FOUND, html_page("<div class='card'><p>Route not found.</p></div>"))

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/process":
            self._send_bytes(HTTPStatus.NOT_FOUND, html_page("<div class='card'><p>Route not found.</p></div>"))
            return

        ctype = self.headers.get("Content-Type", "")
        if "multipart/form-data" not in ctype:
            self._send_bytes(HTTPStatus.BAD_REQUEST, render_home("Expected multipart form-data."))
            return

        if shutil.which("tesseract") is None:
            self._send_bytes(
                HTTPStatus.BAD_REQUEST,
                render_home("Tesseract not found in PATH. Install tesseract + Punjabi language data (pan)."),
            )
            return

        try:
            fields, files = parse_multipart(self)
            image_files = files.get("images", [])
            if not image_files:
                self._send_bytes(HTTPStatus.BAD_REQUEST, render_home("Please upload at least one image file."))
                return

            loops = int((fields.get("loops") or "2").strip())
            loops = max(1, min(loops, 5))
            lang = (fields.get("lang") or "pan").strip() or "pan"
            corrected_text = fields.get("corrected_text", "").strip()

            run_id = f"{now_stamp()}_{uuid.uuid4().hex[:8]}"

            trainer = OCRTrainer()

            ocr_raw_parts: list[str] = []
            segmented: list[dict] = []
            corrected_pass = ""
            source_files: list[str] = []

            uploaded_paths: list[pathlib.Path] = []
            for original_name, data in image_files:
                original_name = sanitize_filename(original_name)
                if not is_valid_image(original_name):
                    self._send_bytes(
                        HTTPStatus.BAD_REQUEST,
                        render_home(f"Unsupported file type for image: {original_name}"),
                    )
                    return
                upload_path = UPLOADS_DIR / f"{run_id}_{original_name}"
                upload_path.write_bytes(data)
                uploaded_paths.append(upload_path)
                source_files.append(original_name)

            for _ in range(loops):
                ocr_raw_parts = []
                segmented = []
                for upload_path in uploaded_paths:
                    ocr_res = do_ocr(upload_path, lang=lang)
                    ocr_raw_parts.append(ocr_res.raw_text.strip())
                    segmented.extend(ocr_res.segmented_words)

                ocr_raw = "\n\n".join(part for part in ocr_raw_parts if part)
                corrected_pass = trainer.apply_corrections(ocr_raw)

                # Self-training from current corrected output to improve token frequency model.
                self_tokens = tokenize_gurmukhi(corrected_pass)
                for tok, count in Counter(self_tokens).items():
                    trainer.vocab_counts[tok] = int(trainer.vocab_counts.get(tok, 0)) + int(count)
                trainer._save()

            training_log = None
            if corrected_text:
                training_log = trainer.train_from_pair(ocr_raw, corrected_text, ",".join(source_files))
                corrected_pass = corrected_text

            txt_name = sanitize_filename(f"ocr_{run_id}.txt")
            docx_name = sanitize_filename(f"ocr_{run_id}.docx")
            txt_path = OUTPUTS_DIR / txt_name
            docx_path = OUTPUTS_DIR / docx_name
            txt_path.write_text(corrected_pass, encoding="utf-8")
            write_docx(corrected_pass, docx_path)

            payload = {
                "source_file": ", ".join(source_files),
                "loops": loops,
                "segmented_words": segmented,
                "final_text": corrected_pass,
                "txt_file": txt_name,
                "docx_file": docx_name,
                "training": training_log,
            }
            self._send_bytes(HTTPStatus.OK, render_result(payload))
        except subprocess.CalledProcessError as err:
            message = f"Tesseract failed: {err.stderr.strip() if err.stderr else str(err)}"
            self._send_bytes(HTTPStatus.BAD_REQUEST, render_home(message))
        except Exception as err:  # pragma: no cover
            self._send_bytes(HTTPStatus.INTERNAL_SERVER_ERROR, render_home(f"Unexpected error: {err}"))


def retrain_from_text(corpus_file: pathlib.Path) -> None:
    trainer = OCRTrainer()
    if not corpus_file.exists():
        raise FileNotFoundError(f"Missing corpus file: {corpus_file}")

    text = corpus_file.read_text(encoding="utf-8", errors="ignore")
    counts = Counter(tokenize_gurmukhi(text))
    for token, amount in counts.items():
        trainer.vocab_counts[token] = int(trainer.vocab_counts.get(token, 0)) + int(amount)
    trainer._save()
    print(f"Loaded {sum(counts.values())} tokens into vocabulary from {corpus_file}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Punjabi Gurmukhi OCR Trainer App")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument(
        "--retrain-from",
        type=pathlib.Path,
        help="Optional text file to train vocabulary from and exit.",
    )
    args = parser.parse_args()

    ensure_dirs()
    bootstrap_model_if_empty()

    if args.retrain_from:
        retrain_from_text(args.retrain_from)
        return

    with ThreadingHTTPServer((args.host, args.port), OCRHandler) as server:
        print(f"Punjabi OCR app running at http://{args.host}:{args.port}")
        server.serve_forever()


if __name__ == "__main__":
    main()
