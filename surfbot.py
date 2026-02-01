#!/usr/bin/env python3
"""
SurfBot - Daily LA County surf reports via Telegram
Optimized for weekend warriors with PTO alerts
"""

import os
import requests
from bs4 import BeautifulSoup
import re
import time
import threading
import schedule
from datetime import datetime, timedelta
import pytz

# ============== CONFIGURATION ==============

TELEGRAM_TOKEN = os.getenv("SURFBOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
TELEGRAM_CHAT_ID = os.getenv("SURFBOT_CHAT_ID", "1552583800")

SPOTS = [
    {"name": "Annenberg/SM Pier", "slug": "Santa-Monica-Pier"},
    {"name": "Venice/Muscle Beach", "slug": "Venice-Breakwater"},
]

TZ = pytz.timezone("America/Los_Angeles")

# Weekend = detailed, weekdays = condensed with PTO flags
WEEKEND_PRIORITY = True
WEEKDAY_PTO_THRESHOLD = 5  # Flag weekdays ⭐5+ as "worth PTO"

# School calendar (Glendale USD - Benjamin Franklin Magnet)
# Update annually from https://www.gusd.net/calendar
GUSD_BREAKS = [
    # (start_date, end_date, name)
    ("2025-11-25", "2025-11-29", "Thanksgiving"),
    ("2025-12-23", "2026-01-06", "Winter Break"),
    ("2026-01-20", "2026-01-20", "MLK Day"),
    ("2026-02-16", "2026-02-20", "Presidents Week"),
    ("2026-03-30", "2026-04-03", "Spring Break"),
    ("2026-05-25", "2026-05-25", "Memorial Day"),
    ("2026-06-11", "2026-08-15", "Summer Break"),
]

# Auto-push features
WEEKEND_BEACH_DIGEST = True      # Saturday 7 AM family beach pick
SCHOOL_BREAK_ALERTS = True       # Alert evening before GUSD breaks
HEAT_WAVE_ALERTS = True          # Push when 90°F+ inland forecast
HEAT_THRESHOLD_F = 90

# Google Maps Distance Matrix API (for commute times)
# Get API key: https://console.cloud.google.com/apis/credentials
GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY", "")
HOME_ADDRESS = "Glendale, CA"  # Origin for commute calculations

# Beaches with addresses for commute calculation
BEACH_ADDRESSES = {
    "carp": "Carpinteria State Beach, Carpinteria, CA",
    "east": "East Beach, Santa Barbara, CA",
    "paradise": "Paradise Cove, Malibu, CA",
    "piedra": "La Piedra State Beach, Malibu, CA",
    "belmont": "Belmont Shore, Long Beach, CA",
    "pedro": "Cabrillo Beach, San Pedro, CA",
    "fletcher": "Fletcher Cove, Solana Beach, CA",
    "oxnard": "Oxnard Shores, Oxnard, CA",
}

# Beach mode locations (tide/temp focused)
BEACH_LOCATIONS = {
    # Travel destinations
    "spo": {
        "name": "Sankt Peter-Ording",
        "region": "travel",
        "focus": ["wind", "tide"],
        "slug": "Sankt-Peter-Ording",
        "note": "Check beach access - some areas close at high tide",
    },
    "van": {
        "name": "Vancouver BC",
        "region": "travel",
        "focus": ["tide", "temp"],
        "spots": ["English Bay", "Kitsilano", "Spanish Banks"],
    },
    # Local SoCal favorites
    "pedro": {
        "name": "San Pedro (Cabrillo)",
        "region": "local",
        "lat": 33.7084, "lon": -118.2865,
    },
    "paradise": {
        "name": "Paradise Cove",
        "region": "local",
        "lat": 34.0142, "lon": -118.7903,
        "note": "$$$ parking but worth it",
    },
    "belmont": {
        "name": "Belmont Shore",
        "region": "local",
        "lat": 33.7542, "lon": -118.1445,
    },
    "fletcher": {
        "name": "Fletcher Cove",
        "region": "local",
        "lat": 32.9634, "lon": -117.2710,
        "note": "Solana Beach - great tide pools",
    },
    "piedra": {
        "name": "La Piedra",
        "region": "local",
        "lat": 34.0367, "lon": -118.8394,
        "note": "Hidden Malibu gem",
    },
    "oxnard": {
        "name": "Oxnard Shores",
        "region": "local",
        "lat": 34.1692, "lon": -119.2245,
    },
    "carp": {
        "name": "Carpinteria State Beach",
        "region": "local",
        "lat": 34.3917, "lon": -119.5181,
        "note": "Calm waves, great for kids",
    },
    "east": {
        "name": "East Beach",
        "region": "local",
        "lat": 34.4133, "lon": -119.6773,
        "note": "Santa Barbara's main beach",
    },
}

# California coast regions for road trips
COAST_REGIONS = ["San-Diego", "Los-Angeles", "Santa-Barbara", "Central-Coast", "San-Francisco"]

DAILY_HOUR = 6
TICKER_START = 6
TICKER_END = 18

# ============== TELEGRAM ==============

def send(msg):
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            json={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "HTML"},
            timeout=10
        )
    except Exception as e:
        print(f"Telegram error: {e}")

