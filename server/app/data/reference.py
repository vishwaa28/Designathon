"""Static reference data for the simulated multimodal network, centred on the Chennai hub."""

AIRLINE = {"code": "MR", "name": "Meridian Airways"}
RAIL_OPERATOR = {"code": "NR", "name": "Southern Rail"}

HUB_AIRPORT = "MAA"
HUB_STATION = "R:MAS"

AIRPORTS = {
    "MAA": {"name": "Chennai International", "city": "Chennai", "lat": 12.9941, "lon": 80.1709},
    "BLR": {"name": "Kempegowda International", "city": "Bengaluru", "lat": 13.1986, "lon": 77.7066},
    "HYD": {"name": "Rajiv Gandhi International", "city": "Hyderabad", "lat": 17.2403, "lon": 78.4294},
    "COK": {"name": "Cochin International", "city": "Kochi", "lat": 10.1520, "lon": 76.4019},
    "CJB": {"name": "Coimbatore International", "city": "Coimbatore", "lat": 11.0300, "lon": 77.0434},
    "IXM": {"name": "Madurai Airport", "city": "Madurai", "lat": 9.8345, "lon": 78.0934},
    "TRZ": {"name": "Tiruchirappalli International", "city": "Tiruchirappalli", "lat": 10.7654, "lon": 78.7097},
    "TRV": {"name": "Thiruvananthapuram International", "city": "Thiruvananthapuram", "lat": 8.4821, "lon": 76.9201},
    "IXE": {"name": "Mangaluru International", "city": "Mangaluru", "lat": 12.9613, "lon": 74.8901},
    "VGA": {"name": "Vijayawada International", "city": "Vijayawada", "lat": 16.5304, "lon": 80.7968},
    "TIR": {"name": "Tirupati Airport", "city": "Tirupati", "lat": 13.6325, "lon": 79.5433},
    "DEL": {"name": "Indira Gandhi International", "city": "Delhi", "lat": 28.5562, "lon": 77.1000},
    "BOM": {"name": "Chhatrapati Shivaji Maharaj International", "city": "Mumbai", "lat": 19.0896, "lon": 72.8656},
    "CCU": {"name": "Netaji Subhas Chandra Bose International", "city": "Kolkata", "lat": 22.6547, "lon": 88.4467},
    "GOI": {"name": "Goa International", "city": "Goa", "lat": 15.3808, "lon": 73.8314},
    "PNQ": {"name": "Pune International", "city": "Pune", "lat": 18.5822, "lon": 73.9197},
}

STATIONS = {
    "MAS": {"name": "Chennai Central", "city": "Chennai", "lat": 13.0827, "lon": 80.2752},
    "MS": {"name": "Chennai Egmore", "city": "Chennai", "lat": 13.0780, "lon": 80.2614},
    "AJJ": {"name": "Arakkonam Junction", "city": "Arakkonam", "lat": 13.0838, "lon": 79.6707},
    "KPD": {"name": "Katpadi Junction", "city": "Vellore", "lat": 12.9716, "lon": 79.1378},
    "SBC": {"name": "KSR Bengaluru", "city": "Bengaluru", "lat": 12.9781, "lon": 77.5697},
    "SA": {"name": "Salem Junction", "city": "Salem", "lat": 11.6710, "lon": 78.1137},
    "ED": {"name": "Erode Junction", "city": "Erode", "lat": 11.3318, "lon": 77.7280},
    "CBE": {"name": "Coimbatore Junction", "city": "Coimbatore", "lat": 10.9965, "lon": 76.9669},
    "VM": {"name": "Villupuram Junction", "city": "Villupuram", "lat": 11.9420, "lon": 79.4879},
    "TPJ": {"name": "Tiruchchirappalli Junction", "city": "Tiruchirappalli", "lat": 10.7951, "lon": 78.6871},
    "MDU": {"name": "Madurai Junction", "city": "Madurai", "lat": 9.9195, "lon": 78.1093},
    "GDR": {"name": "Gudur Junction", "city": "Gudur", "lat": 14.1450, "lon": 79.8513},
    "BZA": {"name": "Vijayawada Junction", "city": "Vijayawada", "lat": 16.5176, "lon": 80.6195},
    "SC": {"name": "Secunderabad Junction", "city": "Hyderabad", "lat": 17.4337, "lon": 78.5016},
}

