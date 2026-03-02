#!/usr/bin/env python3
"""
Bot Diagnostic Tool - Altruix
Diagnose common issues and provide solutions
"""

import os
import sys
import json
import psutil
import platform
import subprocess
from datetime import datetime

def print_header(title):
    """Print section header"""
    print("\n" + "="*60)
    print(f"  {title}")
    print("="*60)

def check_python_version():
    """Check Python version"""
    print_header("🐍 Python Version")
    version = sys.version_info
    print(f"Version: {version.major}.{version.minor}.{version.micro}")
    if version.major < 3 or (version.major == 3 and version.minor < 8):
        print("❌ Python 3.8+ required")
        return False
    print("✅ Python version OK")
    return True

def check_dependencies():
    """Check required dependencies"""
    print_header("📦 Dependencies")
    required = [
        "pyrogram",
        "pymongo",
        "aiofiles",
        "psutil",
        "pyyaml",
        "cachetools"
    ]
    
    missing = []
    for pkg in required:
        try:
            __import__(pkg)
            print(f"✅ {pkg}")
        except ImportError:
            print(f"❌ {pkg} - NOT INSTALLED")
            missing.append(pkg)
    
    if missing:
        print(f"\n⚠️ Missing packages: {', '.join(missing)}")
        print(f"Install with: pip install {' '.join(missing)}")
        return False
    return True

def check_env_file():
    """Check .env file"""
    print_header("⚙️ Environment Configuration")
    
    if not os.path.exists(".env"):
        print("❌ .env file not found")
        if os.path.exists(".env.sample"):
            print("ℹ️ Copy .env.sample to .env and configure it")
        return False
    
    print("✅ .env file exists")
    
    # Check required variables
    required_vars = [
        "API_ID",
        "API_HASH",
        "SESSION_STRING",
        "BOT_TOKEN"
    ]
    
    with open(".env", "r") as f:
        env_content = f.read()
    
    missing_vars = []
    for var in required_vars:
        if var not in env_content or f"{var}=" not in env_content:
            missing_vars.append(var)
            print(f"⚠️ {var} - NOT SET")
        else:
            print(f"✅ {var}")
    
    if missing_vars:
        print(f"\n⚠️ Missing variables: {', '.join(missing_vars)}")
        return False
    return True

def check_database():
    """Check database files"""
    print_header("💾 Database")
    
    if not os.path.exists("DATABASE"):
        print("⚠️ DATABASE directory not found, will be created on startup")
        return True
    
    print("✅ DATABASE directory exists")
    
    # Check important files
    important_files = [
        "altruix_local_db.json",
        "pm_logger_sessions.json",
        "pm_logger_cache.json"
    ]
    
    for file in important_files:
        path = os.path.join("DATABASE", file)
        if os.path.exists(path):
            size = os.path.getsize(path)
            print(f"✅ {file} ({size} bytes)")
        else:
            print(f"ℹ️ {file} - will be created on startup")
    
    return True

def check_cache():
    """Check cache directory"""
    print_header("📁 Cache")
    
    if not os.path.exists("cache"):
        print("⚠️ cache directory not found, will be created on startup")
        return True
    
    print("✅ cache directory exists")
    
    # Count session files
    session_files = [f for f in os.listdir("cache") if f.endswith(".session")]
    print(f"ℹ️ Found {len(session_files)} session file(s)")
    
    return True

def check_log_file():
    """Check log file for errors"""
    print_header("📋 Log Analysis")
    
    if not os.path.exists("altruix.log"):
        print("ℹ️ No log file found (bot hasn't run yet)")
        return True
    
    print("✅ Log file exists")
    
    # Read last 100 lines
    with open("altruix.log", "r", encoding="utf-8") as f:
        lines = f.readlines()
    
    recent_lines = lines[-100:] if len(lines) > 100 else lines
    
    # Count errors
    errors = [l for l in recent_lines if "ERROR" in l]
    timeouts = [l for l in recent_lines if "TimeoutError" in l]
    crashes = [l for l in recent_lines if "exception was never retrieved" in l]
    
    print(f"ℹ️ Recent errors: {len(errors)}")
    print(f"ℹ️ Recent timeouts: {len(timeouts)}")
    print(f"ℹ️ Recent crashes: {len(crashes)}")
    
    if timeouts:
        print("\n⚠️ TIMEOUT ERRORS DETECTED:")
        print("This may cause bot to hang. Check network connection.")
        print("Recent timeout:")
        for line in timeouts[-3:]:
            print(f"  {line.strip()}")
    
    if crashes:
        print("\n❌ TASK CRASHES DETECTED:")
        print("Bot may be unstable. Check full log for details.")
    
    return len(crashes) == 0

