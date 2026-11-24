"""
Lensetek Plugin Entry Point Template
Customize this module to extend the harness capabilities.
"""

from typing import Any, Dict, List

def on_load(context: Dict[str, Any]) -> bool:
    """
    Lifecycle hook called when the plugin is initialized.
    context includes:
      - 'workspace': Current Path of the active workspace
      - 'lang': Active language ('en', 'id', 'cn')
      - 'config': Application configuration
    Return True if initialization succeeded, False otherwise.
    """
    workspace = context.get("workspace")
    lang = context.get("lang", "en")
    print(f"[Plugin] Loaded template plugin in workspace: {workspace} ({lang})")
    return True

def on_unload(context: Dict[str, Any]) -> None:
    """
    Lifecycle hook called when the plugin is disabled or application exits.
    Use this to terminate background workers, close sockets, or clean up temp files.
    """
    pass

def register_tools() -> List[Dict[str, Any]]:
    """
    Register custom agent tools that the local LLM can invoke.
    Each tool returns a schema dict compatible with OpenAI/Llama function calling.
    """
    return [
        {
            "name": "example_custom_tool",
            "description": "Example custom tool provided by this plugin",
            "parameters": {
                "type": "object",
                "properties": {
                    "input_text": {
                        "type": "string",
                        "description": "Input text to process"
                    }
                },
                "required": ["input_text"]
            },
            "handler": handle_example_tool
        }
    ]

def handle_example_tool(args: Dict[str, Any], context: Dict[str, Any]) -> str:
    """
    Execution logic for 'example_custom_tool'.
    Always sanitize inputs and avoid credential leaks.
    """
    input_text = args.get("input_text", "")
    return f"Processed input: '{input_text}' via template plugin."
