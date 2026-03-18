import docker
import time
import os
import google.generativeai as genai
from bots.discord_bot import send_continuous_alert_to_discord

POLL_INTERVAL_SECONDS = 30

targets_env = os.environ.get("TARGET_CONTAINERS", "checkoutservice,frontend")
TARGET_CONTAINERS = [c.strip() for c in targets_env.split(",")]

try:
    docker_client = docker.from_env()
    print("[INFO] Docker client initialized successfully.")
except Exception as e:
    print(f"[CRITICAL] Failed to initialize Docker client: {e}")
    docker_client = None

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL_CONTINUOUS")

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel('gemini-2.5-flash') 
else:
    model = None

def get_container_logs(container_name, since_timestamp):
    """
    Extracts logs from the target container generated AFTER the given timestamp.
    """
    if not docker_client:
        return ""
        
    try:
        container = docker_client.containers.get(container_name)
        
        raw_logs = container.logs(since=since_timestamp).decode('utf-8').strip()
        
        if len(raw_logs) > 100000:
            print(f"⚠️ [WARNING] Massive log flood in {container_name}. Truncating to save tokens.")
            return raw_logs[-100000:]
            
        return raw_logs
    except docker.errors.NotFound:
        print(f"[ERROR] Container {container_name} not found. Is it running?")
        return ""
    except Exception as e:
        print(f"[ERROR] Failed to extract logs from {container_name}: {e}")
        return ""

def trigger_llm_analysis(containers_list, combined_logs, interval_seconds):
    """Sends aggregated logs to the LLM, measures FinOps metrics, and alerts Discord ONLY on errors."""
    
    system_prompt = f"""
    You are an expert Site Reliability Engineer (SRE) monitoring a microservices architecture. 
    Analyze the following COMBINED logs from multiple containers ({', '.join(containers_list)}), generated over the last {interval_seconds} seconds.
    
    Your goal is to identify: hidden anomalies, logical errors (HTTP 4xx/5xx), crashes, gRPC exceptions, performance degradation, resource exhaustion, or memory leaks.
    Ignore standard operational logs (INFO, 200 OK HTTP requests, startup routines) unless they form an anomalous pattern.
    
    🔍 CRITICAL INSTRUCTION FOR DISTRIBUTED TRACING:
    Logs from different microservices are separated by "=== CONTAINER: <NAME> ===".
    When you detect an error or anomaly in the entry point (e.g., frontend), immediately extract its native correlation IDs (like 'http.req.id', 'session', 'trace_id', or 'span_id') found in the JSON payload. 
    You MUST search for that EXACT SAME ID within the logs of the downstream services (like checkoutservice) in this payload. 
    Use this ID to map the deterministic journey of the failed request and pinpoint the exact Root Cause Analysis (RCA) across the service boundaries. Include this trace journey in your report.
    
    💰 CRITICAL RULE FOR FINOPS: 
    If the logs across ALL containers show normal operation and NO issues, you MUST reply EXACTLY AND ONLY with the phrase "STATUS: NORMAL". Do not add any other text.
    If you detect an issue, provide a brief, actionable SRE Root Cause Analysis (RCA) report in Markdown.
    
    --- RAW LOGS ---
    {combined_logs}
    --- END LOGS ---
    """
    
    print("\n" + "="*60)
    print(f"🔄 [{time.strftime('%H:%M:%S')}] [CONTINUOUS AIOps] Analyzing {len(combined_logs)} bytes of combined logs...")
    
    if model:
        try:
            start_time = time.time()
            response = model.generate_content(system_prompt)
            end_time = time.time()
            
            latency = round(end_time - start_time, 2)
            prompt_tokens = response.usage_metadata.prompt_token_count
            completion_tokens = response.usage_metadata.candidates_token_count
            total_tokens = response.usage_metadata.total_token_count
            
            ai_text = response.text.strip()
            
            print(f"⏱️ Latency (Time to diagnose): {latency} seconds")
            print(f"🪙 Tokens Used: {total_tokens} Total ({prompt_tokens} Input + {completion_tokens} Output)")
            
            if "STATUS: NORMAL" in ai_text.upper():
                print(f"✅ [INFO] Services {containers_list} are healthy. No Discord alert sent.")
            else:
                print(f"🚨 [ALERT] Cross-service issue detected! Sending to Discord...")
                print("-" * 60)
                print(ai_text)
                print("-" * 60)
                send_continuous_alert_to_discord(ai_text, latency, total_tokens)
            
            print("="*60 + "\n")
            
        except Exception as e:
            print(f"⚠️ [API ERROR] Gemini API request failed: {e}")
    else:
        print("⚠️ [MOCK] AI Disabled. Logs captured but not analyzed.")

def main():
    print("="*60)
    print(f"🚀 Continuous AIOps Agent Started (Multi-Service Trace Mode).")
    print(f"📡 Polling targets: {TARGET_CONTAINERS} every {POLL_INTERVAL_SECONDS} seconds...")
    print("="*60)
    
    last_check_times = {container: int(time.time()) - POLL_INTERVAL_SECONDS for container in TARGET_CONTAINERS}
    
    while True:
        loop_start_time = time.time()
        
        combined_logs = ""
        current_check_time = int(time.time())
        
        # 1. Collect and Aggregate Logs
        for container in TARGET_CONTAINERS:
            logs = get_container_logs(container, last_check_times[container])
            last_check_times[container] = current_check_time
            
            if logs:
                combined_logs += f"\n\n{'='*20} CONTAINER: {container.upper()} {'='*20}\n"
                combined_logs += logs
        
        # 2. Trigger Single LLM Analysis with Full Context
        if combined_logs.strip():
            trigger_llm_analysis(TARGET_CONTAINERS, combined_logs.strip(), POLL_INTERVAL_SECONDS)
        
        loop_duration = time.time() - loop_start_time
        sleep_time = max(0, POLL_INTERVAL_SECONDS - loop_duration)
        time.sleep(sleep_time)

if __name__ == "__main__":
    main()