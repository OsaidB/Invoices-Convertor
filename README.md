# Invoice Converter

## 1. Overview

This project is a Python **FastAPI microservice** that converts invoice PDFs into structured JSON.

Important clarifications about what this tool is and is not:

- It is a **rule-based parser** — extraction is done with hardcoded regular expressions and a hardcoded list of Arabic keywords, not a trained model.
- It is **not AI-based**. There is no call to any LLM (OpenAI, Gemini, Claude, or otherwise) anywhere in this codebase.
- It is **not OCR-based**. It does not read pixels/images. It uses [PyMuPDF](https://pymupdf.readthedocs.io/) (`fitz`) to extract the **embedded text layer** of a PDF. A scanned/image-only PDF with no text layer will not be parsed correctly (it will yield little or no text).
- It is currently designed around **one specific Arabic invoice PDF template** (a point-of-sale/billing system export). The worksite marker (`ملاحظات`), totals labels (`المجموع` / `الصافي`), and the skip-word list are all tuned to this one layout. Other invoice layouts are very likely to parse incorrectly or produce incomplete/garbage output, silently (there is no confidence score beyond the total-matching check).
- It reads **only the first page** of the PDF (`doc[0]`). Content on additional pages is ignored.
- It **does not save invoices itself**. There is no database and no file persistence in the live HTTP request path.
- It **does not currently POST parsed invoices to any backend**. An earlier version of this service did push directly to a Spring Boot backend; that call has since been removed (see [Section 8](#8-python--backend-relationship)).
- The **caller/backend is responsible for persisting** whatever JSON this service returns. This service's job ends at "return the parsed JSON in the HTTP response."

## 2. Current Architecture

```
Caller (backend / frontend / Android app / SMS extractor / anything else)
        │
        │  POST /process-invoice or /fix-mismatched
        │  { "url": "<link to a PDF>", "originalId": <optional int> }
        ▼
This FastAPI service (invoice_processor/main.py)
        │
        │  1. downloads the PDF from the given URL
        │  2. parses the PDF's text layer (page 1 only)
        │  3. extracts date / worksite / line items / totals
        │  4. computes a total-match sanity check
        ▼
Returns structured invoice JSON in the HTTP response
        │
        ▼
Caller decides what to do with the result
(save it, display it, retry it, discard it, etc.)
```

In short: this tool is currently **"PDF URL in, invoice JSON out."** It has no knowledge of, and no dependency on, any database or backend state beyond the one hardcoded (but currently unused) URL in `send_invoices.py`.

## 3. Project Structure

| Path | What it does | Status |
|---|---|---|
| `invoice_processor/main.py` | FastAPI app (`app = FastAPI()`). Defines the two live HTTP endpoints, `/process-invoice` and `/fix-mismatched`. Downloads the PDF, calls the parser, tags the result with `pdfUrl`/`confirmed`/`parsedAt`, and returns it. | **Active runtime code.** |
| `invoice_processor/parse_invoice/convert_invoice.py` | Core parser. `process_invoice_pdf(input_file)` opens the PDF with PyMuPDF, extracts the date/worksite/items/totals via regex and keyword matching, and computes `totalMatch`. This is the heart of the tool. | **Active runtime code.** |
| `invoice_processor/fix_mismatched/fix_mismatched_invoices.py` | `fix_mismatched_invoice(invoice_data)`. When an invoice's computed total doesn't match the printed total, this recomputes item quantities from `total_price / unit_price` and re-checks the match. Used only by `/fix-mismatched`. | **Active runtime code.** |
| `invoice_processor/models/schemas.py` | Pydantic v2 models: `InvoiceRequest` (request body), `PendingInvoiceItem` and `PendingInvoice` (response body). Defines the exact field names/aliases returned over HTTP. | **Active runtime code.** |
| `invoice_processor/send_invoices.py` | `send_invoice_to_api(invoice_data)` — POSTs an invoice to a hardcoded external backend URL (`https://intfitout-backend-production.up.railway.app/api/invoices/pending/upload`). | **Dead/legacy code.** It is still imported in `main.py`, but neither endpoint calls it anymore — both call sites are commented out in `main.py`. Kept in the repo but currently has no effect on any request. |
| `invoice_processor/utils/process_messages.py` | Standalone batch script intended to scan an exported SMS/message log, find invoice-download links, download each PDF, and parse it. | **Broken/legacy.** It calls `process_invoice_pdf(pdf_path, "pdfs", "jsons")` with three arguments, but the current `process_invoice_pdf` only accepts one (`input_file`). Running this script as-is raises a `TypeError` immediately. It has not been kept in sync with the parser's current signature. |
| `invoice_processor/utils/move_mismatched_invoices.py` | Standalone script meant to move previously-saved JSON files from a "correctly matched" folder into a "mismatched" folder based on their `total_match`/`totalMatch` flag. | **Broken/legacy.** It computes its target folders relative to its own script directory (`invoice_processor/utils/jsons/...`), but no such folder exists there — the real data folder is at the repo root (`jsons/...`). As written, it will find nothing to move (or raise `FileNotFoundError` if the base folder is missing). Also runs its logic at import time (not guarded by `if __name__ == "__main__"`), so importing this module executes it. |
| `invoice_processor/utils/move_matched_back.py` | The reverse of the above — moves files back from "mismatched" to "correctly matched" once resolved. | **Broken/legacy**, same wrong-path issue as `move_mismatched_invoices.py`. |
| `invoice_processor/utils/t.py` | A small one-off script that filters an SMS export (`messages.txt`, hardcoded UTF-16) down to lines containing `address=AL-Eatimad` and writes them to `output.txt`. | **Legacy/duplicate.** Its filtering logic is superseded by the more robust encoding-detection version inside `process_messages.py`. Not part of any active pipeline. |
| `requirements.txt` | Lists runtime dependencies: `fastapi`, `uvicorn[standard]`, `requests`, `charset_normalizer`, `PyMuPDF`. | Active, but **no versions are pinned** — see [Section 5](#5-dependencies). |
| `render.yaml` | Render.com deploy config. Declares a free-tier web service and a `startCommand`. | Active, but its `startCommand` **does not currently match the working local invocation** — see [Section 4](#4-runtime--how-to-run-locally). |
| `README.md` | This file. | Documentation only. |
| `jsons/` | Archived output from earlier manual runs. Only a `mismatched/` subfolder currently exists in this directory; the `correctly matched/` tree was removed in a repo cleanup. | Data, not code. Not written to or read from by the live HTTP service — only referenced by the utility scripts above. |

## 4. Runtime / How to Run Locally

The working local invocation, verified against the current code, is to run uvicorn **from the repository root**, targeting the fully-qualified module path:

```
python -m uvicorn invoice_processor.main:app --host 0.0.0.0 --port 10000
```

or equivalently:

```
uvicorn invoice_processor.main:app --host 0.0.0.0 --port 10000
```

Once running, interactive API docs are available at:

```
http://localhost:10000/docs
```

### Known `render.yaml` issue (documented, not fixed here)

`render.yaml` currently specifies:

```yaml
startCommand: uvicorn main:app --host 0.0.0.0 --port 10000
```

Local verification shows **this exact command does not work** with the project's current import structure, regardless of which directory it's run from:

- Run from `invoice_processor/` (so that `main` resolves as a module): fails with `ModuleNotFoundError: No module named 'invoice_processor'`, because `main.py` imports its own sibling modules via the absolute path `invoice_processor.parse_invoice...`, `invoice_processor.models...`, etc., which requires the **repository root** to be on the Python path.
- Run from the repository root (so that path is importable): fails with `ModuleNotFoundError: No module named 'main'`, because there is no `main.py` at the repository root — it lives at `invoice_processor/main.py`.

The command that **does** work, confirmed locally, is:

```
uvicorn invoice_processor.main:app --host 0.0.0.0 --port 10000
```

run from the repository root. This is very likely the correct fix for `render.yaml`, but **this has not been changed in this update** and should be verified against the actual Render dashboard/deployment configuration before assuming the live service is affected — Render's dashboard settings can override `render.yaml`, and this repo alone cannot confirm what is actually configured there or whether the live service is currently reachable.

## 5. Dependencies

From `requirements.txt`:

```
fastapi
uvicorn[standard]
requests
charset_normalizer
PyMuPDF
```

Main runtime dependencies and what they're used for:

- **FastAPI** — the web framework; defines `app` and the two HTTP endpoints in `main.py`.
- **Uvicorn** — the ASGI server used to run the FastAPI app.
- **requests** — used to download the invoice PDF from the caller-supplied URL, and (in the now-unused `send_invoices.py`) to POST to the backend.
- **PyMuPDF (`fitz`)** — used to open PDFs and extract their text layer in `convert_invoice.py`.
- **charset_normalizer** — used only by the utility script `invoice_processor/utils/process_messages.py` to detect the encoding of the exported SMS log file. Not used by the live HTTP service.

Notes:

- **No dependency versions are pinned** in `requirements.txt` — every package resolves to whatever is "latest" at install time. This means the exact behavior of the service (especially anything Pydantic-version-sensitive) can vary between installs unless this is addressed separately.
- **Pydantic** is not listed directly in `requirements.txt` — it is pulled in transitively as a dependency of FastAPI.
- The current `invoice_processor/models/schemas.py` is written with **Pydantic v2-compatible configuration** (`populate_by_name = True`, `from_attributes = True` inside each model's `class Config`), verified directly from the source. This is the correct, non-deprecated way to configure these options under Pydantic v2, as opposed to the old v1-style `allow_population_by_field_name`/`orm_mode` keys.

## 6. HTTP API

This service exposes exactly two HTTP endpoints. Neither requires authentication, and neither calls any backend or writes to disk beyond the request-scoped temp PDF file (deleted before the response is returned).

### POST `/process-invoice`

**Purpose:** Parse an invoice PDF from a URL and return structured invoice JSON. Does not persist or forward the result anywhere.

**Request body:**

```json
{
  "url": "https://example.com/invoice.pdf",
  "originalId": null
}
```

- `url` (string, required) — a URL this service will fetch server-side with `requests.get(url, timeout=10)`. There is currently no restriction on scheme, host, or content type, and no size limit on the downloaded content (see [Section 10](#10-security--privacy-notes)).
- `originalId` (integer, optional) — accepted by the request schema but **not used** by this endpoint. It only has an effect on `/fix-mismatched` (see below).

**Success response — `200 OK`:**

```json
{
  "id": null,
  "date": "2025-02-25T09:17:15",
  "netTotal": 1140.0,
  "total": 1140.0,
  "worksiteName": "قرب الهباش",
  "worksiteId": null,
  "items": [
    {
      "description": "ﻣﻌﺠﻮﻧﺔ ﻣﺠﻚ ﺑﻮﻧﺪ ﻃﻤﺒﻮﺭ ﻛﻴﻠﻮ25",
      "quantity": 2.0,
      "unit_price": 55.0,
      "total_price": 110.0,
      "materialId": null
    }
  ],
  "totalMatch": true,
  "pdfUrl": "https://example.com/invoice.pdf",
  "confirmed": false,
  "parsedAt": "2026-07-01T10:03:33.795394",
  "reprocessedFromId": null
}
```

This exact shape (top-level fields in camelCase, but `unit_price`/`total_price` inside each item in snake_case) was verified live against the current code — see [Section 7](#7-field-casing) for the full explanation and a complete field-by-field table.

**Error responses:**

- `400 Bad Request` — the PDF could not be downloaded (bad URL, network error, non-2xx response, timeout):
  ```json
  { "detail": "Failed to download PDF: <underlying error>" }
  ```
- `500 Internal Server Error` — parsing raised an exception (e.g. the file isn't a valid PDF):
  ```json
  { "detail": "Failed to process PDF: <underlying error>" }
  ```
- `500 Internal Server Error`, **opaque, plain-text `"Internal Server Error"` body (not JSON)** — this happens if the parsed data fails to satisfy the `PendingInvoice` response schema (for example, if `date`, `netTotal`, or `worksiteName` came back empty/`None` because the PDF didn't match the expected template). This failure happens in FastAPI's own response-serialization step, **outside** this endpoint's `try/except`, so it does not produce the same structured `{"detail": ...}` body as the other error cases. This is a known, currently-unhandled edge case — see [Section 9](#9-known-limitations).

### POST `/fix-mismatched`

**Purpose:** Re-download and re-parse an invoice PDF, then attempt to reconcile item quantities when the computed total doesn't match the printed total. Also does not persist or forward the result anywhere — it only returns JSON.

**Request body:** identical shape to `/process-invoice`:

```json
{
  "url": "https://example.com/invoice.pdf",
  "originalId": 123
}
```

- `originalId` (integer, optional) — if provided, and the parsed invoice doesn't already have a `reprocessedFromId`, this endpoint sets `reprocessedFromId` to `originalId` and drops any `id` field from the parsed data. This is meant to let a caller track "this JSON is a reprocessed version of pending invoice #123."

**Behavior:**

1. Downloads and parses the PDF exactly like `/process-invoice`.
2. Sets `reprocessedFromId` from `originalId` if applicable.
3. Calls `fix_mismatched_invoice()`, which recomputes each item's quantity as `total_price / unit_price` (rounded), and recalculates `totalMatch`.
4. Tags `pdfUrl` / `confirmed` / `parsedAt`.
5. **If the invoice is already matched (`totalMatch: true`) and no `originalId` was supplied**, it returns immediately without further changes — this is meant to avoid pointless reprocessing.
6. Otherwise, it returns the (possibly corrected) invoice JSON.

**This endpoint does not call any backend and does not save anything to disk.** It is purely "take a PDF, try to fix its numbers, return the result" — whatever calls this endpoint is responsible for deciding what to do with the corrected JSON (e.g., overwrite a previously-saved pending invoice).

**Success response — `200 OK`:** same `PendingInvoice` shape as `/process-invoice`.

**Error responses:**

- `400 Bad Request` — same PDF-download failure case as above.
- `500 Internal Server Error` — structured, `{"detail": "Failed to fix mismatched invoice: <underlying error>"}`. Unlike `/process-invoice`, this endpoint constructs the `PendingInvoice` object explicitly inside its own `try/except`, so a schema-validation failure here **does** produce this structured error body rather than an opaque plain-text 500.

## 7. Field Casing

The current response schema uses a **deliberately mixed casing convention**, confirmed by reading `invoice_processor/models/schemas.py` and by live testing:

- **Invoice-level fields are camelCase**, with no aliasing — the Pydantic field name is exactly what appears in the JSON: `date`, `netTotal`, `total`, `worksiteName`, `worksiteId`, `totalMatch`, `pdfUrl`, `confirmed`, `parsedAt`, `reprocessedFromId`, `id`.
- **Item-level `unit_price` and `total_price` are snake_case in the JSON**, even though the Pydantic field names internally are `unitPrice`/`totalPrice`. This is done via Pydantic `Field(..., alias="unit_price")` / `Field(..., alias="total_price")`, and FastAPI serializes response models using their aliases by default — so the wire format ends up snake_case for these two fields specifically. This was a deliberate choice (per this project's commit history), not an oversight — but it means item-level and invoice-level fields use different casing conventions in the same payload.

Full field table:

| Field | JSON key returned | Required? | Notes |
|---|---|---|---|
| id | `id` | No (default `null`) | Never populated by the parser itself; passthrough only |
| date | `date` | **Yes** | Parser sets this from a `DD/MM/YYYY HH:MM:SS` match on the PDF text; if not found, stays `null` and **fails schema validation** |
| net total | `netTotal` | **Yes** | Falls back to `total` if no separate net-total line is found; if neither is found, stays `null` and **fails schema validation** |
| total | `total` | No (default `null`) | Tolerates a missing/failed extraction without breaking the response |
| worksite name | `worksiteName` | **Yes** | Defaults to the literal string `"other"` if no worksite marker is found, so this rarely ends up `null` in practice |
| worksite id | `worksiteId` | No (default `null`) | Never populated by the parser itself; passthrough only |
| items | `items` | Yes (can be an empty list) | See item table below |
| total match | `totalMatch` | No (default `null`) | `true`/`false` once computed; tolerates missing/`null` |
| pdf url | `pdfUrl` | **Yes** | Always set by `main.py` from the request's `url` before returning |
| confirmed | `confirmed` | **Yes** | Always set to `false` by `main.py` before returning |
| parsed at | `parsedAt` | No (default `null`) | Always set by `main.py` in practice, but tolerates `null`/missing at the schema level |
| reprocessed from id | `reprocessedFromId` | No (default `null`) | Only set by `/fix-mismatched` when `originalId` is supplied |

Item-level fields (inside `items[]`):

| Field | JSON key returned | Required? | Notes |
|---|---|---|---|
| description | `description` | Yes | Free text, extracted/cleaned from the PDF line(s) |
| quantity | `quantity` | Yes | Float; inferred via several regex heuristics if not explicitly printed |
| unit price | `unit_price` | Yes | snake_case in JSON — see explanation above |
| total price | `total_price` | Yes | snake_case in JSON — see explanation above |
| material id | `materialId` | No (default `null`) | Never populated by the parser itself; passthrough only |

**Not present anywhere in the current response schema:** supplier/vendor name, tax, discount, currency, or any confidence score beyond the boolean `totalMatch`.

## 8. Python ↔ Backend Relationship

This is a significant point to understand about the current state of the tool:

- **This service does not POST anything to any backend today.** Both endpoints only ever return a JSON HTTP response.
- A hardcoded call to an external backend (`send_invoice_to_api`, POSTing to `https://intfitout-backend-production.up.railway.app/api/invoices/pending/upload`) **used to exist** in `/process-invoice`, but that call is now commented out in `main.py`. It is also commented out in `/fix-mismatched`.
- The function itself, `send_invoice_to_api` in `invoice_processor/send_invoices.py`, **still exists and is still imported** by `main.py`, but is **dead code** — nothing in the current codebase calls it.
- Because of this, **whoever calls `/process-invoice` or `/fix-mismatched` is now fully responsible for persisting the returned JSON.** This service has no memory of, and no further interaction with, any invoice after it returns the HTTP response.
- **This repository alone cannot confirm whether the backend has been updated to reflect this.** If the backend previously relied on this Python service to push data on its own, and hasn't been updated to instead call these endpoints and save the response itself, invoices may currently not be getting persisted anywhere. This needs to be confirmed against the backend codebase directly — see [Section 11](#11-open-backend-questions).

## 9. Known Limitations

- **Single-template parser.** The extraction logic (skip-word list, `ملاحظات` worksite marker, `المجموع`/`الصافي` totals labels) is hardcoded to one specific Arabic invoice layout. Any other invoice format is likely to parse incorrectly, silently.
- **First page only.** `process_invoice_pdf` only reads `doc[0]` — a multi-page invoice's later pages are never read.
- **Text-layer PDFs only.** There is no OCR fallback; a scanned/image PDF with no embedded text layer will yield little or no extractable content.
- **Required fields can legitimately come back empty.** `date`, `netTotal`, and `worksiteName` (in practice, less so — see the table above) are non-optional in the response schema, but the parser can produce `None` for `date`/`netTotal` if the PDF doesn't match the expected layout. When that happens, `/process-invoice` returns an opaque, plain-text `500 Internal Server Error` (not the usual structured `{"detail": ...}` body), because the failure happens during FastAPI's own response validation rather than inside the endpoint's `try/except`. `/fix-mismatched` handles the same failure mode more gracefully, returning a structured `{"detail": "...validation error..."}`.
- **No authentication, no rate limiting, no CORS configuration** on either endpoint.
- **Server-side URL fetch with no restrictions** — `requests.get(req.url, ...)` will fetch any URL the caller supplies, with no scheme/host allow-list, no content-type check, and no size cap on the response before it's written to a temp file and opened as a PDF.
- **No environment-variable configuration.** The backend URL (in the now-dead `send_invoices.py`) and every parsing constant are hardcoded in source; nothing is configurable without editing code.
- **Unpinned dependencies.** `requirements.txt` has no version pins, so the exact installed versions (and therefore some edge-case behaviors) can vary between environments/deployments.
- **Verbose, unstructured logging.** The parser and endpoints print extensive debug output (including full invoice contents — worksite names, item descriptions, totals) to stdout via `print()`, not a proper logging framework. On a machine/console using a non-UTF-8 default encoding, printing the Arabic text embedded in these log lines can raise a `UnicodeEncodeError`, which will surface as a request failure.
- **No automated tests** exist in this repository.

## 10. Security / Privacy Notes

- **No authentication** on `/process-invoice` or `/fix-mismatched` — anyone who can reach a deployed instance of this service can call them.
- **No CORS policy** is configured.
- **Potential SSRF surface**: both endpoints perform a server-side `requests.get()` against a caller-supplied URL with no scheme/host restrictions, no content-type validation, and no response-size cap.
- **No secrets or API keys** exist anywhere in this repository.
- **A hardcoded backend URL** remains in `invoice_processor/send_invoices.py`, though it is currently unreachable dead code.
- **Business-sensitive data in logs**: worksite names, item descriptions, and totals are printed to stdout in multiple places. If deployment logs are retained or aggregated, this invoice content is retained along with them.
- **Temp files**: each request writes the downloaded PDF to a system temp file (`tempfile.NamedTemporaryFile(delete=False, ...)`) and deletes it in a `finally` block after parsing. Under normal operation this cleanup succeeds; it is not guarded separately from the rest of the request's error handling.

## 11. Open Backend Questions

These cannot be answered from this repository alone and should be confirmed against the backend codebase/team before relying on this service in production:

1. Does the backend currently call `/process-invoice` and then save the returned JSON itself? If not, invoices parsed by this service may not be getting persisted anywhere right now.
2. Does the backend call `/fix-mismatched` and save its returned JSON? This endpoint has never saved its own output, even in older versions of this service.
3. Is `https://intfitout-backend-production.up.railway.app/api/invoices/pending/upload` (referenced in the now-unused `send_invoices.py`) still an active backend endpoint, or is it legacy?
4. What exact field casing does the backend's deserializer expect? The current output mixes camelCase (invoice-level) and snake_case (`unit_price`/`total_price` at the item level) — this needs to be confirmed as intentional and compatible with the backend, not assumed.
5. Is `render.yaml`'s `startCommand` actually what Render uses to run the live service, or does a dashboard-configured command override it? This determines whether the deployed service is currently reachable at all.

## 12. Legacy / Utility Scripts

None of the scripts below are part of the live FastAPI service (`main.py` does not import or invoke any of them). They are standalone, run-manually scripts, and — based on the current code — none of them should be trusted to work correctly until repaired.

### `invoice_processor/utils/process_messages.py`

- **Intended purpose:** Read an exported SMS/message log, find rows from a specific sender containing invoice-download links, download each linked PDF, and run it through the parser.
- **Part of the live service?** No.
- **Current status: broken.** It calls `process_invoice_pdf(pdf_path, "pdfs", "jsons")` with three positional arguments, but `process_invoice_pdf` currently only accepts one (`input_file`). Running this script as-is raises `TypeError` immediately, before it gets anywhere near actually processing a PDF.
- **Why not to trust it:** Its call into the parser has not been kept in sync with the parser's current signature. It needs to be updated to call `process_invoice_pdf(pdf_path)` only, and its file-saving assumptions (it also assumes the parser still writes files, which it no longer does) need to be re-checked before use.

### `invoice_processor/utils/t.py`

- **Intended purpose:** A quick one-off filter — reads `messages.txt` (hardcoded as UTF-16), keeps only lines containing `address=AL-Eatimad`, and writes them to `output.txt`.
- **Part of the live service?** No.
- **Current status: legacy/duplicate.** Its logic is a cruder subset of what `process_messages.py` already does (with better encoding auto-detection via `charset_normalizer`).
- **Why not to trust it:** It hardcodes the input encoding as UTF-16, which will silently produce garbage or throw a decode error if the actual export encoding differs. It has no error handling and is not part of any documented workflow — treat it as scratch-work left in the repo, not a maintained tool.

### `invoice_processor/utils/move_mismatched_invoices.py`

- **Intended purpose:** Scan a folder of previously-saved "correctly matched" invoice JSON files and move any whose `total_match`/`totalMatch` flag is `False` into a separate "mismatched" folder.
- **Part of the live service?** No.
- **Current status: broken.** It computes its source/target folders relative to its own script location (`invoice_processor/utils/jsons/correctly matched` and `.../jsons/mismatched`), but no `jsons/` folder exists under `invoice_processor/utils/` at all — the real data lives at the repository root (`jsons/`). As written, it will either find nothing to move or raise `FileNotFoundError`.
- **Why not to trust it:** Beyond the wrong path, this script executes its entire logic at import time (it is not wrapped in `if __name__ == "__main__":`), so simply importing this module runs it. Combined with the wrong path, this makes it unsafe to touch until both issues are fixed.

### `invoice_processor/utils/move_matched_back.py`

- **Intended purpose:** The reverse of the above — after a previously-mismatched invoice has been manually corrected, move its JSON file back from the "mismatched" folder into "correctly matched".
- **Part of the live service?** No.
- **Current status: broken**, for the same reason as `move_mismatched_invoices.py` — it looks for `jsons/...` relative to `invoice_processor/utils/`, which doesn't exist there.
- **Why not to trust it:** Same wrong-path issue as above. Unlike `move_mismatched_invoices.py`, its logic is wrapped in a function (`move_matched_back()`) rather than running at import time, so importing it is safe, but calling that function will not find the real data.

## 13. Deployment Notes

- **Hosting style:** a single FastAPI application served by Uvicorn (ASGI). No worker/queue processes, no scheduled jobs, no database connections in the live request path.
- **Port:** the service is intended to listen on port `10000` (per `render.yaml` and the documented run command).
- **Working local command** (see [Section 4](#4-runtime--how-to-run-locally) for full detail):
  ```
  uvicorn invoice_processor.main:app --host 0.0.0.0 --port 10000
  ```
  run from the repository root.
- **`render.yaml` concern (documented, not fixed):** its `startCommand` (`uvicorn main:app --host 0.0.0.0 --port 10000`) does not match the working invocation above and fails locally regardless of working directory — see Section 4 for the exact errors reproduced.
- **No database** is used or required by this service.
- **No persistent storage is required for normal API calls.** Both endpoints are stateless: they download a PDF, parse it in memory, and return JSON. Nothing needs to survive between requests.
- **Temp PDFs are per-request only.** Each call to `/process-invoice` or `/fix-mismatched` writes the downloaded PDF to a system temp file and deletes it before the response is returned (or in the `finally` block if an error occurs). No temp file is expected to persist across requests.
- **The actual Render dashboard configuration has not been verified.** It's possible the live deployment uses a dashboard-configured start command that differs from `render.yaml` and actually works — this should be checked directly in Render before assuming the deployed service is broken or working either way.

## 14. Development Notes

Guidance for anyone changing this codebase going forward:

- **Preserve the current JSON contract** (field names, casing, required/optional-ness) unless the backend and/or frontend are updated in the same change. Nothing in this repository enforces contract compatibility automatically — a silent field rename here can silently break a caller.
- **Do not re-enable direct backend posting from Python** (i.e., un-comment `send_invoice_to_api` calls in `main.py`) without explicitly deciding, and documenting, that this is the intended architecture again. The current design is "Python returns JSON, caller persists it" — reverting to "Python also pushes to the backend" would reintroduce a second, harder-to-reason-about save path.
- **Add tests and fixtures before changing parser behavior.** There are currently no automated tests and no sample PDF fixtures in this repository (the originals were removed in a repo cleanup) — changing `convert_invoice.py`'s regex/keyword logic today is effectively unverifiable without first adding a representative sample PDF and a test harness.
- **Be careful with Arabic text normalization and PDF extraction order.** The parser depends on `unicodedata.normalize("NFKC", ...)` and a specific line-by-line extraction order from PyMuPDF; changes to either can silently shift how the skip-word matching and item-boundary detection behave.
- **Avoid logging sensitive invoice data in production.** The current code prints full invoice contents (worksite names, item descriptions, totals) to stdout in several places — any future logging changes should actively reduce this, not add to it.
- **Backend integration must be checked before changing field names.** Because this service's only "contract" with its caller is the returned JSON shape, any rename (e.g. `worksiteName` → `worksite_name`) needs to be coordinated with whatever currently consumes this API.
- **Treat `unit_price` and `total_price` casing as part of the current public contract.** These two fields are deliberately snake_case in the JSON output even though every other field is camelCase (see [Section 7](#7-field-casing)) — this looks like an inconsistency but is intentional per this project's history; don't "fix" it to camelCase without confirming the backend doesn't depend on the current casing.

## 15. Future Improvement Ideas

Practical, non-committal ideas for future work (none of this has been done in this update):

- Add safe, synthetic or anonymized sample PDF fixtures to the repository for testing.
- Add an automated test suite covering the parser, schemas, and both endpoints.
- Fix `render.yaml`'s `startCommand` to match the working invocation (after verifying against the actual Render dashboard settings).
- Remove or repair the broken utility scripts (`process_messages.py`, `move_mismatched_invoices.py`, `move_matched_back.py`).
- Remove `send_invoices.py`, or clearly mark/relocate it as legacy/reference-only code, since it is currently dead but still imported.
- Add authentication (e.g. an API key or shared secret) or otherwise restrict which callers can reach these endpoints.
- Add a URL allow-list or other SSRF protection around the server-side PDF download.
- Add content-type and file-size validation before treating a downloaded response as a PDF.
- Improve error responses for the missing-`date`/`netTotal`/`worksiteName` case so `/process-invoice` returns a structured error instead of an opaque plain-text 500.
- Support multi-page PDFs instead of only reading the first page.
- Optionally support OCR as a fallback for scanned/image-only invoices.
- Replace ad-hoc `print()` debugging with structured logging (with configurable levels).
- Avoid including raw invoice data (worksite names, item descriptions, totals) in logs.
- Pin dependency versions in `requirements.txt`.
- Add CI (lint/test) for this project.

## 16. Quick Reference

- **Run locally:**
  ```
  uvicorn invoice_processor.main:app --host 0.0.0.0 --port 10000
  ```
  (from the repository root)
- **Docs URL:** `http://localhost:10000/docs`
- **Endpoints:**
  - `POST /process-invoice` — parse a PDF from a URL, return JSON, no persistence
  - `POST /fix-mismatched` — re-parse and attempt to reconcile quantities, return JSON, no persistence
- **Request example (both endpoints):**
  ```json
  { "url": "https://example.com/invoice.pdf", "originalId": null }
  ```
- **Response shape note:** invoice-level fields are camelCase (`netTotal`, `worksiteName`, `totalMatch`, `pdfUrl`, `parsedAt`, ...); item-level `unit_price`/`total_price` are snake_case. See [Section 7](#7-field-casing) for the full table.
