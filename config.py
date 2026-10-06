import os
from dotenv import load_dotenv
load_dotenv()

HF_MODEL = os.getenv("HF_MODEL", "Qwen/Qwen2.5-1.5B-Instruct")
USE_MOCK_MCP = os.getenv("USE_MOCK_MCP", "1") == "1"
RATE_LIMIT_PER_MIN = int(os.getenv("RATE_LIMIT_PER_MIN", "30"))
DB_PATH, AUDIT_LOG = "memory.db", "audit.jsonl"
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")

MCP_SERVERS = {
    "google":  {"command": "npx", "args": ["-y", "@modelcontextprotocol/server-google-calendar"]},
    "outlook": {"command": "npx", "args": ["-y", "outlook-mcp-server"]},
    "slack":   {"command": "npx", "args": ["-y", "@modelcontextprotocol/server-slack"],
                "env": {"SLACK_BOT_TOKEN": os.getenv("SLACK_BOT_TOKEN", "")}},
}

TOOL_MAP = {
    "list_events":  ("google", "list-events"),
    "create_event": ("google", "create-event"),
    "send_email":   ("outlook", "send-email"),
    "read_email":   ("outlook", "list-emails"),
    "post_slack":   ("slack", "slack_post_message"),
}
