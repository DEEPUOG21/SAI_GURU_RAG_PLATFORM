import { expect, test } from "vitest";
test("browser supports streaming response decoding", () => {
  expect(new TextDecoder().decode(new TextEncoder().encode("Sai Guru"))).toBe(
    "Sai Guru",
  );
});