# Station codes can collide with airport codes, so rail nodes are namespaced internally.
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
    ("VT-MRA", "A320neo", 180, "MAA", ["DEL", "BLR"]),
    ("VT-MRB", "A321neo", 220, "MAA", ["BOM", "HYD"]),
    ("VT-MRT", "A320neo", 180, "MAA", ["CJB", "COK"]),
    ("VT-MRD", "A320neo", 180, "MAA", ["TRV", "HYD"]),
    ("VT-MRU", "A321neo", 220, "MAA", ["DEL", "IXM"]),
    ("VT-MRE", "A320neo", 180, "MAA", ["CCU", "TRZ"]),
    ("VT-MRF", "A321neo", 220, "MAA", ["BOM", "BLR"]),
    ("VT-MRG", "ATR72-600", 72, "MAA", ["IXM", "TRZ", "CJB"]),
    ("VT-MRH", "ATR72-600", 72, "MAA", ["VGA", "TRZ", "VGA"]),
    ("VT-MRC", "A320neo", 180, "MAA", ["GOI", "HYD"]),
    ("VT-MRP", "A320neo", 180, "MAA", ["PNQ", "CJB"]),
    ("VT-MRV", "A320neo", 180, "MAA", ["IXE", "BLR"]),
    ("VT-MRJ", "B737-8", 189, "BLR", ["MAA", "DEL"]),
    ("VT-MRK", "A320neo", 180, "HYD", ["MAA", "COK"]),
    ("VT-MRL", "A321neo", 220, "DEL", ["MAA", "BOM"]),
    ("VT-MRM", "A320neo", 180, "BOM", ["MAA", "BLR"]),
    ("VT-MRN", "B737-8", 189, "COK", ["MAA", "BLR"]),
    ("VT-MRQ", "A320neo", 180, "BLR", ["HYD", "MAA"]),
]
SPARE_AIRCRAFT = [("VT-MRS", "A320neo", 180, "BLR")]

# Rail rakes: rake id, type, seats, route (stations in order). Each rake runs an out-and-back.
# List order sets the first departure (55 min apart from four hours before the current hour), so
# rakes through the scenario corridors are spaced to be on the line around "now".
RAKES = [
    ("RK-205", "Vande Bharat 8-car", 300, ["MS", "VM", "TPJ", "MDU"]),
    ("RK-201", "Vande Bharat 16-car", 420, ["MAS", "AJJ", "KPD", "SBC"]),
    ("RK-206", "LHB 22-coach", 460, ["MS", "VM", "TPJ", "MDU"]),
    ("RK-202", "Shatabdi 18-coach", 380, ["MAS", "AJJ", "KPD", "SBC"]),
    ("RK-209", "Intercity 16-coach", 360, ["MAS", "AJJ", "KPD"]),
    ("RK-203", "Vande Bharat 8-car", 300, ["MAS", "AJJ", "KPD", "SA", "ED", "CBE"]),
    ("RK-207", "LHB 22-coach", 460, ["MAS", "GDR", "BZA", "SC"]),
    ("RK-211", "Shatabdi 18-coach", 380, ["MAS", "AJJ", "KPD", "SBC"]),
    ("RK-208", "Vande Bharat 8-car", 300, ["MAS", "GDR", "BZA"]),
    ("RK-204", "LHB 22-coach", 460, ["MAS", "AJJ", "KPD", "SA", "ED", "CBE"]),
    ("RK-210", "Intercity 16-coach", 360, ["MS", "VM", "TPJ"]),
    ("RK-213", "LHB 22-coach", 460, ["MAS", "AJJ", "KPD", "SA", "ED", "CBE"]),
    ("RK-212", "Intercity 16-coach", 360, ["MAS", "GDR"]),
    ("RK-215", "Intercity 16-coach", 360, ["MAS", "AJJ"]),
    ("RK-214", "Shatabdi 18-coach", 380, ["MS", "VM", "TPJ", "MDU"]),
]

