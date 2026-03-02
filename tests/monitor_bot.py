#!/usr/bin/env python3
"""
Bot Health Monitor - Altruix
Monitors bot health and auto-restart if needed
"""

import os
import sys
import time
import psutil
import subprocess
from datetime import datetime

# Configuration
CHECK_INTERVAL = 60  # Check every 60 seconds
MAX_MEMORY_MB = 1024  # Restart if memory > 1GB
MAX_CPU_PERCENT = 90  # Restart if CPU > 90%
LOG_FILE = "monitor.log"
BOT_COMMAND = [sys.executable, "-m", "Main"]

def log(message):
    """Log message with timestamp"""
    timestamp = datetime.now().strftime("[%d/%m/%Y %H:%M:%S]")
    log_msg = f"{timestamp} - {message}"
    print(log_msg)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(log_msg + "\n")

def find_bot_process():
    """Find running bot process"""
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            cmdline = proc.info['cmdline']
            if cmdline and 'Main' in ' '.join(cmdline):
                return proc
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return None

def check_bot_health(proc):
    """Check if bot is healthy"""
    try:
        # Check if process is running
        if not proc.is_running():
            return False, "Process not running"
        
        # Check memory usage
        mem_info = proc.memory_info()
        mem_mb = mem_info.rss / (1024 * 1024)
        if mem_mb > MAX_MEMORY_MB:
            return False, f"Memory usage too high: {mem_mb:.2f}MB"
        
        # Check CPU usage
        cpu_percent = proc.cpu_percent(interval=1)
        if cpu_percent > MAX_CPU_PERCENT:
            return False, f"CPU usage too high: {cpu_percent:.1f}%"
        
        # Check if log file has recent activity
        if os.path.exists("altruix.log"):
            log_mtime = os.path.getmtime("altruix.log")
            time_since_update = time.time() - log_mtime
            if time_since_update > 300:  # No activity for 5 minutes
                return False, f"No log activity for {time_since_update:.0f}s"
        
        return True, "Healthy"
    except Exception as e:
        return False, f"Health check error: {e}"

def start_bot():
    """Start bot process"""
    log("🚀 Starting bot...")
    try:
        proc = subprocess.Popen(
            BOT_COMMAND,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=os.getcwd()
        )
        time.sleep(5)  # Wait for bot to start
        log(f"✅ Bot started with PID: {proc.pid}")
        return proc
    except Exception as e:
        log(f"❌ Failed to start bot: {e}")
        return None

def stop_bot(proc):
    """Stop bot process gracefully"""
    log("🛑 Stopping bot...")
    try:
        proc.terminate()
        proc.wait(timeout=10)
        log("✅ Bot stopped gracefully")
    except subprocess.TimeoutExpired:
        log("⚠️ Bot didn't stop gracefully, killing...")
        proc.kill()
        log("✅ Bot killed")
    except Exception as e:
        log(f"❌ Error stopping bot: {e}")

def main():
    """Main monitoring loop"""
    log("="*60)
    log("🔍 Bot Health Monitor Started")
    log("="*60)
    
    restart_count = 0
    last_restart_time = 0
    
    while True:
        try:
            # Find bot process
            proc = find_bot_process()
            
            if proc is None:
                log("⚠️ Bot process not found, starting...")
                start_bot()
                time.sleep(CHECK_INTERVAL)
                continue
            
            # Check health
            is_healthy, status = check_bot_health(proc)
            
            if is_healthy:
                log(f"✅ Bot healthy - PID: {proc.pid}, Status: {status}")
            else:
                log(f"❌ Bot unhealthy - Status: {status}")
                
                # Check restart rate limit
                current_time = time.time()
                if current_time - last_restart_time < 3600:
                    restart_count += 1
                    if restart_count >= 5:
                        log("⚠️ Too many restarts in 1 hour, waiting 10 minutes...")
                        time.sleep(600)
                        restart_count = 0
                else:
                    restart_count = 0
                
                last_restart_time = current_time
                
                # Restart bot
                log("🔄 Restarting bot...")
                stop_bot(proc)
                time.sleep(5)
                start_bot()
            
            time.sleep(CHECK_INTERVAL)
            
        except KeyboardInterrupt:
            log("⚠️ Monitor stopped by user")
            break
        except Exception as e:
            log(f"❌ Monitor error: {e}")
            time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    main()
