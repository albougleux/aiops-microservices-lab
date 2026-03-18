import http from "k6/http";
import { sleep, check } from "k6";

export const options = {
  stages: [
    { duration: "20s", target: 50 },
    { duration: "40s", target: 50 },
    { duration: "10s", target: 0 },
  ],
};

const targetHost = __ENV.TARGET_HOST || "localhost";
const BASE_URL = `http://${targetHost}:8080`;

const EFFICIENT_JUNK_DATA = "A".repeat(500000);

export default function () {
  // 50% chance to be a "Normal" aggressive user (CPU heavy)
  // 50% chance to be a "Malicious" user (Error heavy + Memory bloat)
  const isMalicious = Math.random() < 0.5;

  let res = http.get(`${BASE_URL}/`);

  const cartPayload = {
    product_id: "0PUK6V6EV0",
    quantity: 1,
  };
  http.post(`${BASE_URL}/cart`, cartPayload);

  if (!isMalicious) {
    // Normal aggressive checkout
    const checkoutPayload = {
      email: "aiops-normal@example.com",
      street_address: "123 Main St",
      zip_code: "12345",
      city: "Normal City",
      state: "NY",
      country: "US",
      credit_card_number: "4111222233334444",
      credit_card_expiration_month: "12",
      credit_card_expiration_year: "2030",
      credit_card_cvv: "123",
    };
    res = http.post(`${BASE_URL}/cart/checkout`, checkoutPayload);
    check(res, {
      "Normal checkout processed": (r) => r.status === 200 || r.status === 302,
    });
  } else {
    // Malicious checkout (Generates 500 Errors AND Memory pressure)
    const badCheckoutPayload = {
      email: "not-an-email",
      street_address: "Chaos Street - " + EFFICIENT_JUNK_DATA,
      zip_code: "000",
      city: "Nowhere",
      state: "XX",
      country: "US",
      credit_card_number: "0000000000000000",
      credit_card_expiration_month: "13", // Invalid month to trigger payment logic crash
      credit_card_expiration_year: "1999",
      credit_card_cvv: "999",
    };
    res = http.post(`${BASE_URL}/cart/checkout`, badCheckoutPayload);
    check(res, { "Malicious checkout rejected": (r) => r.status >= 400 });
  }

  sleep(0.01);
}