FIRST_NAMES = [
    "Karthik", "Arjun", "Vignesh", "Surya", "Prakash", "Saravanan", "Senthil", "Murugan", "Balaji", "Dinesh",
    "Gokul", "Hari", "Ashwin", "Pradeep", "Naveen", "Sanjay", "Venkatesh", "Srinivas", "Ravi", "Manoj",
    "Abhishek", "Rahul", "Anand", "Vishnu", "Akhil", "Arun", "Sreejith", "Nithin", "Kiran", "Raghav",
    "Priya", "Divya", "Lakshmi", "Meenakshi", "Kavya", "Deepika", "Swathi", "Harini", "Gayathri", "Nandhini",
    "Keerthana", "Aishwarya", "Revathi", "Sangeetha", "Janani", "Anitha", "Bhavana", "Sowmya", "Pavithra", "Ramya",
    "Anjali", "Aparna", "Sneha", "Sruthi", "Shalini", "Malavika", "Nivetha", "Yamini", "Haritha", "Sindhu",
]
LAST_NAMES = [
    "Iyer", "Iyengar", "Krishnan", "Subramanian", "Rajan", "Natarajan", "Venkatesan", "Ramasamy", "Murugesan",
    "Shanmugam", "Arumugam", "Annamalai", "Selvaraj", "Sundaram", "Balasubramanian", "Ganesan", "Srinivasan",
    "Raghavan", "Pillai", "Nair", "Menon", "Kurup", "Varghese", "Kuriakose", "Thomas", "Reddy", "Naidu",
    "Rao", "Chowdary", "Varma", "Gowda", "Hegde", "Shetty", "Kamath", "Bhat", "Chandrasekaran", "Palanisamy",
]

CITY_LANGUAGE = {
    "Chennai": "ta", "Arakkonam": "ta", "Vellore": "ta", "Salem": "ta", "Erode": "ta", "Coimbatore": "ta",
    "Villupuram": "ta", "Tiruchirappalli": "ta", "Madurai": "ta",
    "Hyderabad": "te", "Vijayawada": "te", "Gudur": "te", "Tirupati": "te",
    "Bengaluru": "kn", "Mangaluru": "kn", "Kochi": "ml", "Thiruvananthapuram": "ml",
    "Delhi": "hi", "Mumbai": "mr", "Pune": "mr", "Kolkata": "bn", "Goa": "en",
}

LANGUAGES = {
    "en": "English", "hi": "Hindi", "mr": "Marathi", "gu": "Gujarati", "kn": "Kannada",
    "ta": "Tamil", "te": "Telugu", "bn": "Bengali", "ml": "Malayalam",
}

# Passengers with real contact details. They are seeded on every run and attached to the
# services hit by each disruption so they receive the e-mail / SMS notifications.
CONTACT_PASSENGERS = [
    {"pnr": "VSHWA1", "first_name": "Vishwaa", "last_name": "Yuvaraj", "email": "vishwaayuvaraj@gmail.com",
     "phone": "+919597458656", "language": "en", "tier": "GOLD"},
    {"pnr": "TAUSF2", "first_name": "Lathifunisa", "last_name": "Tausifa", "email": "lathifunisatausifa@gmail.com",
     "phone": "+918610472292", "language": "en", "tier": None},
    {"pnr": "AMALS3", "first_name": "Amal", "last_name": "Sivan", "email": "amalsivan1753@gmail.com",
     "phone": "+918897439734", "language": "en", "tier": "SILVER"},
    {"pnr": "SUSHM4", "first_name": "Sushmitha", "last_name": "Saravanan", "email": "sus200327@gmail.com",
     "phone": "+916381758235", "language": "en", "tier": None},
]

MAINTENANCE_TEAMS = [
    {"id": "MT-AIRSIDE-MAA", "name": "Airside Operations & Runway Safety, MAA", "skill": "AIRSIDE", "base": "MAA", "eta_min": 10, "members": 8},
    {"id": "MT-LINE-MAA", "name": "Line Maintenance B1/B2, MAA", "skill": "AIRCRAFT", "base": "MAA", "eta_min": 15, "members": 6},
    {"id": "MT-AIRSIDE-BLR", "name": "Airside Operations & Runway Safety, BLR", "skill": "AIRSIDE", "base": "BLR", "eta_min": 12, "members": 6},
    {"id": "MT-LINE-BLR", "name": "Line Maintenance B1/B2, BLR", "skill": "AIRCRAFT", "base": "BLR", "eta_min": 25, "members": 4},
    {"id": "MT-SNT-MAS", "name": "Signal & Telecom Response, Chennai Central", "skill": "SIGNALLING", "base": "R:MAS", "eta_min": 40, "members": 4},
    {"id": "MT-SNT-AJJ", "name": "Signal & Telecom Response, Arakkonam", "skill": "SIGNALLING", "base": "R:AJJ", "eta_min": 35, "members": 3},
    {"id": "MT-PWAY-MAS", "name": "Permanent Way & Track, Chennai", "skill": "TRACK", "base": "R:MAS", "eta_min": 60, "members": 6},
    {"id": "MT-OHE-MS", "name": "Overhead Equipment Unit, Chennai Egmore", "skill": "OHE", "base": "R:MS", "eta_min": 45, "members": 5},
]

