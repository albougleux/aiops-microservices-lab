import requests
import datetime
import sys
import os

ALERTMANAGER_URL = os.getenv("ALERTMANAGER_URL", "http://alertmanager:9093")

def disable_alert(alert_name):
    """Mutes the alert effectively forever (10 years) using Alertmanager Silences."""
    start_time = datetime.datetime.now(datetime.timezone.utc)
    end_time = start_time + datetime.timedelta(days=365 * 10)

    payload = {
        "matchers": [
            {"name": "alertname", "value": alert_name, "isRegex": False, "isEqual": True}
        ],
        "startsAt": start_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "endsAt": end_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "createdBy": "AIOps CLI",
        "comment": "Manually DISABLED via CLI for testing"
    }

    try:
        response = requests.post(f"{ALERTMANAGER_URL}/api/v2/silences", json=payload)
        response.raise_for_status()
        print(f"🛑 [DISABLED] Alert '{alert_name}' is now MUTED.")
    except Exception as e:
        print(f"❌ [ERROR] Failed to disable alert: {e}")

def enable_alert(alert_name):
    """Finds active silences for this alert and deletes them, re-enabling the alert."""
    try:
        response = requests.get(f"{ALERTMANAGER_URL}/api/v2/silences")
        response.raise_for_status()
        silences = response.json()

        deleted_any = False
        
        for silence in silences:
            if silence.get('status', {}).get('state') == 'active':
                for matcher in silence.get('matchers', []):
                    if matcher.get('name') == 'alertname' and matcher.get('value') == alert_name:
                        silence_id = silence['id']
                        
                        del_response = requests.delete(f"{ALERTMANAGER_URL}/api/v2/silence/{silence_id}")
                        del_response.raise_for_status()
                        deleted_any = True
                        break
        
        if deleted_any:
            print(f"✅ [ENABLED] Alert '{alert_name}' is now ACTIVE and watching.")
        else:
            print(f"⚠️ [INFO] Alert '{alert_name}' was already enabled (no active silences found).")

    except Exception as e:
        print(f"❌ [ERROR] Failed to enable alert: {e}")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python alert_toggle.py <enable|disable> <AlertName>")
        print("Example: python alert_toggle.py disable HighMemory_OOM_Risk")
        sys.exit(1)
    
    action = sys.argv[1].lower()
    target_alert = sys.argv[2]
    
    if action == "disable":
        disable_alert(target_alert)
    elif action == "enable":
        enable_alert(target_alert)
    else:
        print("❌ Invalid action. Use 'enable' or 'disable'.")