
import os

path = r'f:\2025\DESEMBER\altruix\AltruixX\Main\core\client.py'
with open(path, 'r', encoding='utf-8', errors='ignore') as f:
    lines = f.readlines()

new_lines = []
skip = 0
found_get_string = False

for i, line in enumerate(lines):
    if skip > 0:
        skip -= 1
        continue
    
    # FIX 1: get_string function
    if 'def get_string(self, keyword: str, args: tuple = None) -> str:' in line:
        found_get_string = True
        new_lines.append(line)
        new_lines.append('        try:\n')
        new_lines.append('            # ✅ Robust fallback for Bot Assistant\n')
        new_lines.append('            lang_code = self.selected_lang or "id"\n')
        new_lines.append('            if self.bot and not self.clients: # Independent Bot Mode\n')
        new_lines.append('                lang_code = "id"\n')
        new_lines.append('            \n')
        new_lines.append('            # Corrected attribute name: all_lang_strings\n')
        new_lines.append('            lang = self.all_lang_strings.get(lang_code) or self.all_lang_strings.get("english") or self.all_lang_strings.get("id") or self.all_lang_strings.get("en")\n')
        new_lines.append('            if not lang:\n')
        new_lines.append('                return keyword\n')
        new_lines.append('            \n')
        new_lines.append('            format_string = lang.get(keyword, keyword)\n')
        new_lines.append('            if args:\n')
        new_lines.append('                 return format_string.format(*args) if isinstance(args, tuple) else format_string.format(args)\n')
        new_lines.append('            return format_string\n')
        new_lines.append('        except Exception:\n')
        new_lines.append('            return keyword\n')
        
        # Skip until next method
        for j in range(i + 1, len(lines)):
            if lines[j].strip().startswith('def ') and lines[j].startswith('    def '):
                skip = j - i - 1
                break
        continue
            
    new_lines.append(line)

with open(path, 'w', encoding='utf-8') as f:
    f.writelines(new_lines)

if found_get_string:
    print("Successfully patched get_string in client.py")
else:
    print("Failed to find get_string")