INFRA_ASSETS = [
    {"id": "MAA-RWY-0725", "name": "Runway 07/25", "type": "RUNWAY", "category": "Airside", "location": "MAA",
     "criticality": "CRITICAL", "metrics": {"friction_coefficient": 0.71, "standing_water_mm": 0.0, "crosswind_kt": 7.0}},
    {"id": "MAA-RWY-1230", "name": "Runway 12/30", "type": "RUNWAY", "category": "Airside", "location": "MAA",
     "criticality": "CRITICAL", "metrics": {"friction_coefficient": 0.69, "standing_water_mm": 0.0, "crosswind_kt": 6.0}},
    {"id": "MAA-ILS-07", "name": "ILS CAT-II Runway 07", "type": "NAVAID", "category": "Airside", "location": "MAA",
     "criticality": "HIGH", "metrics": {"localizer_signal_dbm": -61.0, "glide_slope_dev_deg": 0.02}},
    {"id": "MAA-BHS-T1", "name": "Baggage Sorter, Terminal 1", "type": "BAGGAGE", "category": "Terminal", "location": "MAA",
     "criticality": "MEDIUM", "metrics": {"throughput_bags_hr": 2400.0, "jam_rate_pct": 0.5}},
    {"id": "BLR-RWY-09L", "name": "Runway 09L/27R", "type": "RUNWAY", "category": "Airside", "location": "BLR",
     "criticality": "CRITICAL", "metrics": {"friction_coefficient": 0.72, "standing_water_mm": 0.0, "crosswind_kt": 5.0}},
    {"id": "NR-SIG-AJJ14", "name": "Block Signal AJJ-14 (Interlocking)", "type": "SIGNAL", "category": "Signalling",
     "location": "R:MAS", "corridor": ["R:MAS", "R:AJJ"], "criticality": "CRITICAL",
     "metrics": {"relay_voltage_v": 24.1, "response_ms": 118.0, "track_circuit_ohm": 3.2}},
    {"id": "NR-PM-KPD22", "name": "Point Machine PM-22, Katpadi", "type": "POINT_MACHINE", "category": "Signalling",
     "location": "R:KPD", "corridor": ["R:AJJ", "R:KPD"], "criticality": "HIGH",
     "metrics": {"throw_time_s": 4.1, "motor_current_a": 3.8}},
    {"id": "NR-OHE-MSVM", "name": "OHE Section Egmore-Villupuram km 34", "type": "OHE", "category": "Traction",
     "location": "R:MS", "corridor": ["R:MS", "R:VM"], "criticality": "HIGH",
     "metrics": {"catenary_voltage_kv": 25.0, "tension_kn": 10.2}},
    {"id": "NR-TC-31", "name": "Track Circuit TC-31 (Ennore-Ponneri)", "type": "TRACK_CIRCUIT", "category": "Track",
     "location": "R:MAS", "corridor": ["R:MAS", "R:GDR"], "criticality": "CRITICAL",
     "metrics": {"rail_temp_c": 30.0, "shunt_resistance_ohm": 0.4, "water_above_rail_mm": 0.0}},
]

# Reserve / standby crew available at each base.
RESERVE_CREW = {
    "MAA": {"CPT": 3, "FO": 3, "CC": 8},
    "BLR": {"CPT": 2, "FO": 2, "CC": 4},
    "HYD": {"CPT": 1, "FO": 1, "CC": 2},
    "COK": {"CPT": 1, "FO": 1, "CC": 2},
    "DEL": {"CPT": 1, "FO": 1, "CC": 2},
    "BOM": {"CPT": 1, "FO": 1, "CC": 2},
    "R:MAS": {"LP": 3, "ALP": 3, "GRD": 3},
    "R:SBC": {"LP": 1, "ALP": 1, "GRD": 1},
    "R:CBE": {"LP": 1, "ALP": 1, "GRD": 1},
    "R:MDU": {"LP": 1, "ALP": 1, "GRD": 1},
}

ROLE_LABELS = {
    "CPT": "Captain", "FO": "First Officer", "CC": "Cabin Crew",
    "LP": "Loco Pilot", "ALP": "Asst. Loco Pilot", "GRD": "Train Manager",
}
