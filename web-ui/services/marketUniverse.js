'use strict';

const EGX_FORECAST_UNIVERSE = [
    { symbol: 'COMI.CA', name_en: 'Commercial International Bank', name_ar: 'البنك التجاري الدولي' },
    { symbol: 'ETEL.CA', name_en: 'Telecom Egypt', name_ar: 'المصرية للاتصالات' },
    { symbol: 'HRHO.CA', name_en: 'El Sewedy Electric', name_ar: 'السويدي إليكتريك' },
    { symbol: 'SWDY.CA', name_en: 'Swedy Electric', name_ar: 'السويدي للكابلات' },
    { symbol: 'SKPC.CA', name_en: 'Sidi Kerir Petrochemicals', name_ar: 'سيدي كرير للبتروكيماويات' },
    { symbol: 'ABUK.CA', name_en: 'Abu Qir Fertilizers', name_ar: 'أبو قير للأسمدة' },
    { symbol: 'MNVL.CA', name_en: 'Misr National Valves', name_ar: 'صمامات مصر الوطنية' },
    { symbol: 'ORWE.CA', name_en: 'Oriental Weavers', name_ar: 'النساجون الشرقيون' },
    { symbol: 'CLHO.CA', name_en: 'Cleopatra Hospitals', name_ar: 'مستشفيات كليوباترا' },
    { symbol: 'PHDC.CA', name_en: 'Palm Hills Developments', name_ar: 'بالم هيلز للتعمير' },
    { symbol: 'EMFD.CA', name_en: 'Emaar Misr', name_ar: 'إعمار مصر' },
    { symbol: 'TMGH.CA', name_en: 'Talaat Moustafa Group', name_ar: 'مجموعة طلعت مصطفى' },
    { symbol: 'EFIC.CA', name_en: 'Egyptian Fertilizers', name_ar: 'الأسمدة المصرية' },
    { symbol: 'OCDI.CA', name_en: 'Orascom Development Egypt', name_ar: 'أوراسكوم للتنمية' },
    { symbol: 'ESRS.CA', name_en: 'Ezz Steel', name_ar: 'عز للصلب' },
    { symbol: 'IRON.CA', name_en: 'Ezz Iron and Steel', name_ar: 'عز الدخيلة للصلب' },
    { symbol: 'RAYA.CA', name_en: 'Raya Holding', name_ar: 'راية القابضة' },
    { symbol: 'CIEB.CA', name_en: 'CIB Egypt', name_ar: 'بنك CIB' },
    { symbol: 'ALCN.CA', name_en: 'Al Ahli Ceramics', name_ar: 'السيراميك والفخار' },
    { symbol: 'EAST.CA', name_en: 'Eastern Tobacco', name_ar: 'الشرقية للدخان' },
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

function getEgxUniverseSymbols() {
    return EGX_FORECAST_UNIVERSE.map((entry) => entry.symbol);
}

function getEgxStockNames() {
    return EGX_FORECAST_UNIVERSE.reduce((acc, entry) => {
        acc[entry.symbol] = [entry.name_en, entry.name_ar];
        return acc;
    }, {});
}

// Legacy aliases used by callers built for the KSA version
const getKsaUniverseSymbols = getEgxUniverseSymbols;
const getKsaStockNames = getEgxStockNames;

async function resolveMarketSymbol(rawSymbol, db) {
    const input = String(rawSymbol || '').trim().toUpperCase();
    if (!input) return '';

    if (input === 'EGX30' || input === '^CASE') return 'EGX30.CA';
    if (/\.(CA|SR)$/i.test(input)) return input;

    // EGX symbols are alphabetic (e.g. COMI, ETEL); numeric → not an EGX code
    const candidates = /^\d+$/.test(input)
        ? [`${input}.CA`, input]
        : [`${input}.CA`, input];

    if (db && typeof db.all === 'function') {
        try {
            const isPostgres = !!db._isPostgres;
            const sql = isPostgres
                ? `SELECT DISTINCT symbol
                   FROM prices
                   WHERE UPPER(symbol) = ANY($1)
                   ORDER BY CASE
                     WHEN UPPER(symbol) LIKE '%.CA' THEN 0
                     ELSE 1
                   END
                   LIMIT 1`
                : `SELECT DISTINCT symbol
                   FROM prices
                   WHERE UPPER(symbol) IN (${candidates.map(() => '?').join(',')})
                   ORDER BY CASE
                     WHEN UPPER(symbol) LIKE '%.CA' THEN 0
                     ELSE 1
                   END
                   LIMIT 1`;
            const rows = await dbAll(db, sql, isPostgres ? [candidates] : candidates);
            if (rows[0] && rows[0].symbol) return String(rows[0].symbol).toUpperCase();
        } catch (_err) {
            // Fall back to .CA suffix for EGX symbols
        }
    }

    return `${input}.CA`;
}

module.exports = {
    getKsaStockNames,
    getKsaUniverseSymbols,
    getEgxStockNames,
    getEgxUniverseSymbols,
    normalizeDisplaySymbol,
    resolveMarketSymbol,
};