# ============== COMMUTE TIMES ==============

def get_commute_times(destinations=None):
    """
    Get drive times from home to beaches and back using Google Distance Matrix API.
    Returns dict: {beach_code: {"to": "1h 15m", "back": "1h 05m"}}
    """
    if not GOOGLE_MAPS_API_KEY:
        return {}

    if destinations is None:
        destinations = ["carp", "paradise", "belmont"]  # Default top 3

    results = {}

    for code in destinations:
        if code not in BEACH_ADDRESSES:
            continue

        beach_addr = BEACH_ADDRESSES[code]

        try:
            # Drive TO beach
            url = "https://maps.googleapis.com/maps/api/distancematrix/json"
            params = {
                "origins": HOME_ADDRESS,
                "destinations": beach_addr,
                "departure_time": "now",
                "key": GOOGLE_MAPS_API_KEY,
            }
            r = requests.get(url, params=params, timeout=10)
            data = r.json()

            to_duration = "?"
            if data.get("rows") and data["rows"][0].get("elements"):
                elem = data["rows"][0]["elements"][0]
                if elem.get("duration_in_traffic"):
                    to_duration = elem["duration_in_traffic"]["text"]
                elif elem.get("duration"):
                    to_duration = elem["duration"]["text"]

            # Drive BACK from beach
            params["origins"] = beach_addr
            params["destinations"] = HOME_ADDRESS
            r = requests.get(url, params=params, timeout=10)
            data = r.json()

            back_duration = "?"
            if data.get("rows") and data["rows"][0].get("elements"):
                elem = data["rows"][0]["elements"][0]
                if elem.get("duration_in_traffic"):
                    back_duration = elem["duration_in_traffic"]["text"]
                elif elem.get("duration"):
                    back_duration = elem["duration"]["text"]

            results[code] = {"to": to_duration, "back": back_duration}

        except Exception as e:
            print(f"Commute error for {code}: {e}")
            results[code] = {"to": "?", "back": "?"}

    return results

# ============== SCRAPING ==============

def meters_to_feet(m):
    try:
        return round(float(m) * 3.28)
    except:
        return 0

