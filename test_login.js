const fetch = require('node-fetch').default;

(async () => {
  const response = await fetch('http://localhost:3000/api/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      email: 'test@example.com',
      password: 'password123'
    }),
    credentials: 'include'
  });

  const data = await response.json();
  console.log('Status:', response.status);
  console.log('Response:', data);
})();