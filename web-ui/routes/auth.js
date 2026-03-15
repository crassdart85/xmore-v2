/**
 * Xmore — Authentication Routes
 * POST /api/auth/signup
 * POST /api/auth/login
 * POST /api/auth/logout
 * GET  /api/auth/me
 * PUT  /api/auth/me
 */

const express = require('express');
const bcrypt = require('bcryptjs');
const rateLimit = require('express-rate-limit');
const { generateToken, authMiddleware, COOKIE_OPTIONS } = require('../middleware/auth');

const router = express.Router();
const SALT_ROUNDS = 12;

// Rate limit login: 5 attempts per minute per IP
const loginLimiter = rateLimit({
    windowMs: 60 * 1000,
    max: 5,
    message: { error: 'Too many login attempts. Please try again in a minute.' },
    standardHeaders: true,
    legacyHeaders: false,
});

/**
 * Attach the database helper so routes can use it.
 * Called from server.js: attachDb(db, isPostgres)
 */
let db = null;
let isPostgres = false;

function attachDb(_db, _isPostgres) {
    db = _db;
    isPostgres = _isPostgres;
}

// Helper: promisify db.get / db.all for cleaner async/await
function dbGet(query, params) {
    return new Promise((resolve, reject) => {
        db.get(query, params, (err, row) => {
            if (err) reject(err);
            else resolve(row);
        });
    });
}

function dbAll(query, params) {
    return new Promise((resolve, reject) => {
        db.all(query, params, (err, rows) => {
            if (err) reject(err);
            else resolve(rows);
        });
    });
}

function dbRun(query, params) {
    return new Promise((resolve, reject) => {
        if (db.run) {
            // SQLite has db.run
            db.run(query, params, (err, result) => {
                if (err) reject(err);
                else resolve(result);
            });
        } else {
            // PostgreSQL — use db.all which calls pool.query
            db.all(query, params, (err, rows) => {
                if (err) reject(err);
                else resolve(rows);
            });
        }
    });
}

// Use $1/$2 for PostgreSQL, ? for SQLite
function ph(n) {
    return isPostgres ? `$${n}` : '?';
}

// ============================================
// POST /api/auth/signup
// ============================================
router.post('/auth/signup', async (req, res) => {
    try {
        const { email, password } = req.body;

        // Validate
        if (!email || !password) {
            return res.status(400).json({ error: 'Email and password required' });
        }
        if (password.length < 8) {
            return res.status(400).json({ error: 'Password must be at least 8 characters' });
        }
        const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        if (!emailRegex.test(email)) {
            return res.status(400).json({ error: 'Invalid email format' });
        }

        const emailLower = email.toLowerCase().trim();

        // Check if email exists
        const existing = await dbGet(
            `SELECT id FROM users WHERE email_lower = ${ph(1)}`,
            [emailLower]
        );
        if (existing) {
            // Generic error — don't reveal email exists
            return res.status(400).json({ error: 'Signup failed. Please try again.' });
        }

        // Hash password
        const passwordHash = await bcrypt.hash(password, SALT_ROUNDS);

        // Insert user
        if (isPostgres) {
            const rows = await dbAll(
                `INSERT INTO users (email, email_lower, password_hash)
         VALUES ($1, $2, $3) RETURNING id, email, preferred_language`,
                [email.trim(), emailLower, passwordHash]
            );
            const user = rows[0];
            const token = generateToken(user.id);
            res.cookie('xmore_token', token, COOKIE_OPTIONS);
            return res.status(201).json({
                success: true,
                user: { id: user.id, email: user.email, preferred_language: user.preferred_language }
            });
        } else {
            // SQLite: INSERT then get last id
            await dbRun(
                `INSERT INTO users (email, email_lower, password_hash) VALUES (?, ?, ?)`,
                [email.trim(), emailLower, passwordHash]
            );
            const newUser = await dbGet(
                `SELECT id, email, preferred_language FROM users WHERE email_lower = ?`,
                [emailLower]
            );
            const token = generateToken(newUser.id);
            res.cookie('xmore_token', token, COOKIE_OPTIONS);
            return res.status(201).json({
                success: true,
                user: { id: newUser.id, email: newUser.email, preferred_language: newUser.preferred_language }
            });
        }
    } catch (err) {
        console.error('Signup error:', err);
        return res.status(500).json({ error: 'Internal server error' });
    }
});

