"""
Tadawul reference universe for the KSA version of Xmore.

This module provides a curated Saudi universe used for:
- price-history backfill
- stock metadata seeding
- KSA-first pipeline defaults
"""

KSA_TOP50 = [
    {"symbol": "2222.SR", "name_en": "Saudi Aramco", "name_ar": "Saudi Aramco", "sector_en": "Energy", "sector_ar": "Energy"},
    {"symbol": "2010.SR", "name_en": "SABIC", "name_ar": "SABIC", "sector_en": "Materials", "sector_ar": "Materials"},
    {"symbol": "1211.SR", "name_en": "Maaden", "name_ar": "Maaden", "sector_en": "Materials", "sector_ar": "Materials"},
    {"symbol": "1120.SR", "name_en": "Al Rajhi Bank", "name_ar": "Al Rajhi Bank", "sector_en": "Banking", "sector_ar": "Banking"},
    {"symbol": "7010.SR", "name_en": "stc", "name_ar": "stc", "sector_en": "Telecommunications", "sector_ar": "Telecommunications"},
    {"symbol": "1150.SR", "name_en": "Alinma Bank", "name_ar": "Alinma Bank", "sector_en": "Banking", "sector_ar": "Banking"},
    {"symbol": "1180.SR", "name_en": "Saudi National Bank", "name_ar": "Saudi National Bank", "sector_en": "Banking", "sector_ar": "Banking"},
    {"symbol": "1140.SR", "name_en": "Bank Albilad", "name_ar": "Bank Albilad", "sector_en": "Banking", "sector_ar": "Banking"},
    {"symbol": "1060.SR", "name_en": "Saudi Awwal Bank", "name_ar": "Saudi Awwal Bank", "sector_en": "Banking", "sector_ar": "Banking"},
    {"symbol": "1010.SR", "name_en": "Riyad Bank", "name_ar": "Riyad Bank", "sector_en": "Banking", "sector_ar": "Banking"},
    {"symbol": "1050.SR", "name_en": "Banque Saudi Fransi", "name_ar": "Banque Saudi Fransi", "sector_en": "Banking", "sector_ar": "Banking"},
    {"symbol": "1020.SR", "name_en": "Bank Aljazira", "name_ar": "Bank Aljazira", "sector_en": "Banking", "sector_ar": "Banking"},
    {"symbol": "1030.SR", "name_en": "Saudi Investment Bank", "name_ar": "Saudi Investment Bank", "sector_en": "Banking", "sector_ar": "Banking"},
    {"symbol": "1080.SR", "name_en": "Arab National Bank", "name_ar": "Arab National Bank", "sector_en": "Banking", "sector_ar": "Banking"},
    {"symbol": "2082.SR", "name_en": "ACWA Power", "name_ar": "ACWA Power", "sector_en": "Utilities", "sector_ar": "Utilities"},
    {"symbol": "2280.SR", "name_en": "Almarai", "name_ar": "Almarai", "sector_en": "Consumer Staples", "sector_ar": "Consumer Staples"},
    {"symbol": "4002.SR", "name_en": "Mouwasat Medical", "name_ar": "Mouwasat Medical", "sector_en": "Healthcare", "sector_ar": "Healthcare"},
    {"symbol": "4013.SR", "name_en": "Dr. Sulaiman Al Habib", "name_ar": "Dr. Sulaiman Al Habib", "sector_en": "Healthcare", "sector_ar": "Healthcare"},
    {"symbol": "4004.SR", "name_en": "Dallah Healthcare", "name_ar": "Dallah Healthcare", "sector_en": "Healthcare", "sector_ar": "Healthcare"},
    {"symbol": "4003.SR", "name_en": "United Electronics", "name_ar": "United Electronics", "sector_en": "Consumer Discretionary", "sector_ar": "Consumer Discretionary"},
    {"symbol": "4190.SR", "name_en": "Jarir Marketing", "name_ar": "Jarir Marketing", "sector_en": "Consumer Discretionary", "sector_ar": "Consumer Discretionary"},
    {"symbol": "5110.SR", "name_en": "Saudi Electricity", "name_ar": "Saudi Electricity", "sector_en": "Utilities", "sector_ar": "Utilities"},
    {"symbol": "2380.SR", "name_en": "Petro Rabigh", "name_ar": "Petro Rabigh", "sector_en": "Materials", "sector_ar": "Materials"},
    {"symbol": "2060.SR", "name_en": "National Industrialization", "name_ar": "National Industrialization", "sector_en": "Industrials", "sector_ar": "Industrials"},
    {"symbol": "1810.SR", "name_en": "Seera Group", "name_ar": "Seera Group", "sector_en": "Consumer Discretionary", "sector_ar": "Consumer Discretionary"},
    {"symbol": "4300.SR", "name_en": "Dar Al Arkan", "name_ar": "Dar Al Arkan", "sector_en": "Real Estate", "sector_ar": "Real Estate"},
    {"symbol": "4321.SR", "name_en": "Cenomi Centers", "name_ar": "Cenomi Centers", "sector_en": "Real Estate", "sector_ar": "Real Estate"},
    {"symbol": "4323.SR", "name_en": "Sumou Real Estate", "name_ar": "Sumou Real Estate", "sector_en": "Real Estate", "sector_ar": "Real Estate"},
    {"symbol": "7203.SR", "name_en": "Elm", "name_ar": "Elm", "sector_en": "Technology", "sector_ar": "Technology"},
    {"symbol": "7202.SR", "name_en": "solutions by stc", "name_ar": "solutions by stc", "sector_en": "Technology", "sector_ar": "Technology"},
    {"symbol": "2020.SR", "name_en": "SABIC Agri-Nutrients", "name_ar": "SABIC Agri-Nutrients", "sector_en": "Materials", "sector_ar": "Materials"},
    {"symbol": "2290.SR", "name_en": "Yanbu National Petrochemical", "name_ar": "Yanbu National Petrochemical", "sector_en": "Materials", "sector_ar": "Materials"},
    {"symbol": "2310.SR", "name_en": "Sahara International Petrochemical", "name_ar": "Sahara International Petrochemical", "sector_en": "Materials", "sector_ar": "Materials"},
    {"symbol": "2350.SR", "name_en": "Saudi Kayan Petrochemical", "name_ar": "Saudi Kayan Petrochemical", "sector_en": "Materials", "sector_ar": "Materials"},
    {"symbol": "2330.SR", "name_en": "Advanced Petrochemical", "name_ar": "Advanced Petrochemical", "sector_en": "Materials", "sector_ar": "Materials"},
    {"symbol": "3040.SR", "name_en": "Qassim Cement", "name_ar": "Qassim Cement", "sector_en": "Materials", "sector_ar": "Materials"},
    {"symbol": "3030.SR", "name_en": "Saudi Cement", "name_ar": "Saudi Cement", "sector_en": "Materials", "sector_ar": "Materials"},
    {"symbol": "3050.SR", "name_en": "Southern Province Cement", "name_ar": "Southern Province Cement", "sector_en": "Materials", "sector_ar": "Materials"},
    {"symbol": "3060.SR", "name_en": "Yanbu Cement", "name_ar": "Yanbu Cement", "sector_en": "Materials", "sector_ar": "Materials"},
    {"symbol": "3080.SR", "name_en": "Eastern Province Cement", "name_ar": "Eastern Province Cement", "sector_en": "Materials", "sector_ar": "Materials"},
    {"symbol": "3090.SR", "name_en": "Tabuk Cement", "name_ar": "Tabuk Cement", "sector_en": "Materials", "sector_ar": "Materials"},
]


def get_ksa_top50_symbols():
    return [stock["symbol"] for stock in KSA_TOP50]


def get_ksa_reference_rows():
    return [
        (
            stock["symbol"],
            stock["name_en"],
            stock["name_ar"],
            stock["sector_en"],
            stock["sector_ar"],
        )
        for stock in KSA_TOP50
    ]