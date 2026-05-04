#!/usr/bin/env python3
import sys
import os
import datetime

# ANSI Color Codes
TS_COLOR = "\033[97;48;5;141m"
TAG_COLOR = "\033[97;48;2;69;104;130m"
DEBUG_COLOR = "\033[97;46m"
RESET = "\033[0m"

def main():
    is_debug = os.getenv("DEBUG", "false").lower() == "true"
    
    try:
        for line in sys.stdin:
            clean_line = line.strip()
            if not clean_line:
                continue
                
            # Get current time
            now = datetime.datetime.now()
            ts = now.strftime("%H:%M:%S.%f")[:-3]
            
            # --- SPECIAL HANDLING FOR PIP SUCCESS LIST ---
            # Pip prints: "Successfully installed lib1-1.0 lib2-2.0 ..."
            if "Successfully installed" in clean_line:
                # Extract the list of packages
                pkg_part = clean_line.replace("Successfully installed", "").strip()
                pkgs = pkg_part.split()
                
                # Print a header
                header = f"{TS_COLOR}[{ts}]{RESET} - {TAG_COLOR}[Altroid-X]{RESET} {DEBUG_COLOR if is_debug else ''}📦 Installation Report:{RESET}"
                sys.stdout.write(header + "\n")
                
                # Print each package with a checkmark
                for pkg in pkgs:
                    # Slow down slightly for visual effect if you want, but pip is already done here
                    sys.stdout.write(f"{TS_COLOR}[{ts}]{RESET} - {TAG_COLOR}[Altroid-X]{RESET}   ✅ {pkg}\n")
                sys.stdout.flush()
                continue

            # --- STANDARD LOGGING ---
            if is_debug:
                padded_debug = "DEBUG".center(8)
                output = f"{TS_COLOR}[{ts}]{RESET} - {TAG_COLOR}[Altroid-X]{RESET} {DEBUG_COLOR}|» {padded_debug} «|{RESET} : » {clean_line}\n"
            else:
                output = f"{TS_COLOR}[{ts}]{RESET} - {TAG_COLOR}[Altroid-X]{RESET} {clean_line}\n"
                
            sys.stdout.write(output)
            sys.stdout.flush()
    except EOFError:
        pass
    except KeyboardInterrupt:
        pass

if __name__ == "__main__":
    main()
