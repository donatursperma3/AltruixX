# Main/plugins/userbot/XProfile_Manager_Pro/identity_gen.py
import random
import re
import logging
from typing import Tuple

try:
    from faker import Faker
    fake = Faker(['id_ID', 'en_US'])
except ImportError:
    fake = None
    logging.warning("Faker library not found. Using fallback identity generator.")

logger = logging.getLogger("altruix.xprofile.gen")

# Aesthetic Bios (Indonesia/English)
BOY_BIOS = [
    "Simplicity is the ultimate sophistication.",
    "Living life on my own terms.",
    "Work hard, stay humble.",
    "Chasing dreams and making them happen.",
    "Quietly building an empire.",
    "Focus on the good.",
    "Stay wild, moon child.",
    "Better days are coming.",
    "Explore. Dream. Discover.",
    "Menjadi versi terbaik dari diri sendiri.",
    "Hanya seorang pemimpi yang sedang berusaha.",
    "Tetap rendah hati, tetap berproses.",
    "Fokus pada tujuan, bukan hambatan.",
    "Membangun masa depan, satu langkah setiap waktu.",
]

GIRL_BIOS = [
    "Sunshine mixed with a little hurricane.",
    "Be your own kind of beautiful.",
    "Sparkle every day.",
    "Dream big, sparkle more, shine bright.",
    "Kindness is my favorite accessory.",
    "Creating my own sunshine.",
    "Life is short, make it sweet.",
    "Stay graceful, always.",
    "Less perfection, more authenticity.",
    "Menebar kebaikan di mana pun berada.",
    "Hanya seorang gadis dengan mimpi besar.",
    "Cantik itu relatif, tulus itu pasti.",
    "Berusaha menjadi sinar di tengah kegelapan.",
    "Menikmati setiap detik perjalanan hidup.",
]

def generate_username(name: str, usr_format: str = "random") -> str:
    """Generate a human-like username based on name and requested format."""
    clean_name = re.sub(r'[^a-zA-Z]', '', name).lower()
    base = clean_name[:12] if len(clean_name) > 12 else clean_name
    
    alpha = "abcdefghijklmnopqrstuvwxyz"
    rand_alpha = "".join(random.choice(alpha) for _ in range(random.randint(1, 2)))
    rand_num = str(random.randint(10, 9999))
    
    # [1] nama_xy123 (base_alpha_num)
    p1 = f"{base}_{rand_alpha}{rand_num}"
    # [2] real_namax12 (prefix_base_alpha_num)
    p2 = f"real_{base}{rand_alpha}{random.randint(10, 99)}"
    # [3] official_nama_999 (prefix_base_num)
    p3 = f"official_{base}_{random.randint(100, 999)}"
    
    if usr_format == "pattern1": return p1
    if usr_format == "pattern2": return p2
    if usr_format == "pattern3": return p3
    
    # Random fallback including original variants
    variants = [
        p1, p2, p3,
        f"{base}{rand_alpha}_{rand_num}",
        f"{base}{rand_num}{rand_alpha}",
        f"{base}_{random.choice(alpha)}{random.randint(10, 99)}",
        f"{base}{random.randint(1, 9)}{random.choice(alpha)}{random.randint(10, 99)}",
    ]
    return random.choice(variants)

def generate_identity(gender: str = "random") -> Tuple[str, str, str]:
    """Generate Name, Bio, and Username."""
    if gender == "random":
        gender = random.choice(["boy", "girl"])
    
    # 1. Name
    if fake:
        if gender == "boy":
            name = fake.name_male()
        else:
            name = fake.name_female()
    else:
        # Fallback names
        boys = ["Aditya", "Bima", "Candra", "Dika", "Eka", "Fajar", "Galang", "Hendra"]
        girls = ["Anisa", "Bella", "Citra", "Dewi", "Endah", "Fitri", "Gita", "Hana"]
        name = random.choice(boys if gender == "boy" else girls) + " " + random.choice(["Saputra", "Pratama", "Wijaya", "Putra"] if gender == "boy" else ["Putri", "Lestari", "Sari", "Permata"])

    # 2. Bio
    bio = random.choice(BOY_BIOS if gender == "boy" else GIRL_BIOS)
    
    # 3. Username
    username = generate_username(name)
    
    return name, bio, username

import httpx
import re

async def get_pinterest_avatar(gender: str, keyword: str = None) -> str:
    """Scrape a random aesthetic profile picture from Pinterest."""
    # Use manual keyword if provided, otherwise fallback to gender-based query
    if keyword:
        query = keyword
    else:
        query = f"{gender} aesthetic profile picture"
        
    url = f"https://www.pinterest.com/search/pins/?q={query.replace(' ', '%20')}"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 14_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0.3 Mobile/15E148 Safari/604.1",
        "Accept-Language": "en-US,en;q=0.9"
    }
    
    try:
        async with httpx.AsyncClient(headers=headers, follow_redirects=True, timeout=10.0) as client:
            resp = await client.get(url)
            if resp.status_code == 200:
                # Find high quality pinimg links
                links = re.findall(r'https://i\.pinimg\.com/(?:736x|originals)/[0-9a-f/]+\.jpg', resp.text)
                if links:
                    return random.choice(list(set(links)))
    except Exception as e:
        import logging
        logging.getLogger("altruix.xprofile").error(f"Pinterest scrape error: {e}")
    
    return "" # Fallback indicator

async def get_avatar_url(gender: str = "random", src: str = "xsgames", keyword: str = None) -> str:
    """Get a random AI-generated or scraped avatar URL based on gender and source."""
    if gender == "random":
        gender = random.choice(["boy", "girl"])
        
    g_str = "male" if gender == "boy" else "female"
    
    if src == "pinterest":
        url = await get_pinterest_avatar(gender, keyword=keyword)
        if url:
            return url
        # Fallback to xsgames if pinterest fails
        src = "xsgames"
    
    if src == "tpdne":
        # thispersondoesnotexist (HQ but random gender)
        return f"https://thispersondoesnotexist.com/?v={random.randint(10000, 99999)}"
        
    elif src == "randomuser":
        # randomuser.me (Gendered, Lower Quality)
        g_ru = "men" if gender == "boy" else "women"
        rand_idx = random.randint(0, 99)
        return f"https://randomuser.me/api/portraits/{g_ru}/{rand_idx}.jpg?v={random.randint(10000, 99999)}"
        
    else:
        # Default: xsgames.co (Gendered, High Quality)
        rand_idx = random.randint(0, 78)
        return f"https://xsgames.co/randomusers/assets/avatars/{g_str}/{rand_idx}.jpg?v={random.randint(10000, 99999)}"
