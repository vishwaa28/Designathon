"""Static reference data for the simulated multimodal network."""

AIRLINE = {"code": "MR", "name": "Meridian Airways"}
RAIL_OPERATOR = {"code": "NR", "name": "Northstar Rail"}

AIRPORTS = {
    "DEL": {"name": "Indira Gandhi International", "city": "Delhi", "lat": 28.5562, "lon": 77.1000},
    "BOM": {"name": "Chhatrapati Shivaji Maharaj International", "city": "Mumbai", "lat": 19.0896, "lon": 72.8656},
    "BLR": {"name": "Kempegowda International", "city": "Bengaluru", "lat": 13.1986, "lon": 77.7066},
    "MAA": {"name": "Chennai International", "city": "Chennai", "lat": 12.9941, "lon": 80.1709},
    "HYD": {"name": "Rajiv Gandhi International", "city": "Hyderabad", "lat": 17.2403, "lon": 78.4294},
    "CCU": {"name": "Netaji Subhas Chandra Bose International", "city": "Kolkata", "lat": 22.6547, "lon": 88.4467},
    "COK": {"name": "Cochin International", "city": "Kochi", "lat": 10.1520, "lon": 76.4019},
    "GOI": {"name": "Goa International", "city": "Goa", "lat": 15.3808, "lon": 73.8314},
    "PNQ": {"name": "Pune International", "city": "Pune", "lat": 18.5822, "lon": 73.9197},
    "AMD": {"name": "Sardar Vallabhbhai Patel International", "city": "Ahmedabad", "lat": 23.0772, "lon": 72.6347},
    "LKO": {"name": "Chaudhary Charan Singh International", "city": "Lucknow", "lat": 26.7606, "lon": 80.8893},
    "JAI": {"name": "Jaipur International", "city": "Jaipur", "lat": 26.8242, "lon": 75.8122},
}

STATIONS = {
    "NDLS": {"name": "New Delhi", "city": "Delhi", "lat": 28.6430, "lon": 77.2194},
    "AGC": {"name": "Agra Cantt", "city": "Agra", "lat": 27.1588, "lon": 77.9902},
    "BPL": {"name": "Bhopal Junction", "city": "Bhopal", "lat": 23.2665, "lon": 77.4126},
    "JP": {"name": "Jaipur Junction", "city": "Jaipur", "lat": 26.9196, "lon": 75.7878},
    "LKO": {"name": "Lucknow Charbagh", "city": "Lucknow", "lat": 26.8317, "lon": 80.9203},
    "CSMT": {"name": "Mumbai CSMT", "city": "Mumbai", "lat": 18.9402, "lon": 72.8356},
    "PUNE": {"name": "Pune Junction", "city": "Pune", "lat": 18.5286, "lon": 73.8743},
    "ADI": {"name": "Ahmedabad Junction", "city": "Ahmedabad", "lat": 23.0262, "lon": 72.6008},
    "SBC": {"name": "KSR Bengaluru", "city": "Bengaluru", "lat": 12.9781, "lon": 77.5697},
    "MAS": {"name": "Chennai Central", "city": "Chennai", "lat": 13.0827, "lon": 80.2752},
    "SC": {"name": "Secunderabad Junction", "city": "Hyderabad", "lat": 17.4337, "lon": 78.5016},
}

# Station codes collide with airport codes for Lucknow, so rail nodes are namespaced internally.
def station_key(code: str) -> str:
    return f"R:{code}"


def place(code: str) -> dict:
    if code.startswith("R:"):
        return STATIONS[code[2:]]
    return AIRPORTS[code]


def city_of(code: str) -> str:
    return place(code)["city"]


def display_code(code: str) -> str:
    return code[2:] if code.startswith("R:") else code


# Aircraft: tail, type, seats, home base, rotation destinations (out-and-back from base).
AIRCRAFT = [
    ("VT-MRA", "A320neo", 180, "DEL", ["BOM", "LKO"]),
    ("VT-MRB", "A321neo", 220, "DEL", ["BLR", "JAI"]),
    ("VT-MRT", "A320neo", 180, "DEL", ["MAA", "LKO"]),
    ("VT-MRD", "A320neo", 180, "DEL", ["HYD", "AMD"]),
    ("VT-MRU", "A321neo", 220, "DEL", ["BOM", "HYD"]),
    ("VT-MRE", "A320neo", 180, "DEL", ["CCU", "JAI"]),
    ("VT-MRF", "A321neo", 220, "DEL", ["BOM", "GOI"]),
    ("VT-MRG", "ATR72-600", 72, "DEL", ["JAI", "LKO", "JAI"]),
    ("VT-MRH", "A320neo", 180, "DEL", ["PNQ", "AMD"]),
    ("VT-MRC", "A320neo", 180, "BOM", ["DEL", "GOI"]),
    ("VT-MRJ", "B737-8", 189, "BOM", ["BLR", "AMD"]),
    ("VT-MRK", "A320neo", 180, "BOM", ["HYD", "COK"]),
    ("VT-MRL", "A321neo", 220, "BOM", ["DEL", "JAI"]),
    ("VT-MRM", "A320neo", 180, "BOM", ["MAA", "GOI"]),
    ("VT-MRN", "B737-8", 189, "BLR", ["DEL", "COK"]),
    ("VT-MRP", "A320neo", 180, "BLR", ["BOM", "HYD"]),
    ("VT-MRQ", "A320neo", 180, "HYD", ["DEL", "MAA"]),
]
SPARE_AIRCRAFT = [("VT-MRS", "A320neo", 180, "DEL")]

