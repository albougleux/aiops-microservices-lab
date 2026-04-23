import os
import requests

def _send_discord_webhook(webhook_url, username, avatar_url, embed_title, embed_color, report, latency, total_tokens, footer_text):
    """
    Internal base function to handle the Discord API request and payload construction.
    """
    if not webhook_url:
        print(f"[INFO] Webhook URL for {username} not configured. Skipping ChatOps alert.")
        return

    safe_report = report
    if len(report) > 4000:
        safe_report = report[:4000] + "\n\n... [REPORT TRUNCATED DUE TO DISCORD LIMITS]"

    payload = {
        "username": username,
        "avatar_url": avatar_url,
        "embeds": [
            {
                "title": embed_title,
                "color": embed_color,
                "description": f"```markdown\n{safe_report}\n```",
                "fields": [
                    {"name": "⏱️ Diagnosis Time", "value": f"{latency}s", "inline": True},
                    {"name": "🪙 Tokens Used", "value": f"{total_tokens}", "inline": True}
                ],
                "footer": {"text": footer_text}
            }
        ]
    }
    
    try:
        response = requests.post(webhook_url, json=payload)
        response.raise_for_status()
        print(f"✅ [CHATOPS] Alert successfully sent to Discord via {username}!")
    except Exception as e:
        print(f"❌ [ERROR] Failed to send alert to Discord: {e}")


def send_event_alert_to_discord(report, latency, total_tokens):
    """Sends the Event-Driven (Prometheus Trigger) diagnostic report to Discord."""
    _send_discord_webhook(
        webhook_url=os.environ.get("DISCORD_WEBHOOK_URL"),
        username="AIOps Triage Bot (Event-Driven)",
        avatar_url="https://cdn-icons-png.flaticon.com/512/4712/4712010.png",
        embed_title="🚨 SRE Incident Diagnosed",
        embed_color=16711680,  # Red
        report=report,
        latency=latency,
        total_tokens=total_tokens,
        footer_text="AIOps FinOps Agent (Event-Driven Mode)"
    )


def send_continuous_alert_to_discord(report, latency, total_tokens):
    """Sends the Continuous Analysis anomaly report to Discord."""
    _send_discord_webhook(
        webhook_url=os.environ.get("DISCORD_WEBHOOK_URL_CONTINUOUS"),
        username="AIOps Continuous Bot",
        avatar_url="https://cdn-icons-png.flaticon.com/512/4712/4712011.png",
        embed_title="🔄 Continuous AI Analysis",
        embed_color=3447003,  # Blue
        report=report,
        latency=latency,
        total_tokens=total_tokens,
        footer_text="AIOps FinOps Agent (Continuous Mode)"
    )