def fetch_spot(slug):
    """Fetch 7-day forecast: 7 days × 3 periods (AM, PM, Night)"""
    url = f"https://www.surf-forecast.com/breaks/{slug}/forecasts/latest/six_day"
    headers = {"User-Agent": "Mozilla/5.0 (compatible; SurfBot/1.0)"}

    try:
        r = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(r.text, "html.parser")

        data = {"ratings": [], "waves_m": [], "periods": [], "wind_states": [], "water_temp_f": None}

        for row in soup.find_all("tr"):
            cells = row.find_all("td")
            if len(cells) < 2:
                continue

            label = cells[0].get_text().strip().lower()
            values = [c.get_text().strip() for c in cells[1:22]]

            if "rating" in label:
                data["ratings"] = values
            elif "wave height" in label or "wave (m)" in label:
                data["waves_m"] = [re.search(r"[\d.]+", v).group() if re.search(r"[\d.]+", v) else "0" for v in values]
            elif label.startswith("period"):
                data["periods"] = [re.search(r"\d+", v).group() if re.search(r"\d+", v) else "0" for v in values]
            elif "wind state" in label:
                data["wind_states"] = values

        data["waves_ft"] = [meters_to_feet(m) for m in data["waves_m"]]

        temp_match = re.search(r"(\d+\.?\d*)\s*°\s*C", r.text)
        if temp_match:
            c = float(temp_match.group(1))
            data["water_temp_f"] = round(c * 9/5 + 32)

        return data
    except Exception as e:
        print(f"Error fetching {slug}: {e}")
        return None

def fetch_county_rankings():
    """Get current ratings for all LA County spots"""
    url = "https://www.surf-forecast.com/regions/Los-Angeles-County"
    headers = {"User-Agent": "Mozilla/5.0 (compatible; SurfBot/1.0)"}

    try:
        r = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(r.text, "html.parser")

        spots = []
        for row in soup.find_all("tr"):
            cells = row.find_all("td")
            if len(cells) < 4:
                continue

            link = row.find("a", href=re.compile(r"/breaks/"))
            if not link:
                continue

            name = link.get_text().strip()
            if "CAL -" in name:
                name = name.split("CAL")[0].strip()

            for cell in cells:
                txt = cell.get_text().strip()
                if txt.isdigit() and len(txt) == 1:
                    spots.append({"name": name, "rating": int(txt)})
                    break

        spots.sort(key=lambda x: x["rating"], reverse=True)
        return spots
    except Exception as e:
        print(f"Error fetching county: {e}")
        return []

# ============== FORMATTING ==============

def wind_text(state):
    """Plain English wind states"""
    s = (state or "").lower()
    if "glass" in s or "off" in s:
        return "calm"
    elif "cross" in s and "on" not in s:
        return "light wind"
    else:
        return "windy"

def get_day_names():
    """Day names starting from today"""
    now = datetime.now(TZ)
    names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    today_idx = now.weekday()
    return [names[(today_idx + i) % 7] for i in range(7)]

def find_best_windows(data, days):
    """Find best weekend and weekday windows"""
    weekend_best = {"day": None, "per": "AM", "rating": -1, "height": 0, "period": "0", "wind": ""}
    pto_worthy = []

    for i, day in enumerate(days[:7]):
        for p, per_name in enumerate(["AM", "PM"]):
            idx = i * 3 + p
            if idx >= len(data.get("ratings", [])):
                continue

            try:
                rating = int(data["ratings"][idx])
            except:
                continue

            height = data["waves_ft"][idx] if idx < len(data["waves_ft"]) else 0
            period = data["periods"][idx] if idx < len(data["periods"]) else "0"
            wind = wind_text(data["wind_states"][idx] if idx < len(data["wind_states"]) else "")

            entry = {"day": day, "per": per_name, "rating": rating, "height": height, "period": period, "wind": wind}

            if day in ["Sat", "Sun"]:
                if rating > weekend_best["rating"]:
                    weekend_best = entry
            else:
                if rating >= WEEKDAY_PTO_THRESHOLD:
                    pto_worthy.append(entry)

    return weekend_best, pto_worthy

def generate_explainer(weekend_best, pto_worthy):
    """Plain English summary"""
    lines = []

    if weekend_best["rating"] >= 3:
        lines.append(f"{weekend_best['day']} {weekend_best['per']} is your weekend play - {weekend_best['height']}ft at {weekend_best['period']}s, {weekend_best['wind']}.")
    elif weekend_best["rating"] >= 1:
        lines.append(f"Weekend is weak. Best is {weekend_best['day']} {weekend_best['per']} at ⭐{weekend_best['rating']}.")
    else:
        lines.append("Weekend is flat. Maybe next week.")

    if pto_worthy:
        top = max(pto_worthy, key=lambda x: x["rating"])
        if top["rating"] > weekend_best["rating"] + 1:
            lines.append(f"\nBut {top['day']} {top['per']} is worth PTO - {top['height']}ft at {top['period']}s, {top['wind']}. Much better than the weekend.")

    return "\n".join(lines)

