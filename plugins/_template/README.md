# 🧩 Lensetek Plugin Template & Contributor Guide

Welcome to the **Lensetek Agent Harness** plugin ecosystem! Plugins allow you to extend the capabilities of the agent harness without bloating the lean core installer.

---

## 📁 Plugin Anatomy

A standard Lensetek plugin lives in its own subdirectory inside `plugins/<plugin-id>/` and contains:

1. **`plugin.json`** *(Required)*: Metadata, version, author, dependencies, and permissions.
2. **`main.py`** *(Required)*: Main entry point providing lifecycle hooks (`on_load`, `on_unload`) and tool definitions (`register_tools`).
3. **`__init__.py`** *(Required)*: Python package exports.
4. **`requirements.txt`** *(Optional)*: Additional Python packages needed by the plugin.
5. **`README.md`** *(Recommended)*: Documentation and usage examples.

---

## 🚀 Lifecycle Hooks & Extensibility

### 1. `on_load(context: dict) -> bool`
Called when the user or harness activates the plugin. Use this to prepare databases, start background local services, or verify prerequisites.

### 2. `on_unload(context: dict) -> None`
Called when the plugin is deactivated or the CLI exits. Clean up any open sockets, background workers, or temporary files.

### 3. `register_tools() -> list[dict]`
Return standard tool schemas that the local LLM agent can call dynamically during multi-step reasoning.

---

## 🔒 Security & Best Practices

1. **Workspace Boundary**: Never write outside the active project workspace unless explicitly requested by the user.
2. **Credential Protection**: Never leak or log `.env`, `.git/`, tokens, or credentials into client-side code, logs, or LLM prompts.
3. **Responsive UI (Mobile-First)**: If your plugin provides a web interface, ensure it is responsive and works smoothly on mobile devices.

---

## 🤝 How to Contribute Your Plugin

1. Copy this template folder to `plugins/<your-plugin-id>/` (or use `/plugins create <your-plugin-id>`).
2. Implement your tool or server logic in `main.py`.
3. Test locally using `/plugins` inside the CLI agent.
4. Register your plugin entry in `plugins/manifest.json`.
5. Submit a Pull Request to `https://github.com/lensetek-int/local-agent-harness`!
