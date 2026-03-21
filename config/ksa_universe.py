"""
KSA (Saudi Arabia) Stock Universe Configuration
Tadawul / Saudi Exchange listed stocks
Symbols use the format: NNNN.SR (4-digit code + .SR suffix)
"""

# Top 50 KSA stocks by market cap / liquidity (Tadawul)
KSA_TOP50 = [
    # Banking & Financial Services
    {"symbol": "1180.SR", "name_en": "Al Rajhi Bank",             "name_ar": "مصرف الراجحي",             "sector_en": "Banking",              "sector_ar": "البنوك"},
    {"symbol": "1120.SR", "name_en": "Al Jazira Bank",            "name_ar": "بنك الجزيرة",              "sector_en": "Banking",              "sector_ar": "البنوك"},
    {"symbol": "1140.SR", "name_en": "Al Bilad Bank",             "name_ar": "بنك البلاد",               "sector_en": "Banking",              "sector_ar": "البنوك"},
    {"symbol": "1010.SR", "name_en": "Riyad Bank",                "name_ar": "بنك الرياض",               "sector_en": "Banking",              "sector_ar": "البنوك"},
    {"symbol": "1020.SR", "name_en": "Bank AlJazira",             "name_ar": "بنك الجزيرة",              "sector_en": "Banking",              "sector_ar": "البنوك"},
    {"symbol": "1030.SR", "name_en": "Saudi Investment Bank",     "name_ar": "البنك السعودي للاستثمار",  "sector_en": "Banking",              "sector_ar": "البنوك"},
    {"symbol": "1050.SR", "name_en": "Banque Saudi Fransi",       "name_ar": "بنك ساب السعودي الفرنسي", "sector_en": "Banking",              "sector_ar": "البنوك"},
    {"symbol": "1060.SR", "name_en": "Saudi Arabian British Bank","name_ar": "البنك السعودي البريطاني",  "sector_en": "Banking",              "sector_ar": "البنوك"},
    {"symbol": "1080.SR", "name_en": "Arab National Bank",        "name_ar": "البنك العربي الوطني",      "sector_en": "Banking",              "sector_ar": "البنوك"},
    {"symbol": "1150.SR", "name_en": "Alinma Bank",               "name_ar": "مصرف الإنماء",             "sector_en": "Banking",              "sector_ar": "البنوك"},
    {"symbol": "1160.SR", "name_en": "Al-Rajhi Takaful",          "name_ar": "الراجحي للتكافل",          "sector_en": "Insurance",            "sector_ar": "التأمين"},
    {"symbol": "1170.SR", "name_en": "Saudi National Bank",       "name_ar": "البنك الأهلي السعودي",     "sector_en": "Banking",              "sector_ar": "البنوك"},
    # Energy & Petrochemicals
    {"symbol": "2222.SR", "name_en": "Saudi Aramco",              "name_ar": "أرامكو السعودية",          "sector_en": "Energy",               "sector_ar": "الطاقة"},
    {"symbol": "2010.SR", "name_en": "SABIC",                     "name_ar": "سابك",                     "sector_en": "Petrochemicals",       "sector_ar": "البتروكيماويات"},
    {"symbol": "2020.SR", "name_en": "Saudi Industrial Investment","name_ar": "الاستثمار الصناعي السعودي","sector_en": "Petrochemicals",      "sector_ar": "البتروكيماويات"},
    {"symbol": "2030.SR", "name_en": "SAFCO",                     "name_ar": "سافكو",                    "sector_en": "Petrochemicals",       "sector_ar": "البتروكيماويات"},
    {"symbol": "2060.SR", "name_en": "Yanbu National Petrochemicals","name_ar": "ينساب",                 "sector_en": "Petrochemicals",       "sector_ar": "البتروكيماويات"},
    {"symbol": "2080.SR", "name_en": "National Industrialization", "name_ar": "التصنيع الوطنية",         "sector_en": "Petrochemicals",       "sector_ar": "البتروكيماويات"},
    {"symbol": "2090.SR", "name_en": "National Petrochemical",    "name_ar": "الوطنية للبتروكيماويات",   "sector_en": "Petrochemicals",       "sector_ar": "البتروكيماويات"},
    {"symbol": "2100.SR", "name_en": "Gulf International Services","name_ar": "الخليج الدولية للخدمات", "sector_en": "Energy",               "sector_ar": "الطاقة"},
    # Telecom
    {"symbol": "7010.SR", "name_en": "Saudi Telecom Company",     "name_ar": "شركة الاتصالات السعودية",  "sector_en": "Telecom",              "sector_ar": "الاتصالات"},
    {"symbol": "7020.SR", "name_en": "Etihad Etisalat (Mobily)",  "name_ar": "اتحاد اتصالات (موبايلي)", "sector_en": "Telecom",              "sector_ar": "الاتصالات"},
    {"symbol": "7030.SR", "name_en": "Zain KSA",                  "name_ar": "زين السعودية",             "sector_en": "Telecom",              "sector_ar": "الاتصالات"},
    # Retail & Consumer
    {"symbol": "4003.SR", "name_en": "Extra (United Electronics)", "name_ar": "إكسترا",                  "sector_en": "Retail",               "sector_ar": "التجزئة"},
    {"symbol": "4050.SR", "name_en": "Savola Group",               "name_ar": "مجموعة صافولا",           "sector_en": "Food & Beverages",     "sector_ar": "الأغذية والمشروبات"},
    {"symbol": "4061.SR", "name_en": "Almarai",                   "name_ar": "المراعي",                  "sector_en": "Food & Beverages",     "sector_ar": "الأغذية والمشروبات"},
    {"symbol": "4001.SR", "name_en": "Aldrees Petroleum & Transport","name_ar": "الدريس للبترول",       "sector_en": "Retail",               "sector_ar": "التجزئة"},
    {"symbol": "4190.SR", "name_en": "Jarir Marketing",           "name_ar": "مكتبة جرير",               "sector_en": "Retail",               "sector_ar": "التجزئة"},
    {"symbol": "4240.SR", "name_en": "Fawaz Alhokair",            "name_ar": "فواز الحكير",              "sector_en": "Retail",               "sector_ar": "التجزئة"},
    {"symbol": "4321.SR", "name_en": "Abdullah Al Othaim Markets","name_ar": "أسواق عبدالله العثيم",    "sector_en": "Retail",               "sector_ar": "التجزئة"},
    # Real Estate
    {"symbol": "4020.SR", "name_en": "Dar Al Arkan Real Estate",  "name_ar": "دار الأركان",              "sector_en": "Real Estate",          "sector_ar": "العقارات"},
    {"symbol": "4040.SR", "name_en": "Saudi Real Estate",         "name_ar": "شركة العقارية",            "sector_en": "Real Estate",          "sector_ar": "العقارات"},
    {"symbol": "4100.SR", "name_en": "Emaar The Economic City",   "name_ar": "إعمار المدينة الاقتصادية","sector_en": "Real Estate",          "sector_ar": "العقارات"},
    {"symbol": "4150.SR", "name_en": "Taiba Investments",         "name_ar": "طيبة للاستثمار",           "sector_en": "Real Estate",          "sector_ar": "العقارات"},
    # Industrials & Construction
    {"symbol": "2110.SR", "name_en": "Saudi Steel Pipe",          "name_ar": "الأنابيب السعودية للصلب",  "sector_en": "Materials",            "sector_ar": "المواد"},
    {"symbol": "2120.SR", "name_en": "Astra Industrial Group",    "name_ar": "مجموعة أسترا الصناعية",   "sector_en": "Industrials",          "sector_ar": "الصناعات"},
    {"symbol": "2130.SR", "name_en": "Saudi Ceramics",            "name_ar": "السيراميك السعودي",        "sector_en": "Building Materials",   "sector_ar": "مواد البناء"},
    {"symbol": "2140.SR", "name_en": "Al Hassan Ghazi Ibrahim Shaker","name_ar": "شركة شاكر",           "sector_en": "Industrials",          "sector_ar": "الصناعات"},
    {"symbol": "2150.SR", "name_en": "Saudi Printing & Packaging","name_ar": "الطباعة والتغليف السعودية","sector_en": "Industrials",         "sector_ar": "الصناعات"},
    {"symbol": "3001.SR", "name_en": "Cement - Yamama",           "name_ar": "يمامة للإسمنت",            "sector_en": "Building Materials",   "sector_ar": "مواد البناء"},
    {"symbol": "3002.SR", "name_en": "Saudi Cement",              "name_ar": "الإسمنت السعودية",         "sector_en": "Building Materials",   "sector_ar": "مواد البناء"},
    {"symbol": "3003.SR", "name_en": "Qassim Cement",             "name_ar": "إسمنت القصيم",             "sector_en": "Building Materials",   "sector_ar": "مواد البناء"},
    # Healthcare
    {"symbol": "4002.SR", "name_en": "Dallah Healthcare",         "name_ar": "دله الصحية",               "sector_en": "Healthcare",           "sector_ar": "الرعاية الصحية"},
    {"symbol": "4005.SR", "name_en": "National Medical Care",     "name_ar": "الرعاية الطبية الوطنية",   "sector_en": "Healthcare",           "sector_ar": "الرعاية الصحية"},
    {"symbol": "4007.SR", "name_en": "Mouwasat Medical Services", "name_ar": "مواساة للخدمات الطبية",    "sector_en": "Healthcare",           "sector_ar": "الرعاية الصحية"},
    {"symbol": "4009.SR", "name_en": "Al Hammadi",                "name_ar": "الحمادي",                  "sector_en": "Healthcare",           "sector_ar": "الرعاية الصحية"},
    # Insurance
    {"symbol": "8010.SR", "name_en": "Tawuniya",                  "name_ar": "التعاونية",                "sector_en": "Insurance",            "sector_ar": "التأمين"},
    {"symbol": "8020.SR", "name_en": "BUPA Arabia",               "name_ar": "بوبا العربية",             "sector_en": "Insurance",            "sector_ar": "التأمين"},
    {"symbol": "8030.SR", "name_en": "Medgulf",                   "name_ar": "ميدغلف",                   "sector_en": "Insurance",            "sector_ar": "التأمين"},
    # Transportation & Logistics
    {"symbol": "4030.SR", "name_en": "Saudi Airlines Catering",   "name_ar": "الخطوط الجوية للتموين",   "sector_en": "Transportation",       "sector_ar": "النقل"},
    {"symbol": "4031.SR", "name_en": "Bahri (National Shipping)", "name_ar": "البحري",                   "sector_en": "Transportation",       "sector_ar": "النقل"},
]