# ============== REPORTS ==============

def daily_report():
    """7-day report with weekend priority"""
    now = datetime.now(TZ)
    days = get_day_names()

    msg = f"🏄 <b>Surf Report</b>\n{now.strftime('%A %b %d')}\n" + "━" * 24 + "\n\n"

    for spot in SPOTS:
        data = fetch_spot(spot["slug"])
        if not data or not data.get("waves_ft"):
            msg += f"<b>{spot['name']}</b>\n⚠️ Data unavailable\n\n"
            continue

        msg += f"<b>📍 {spot['name']}</b>\n\n"

        weekend_best, pto_worthy = find_best_windows(data, days)

        # WEEKEND (detailed)
        msg += "<b>WEEKEND</b>\n"
        for i, day in enumerate(days[:7]):
            if day not in ["Sat", "Sun"]:
                continue

            for p, per_name in enumerate(["AM", "PM"]):
                idx = i * 3 + p
                if idx >= len(data.get("ratings", [])):
                    continue

                height = data["waves_ft"][idx] if idx < len(data["waves_ft"]) else "?"
                period = data["periods"][idx] if idx < len(data["periods"]) else "?"
                rating = data["ratings"][idx] if idx < len(data["ratings"]) else "?"
                wind = wind_text(data["wind_states"][idx] if idx < len(data["wind_states"]) else "")

                is_best = (day == weekend_best["day"] and per_name == weekend_best["per"])
                marker = " 🏆" if is_best else ""

                msg += f"{day:3}  {per_name}  {height}ft  {period}s  ⭐{rating}  {wind}{marker}\n"

        # WEEKDAYS (condensed AM only)
        msg += "\n<b>WEEKDAYS</b> <i>(PTO worthy?)</i>\n"
        for i, day in enumerate(days[:7]):
            if day in ["Sat", "Sun"]:
                continue

            idx = i * 3  # AM only
            if idx >= len(data.get("ratings", [])):
                continue

            height = data["waves_ft"][idx] if idx < len(data["waves_ft"]) else "?"
            period = data["periods"][idx] if idx < len(data["periods"]) else "?"
            rating = data["ratings"][idx] if idx < len(data["ratings"]) else "?"
            wind = wind_text(data["wind_states"][idx] if idx < len(data["wind_states"]) else "")

            try:
                pto_flag = " ← worth it" if int(rating) >= WEEKDAY_PTO_THRESHOLD else ""
            except:
                pto_flag = ""

            msg += f"{day}  {height}ft {period}s ⭐{rating} {wind}{pto_flag}\n"

        # Explainer
        explainer = generate_explainer(weekend_best, pto_worthy)
        msg += f"\n<i>{explainer}</i>\n"

        # Water temp
        if data.get("water_temp_f"):
            temp = data["water_temp_f"]
            suit = "full 4/3" if temp < 60 else "3/2" if temp < 65 else "spring" if temp < 70 else "trunks"
            msg += f"\n🌊 Water: {temp}°F ({suit})\n"

        msg += "\n"

    # County rankings
    spots = fetch_county_rankings()
    if spots:
        best3 = [s for s in spots[:5] if s["rating"] >= 3]
        if best3:
            msg += "<b>🏆 Best in LA County</b>\n"
            for s in best3[:3]:
                msg += f"  {s['name']}: ⭐{s['rating']}\n"

    return msg

