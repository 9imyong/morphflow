import http from 'k6/http';
import { check, sleep } from 'k6';

export const options = {
  vus: __ENV.VUS ? Number(__ENV.VUS) : 10,
  duration: __ENV.DURATION || '1m',
  thresholds: {
    http_req_failed: ['rate<0.05'],
    http_req_duration: ['p(95)<2000'],
  },
};

const BASE_URL = __ENV.BASE_URL || 'http://localhost:8000';

export default function () {
  const idem = `k6-${__VU}-${__ITER}`;
  const payload = JSON.stringify({
    input: { type: 'text', content: `load test ${__VU}-${__ITER}` },
    options: { priority: 'normal' },
  });

  const postRes = http.post(`${BASE_URL}/jobs`, payload, {
    headers: {
      'Content-Type': 'application/json',
      'Idempotency-Key': idem,
    },
  });

  check(postRes, {
    'POST /jobs status is 202': (r) => r.status === 202,
  });

  if (postRes.status === 202) {
    const body = postRes.json();
    if (body && body.job_id) {
      const getRes = http.get(`${BASE_URL}/jobs/${body.job_id}`);
      check(getRes, {
        'GET /jobs/{id} status is 200': (r) => r.status === 200,
      });
    }
  }

  sleep(0.2);
}
