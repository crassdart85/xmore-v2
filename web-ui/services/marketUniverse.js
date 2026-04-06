'use strict';

const KSA_FORECAST_UNIVERSE = [
    { symbol: '2222.SR', name_en: 'Saudi Aramco', name_ar: 'Saudi Aramco' },
    { symbol: '2010.SR', name_en: 'SABIC', name_ar: 'SABIC' },
    { symbol: '1211.SR', name_en: 'Maaden', name_ar: 'Maaden' },
    { symbol: '1120.SR', name_en: 'Al Rajhi Bank', name_ar: 'Al Rajhi Bank' },
    { symbol: '7010.SR', name_en: 'stc', name_ar: 'stc' },
    { symbol: '1150.SR', name_en: 'Alinma Bank', name_ar: 'Alinma Bank' },
    { symbol: '1180.SR', name_en: 'Saudi National Bank', name_ar: 'Saudi National Bank' },
    { symbol: '1140.SR', name_en: 'Bank Albilad', name_ar: 'Bank Albilad' },
    { symbol: '1060.SR', name_en: 'Saudi Awwal Bank', name_ar: 'Saudi Awwal Bank' },
    { symbol: '1010.SR', name_en: 'Riyad Bank', name_ar: 'Riyad Bank' },
    { symbol: '1050.SR', name_en: 'Banque Saudi Fransi', name_ar: 'Banque Saudi Fransi' },
    { symbol: '2082.SR', name_en: 'ACWA Power', name_ar: 'ACWA Power' },
    { symbol: '2280.SR', name_en: 'Almarai', name_ar: 'Almarai' },
    { symbol: '4002.SR', name_en: 'Mouwasat Medical', name_ar: 'Mouwasat Medical' },
    { symbol: '4013.SR', name_en: 'Dr. Sulaiman Al Habib', name_ar: 'Dr. Sulaiman Al Habib' },
    { symbol: '4190.SR', name_en: 'Jarir Marketing', name_ar: 'Jarir Marketing' },
    { symbol: '5110.SR', name_en: 'Saudi Electricity', name_ar: 'Saudi Electricity' },
    { symbol: '2380.SR', name_en: 'Petro Rabigh', name_ar: 'Petro Rabigh' },
    { symbol: '2060.SR', name_en: 'National Industrialization', name_ar: 'National Industrialization' },
    { symbol: '1810.SR', name_en: 'Seera Group', name_ar: 'Seera Group' },
];

const DISPLAY_SUFFIX_RE = /\.(CA|SR)$/i;

function dbAll(db, query, params) {
    return new Promise((resolve, reject) => {
        db.all(query, params, (err, rows) => {
            if (err) reject(err);
            else resolve(rows || []);
        });
    });
}

function normalizeDisplaySymbol(symbol) {
    return String(symbol || '').toUpperCase().replace(DISPLAY_SUFFIX_RE, '');
}

function getKsaUniverseSymbols() {
    return KSA_FORECAST_UNIVERSE.map((entry) => entry.symbol);
}

function getKsaStockNames() {
    return KSA_FORECAST_UNIVERSE.reduce((acc, entry) => {
        acc[entry.symbol] = [entry.name_en, entry.name_ar];
        return acc;
    }, {});
}

async function resolveMarketSymbol(rawSymbol, db) {
    const input = String(rawSymbol || '').trim().toUpperCase();
    if (!input) return '';

    if (input === 'TASI' || input === '^TASI') return 'TASI.SR';
    if (/\.(SR|CA)$/i.test(input)) return input;

    const candidates = /^\d{4}$/.test(input)
        ? [`${input}.SR`, `${input}.CA`, input]
        : [`${input}.SR`, `${input}.CA`, input];

    if (db && typeof db.all === 'function') {
        try {
            const isPostgres = !!db._isPostgres;
            const sql = isPostgres
                ? `SELECT DISTINCT symbol
                   FROM prices
                   WHERE UPPER(symbol) = ANY($1)
                   ORDER BY CASE
                     WHEN UPPER(symbol) LIKE '%.SR' THEN 0
                     WHEN UPPER(symbol) LIKE '%.CA' THEN 1
                     ELSE 2
                   END
                   LIMIT 1`
                : `SELECT DISTINCT symbol
                   FROM prices
                   WHERE UPPER(symbol) IN (${candidates.map(() => '?').join(',')})
                   ORDER BY CASE
                     WHEN UPPER(symbol) LIKE '%.SR' THEN 0
                     WHEN UPPER(symbol) LIKE '%.CA' THEN 1
                     ELSE 2
                   END
                   LIMIT 1`;
            const rows = await dbAll(db, sql, isPostgres ? [candidates] : candidates);
            if (rows[0] && rows[0].symbol) return String(rows[0].symbol).toUpperCase();
        } catch (_err) {
            // Fall back to KSA-first heuristics when the DB cannot resolve the symbol.
        }
    }

    return /^\d{4}$/.test(input) ? `${input}.SR` : `${input}.SR`;
}

module.exports = {
    getKsaStockNames,
    getKsaUniverseSymbols,
    normalizeDisplaySymbol,
    resolveMarketSymbol,
};