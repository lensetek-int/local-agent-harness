# Lensetek Project Rules & Release Workflow

1. **Commit & Push Confirmation:** Never run `git commit` or `git push` unless the user explicitly asks or confirms first. Always verify no credentials, `.env`, or sensitive files are staged.
2. **What's New & Versioning (`cli-agent/version.json`, `cli-agent/version.py`):**
   - Keep default `changelog` / What's New entries in **English** and synchronized between `version.json` and `version.py`.
   - Focus What's New strictly on **app capabilities, bug fixes, and stability** (CLI, WebUI, Installer, Downloader), NOT landing page tweaks.
   - Bump the version (e.g. `0.3.0` -> `0.3.1`) and `release_date` when releasing user-facing fixes so `lensetek --update` / `/update` detects them.
3. **Landing Page Sync on What's New:** Whenever a new version / What's New is released, check and update the landing page (`index.html`, `docs/index.html`) and `README.md` (preserving responsive mobile-view-first design).
4. **CLI & WebUI Parity:** Every slash command listed in `cli-agent/i18n.py` (`get_localized_slash_items`) must be handled in both `cli-agent/main.py` and `plugins/webui/server.py` (`_handle_slash_command`).
5. **End-User Resilience:** Keep `install.ps1` / `install.sh` self-healing (stop locked `llama-server`/WebUI processes, validate `cli-agent/main.py`, fallback to ZIP on git failure), and verify syntax/tests before reporting done.