# Rail rakes: rake id, type, seats, route (stations in order). Each rake runs an out-and-back.
RAKES = [
    ("RK-201", "Vande Bharat 16-car", 420, ["NDLS", "AGC"]),
    ("RK-202", "LHB 22-coach", 460, ["NDLS", "AGC", "BPL"]),
    ("RK-203", "Vande Bharat 16-car", 420, ["NDLS", "AGC", "BPL"]),
    ("RK-204", "LHB 22-coach", 460, ["NDLS", "AGC"]),
    ("RK-205", "Shatabdi 18-coach", 380, ["NDLS", "JP"]),
    ("RK-206", "Shatabdi 18-coach", 380, ["NDLS", "LKO"]),
    ("RK-207", "LHB 22-coach", 460, ["NDLS", "AGC", "BPL"]),
    ("RK-208", "Deccan 16-coach", 360, ["CSMT", "PUNE"]),
    ("RK-209", "Deccan 16-coach", 360, ["CSMT", "PUNE"]),
    ("RK-210", "Vande Bharat 8-car", 300, ["CSMT", "ADI"]),
    ("RK-211", "Shatabdi 18-coach", 380, ["SBC", "MAS"]),
    ("RK-212", "LHB 22-coach", 460, ["MAS", "SC"]),
    ("RK-213", "Vande Bharat 8-car", 300, ["NDLS", "JP"]),
    ("RK-214", "Deccan 16-coach", 360, ["CSMT", "PUNE"]),
    ("RK-215", "Shatabdi 18-coach", 380, ["SBC", "MAS"]),
]

FIRST_NAMES = [
    "Aarav", "Vivaan", "Aditya", "Arjun", "Reyansh", "Ishaan", "Kabir", "Rohan", "Siddharth", "Vikram",
    "Rahul", "Karthik", "Nikhil", "Pranav", "Imran", "Joseph", "Ananya", "Diya", "Isha", "Kavya",
    "Meera", "Nisha", "Pooja", "Riya", "Saanvi", "Sneha", "Tanvi", "Aditi", "Lakshmi", "Fatima",
    "Priya", "Divya", "Neha", "Shreya", "Anjali", "Sara", "Harini", "Gayatri", "Zoya", "Maria",
]
LAST_NAMES = [
    "Sharma", "Verma", "Iyer", "Nair", "Reddy", "Rao", "Patel", "Shah", "Mehta", "Gupta",
    "Singh", "Kapoor", "Menon", "Pillai", "Banerjee", "Chatterjee", "Das", "Mukherjee", "Kulkarni", "Joshi",
    "Deshpande", "Khan", "Fernandes", "D'Souza", "Agarwal", "Bhat", "Hegde", "Naidu", "Ghosh", "Malhotra",
]

CITY_LANGUAGE = {
    "Delhi": "hi", "Agra": "hi", "Bhopal": "hi", "Jaipur": "hi", "Lucknow": "hi",
    "Mumbai": "mr", "Pune": "mr", "Ahmedabad": "gu", "Goa": "en",
    "Bengaluru": "kn", "Chennai": "ta", "Hyderabad": "te", "Kolkata": "bn", "Kochi": "ml",
}

LANGUAGES = {
    "en": "English", "hi": "Hindi", "mr": "Marathi", "gu": "Gujarati", "kn": "Kannada",
    "ta": "Tamil", "te": "Telugu", "bn": "Bengali", "ml": "Malayalam",
}

