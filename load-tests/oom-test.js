import http from "k6/http";
import { sleep, check } from "k6";

export const options = {
  stages: [
    { duration: "10s", target: 100 },
    { duration: "2m", target: 100 },
    { duration: "10s", target: 0 },
  ],
};

const targetHost = __ENV.TARGET_HOST || "localhost";
const BASE_URL = `http://${targetHost}:8080`;

const EFFICIENT_JUNK_DATA = "A".repeat(2000000);

export default function () {
  let res = http.get(`${BASE_URL}/`);
  check(res, { "Homepage loaded": (r) => r.status === 200 });

  const cartPayload = {
    product_id: "0PUK6V6EV0",
    quantity: 1,
  };
  res = http.post(`${BASE_URL}/cart`, cartPayload);
  check(res, { "Added to cart": (r) => r.status === 200 || r.status === 302 });

  const checkoutPayload = {
    email: "aiops-test@example.com",
    street_address: "1600 Amphitheatre Parkway - " + EFFICIENT_JUNK_DATA,
    zip_code: "94043",
    city: "Mountain View",
    state: "CA",
    country: "US",
    credit_card_number: "4111222233334444",
    credit_card_expiration_month: "12",
    credit_card_expiration_year: "2030",
    credit_card_cvv: "123",
  };

  res = http.post(`${BASE_URL}/cart/checkout`, checkoutPayload);

  check(res, {
    "Checkout attempted (OOM expected)": (r) =>
      r.status === 200 || r.status === 302 || r.status >= 500,
  });

  sleep(0.5);
}
