import copy from "../lib/copy.json" with { type: "json" };
import { assertCompliantStrings } from "@spectraquant/compliance-rules";

function collectStrings(value, path = []) {
  if (typeof value === "string") {
    const joinedPath = path.join(".");
    const context =
      joinedPath === "footer.disclaimer"
        ? "copy.disclaimer.footer"
        : joinedPath === "disclaimer.banner"
          ? "copy.disclaimer.banner"
          : joinedPath;

    return [{ context, text: value }];
  }

  if (Array.isArray(value)) {
    return value.flatMap((entry, index) => collectStrings(entry, [...path, String(index)]));
  }

  if (value && typeof value === "object") {
    return Object.entries(value).flatMap(([key, nested]) => collectStrings(nested, [...path, key]));
  }

  return [];
}

assertCompliantStrings(collectStrings(copy));
console.log("web compliance check passed");
