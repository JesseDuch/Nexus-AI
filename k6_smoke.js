// k6 smoke/load script (roadmap 8.2) — OpenAI-compatible endpoint under load.
//   k6 run -e BASE_URL=http://localhost:8000 -e API_KEY=sk-nx-... k6_smoke.js
import http from 'k6/http';
import { check, sleep } from 'k6';

export const options = {
  stages: [
    { duration: '20s', target: 10 },   // ramp up
    { duration: '40s', target: 10 },   // steady
    { duration: '10s', target: 0 },    // ramp down
  ],
  thresholds: {
    http_req_failed: ['rate<0.05'],
    http_req_duration: ['p(95)<15000'],
  },
};

const BASE = __ENV.BASE_URL || 'http://localhost:8000';
const KEY = __ENV.API_KEY || '';

export default function () {
  const res = http.post(
    `${BASE}/v1/chat/completions`,
    JSON.stringify({ messages: [{ role: 'user', content: 'ping' }] }),
    { headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${KEY}` } },
  );
  check(res, {
    'status 200': (r) => r.status === 200,
    'openai shape': (r) => r.json('object') === 'chat.completion',
  });
  sleep(1);
}
