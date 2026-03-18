import http from "k6/http";
import { check, sleep } from "k6";

export const options = {
  vus: 5,
  duration: "1m",
};

const targetHost = __ENV.TARGET_HOST || "localhost";
const targetUrl = `http://${targetHost}:8080`;

export default function () {
  const res = http.get(targetUrl);

  check(res, {
    "is status 200 OK": (r) => r.status === 200,
  });

  sleep(Math.random() + 1);
}
