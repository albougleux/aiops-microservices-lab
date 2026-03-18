import http from "k6/http";
import { sleep, check } from "k6";

export const options = {
  vus: 10,
  duration: "1m",
};

const targetHost = __ENV.TARGET_HOST || "localhost";
const BASE_URL = `http://${targetHost}:8080`;

export default function () {
  let res = http.get(`${BASE_URL}/`);

  const cartPayload = {
    product_id: "0PUK6V6EV0",
    quantity: 1,
  };
  res = http.post(`${BASE_URL}/cart`, cartPayload);

  const badCheckoutPayload = {
    email: "not-an-email",
    street_address: "", // Empty string to fail validation
    zip_code: "000",
    city: "Nowhere",
    state: "XX",
    country: "US",
    credit_card_number: "0000000000000000",
    credit_card_expiration_month: "13", // Invalid month to trigger payment logic crash
    credit_card_expiration_year: "1999", // Expired year
    credit_card_cvv: "999",
  };

  res = http.post(`${BASE_URL}/cart/checkout`, badCheckoutPayload);

  check(res, {
    "transaction failed as expected (400 or 500)": (r) => r.status >= 400,
  });

  sleep(0.5);
}
