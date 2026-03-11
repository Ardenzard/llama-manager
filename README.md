# Llama Manager

A GUI controller for [llama.cpp](https://github.com/ggerganov/llama.cpp) servers and [Open WebUI](https://github.com/open-webui/open-webui), with a built-in pipeline for downloading, converting, and quantising HuggingFace models.

> **⚠️ Vibe Coded**
> This project was entirely vibe coded. The code works for my use case but has not been rigorously reviewed or hardened. Use it at your own risk, expect rough edges, and feel free to improve it.

---

## Features

| Tab | What it does |
|-----|-------------|
| **Models** | Add, remove, edit, and toggle GGUF model entries. Changes are saved to `app_config.json` and the optional `models.ini` for llama-server. |
| **Pipeline** | One-click workflow: download a HuggingFace model → convert to GGUF (via `convert_hf_to_gguf.py`) → quantise (via `llama-quantize`). Runs in the background with per-step progress bars. |
| **Settings** | Configure all paths, server flags, and UI preferences. Supports Dark Modern and Classic themes. |

---

## Requirements

- Python 3.10+
- `tkinter` (ships with most Python installs; on Linux: `sudo apt install python3-tk`)
- `requests` — only required for the Pipeline downloader

```
pip install requests
```

Optional:
- `huggingface_hub` — enables automatic HF token authentication

---

## Installation

```bash
git clone https://github.com/your-username/llama-manager.git
cd llama-manager
pip install requests          # optional but recommended
```

---

## Usage

**Windows**
```
start.bat
```
or
```
python -m llama_manager
```

**Linux / macOS**
```
python -m llama_manager
```

---

## Configuration

On first launch, `app_config.json` is created in the working directory with
blank path fields.  Fill them in via **Settings → Server & Llama.cpp Settings**
and click **Save Settings**.

| Key | Description |
|-----|-------------|
| `llama_server_path` | Path to `llama-server` (or `llama-server.exe`) |
| `open_webui_path` | Path to the Open WebUI executable inside its venv |
| `models_ini_path` | Path to `models.ini` consumed by `llama-server --models-preset` |
| `host` | Bind address for both servers (default `127.0.0.1`) |
| `llama_port` | llama-server port (default `5001`) |
| `webui_port` | Open WebUI port (default `5002`) |
| `api_key` | API key passed to llama-server |
| `threads` | CPU thread count (`-t` flag) |
| `ngl` | GPU layers (`-ngl`); use `auto` to let the server decide |

Pipeline paths are configured separately under **Settings → Pipeline Paths**.

---

## Running Tests

```bash
python -m pytest tests/
```

Or with the built-in runner:

```bash
python -m unittest discover tests/
```

---

## Project Structure

```
llama_manager/          Python package
├── __init__.py
├── __main__.py         Entry point (python -m llama_manager)
├── app.py              LlamaManagerApp — main window and all tabs
├── config.py           LlamaConfigManager + DEFAULT_CONFIG
├── constants.py        QUANTS, HF_BASE, pipeline path defaults
├── downloader.py       ModelDownloader — HuggingFace download with resume
├── themes.py           MODERN_THEME, CLASSIC_THEME, THEMES registry
└── widgets.py          ThemedButton canvas widget
tests/
├── test_config.py
├── test_constants.py
├── test_downloader.py
└── test_themes.py
start.bat               Windows launcher
```

---

## License

MIT — see `LICENSE` for details.
