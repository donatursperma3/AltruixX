import os

file_path = r'f:\2025\DESEMBER\altruix\AltruixX\Main\core\client.py'
with open(file_path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

new_lines = []
inserted = False
for line in lines:
    if 'class AltruixClient:' in line and not inserted:
        new_lines.append(line)
        new_lines.append('    def get_master(self):\n')
        new_lines.append('        """Returns the designated Master client instance. Fallback to clients[0]."""\n')
        new_lines.append('        master_id = getattr(self.config, "ALLIANCE_MASTER_ID", None)\n')
        new_lines.append('        if master_id:\n')
        new_lines.append('            for cli in self.clients:\n')
        new_lines.append('                if hasattr(cli, "me") and cli.me and cli.me.id == int(master_id):\n')
        new_lines.append('                    return cli\n')
        new_lines.append('        # Fallback to the first authorized client if no master is set or found\n')
        new_lines.append('        for cli in self.clients:\n')
        new_lines.append('            if hasattr(cli, "me") and cli.me and getattr(cli, "is_authorized", True):\n')
        new_lines.append('                return cli\n')
        new_lines.append('        return self.clients[0] if self.clients else None\n\n')
        inserted = True
    else:
        new_lines.append(line)

with open(file_path, 'w', encoding='utf-8') as f:
    f.writelines(new_lines)

print("Successfully updated Main/core/client.py")
 Riverside
 Riverside