def hourly_top10():
    """Master blast: surf + weekend windows + beaches + commute + all options"""
    now = datetime.now(TZ)

    msg = f"<b>🏄 SurfBot</b>\n{now.strftime('%A %b %d, %I:%M %p')}\n" + "━" * 28 + "\n\n"

    # ===== SURF TOP 5 =====
    spots = fetch_county_rankings()
    msg += "<b>🌊 SURF NOW (LA County)</b>\n"
    if spots:
        for i, s in enumerate(spots[:5], 1):
            msg += f"{i}. {s['name'][:16]:16} ⭐{s['rating']}\n"

        best = spots[0]["rating"]
        if best >= 5:
            verdict = "✅ Firing - go now!"
        elif best >= 3:
            verdict = "👍 Solid session"
        elif best >= 2:
            verdict = "🤷 Meh but rideable"
        else:
            verdict = "❌ Skip surfing today"
        msg += f"<i>{verdict}</i>\n"
    else:
        msg += "<i>Data unavailable</i>\n"

    # ===== WEEKEND WINDOWS (the good stuff) =====
    msg += "\n<b>📅 WEEKEND WINDOWS</b>\n"
    days = get_day_names()

    # Get data for primary spot
    data = fetch_spot(SPOTS[0]["slug"]) if SPOTS else None

    if data and data.get("waves_ft"):
        weekend_best = {"day": None, "per": None, "rating": -1}

        for i, day in enumerate(days[:7]):
            if day not in ["Sat", "Sun"]:
                continue

            for p, per_name in enumerate(["AM", "PM"]):
                idx = i * 3 + p
                if idx >= len(data.get("ratings", [])):
                    continue

                height = data["waves_ft"][idx] if idx < len(data["waves_ft"]) else "?"
                period = data["periods"][idx] if idx < len(data["periods"]) else "?"
                rating = data["ratings"][idx] if idx < len(data["ratings"]) else "?"
                wind = wind_text(data["wind_states"][idx] if idx < len(data["wind_states"]) else "")

                try:
                    r = int(rating)
                    if r > weekend_best["rating"]:
                        weekend_best = {"day": day, "per": per_name, "rating": r}
                except:
                    pass

                is_best = (day == weekend_best["day"] and per_name == weekend_best["per"])
                is_now = (day == days[0] and
                         ((per_name == "AM" and now.hour < 12) or
                          (per_name == "PM" and now.hour >= 12)))

                marker = ""
                if is_best and is_now:
                    marker = " ← NOW 🏆"
                elif is_best:
                    marker = " 🏆"
                elif is_now:
                    marker = " ← NOW"

                msg += f"{day} {per_name}  {height}ft {period}s ⭐{rating} {wind}{marker}\n"
    else:
        msg += "<i>Forecast unavailable</i>\n"

    # ===== BEACHES =====
    msg += "\n<b>🏖 BEACHES</b>\n"
    # TODO: Real API data
    beach_picks = [
        ("Carp", "68°F", "calm, kid-friendly"),
        ("Belmont", "65°F", "close, light chop"),
        ("Paradise", "66°F", "scenic, $$$ parking"),
    ]
    for name, temp, note in beach_picks:
        msg += f"{name}: {temp} - {note}\n"

    # ===== COMMUTE TIMES =====
    commutes = get_commute_times(["carp", "belmont", "paradise"])
    if commutes:
        msg += "\n<b>🚗 DRIVE</b> <i>(from Glendale)</i>\n"
        names = {"carp": "Carp", "belmont": "Belmont", "paradise": "Paradise"}
        for code, times in commutes.items():
            name = names.get(code, code)
            msg += f"{name:8} → {times['to']:7} back {times['back']}\n"

    # ===== TIMING ADVICE =====
    hour = now.hour
    if hour < 9:
        msg += "\n<i>🌅 Early window - beat crowds</i>"
    elif hour < 12:
        msg += "\n<i>☀️ Good time to head out</i>"
    elif hour < 15:
        msg += "\n<i>🏖 Peak hours - expect crowds</i>"
    else:
        msg += "\n<i>🌇 Winds up, beach clearing out</i>"

    # ===== SCHOOL BREAK NOTICE =====
    break_name = is_during_school_break()
    if break_name:
        msg += f"\n<i>📅 {break_name} - kids are off!</i>"

    # ===== FOOTER WITH ALL OPTIONS =====
    msg += "\n\n" + "━" * 28
    msg += "\n<b>More:</b>"
    msg += "\n/week - Full 7-day forecast"
    msg += "\n/local - All your SoCal beaches"
    msg += "\n/beach spo - Sankt Peter-Ording"
    msg += "\n/beach van - Vancouver BC"
    msg += "\n/coast - CA road trip overview"
    msg += "\n/ - All commands"

    return msg

