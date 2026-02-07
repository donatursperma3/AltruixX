
import os

path = r'f:\2025\DESEMBER\altruix\AltruixX\Main\localization\id.yml'
with open(path, 'r', encoding='utf-8', errors='ignore') as f:
    lines = f.readlines()

new_lines = []
for line in lines:
    if 'startup_complete_title:' in line:
        new_lines.append('startup_complete_title: "All clients finished sending startup logs!\\n"\n')
    elif 'startup_total_session:' in line:
        new_lines.append('startup_total_session: "Total Session: <code>{}</code> user + <code>1</code> bot\\n"\n')
    elif 'startup_success_count:' in line:
        new_lines.append('startup_success_count: "Success: <code>{}</code> clients\\n"\n')
    elif 'startup_failed_count:' in line:
        new_lines.append('startup_failed_count: "Failed: <code>{}</code> clients\\n"\n')
    elif 'startup_owner_id:' in line:
        new_lines.append('startup_owner_id: "Owner ID: <code>{}</code>\\n"\n')
    elif 'startup_branch:' in line:
        new_lines.append('startup_branch: "Branch: <code>{}</code>\\n"\n')
    elif 'startup_db:' in line:
        new_lines.append('startup_db: "Database: <code>{}</code>\\n"\n')
    elif 'startup_ver:' in line:
        new_lines.append('startup_ver: "Version: <code>{}</code>\\n"\n')
    elif 'startup_time:' in line:
        new_lines.append('startup_time: "Time: <code>{}</code>"\n')
    else:
        new_lines.append(line)

with open(path, 'w', encoding='utf-8') as f:
    f.writelines(new_lines)
print("Successfully updated localization keys in id.yml")