# Initial universe for data collection (all 50)
KSA_INITIAL_UNIVERSE = [s["symbol"] for s in KSA_TOP50]

# Sector map: sector_en -> list of symbols
KSA_SECTOR_MAP: dict[str, list[str]] = {}
for _stock in KSA_TOP50:
    _sec = _stock["sector_en"]
    KSA_SECTOR_MAP.setdefault(_sec, []).append(_stock["symbol"])

# MSCI Tadawul 30 index constituents (MT30) — large-cap benchmark
KSA_MT30_TICKERS = [
    "2222.SR",  # Saudi Aramco
    "2010.SR",  # SABIC
    "1180.SR",  # Al Rajhi Bank
    "1170.SR",  # Saudi National Bank
    "7010.SR",  # STC
    "2060.SR",  # YANSAB
    "1010.SR",  # Riyad Bank
    "1050.SR",  # Banque Saudi Fransi
    "1080.SR",  # Arab National Bank
    "1150.SR",  # Alinma Bank
    "4061.SR",  # Almarai
    "4190.SR",  # Jarir Marketing
    "4050.SR",  # Savola
    "7020.SR",  # Mobily
    "7030.SR",  # Zain KSA
    "2080.SR",  # NIC
    "2090.SR",  # NATPET
    "4020.SR",  # Dar Al Arkan
    "4100.SR",  # Emaar Economic City
    "3002.SR",  # Saudi Cement
    "8010.SR",  # Tawuniya
    "8020.SR",  # BUPA Arabia
    "4031.SR",  # Bahri
    "4007.SR",  # Mouwasat
    "2030.SR",  # SAFCO
    "1060.SR",  # SABB
    "2100.SR",  # GIS
    "4005.SR",  # NMC
    "3001.SR",  # Yamama Cement
    "2130.SR",  # Saudi Ceramics
]

# Banking tickers — used for sector-specific analysis and capital-adequacy checks
KSA_BANKING_TICKERS = [
    "1180.SR",  # Al Rajhi Bank
    "1170.SR",  # Saudi National Bank
    "1010.SR",  # Riyad Bank
    "1050.SR",  # Banque Saudi Fransi
    "1060.SR",  # SABB
    "1080.SR",  # Arab National Bank
    "1120.SR",  # Al Jazira Bank
    "1140.SR",  # Al Bilad Bank
    "1150.SR",  # Alinma Bank
    "1020.SR",  # Bank AlJazira (duplicate code variant)
    "1030.SR",  # Saudi Investment Bank
]