# ============== BEACH MODE ==============

def local_overview():
    """Overview of all local SoCal beach favorites"""
    now = datetime.now(TZ)

    msg = f"🏖 <b>Your SoCal Beaches</b>\n{now.strftime('%A %b %d')}\n" + "━" * 24 + "\n\n"

    local_spots = {k: v for k, v in BEACH_LOCATIONS.items() if v.get("region") == "local"}

    # Group by rough region (south to north)
    regions = [
        ("San Diego", ["fletcher"]),
        ("Long Beach", ["belmont", "pedro"]),
        ("Malibu", ["paradise", "piedra"]),
        ("Ventura", ["oxnard"]),
        ("Santa Barbara", ["carp", "east"]),
    ]

    for region_name, codes in regions:
        msg += f"<b>{region_name}</b>\n"
        for code in codes:
            if code in local_spots:
                spot = local_spots[code]
                # TODO: Fetch real data
                msg += f"  {spot['name'][:20]:20} 💧62°F\n"
        msg += "\n"

    msg += "<i>Use /beach [code] for details:\npedro, paradise, belmont, fletcher, piedra, oxnard, carp, east</i>\n"
    msg += "\n<i>Note: Temps are placeholder. Vibe code me to add real APIs!</i>"

    return msg

def beach_report(loc_code):
    """Beach conditions for any destination"""
    if not loc_code:
        # Show all available locations
        travel = [f"• {k} - {v['name']}" for k, v in BEACH_LOCATIONS.items() if v.get("region") == "travel"]
        local = [f"• {k} - {v['name']}" for k, v in BEACH_LOCATIONS.items() if v.get("region") == "local"]

        return f"""<b>🏖 Beach Locations</b>

<b>TRAVEL</b>
{chr(10).join(travel)}

<b>LOCAL FAVORITES</b>
{chr(10).join(local)}

Use: /beach [code]
Example: /beach carp

Or /local for SoCal overview"""

    if loc_code not in BEACH_LOCATIONS:
        return f"Unknown location: {loc_code}\n\nType /beach for all options."

    loc = BEACH_LOCATIONS[loc_code]
    now = datetime.now(TZ)

    msg = f"🏖 <b>{loc['name']}</b>\n{now.strftime('%A %b %d, %I:%M %p')}\n" + "━" * 24 + "\n\n"

    # Travel destinations (SPO, Vancouver) - special handling
    if loc_code == "spo":
        msg += """<b>Wind</b> (for kiting)
🌬 15 kts SW - Good for kiting

<b>Tides</b>
🌊 Low:  06:42  (0.3m)
🌊 High: 12:58  (3.1m)
🌊 Low:  19:15  (0.4m)

<b>Temps</b>
💧 Water: 54°F (12°C) - Full wetsuit
🌡 Air: 62°F (17°C)"""
        if loc.get("note"):
            msg += f"\n\n<i>⚠️ {loc['note']}</i>"

    elif loc_code == "van":
        msg += """<b>Tides</b> (English Bay)
🌊 Low:  05:23  (0.8m)
🌊 High: 11:45  (4.2m)
🌊 Low:  18:02  (1.1m)

<b>Temps</b>
💧 Water: 52°F (11°C) - Brisk!
🌡 Air: 58°F (14°C)

<b>Spots</b>
• English Bay - Calm, good swimming
• Kitsilano - Warmer (shallow)
• Spanish Banks - Low tide = huge beach"""

    # Local SoCal beaches
    else:
        msg += """<b>Tides</b>
🌊 Low:  05:45  (1.2ft)
🌊 High: 12:03  (5.1ft)
🌊 Low:  18:22  (0.8ft)
   └─ Now: Rising, ~3ft

<b>Temps</b>
💧 Water: 62°F - Refreshing
🌡 Air: 71°F - Perfect

<b>Conditions</b>
🌊 Waves: 1-2ft, gentle
🌬 Wind: 5 mph W - Light breeze
☀️ UV: High - Bring sunscreen"""

        if loc.get("note"):
            msg += f"\n\n<i>💡 {loc['note']}</i>"

    msg += "\n\n<i>Note: Data is placeholder. Vibe code me to add real APIs!</i>"

    return msg

