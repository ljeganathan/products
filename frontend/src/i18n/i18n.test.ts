import { describe, expect, it } from "vitest";

import en from "@/i18n/en.json";
import ta from "@/i18n/ta.json";

type JsonValue = string | number | boolean | null | { [key: string]: JsonValue };

function flattenKeys(obj: JsonValue, prefix = ""): string[] {
  if (typeof obj !== "object" || obj === null) return [prefix];
  return Object.entries(obj).flatMap(([key, value]) =>
    flattenKeys(value, prefix ? `${prefix}.${key}` : key),
  );
}

describe("i18n locale parity", () => {
  it("en.json and ta.json define exactly the same set of keys", () => {
    const enKeys = new Set(flattenKeys(en));
    const taKeys = new Set(flattenKeys(ta));

    const missingFromTa = [...enKeys].filter((k) => !taKeys.has(k));
    const missingFromEn = [...taKeys].filter((k) => !enKeys.has(k));

    expect(missingFromTa, "keys present in en.json but missing from ta.json").toEqual([]);
    expect(missingFromEn, "keys present in ta.json but missing from en.json").toEqual([]);
  });

  it("no translation value is an empty string in either locale", () => {
    function emptyLeaves(obj: JsonValue, prefix = ""): string[] {
      if (typeof obj !== "object" || obj === null) {
        return typeof obj === "string" && obj.trim() === "" ? [prefix] : [];
      }
      return Object.entries(obj).flatMap(([key, value]) =>
        emptyLeaves(value, prefix ? `${prefix}.${key}` : key),
      );
    }

    expect(emptyLeaves(en), "empty string values in en.json").toEqual([]);
    expect(emptyLeaves(ta), "empty string values in ta.json").toEqual([]);
  });
});