MAINTENANCE_TEAMS = [
    {"id": "MT-SNT-NDLS", "name": "Signal & Telecom Response, New Delhi", "skill": "SIGNALLING", "base": "R:NDLS", "eta_min": 55, "members": 4},
    {"id": "MT-SNT-AGC", "name": "Signal & Telecom Response, Agra", "skill": "SIGNALLING", "base": "R:AGC", "eta_min": 40, "members": 3},
    {"id": "MT-PWAY-CSMT", "name": "Permanent Way & Track, Mumbai", "skill": "TRACK", "base": "R:CSMT", "eta_min": 70, "members": 6},
    {"id": "MT-OHE-NDLS", "name": "Overhead Equipment Unit, New Delhi", "skill": "OHE", "base": "R:NDLS", "eta_min": 45, "members": 5},
    {"id": "MT-AIRSIDE-DEL", "name": "Airside Operations & Runway Safety, DEL", "skill": "AIRSIDE", "base": "DEL", "eta_min": 10, "members": 8},
    {"id": "MT-AIRSIDE-BOM", "name": "Airside Operations & Runway Safety, BOM", "skill": "AIRSIDE", "base": "BOM", "eta_min": 10, "members": 6},
    {"id": "MT-LINE-BOM", "name": "Line Maintenance B1/B2, BOM", "skill": "AIRCRAFT", "base": "BOM", "eta_min": 20, "members": 4},
    {"id": "MT-LINE-DEL", "name": "Line Maintenance B1/B2, DEL", "skill": "AIRCRAFT", "base": "DEL", "eta_min": 20, "members": 5},
]

INFRA_ASSETS = [
    {"id": "DEL-RWY-1028", "name": "Runway 10/28", "type": "RUNWAY", "category": "Airside", "location": "DEL",
     "criticality": "CRITICAL", "metrics": {"friction_coefficient": 0.72, "standing_water_mm": 0.0, "crosswind_kt": 6.0}},
    {"id": "DEL-RWY-1129", "name": "Runway 11/29", "type": "RUNWAY", "category": "Airside", "location": "DEL",
     "criticality": "CRITICAL", "metrics": {"friction_coefficient": 0.70, "standing_water_mm": 0.0, "crosswind_kt": 5.0}},
    {"id": "DEL-ILS-28", "name": "ILS CAT-IIIB Runway 28", "type": "NAVAID", "category": "Airside", "location": "DEL",
     "criticality": "HIGH", "metrics": {"localizer_signal_dbm": -62.0, "glide_slope_dev_deg": 0.02}},
    {"id": "BOM-RWY-0927", "name": "Runway 09/27", "type": "RUNWAY", "category": "Airside", "location": "BOM",
     "criticality": "CRITICAL", "metrics": {"friction_coefficient": 0.69, "standing_water_mm": 0.0, "crosswind_kt": 8.0}},
    {"id": "BLR-BHS-02", "name": "Baggage Sorter Line 2", "type": "BAGGAGE", "category": "Terminal", "location": "BLR",
     "criticality": "MEDIUM", "metrics": {"throughput_bags_hr": 2650.0, "jam_rate_pct": 0.4}},
    {"id": "NR-SIG-BS114", "name": "Block Signal BS-114 (Interlocking)", "type": "SIGNAL", "category": "Signalling",
     "location": "R:NDLS", "corridor": ["R:NDLS", "R:AGC"], "criticality": "CRITICAL",
     "metrics": {"relay_voltage_v": 24.1, "response_ms": 118.0, "track_circuit_ohm": 3.2}},
    {"id": "NR-PM-22", "name": "Point Machine PM-22", "type": "POINT_MACHINE", "category": "Signalling",
     "location": "R:AGC", "corridor": ["R:NDLS", "R:AGC"], "criticality": "HIGH",
     "metrics": {"throw_time_s": 4.1, "motor_current_a": 3.8}},
    {"id": "NR-OHE-LKO7", "name": "OHE Section NDLS-LKO km 7", "type": "OHE", "category": "Traction",
     "location": "R:NDLS", "corridor": ["R:NDLS", "R:LKO"], "criticality": "HIGH",
     "metrics": {"catenary_voltage_kv": 25.0, "tension_kn": 10.2}},
    {"id": "NR-TC-48", "name": "Track Circuit TC-48 (Ghat Section)", "type": "TRACK_CIRCUIT", "category": "Track",
     "location": "R:CSMT", "corridor": ["R:CSMT", "R:PUNE"], "criticality": "CRITICAL",
     "metrics": {"rail_temp_c": 31.0, "shunt_resistance_ohm": 0.4, "water_above_rail_mm": 0.0}},
]

# Reserve / standby crew available at each base.
RESERVE_CREW = {
    "DEL": {"CPT": 2, "FO": 2, "CC": 6},
    "BOM": {"CPT": 2, "FO": 1, "CC": 4},
    "BLR": {"CPT": 1, "FO": 1, "CC": 2},
    "HYD": {"CPT": 1, "FO": 1, "CC": 2},
    "R:NDLS": {"LP": 3, "ALP": 3, "GRD": 2},
    "R:CSMT": {"LP": 2, "ALP": 2, "GRD": 2},
    "R:SBC": {"LP": 1, "ALP": 1, "GRD": 1},
    "R:MAS": {"LP": 1, "ALP": 1, "GRD": 1},
}

ROLE_LABELS = {
    "CPT": "Captain", "FO": "First Officer", "CC": "Cabin Crew",
    "LP": "Loco Pilot", "ALP": "Asst. Loco Pilot", "GRD": "Train Manager",
}