def check_system_resources():
    """Check system resources"""
    print_header("💻 System Resources")
    
    # CPU
    cpu_percent = psutil.cpu_percent(interval=1)
    cpu_count = psutil.cpu_count()
    print(f"CPU: {cpu_percent}% ({cpu_count} cores)")
    if cpu_percent > 80:
        print("⚠️ High CPU usage")
    
    # Memory
    mem = psutil.virtual_memory()
    mem_percent = mem.percent
    mem_available_gb = mem.available / (1024**3)
    print(f"Memory: {mem_percent}% used ({mem_available_gb:.2f}GB available)")
    if mem_percent > 90:
        print("⚠️ High memory usage")
    
    # Disk
    disk = psutil.disk_usage('.')
    disk_percent = disk.percent
    disk_free_gb = disk.free / (1024**3)
    print(f"Disk: {disk_percent}% used ({disk_free_gb:.2f}GB free)")
    if disk_percent > 90:
        print("⚠️ Low disk space")
    
    # Platform
    print(f"Platform: {platform.system()} {platform.release()}")
    
    return True

def check_network():
    """Check network connectivity"""
    print_header("🌐 Network Connectivity")
    
    # Test DNS
    try:
        import socket
        socket.gethostbyname("api.telegram.org")
        print("✅ DNS resolution OK")
    except Exception as e:
        print(f"❌ DNS resolution failed: {e}")
        return False
    
    # Test ping (if available)
    try:
        if platform.system() == "Windows":
            result = subprocess.run(
                ["ping", "-n", "1", "api.telegram.org"],
                capture_output=True,
                timeout=5
            )
        else:
            result = subprocess.run(
                ["ping", "-c", "1", "api.telegram.org"],
                capture_output=True,
                timeout=5
            )
        
        if result.returncode == 0:
            print("✅ Ping to api.telegram.org OK")
        else:
            print("⚠️ Ping to api.telegram.org failed")
    except Exception as e:
        print(f"ℹ️ Ping test skipped: {e}")
    
    return True

def check_bot_process():
    """Check if bot is running"""
    print_header("🤖 Bot Process")
    
    for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'memory_info', 'cpu_percent']):
        try:
            cmdline = proc.info['cmdline']
            if cmdline and 'Main' in ' '.join(cmdline):
                pid = proc.info['pid']
                mem_mb = proc.info['memory_info'].rss / (1024 * 1024)
                cpu = proc.info['cpu_percent']
                print(f"✅ Bot is running")
                print(f"   PID: {pid}")
                print(f"   Memory: {mem_mb:.2f}MB")
                print(f"   CPU: {cpu:.1f}%")
                return True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    
    print("ℹ️ Bot is not running")
    return False

def main():
    """Run all diagnostics"""
    print("\n" + "="*60)
    print("  🔍 ALTRUIX BOT DIAGNOSTIC TOOL")
    print("="*60)
    print(f"  Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)
    
    checks = [
        ("Python Version", check_python_version),
        ("Dependencies", check_dependencies),
        ("Environment Config", check_env_file),
        ("Database", check_database),
        ("Cache", check_cache),
        ("Log Analysis", check_log_file),
        ("System Resources", check_system_resources),
        ("Network", check_network),
        ("Bot Process", check_bot_process),
    ]
    
    results = []
    for name, check_func in checks:
        try:
            result = check_func()
            results.append((name, result))
        except Exception as e:
            print(f"\n❌ Error in {name}: {e}")
            results.append((name, False))
    
    # Summary
    print_header("📊 Summary")
    passed = sum(1 for _, result in results if result)
    total = len(results)
    print(f"Checks passed: {passed}/{total}")
    
    if passed == total:
        print("\n✅ All checks passed! Bot should be working fine.")
    else:
        print("\n⚠️ Some checks failed. Review the output above for details.")
        failed = [name for name, result in results if not result]
        print(f"Failed checks: {', '.join(failed)}")
    
    print("\n" + "="*60)
    print("  For more help, see TROUBLESHOOTING.md")
    print("="*60 + "\n")

if __name__ == "__main__":
    main()
