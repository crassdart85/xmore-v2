const jwt = require('jsonwebtoken');
const { JWT_SECRET } = require('./auth');

function requireAdminSecret(req, res, next) {
    const auth = req.headers['authorization'] || '';
    const token = auth.startsWith('Bearer ') ? auth.slice(7) : null;

    if (!token) {
        return res.status(401).json({ error: 'Not authenticated. Please log in.' });
    }

    try {
        const payload = jwt.verify(token, JWT_SECRET);
        if (!payload || payload.role !== 'admin') {
            return res.status(403).json({ error: 'Admin access denied' });
        }
        next();
    } catch (_e) {
        return res.status(401).json({ error: 'Session expired. Please log in again.' });
    }
}

module.exports = { requireAdminSecret };
