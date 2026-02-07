
import os

path = r'f:\2025\DESEMBER\altruix\AltruixX\Main\core\client.py'
with open(path, 'r', encoding='utf-8', errors='ignore') as f:
    lines = f.readlines()

new_lines = []
imported = False

for line in lines:
    if 'from pyrogram.errors.exceptions.bad_request_400 import (' in line:
        new_lines.append(line)
        continue
        
    if 'MessageNotModified' in line:
        imported = True
        
    if 'UserNotParticipant)' in line and not imported:
        # Check if previous line had MessageNotModified
        if 'MessageNotModified' not in new_lines[-1]:
             new_lines.insert(-1, '    MessageNotModified,\n')
             
    new_lines.append(line)

with open(path, 'w', encoding='utf-8') as f:
    f.writelines(new_lines)

print("Successfully checked/added MessageNotModified import in client.py")