def coast_overview():
    """California coast overview for road trips"""
    now = datetime.now(TZ)

    msg = f"🚗 <b>California Coast</b>\n{now.strftime('%A %b %d')}\n" + "━" * 24 + "\n\n"

    # TODO: Fetch actual data for each region
    msg += """<b>SAN DIEGO</b>
💧 64°F  |  3ft  |  ⭐4 La Jolla best

<b>LOS ANGELES</b>
💧 62°F  |  2ft  |  ⭐3 Malibu cleanest

<b>SANTA BARBARA</b>
💧 60°F  |  2ft  |  ⭐2 Rincon flat

<b>CENTRAL COAST</b>
💧 56°F  |  4ft  |  ⭐5 Morro Bay firing

<b>SAN FRANCISCO</b>
💧 54°F  |  5ft  |  ⭐4 OB solid but cold

<b>Road Trip Verdict:</b>
Central Coast is the call today. Worth the drive for 4ft+ and less crowd.

<i>Note: Data is placeholder. Vibe code me to add real APIs!</i>"""

    return msg

# ============== BOT ==============

class Bot:
    def __init__(self):
        self.last_update_id = 0

    def listen(self):
        while True:
            try:
                r = requests.get(
                    f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates",
                    params={"offset": self.last_update_id + 1, "timeout": 30},
                    timeout=35
                )
                for u in r.json().get("result", []):
                    self.last_update_id = u["update_id"]
                    text = u.get("message", {}).get("text", "").lower().strip()
                    chat = str(u.get("message", {}).get("chat", {}).get("id", ""))

                    if chat == TELEGRAM_CHAT_ID:
                        self.handle(text)
            except Exception as e:
                print(f"Listen error: {e}")
                time.sleep(5)

    def handle(self, text):
        if text == "/":
            send("""<b>🏄 SurfBot Commands</b>

<b>SURF (LA County)</b>
/surf - Top 10 right now
/week - 7-day forecast

<b>BEACH</b>
/local - Your SoCal favorites
/beach [code] - Specific beach
/coast - CA coast road trip

<b>Beach Codes</b>
Travel: spo, van
Local: pedro, paradise, belmont, fletcher, piedra, oxnard, carp, east

<b>INFO</b>
/help - How to read reports
/ping - Health check""")

        elif text in ["/surf", "/now"]:
            msg = hourly_top10()
            if msg:
                send(msg)

        elif text in ["/week", "/forecast"]:
            send(daily_report())

        elif text == "/local":
            send(local_overview())

        elif text.startswith("/beach"):
            parts = text.split()
            loc = parts[1] if len(parts) > 1 else None
            msg = beach_report(loc)
            if msg:
                send(msg)

        elif text == "/coast":
            msg = coast_overview()
            if msg:
                send(msg)

        elif text == "/help":
            send("""<b>📖 Reading the Reports</b>

<b>SURF MODE (LA)</b>
• Height in feet
• Period in seconds (16s=powerful, 10s=weak)
• ⭐1-10 quality rating
• calm / light wind / windy

<b>When to Go:</b>
⭐5+ = drop everything
⭐3-4 = worth the drive
⭐2 = meh
⭐0-1 = don't bother

<b>BEACH MODE (Travel)</b>
• Tide times + current level
• Water temp
• Wind speed/direction
• Air temp

Type / for all commands""")

        elif text == "/ping":
            send("🏄 SurfBot alive!")

