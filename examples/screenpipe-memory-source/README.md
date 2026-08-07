# Screenpipe Memory Source

This example syncs local [Screenpipe](https://screenpi.pe) OCR and audio transcript rows into Mem0.

Screenpipe stores its local timeline in SQLite at `~/.screenpipe/db.sqlite`. The sync script reads common tables such as `frames`, `ocr_text`, and `audio_transcriptions`, converts each row into a Mem0 memory, and preserves useful source metadata for later filtering.

## Install

```bash
pip install mem0ai
```

For Mem0 Platform:

```bash
export MEM0_API_KEY="m0-..."
```

For Mem0 OSS, prepare a Mem0 config JSON and pass it with `--config`.

## Dry Run

```bash
python examples/screenpipe-memory-source/sync_screenpipe.py \
  --user-id alice \
  --limit 5 \
  --dry-run
```

## Sync to Mem0 Platform

```bash
python examples/screenpipe-memory-source/sync_screenpipe.py \
  --user-id alice \
  --limit 50
```

## Sync to Mem0 OSS

```bash
python examples/screenpipe-memory-source/sync_screenpipe.py \
  --config mem0-config.json \
  --user-id alice \
  --limit 50
```

By default, entries are added with `infer=False` so the original screen or transcript observation remains searchable. Pass `--infer` if you want Mem0 to extract concise facts from each observation instead.
