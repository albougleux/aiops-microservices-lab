import os
import time
import threading
from concurrent.futures import ThreadPoolExecutor
import docker
from flask import Flask, request, jsonify
import google.generativeai as genai
from bots.discord_bot import send_event_alert_to_discord

app = Flask(__name__)

try:
    docker_client = docker.from_env()
    print("[INFO] Docker client initialized successfully.")
except Exception as e:
    print(f"[CRITICAL] Failed to initialize Docker client: {e}")
    docker_client = None

DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel('gemini-2.5-flash')
else:
    print("[CRITICAL] GEMINI_API_KEY not found! The agent won't be able to analyze logs.")
    model = None

# Cross-service monitoring targets (same scope as Continuous agent)
MONITOR_TARGETS = ['checkoutservice', 'frontend']

# In-memory cache to prevent duplicate alerts
processed_alerts = {}
COOLDOWN_SECONDS = 300
executor = ThreadPoolExecutor(max_workers=5)

def get_container_logs(container_name, lines=200):
    """Extracts the last log lines from a single container."""
    if not docker_client:
        return "Log extraction failed due to missing Docker client."
        
    try:
        print(f"[INFO] Extracting the last {lines} log lines from container: {container_name}")
        container = docker_client.containers.get(container_name)
        return container.logs(tail=lines).decode('utf-8')
    except docker.errors.NotFound:
        print(f"[ERROR] Container {container_name} not found.")
        return f"Container {container_name} not found."
    except Exception as e:
        print(f"[ERROR] Failed to extract logs from {container_name}: {e}")
        return "Log extraction failed."

def get_cross_service_logs(lines=200):
    """Collects logs from all monitored containers for cross-service analysis."""
    combined_logs = ""
    for target in MONITOR_TARGETS:
        logs = get_container_logs(target, lines)
        combined_logs += f"\n--- LOGS FROM [{target.upper()}] ---\n{logs}\n--- END [{target.upper()}] ---\n"
    return combined_logs

def trigger_llm_analysis(alert_name, container_name, logs):
    """Builds the System Prompt, sends it to Gemini, and calculates FinOps metrics."""
    
    system_prompt = f"""
    You are an expert Site Reliability Engineer (SRE) specializing in microservices diagnostics.
    An infrastructure alert named '{alert_name}' has just fired for the container '{container_name}'.
    
    Below are the most recent log lines from MULTIPLE containers in the service mesh, collected for cross-service correlation.
    Analyze the logs from ALL containers, identify any potential root causes, anomalies, resource exhaustion, or cascading failures.
    Use distributed tracing by correlating IDs (like 'http.req.id', 'session', 'user_id', 'trace_id', or 'span_id') across services to map the full request journey.
    
    🔍 CRITICAL INSTRUCTION FOR TRACING (POISON PILL DETECTION):
    If the infrastructure collapse (e.g., OOMKilled, CPU spike) was triggered by a specific malformed request, a massive payload, or a traffic burst, look for OpenTelemetry correlation IDs in the JSON logs immediately preceding the failure. 
    You MUST explicitly extract and report these IDs in your summary so the engineering team can trace the "poison pill" request upstream to the API gateway.
    
    Provide a concise, actionable Root Cause Analysis (RCA) summary for the on-call engineering team in Markdown format.
    
    --- RAW LOGS (CROSS-SERVICE) ---
    {logs}
    --- END LOGS ---
    """
    
    print("\n" + "="*60)
    print(f"🤖 [AIOps] Sending payload and logs to Google Gemini for {container_name}...")
    print("="*60)
    
    if model:
        try:
            start_time = time.time()
            response = model.generate_content(system_prompt)
            end_time = time.time()
            
            latency = round(end_time - start_time, 2)
            prompt_tokens = response.usage_metadata.prompt_token_count
            completion_tokens = response.usage_metadata.candidates_token_count
            total_tokens = response.usage_metadata.total_token_count
            
            print("\n✅ [AI DIAGNOSTIC REPORT]")
            print("-" * 60)
            print(response.text.strip())
            print("-" * 60)
            
            print("\n📊 [FINOPS METRICS - LAB DATA]")
            print(f"⏱️ Latency (Time to diagnose): {latency} seconds")
            print(f"🪙 Tokens Used: {total_tokens} Total ({prompt_tokens} Input + {completion_tokens} Output)")
            print("="*60 + "\n")
            
            send_event_alert_to_discord(response.text.strip(), latency, total_tokens)
            
        except Exception as e:
            print(f"[ERROR] Failed to get response from Gemini API: {e}")
    else:
        print("[WARNING] AI disabled. Printing Prompt locally instead:")
        print(system_prompt)

@app.route('/webhook', methods=['POST'])
def prometheus_webhook():
    data = request.json
    
    if not data or 'alerts' not in data:
        return jsonify({"error": "Invalid payload format"}), 400

    for alert in data['alerts']:
        if alert['status'] == 'firing':
            labels = alert.get('labels', {})
            alert_name = labels.get('alertname', 'UnknownAlert')
            container_name = labels.get('container_name', labels.get('container', 'UnknownContainer'))
            
            alert_id = f"{alert_name}-{container_name}"
            current_time = time.time()
            
            if alert_id in processed_alerts:
                time_since_last = current_time - processed_alerts[alert_id]
                if time_since_last < COOLDOWN_SECONDS:
                    print(f"\n⏭️ [SKIP] Alert '{alert_id}' was already analyzed {int(time_since_last)}s ago. Ignoring duplicate.")
                    continue
            
            # Mark the alert as processed right now
            processed_alerts[alert_id] = current_time
            
            print(f"\n🚨 [EVENT TRIGGERED] {alert_name} fired on service {container_name}!")
            
            logs = get_cross_service_logs()
            
            executor.submit(
                trigger_llm_analysis, 
                alert_name, container_name, logs
            )

    return jsonify({"status": "Success, alerts accepted for background processing"}), 200

if __name__ == "__main__":
    print("="*60)
    print("🚀 Event-Driven AIOps Agent Started. Listening on port 5000...")
    print("="*60)
    app.run(host='0.0.0.0', port=5000)