# ============== AUTO-PUSH ALERTS ==============

def is_school_break_tomorrow():
    """Check if tomorrow is start of a GUSD break"""
    tomorrow = (datetime.now(TZ) + timedelta(days=1)).strftime("%Y-%m-%d")
    for start, end, name in GUSD_BREAKS:
        if tomorrow == start:
            return name
    return None

def is_during_school_break():
    """Check if currently in a school break"""
    today = datetime.now(TZ).strftime("%Y-%m-%d")
    for start, end, name in GUSD_BREAKS:
        if start <= today <= end:
            return name
    return None

def weekend_beach_digest():
    """Saturday morning family beach recommendation"""
    if not WEEKEND_BEACH_DIGEST:
        return

    now = datetime.now(TZ)
    if now.weekday() != 5:  # Saturday only
        return

    # TODO: Fetch real weather/conditions from APIs
    msg = f"""🏖 <b>Family Beach Day</b>
{now.strftime('%A %b %d')}

<b>Top Pick:</b> Carpinteria
• 72°F water, 78°F air
• Calm waves - great for kids
• Low tide at 2pm = tide pools

<b>Runner Up:</b> Belmont Shore
• 68°F water, closer to home
• Good if you want to sleep in

<i>Beat the crowds - arrive by 9am</i>

<i>Note: Data is placeholder. Vibe code me for real APIs!</i>"""

    send(msg)

def school_break_alert():
    """Evening alert before school breaks"""
    if not SCHOOL_BREAK_ALERTS:
        return

    break_name = is_school_break_tomorrow()
    if not break_name:
        return

    msg = f"""📅 <b>Kids Off Tomorrow!</b>
{break_name} starts

<b>Beach Forecast:</b>
• Best bet: Carpinteria - calm, kid-friendly
• Water: 62°F
• Air: 74°F

<i>Sleep in, then beach day?</i>

Type /local for all your beaches"""

    send(msg)

def heat_wave_alert():
    """Alert when hot day forecast for inland"""
    if not HEAT_WAVE_ALERTS:
        return

    # TODO: Fetch real forecast for Glendale from weather API
    # Stub for now - would check tomorrow's forecast
    inland_high_f = 85  # Placeholder

    if inland_high_f >= HEAT_THRESHOLD_F:
        msg = f"""🔥 <b>Hot Day Tomorrow</b>
{inland_high_f}°F forecast for Glendale

<b>Beach Escape:</b>
Best pick: Carpinteria - 68°F water
• 15-20°F cooler than inland
• Morning fog clears by 10am

<i>Leave early to beat traffic</i>"""
        send(msg)

def check_evening_alerts():
    """Run evening alert checks (8 PM)"""
    school_break_alert()
    # heat_wave_alert()  # Enable when weather API is wired up

# ============== SCHEDULER ==============

def run_scheduler():
    # Daily surf report at 6 AM
    schedule.every().day.at(f"{DAILY_HOUR:02d}:00").do(lambda: send(daily_report()))

    # Saturday beach digest at 7 AM
    schedule.every().saturday.at("07:00").do(weekend_beach_digest)

    # Evening alerts at 8 PM (school breaks, heat waves)
    schedule.every().day.at("20:00").do(check_evening_alerts)

    # Hourly surf updates 6 AM - 6 PM
    schedule.every().hour.at(":00").do(maybe_hourly)

    while True:
        schedule.run_pending()
        time.sleep(30)

def maybe_hourly():
    hour = datetime.now(TZ).hour
    if TICKER_START <= hour < TICKER_END:
        msg = hourly_top10()
        if msg:
            send(msg)

def main():
    print("🏄 SurfBot starting...")
    now = datetime.now(TZ)
    send(f"🏄 <b>SurfBot Online</b>\n{now.strftime('%I:%M %p')}\n\n/surf - now\n/week - forecast")
    threading.Thread(target=run_scheduler, daemon=True).start()
    Bot().listen()

if __name__ == "__main__":
    main()
