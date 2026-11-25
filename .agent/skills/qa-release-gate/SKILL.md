---
name: qa-release-gate
description: Lensetek QA release gate skill that always checks the Obsidian Vault rule of thumb before verifying What's New, landing page sync, CLI-WebUI parity, credential safety, and commit/push confirmation
---

# QA Release Gate & Vault Compliance

Always execute this checklist before finalizing a release or asking to commit/push:

1. **Read the Obsidian Vault Rule of Thumb First:**
   - Read `C:\Users\ACER\Documents\Obsidian Vault\Lensetek-Rule-of-Thumb.md` to ensure all latest project rules are followed.
2. **Verify Version & What's New (`cli-agent/version.json`, `cli-agent/version.py`):**
   - Version and `release_date` must match across both files.
   - Default `changelog` / What's New must be in **English** and focused strictly on **app features and fixes** (not landing page tweaks).
3. **Verify Landing Page & Docs Sync:**
   - When there is a new What's New / release, check `index.html`, `docs/index.html`, and `README.md` for updates while preserving responsive mobile-view-first design.
4. **Verify CLI & WebUI Parity:**
   - Confirm every slash command in `cli-agent/i18n.py` (`get_localized_slash_items`) is handled in `plugins/webui/server.py` and `cli-agent/main.py`.
5. **Verify Installer & Credential Safety:**
   - Confirm `install.ps1` / `install.sh` handle locked processes and partial installs cleanly.
   - Confirm no credentials, `.env`, or keys are exposed client-side or staged in git.
6. **Run Checks & Ask Confirmation:**
   - Run `py_compile` / syntax checks and report PASS/FAIL per item. Never `git commit` or `git push` without explicit user confirmation.