// ============================================
// POST /api/auth/login
// ============================================
router.post('/auth/login', loginLimiter, async (req, res) => {
    try {
        const { email, password } = req.body;

        if (!email || !password) {
            return res.status(400).json({ error: 'Email and password required' });
        }

        const emailLower = email.toLowerCase().trim();

        const user = await dbGet(
            `SELECT id, email, password_hash, preferred_language, display_name, is_active
       FROM users WHERE email_lower = ${ph(1)}`,
            [emailLower]
        );

        if (!user) {
            return res.status(401).json({ error: 'Invalid email or password' });
        }

        // Check active (SQLite stores booleans as 0/1)
        const isActive = isPostgres ? user.is_active : (user.is_active === 1 || user.is_active === true);
        if (!isActive) {
            return res.status(401).json({ error: 'Invalid email or password' });
        }

        const validPassword = await bcrypt.compare(password, user.password_hash);
        if (!validPassword) {
            return res.status(401).json({ error: 'Invalid email or password' });
        }

        // Update last login
        const nowExpr = isPostgres ? 'NOW()' : "datetime('now')";
        await dbRun(
            `UPDATE users SET last_login_at = ${nowExpr} WHERE id = ${ph(1)}`,
            [user.id]
        );

        const token = generateToken(user.id);
        res.cookie('xmore_token', token, COOKIE_OPTIONS);

        return res.json({
            success: true,
            user: {
                id: user.id,
                email: user.email,
                display_name: user.display_name,
                preferred_language: user.preferred_language
            }
        });
    } catch (err) {
        console.error('Login error:', err);
        return res.status(500).json({ error: 'Internal server error' });
    }
});

// ============================================
// POST /api/auth/logout
// ============================================
router.post('/auth/logout', (req, res) => {
    res.clearCookie('xmore_token', COOKIE_OPTIONS);
    return res.json({ success: true });
});

// ============================================
// GET /api/auth/me
// ============================================
router.get('/auth/me', authMiddleware, async (req, res) => {
    try {
        const user = await dbGet(
            `SELECT id, email, display_name, preferred_language
       FROM users WHERE id = ${ph(1)}`,
            [req.userId]
        );

        if (!user) {
            return res.status(401).json({ error: 'User not found' });
        }

        return res.json({ user });
    } catch (err) {
        console.error('Auth /me error:', err);
        return res.status(500).json({ error: 'Internal server error' });
    }
});

// ============================================
// PUT /api/auth/me
// ============================================
router.put('/auth/me', authMiddleware, async (req, res) => {
    try {
        const { display_name, preferred_language } = req.body;

        // Build update fields
        const updates = [];
        const params = [];
        let paramIndex = 1;

        if (display_name !== undefined) {
            updates.push(`display_name = ${ph(paramIndex++)}`);
            params.push(display_name);
        }
        if (preferred_language !== undefined && ['en', 'ar'].includes(preferred_language)) {
            updates.push(`preferred_language = ${ph(paramIndex++)}`);
            params.push(preferred_language);
        }

        if (updates.length === 0) {
            return res.status(400).json({ error: 'No valid fields to update' });
        }

        const nowExpr = isPostgres ? 'NOW()' : "datetime('now')";
        updates.push(`updated_at = ${nowExpr}`);

        params.push(req.userId);
        await dbRun(
            `UPDATE users SET ${updates.join(', ')} WHERE id = ${ph(paramIndex)}`,
            params
        );

        const user = await dbGet(
            `SELECT id, email, display_name, preferred_language
       FROM users WHERE id = ${ph(1)}`,
            [req.userId]
        );

        return res.json({ success: true, user });
    } catch (err) {
        console.error('Auth update error:', err);
        return res.status(500).json({ error: 'Internal server error' });
    }
});

module.exports = { router, attachDb };
