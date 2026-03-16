"""
EGX Top-50 Universe — canonical ticker/name/sector lookup for the intelligence system.
Each tuple: (ca_ticker, yahoo_ticker, name_ar, name_en, sector, mubasher_slug)
"""

EGX_TOP50 = [
    # (ca_ticker, yahoo_ticker, name_ar, name_en, sector, mubasher_slug)
    ("COMI",  "COMI.CA",  "البنك التجاري الدولي",          "Commercial International Bank",         "Banking",             "comi"),
    ("EKHW",  "EKHW.CA",  "أوراسكوم للاستثمار والتنمية",   "Orascom Investment Holdings",           "Diversified",         "ekhw"),
    ("HRHO",  "HRHO.CA",  "هيرميس المالية",                 "EFG Hermes",                            "Financial Services",  "hrho"),
    ("EFGD",  "EFGD.CA",  "إي إف جي للتمويل",              "EFG Finance",                           "Financial Services",  "efgd"),
    ("MNHD",  "MNHD.CA",  "مدينة نصر للإسكان والتعمير",    "Madinat Nasr Housing",                  "Real Estate",         "mnhd"),
    ("OCDI",  "OCDI.CA",  "أوراسكوم للتشييد والصناعة",     "Orascom Construction",                  "Construction",        "ocdi"),
    ("SWDY",  "SWDY.CA",  "السويدي للكابلات",               "Elsewedy Electric",                     "Industrials",         "swdy"),
    ("TALAAT","TALAAT.CA","طلعت مصطفى",                     "Talaat Moustafa Group",                 "Real Estate",         "talaat"),
    ("TMGH",  "TMGH.CA",  "مجموعة طلعت مصطفى",             "TMG Holding",                           "Real Estate",         "tmgh"),
    ("ESRS",  "ESRS.CA",  "عز الدخيلة للصلب",              "Ezz Steel",                             "Steel & Metal",       "esrs"),
    ("ABUK",  "ABUK.CA",  "أبوقير للأسمدة",                 "Abu Qir Fertilizers",                   "Chemicals",           "abuk"),
    ("ALCN",  "ALCN.CA",  "الكيماويات العربية للنيتروجين",  "Arab Chemical for Nitrogen",            "Chemicals",           "alcn"),
    ("ORWE",  "ORWE.CA",  "أوراسكوم للطاقة",               "Orascom Energy",                        "Energy",              "orwe"),
    ("PHDC",  "PHDC.CA",  "بالم هيلز للتطوير",             "Palm Hills Developments",               "Real Estate",         "phdc"),
    ("SODIC", "SODIC.CA", "سوديك",                          "SODIC",                                 "Real Estate",         "sodic"),
    ("ESGE",  "ESGE.CA",  "عز للصلب مصر",                  "Ezz Flat Steel",                        "Steel & Metal",       "esge"),
    ("MFPC",  "MFPC.CA",  "مصر لأوراق التغليف",            "Misr Fertilizers Production",           "Chemicals",           "mfpc"),
    ("AMOC",  "AMOC.CA",  "الإسكندرية لتكرير وتوزيع البترول","Alexandria Mineral Oils",             "Energy",              "amoc"),
    ("CIRA",  "CIRA.CA",  "المجموعة العربية للاستثمار",    "CIRA Education",                        "Education",           "cira"),
    ("ISPH",  "ISPH.CA",  "المصرية للرعاية الصحية",        "Integrated Diagnostics Holdings",       "Healthcare",          "isph"),
    ("CLHO",  "CLHO.CA",  "شركة المنزل",                   "Cleopatra Hospitals",                   "Healthcare",          "clho"),
    ("AMOB",  "AMOB.CA",  "المحمول المصري",                 "Telecom Egypt",                         "Telecom",             "amob"),
    ("ETEL",  "ETEL.CA",  "المصرية للاتصالات",             "Telecom Egypt",                         "Telecom",             "etel"),
    ("EAST",  "EAST.CA",  "ايسترن كومباني",                "Eastern Company",                       "Consumer Goods",      "east"),
    ("JUFO",  "JUFO.CA",  "جهينة",                          "Juhayna Food Industries",               "Food & Beverage",     "jufo"),
    ("DOMTY","DOMTY.CA",  "دومتي للصناعات الغذائية",       "Cairo 3A Dairy",                        "Food & Beverage",     "domty"),
    ("PHAR",  "PHAR.CA",  "مصر للصناعات الدوائية",         "Pharco Pharmaceuticals",                "Healthcare",          "phar"),
    ("AMAN",  "AMAN.CA",  "مجموعة أمان",                   "Aman Group",                            "Financial Services",  "aman"),
    ("EKHO",  "EKHO.CA",  "إيكو للتنمية والاستثمار",       "Orascom Development Egypt",             "Real Estate",         "ekho"),
    ("ICCI",  "ICCI.CA",  "الإسكندرية للاستثمار والإنشاء", "Alex Cement",                          "Construction",        "icci"),
    ("NBKE",  "NBKE.CA",  "البنك الأهلي المصري",           "National Bank of Egypt",                "Banking",             "nbke"),
    ("QNBA",  "QNBA.CA",  "بنك قطر الوطني مصر",            "QNB Alahli",                            "Banking",             "qnba"),
    ("CIEB",  "CIEB.CA",  "بنك الاستثمار العربي",          "Credit Agricole Egypt",                 "Banking",             "cieb"),
    ("HDBK",  "HDBK.CA",  "بنك التنمية الصناعية",          "Housing & Development Bank",            "Banking",             "hdbk"),
    ("MCQE",  "MCQE.CA",  "مصر الجديدة للإسكان",           "Heliopolis Housing",                    "Real Estate",         "mcqe"),
    ("EKPC",  "EKPC.CA",  "إيست كومباني للبترول",          "ENPPI",                                 "Energy",              "ekpc"),
    ("ACGC",  "ACGC.CA",  "العربي للمقاولات",              "Arab Contractors",                      "Construction",        "acgc"),
    ("EGCH",  "EGCH.CA",  "الكيماويات المصرية",            "Egyptian Chemical Industries",          "Chemicals",           "egch"),
    ("SKPC",  "SKPC.CA",  "سيدي كرير للبتروكيماويات",      "Sidi Kerir Petrochemicals",             "Chemicals",           "skpc"),
    ("MAST",  "MAST.CA",  "مصر للتأمين",                   "Misr Insurance",                        "Insurance",           "mast"),
    ("MCDR",  "MCDR.CA",  "مصر للمقاصة والإيداع",          "Misr for Central Clearing",             "Financial Services",  "mcdr"),
    ("ESAI",  "ESAI.CA",  "إيجيبت اير للخدمات",            "EgyptAir Holding",                      "Transport",           "esai"),
    ("ADBH",  "ADBH.CA",  "أبوظبي للتطوير المصري",         "Abu Dhabi Islamic Bank Egypt",          "Banking",             "adbh"),
    ("AIVC",  "AIVC.CA",  "مصر للاستثمار والتنمية",        "Al Ahly Capital Holding",               "Financial Services",  "aivc"),
    ("FWRY",  "FWRY.CA",  "فوري للتكنولوجيا",              "Fawry",                                 "Technology",          "fwry"),
    ("OTMT",  "OTMT.CA",  "أوراسكوم تليكوم",               "Orascom Telecom Media",                 "Telecom",             "otmt"),
    ("GTHE",  "GTHE.CA",  "جاد للتطوير العقاري",           "GIZA Development",                      "Real Estate",         "gthe"),
    ("LCSW",  "LCSW.CA",  "لوسيل للاستثمار",               "Lecico Egypt",                          "Construction",        "lcsw"),
    ("BTFH",  "BTFH.CA",  "البتروكيماويات",                 "Beltone Financial",                     "Financial Services",  "btfh"),
    ("DICE",  "DICE.CA",  "داياموند للاستثمار",             "Delta Insurance",                       "Insurance",           "dice"),
]

# Lookup: CA ticker → full tuple
TICKER_BY_CA: dict = {row[0]: row for row in EGX_TOP50}

# Lookup: English name (lower) → CA ticker
TICKER_BY_NAME: dict = {row[3].lower(): row[0] for row in EGX_TOP50}

# All CA tickers as a list
CA_TICKERS: list = [row[0] for row in EGX_TOP50]

# All Yahoo tickers (with .CA suffix)
YAHOO_TICKERS: list = [row[1] for row in EGX_TOP50]
