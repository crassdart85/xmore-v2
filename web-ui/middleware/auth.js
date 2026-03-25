/**
 * Xmore — JWT Authentication Middleware
 * 
 * Manages JWT tokens via httpOnly cookies.
 * Provides required and optional auth middleware.
 */

const jwt = require('jsonwebtoken');
const crypto = require('crypto');

const IS_PROD = process.env.NODE_ENV === 'production';
const HAS_CONFIGURED_SECRET = !!process.env.JWT_SECRET;
const STABLE_FALLBACK_SECRET = crypto
    .createHash('sha256')
    .update([
        process.env.DATABASE_URL || '',
        process.env.RENDER_SERVICE_ID || '',
        process.env.RENDER_EXTERNAL_URL || '',
        'xmore-ksa-auth-fallback'
    ].join('|'))
    .digest('hex');
const JWT_SECRET = process.env.JWT_SECRET
    || (IS_PROD
        ? STABLE_FALLBACK_SECRET
        : 'dev-local-secret-change-before-production');
const JWT_EXPIRES_IN = '7d';
const JWT_REFRESH_THRESHOLD = 3 * 24 * 60 * 60; // Refresh if less than 3 days remaining

const COOKIE_OPTIONS = {
    httpOnly: true,
    secure: process.env.NODE_ENV === 'production',
    sameSite: 'lax',
    maxAge: 7 * 24 * 60 * 60 * 1000, // 7 days
    path: '/'
};

/**
 * Generate a JWT token for a given user ID.
 */
function generateToken(userId) {
    return jwt.sign({ userId }, JWT_SECRET, { expiresIn: JWT_EXPIRES_IN });
}

/**
 * Required authentication middleware.
 * Blocks request with 401 if no valid token.
 */
function authMiddleware(req, res, next) {
    const token = req.cookies?.xmore_token;
    if (!token) {
        return res.status(401).json({ error: 'Not authenticated' });
    }

    try {
        const decoded = jwt.verify(token, JWT_SECRET);
        req.userId = decoded.userId;

        // Auto-refresh: if token has less than 3 days remaining, issue a new one
        const now = Math.floor(Date.now() / 1000);
        if (decoded.exp && (decoded.exp - now) < JWT_REFRESH_THRESHOLD) {
            const newToken = generateToken(decoded.userId);
            res.cookie('xmore_token', newToken, COOKIE_OPTIONS);
        }

        next();
    } catch (err) {
        res.clearCookie('xmore_token', COOKIE_OPTIONS);
        return res.status(401).json({ error: 'Session expired' });
    }
}

/**
 * Optional authentication middleware.
 * Sets req.userId if logged in, but doesn't block.
 */
function optionalAuth(req, res, next) {
    const token = req.cookies?.xmore_token;
    if (token) {
        try {
            const decoded = jwt.verify(token, JWT_SECRET);
            req.userId = decoded.userId;
        } catch (err) {
            // Ignore invalid/expired token
        }
    }
    next();
}

module.exports = {
    generateToken,
    authMiddleware,
    optionalAuth,
    JWT_SECRET,
    COOKIE_OPTIONS
};

if (!HAS_CONFIGURED_SECRET && IS_PROD) {
    console.error('[auth] JWT_SECRET is not set in production. Using a stable derived fallback secret. Configure JWT_SECRET explicitly for proper secret management.');
} else if (!HAS_CONFIGURED_SECRET && !IS_PROD) {
    // Local/dev convenience only.
    console.warn('[auth] JWT_SECRET is not set. Using dev fallback secret. Set JWT_SECRET to avoid session invalidation between environments.');
}
