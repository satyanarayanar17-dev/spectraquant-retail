import rules from "../forbidden_words.json" with { type: "json" };

function escapeRegex(value) {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

const compiled = Object.entries(rules).flatMap(([category, terms]) => {
  if (!Array.isArray(terms) || category === "exempt_contexts") {
    return [];
  }

  return terms.map((term) => ({
    category,
    term,
    re: new RegExp(`\\b${escapeRegex(term)}\\b`, "i"),
  }));
});

export function complianceCheck(text, ctx) {
  if (rules.exempt_contexts.includes(ctx.route)) {
    return { ok: true, matches: [] };
  }

  const matches = compiled
    .filter(({ re }) => re.test(text))
    .map(({ category, term }) => ({ category, term }));

  return {
    ok: matches.length === 0,
    matches,
  };
}

export function assertCompliantStrings(entries) {
  const failures = entries
    .map((entry) => ({
      ...entry,
      result: complianceCheck(entry.text, { route: entry.context }),
    }))
    .filter((entry) => !entry.result.ok);

  if (failures.length === 0) {
    return;
  }

  const lines = failures.flatMap((failure) =>
    failure.result.matches.map(
      (match) =>
        `${failure.context}: "${match.term}" matched in "${failure.text}"`,
    ),
  );
  throw new Error(`Compliance check failed:\n${lines.join("\n")}`);
}

export { rules };
