# Punjabi Gurmukhi OCR (Go Final Product)

Final product is a Go app that serves a platform-free OCR UI.

## Your requested workflow (implemented)

1. Select **images and/or PDFs** in Punjabi Gurmukhi.
2. OCR reads files in a loop.
3. **Right-side pane** shows editable output text for correction.
4. After correction, you can:
   - Save as a **new DOCX**
   - **Append** to an existing DOCX and download the updated file

Pipeline loops:

`Input -> Reading -> Segmentation -> Correction -> Training -> Output`

## Features

- Multiple file input (images + PDFs)
- Word-level segmentation table (bbox + confidence)
- Intermediate review stage with `Word by word` and `Line by line` correction
- Per-row decision buttons:
  - `Implement Change` (use your correction)
  - `Accept Model Output` (keep model output)
- Editable correction pane on right
- Training from intermediate review stage
- Training from right-pane edits (manual button and auto on save)
- Persistent model memory across refresh via browser storage:
  - token rules
  - phrase/line replacement rules
- Save TXT
- Save New DOCX
- Append to Existing DOCX
- Consent-gated dependency download in browser
- Export/import learning packs for collaboration
- One-click `Submit Pack to GitHub` (via Go backend endpoint)

## Platform-free dependency policy

- No OS OCR installation required.
- On first OCR use, app asks user consent before downloading:
  - `tesseract.js` (OCR runtime + language data)
  - `pdf.js` (PDF page rendering)
  - `jszip` (DOCX read/write)
- If consent is declined, OCR does not run.
- Output text is normalized to Unicode (`NFC`) Gurmukhi-friendly text.
- Default OCR language is `Punjabi + English` to improve recognition of symbols like `☬` and list markers.
- `Symbols handling` option:
  - `Try keep symbols`
  - `Skip non-Gurmukhi symbols`
- Bullet normalization: common OCR bullet variants (`-`, `*`, `o`, `0`, `●`, `◦`) are normalized to `•`.
- Preprocessing mode selector:
  - `Best of variants (recommended)` (auto-picks highest-confidence OCR result)
  - `Original`
  - `Binary Otsu`
  - `Denoise`
  - `Sharpen`

## Files

- `main.go`: Go app entrypoint
- `platform_free_punjabi_ocr.html`: OCR UI and logic
- `go.mod`: Go module

## Run

```bash
go run .
```

Open: `http://127.0.0.1:8080`

## One-click GitHub pack submission setup

`Submit Pack to GitHub` uses backend endpoint `/submit-pack`.  
It always saves a local copy under `app_data/learning_packs/`, and uploads to GitHub if token is configured.

Set environment variables before `go run .`:

```bash
export GITHUB_TOKEN="<your_fine_grained_pat>"
export GITHUB_OWNER="amandeep-punjabi"
export GITHUB_REPO="Gurmukhi-OCR"
export GITHUB_BRANCH="main"
export GITHUB_PACK_PATH="contributions/learning_packs"
```

Optional committer identity:

```bash
export GITHUB_COMMITTER_NAME="Punjabi OCR Bot"
export GITHUB_COMMITTER_EMAIL="bot@example.com"
```

## Build binary

```bash
go build -o punjabi-ocr .
```

## Cross-platform builds

```bash
GOOS=darwin GOARCH=arm64 go build -o punjabi-ocr-macos-arm64 .
GOOS=windows GOARCH=amd64 go build -o punjabi-ocr-windows-amd64.exe .
GOOS=linux GOARCH=amd64 go build -o punjabi-ocr-linux-amd64 .
```

## Important note

Due to browser file security, "append to existing DOCX" creates and downloads a new appended DOCX file (it cannot modify the original file in place on disk).

## Current machine status

Go toolchain is not installed on this machine yet, so I could not execute `go run` or `go build` here.
