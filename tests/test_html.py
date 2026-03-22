from bs4 import BeautifulSoup
import re

def fix_html_current(text: str) -> str:
    if not text:
        return ""
    soup = BeautifulSoup(text, "html.parser")
    fixed = str(soup)
    return fixed.replace('expandable=""', 'expandable')

def fix_html_new(text: str) -> str:
    if not text:
        return ""
    soup = BeautifulSoup(text, "html.parser")
    # For fragments, use decode_contents or similar
    fixed = soup.decode_contents()
    return fixed.replace('expandable=""', 'expandable')

test_str = "<blockquote expandable><b>Header</b>\nContent"
print(f"Current: '{fix_html_current(test_str)}'")
print(f"New:     '{fix_html_new(test_str)}'")

test_str2 = "Plain text"
print(f"Current2: '{fix_html_current(test_str2)}'")
print(f"New2:     '{fix_html_new(test_str2)}'")
