---
stack: [any, dependencies, maven, npm, pypi, gradle, process]
kind: gotcha
last_verified: 2026-08-09
---

# A package search index is not the package registry — read the registry's own metadata

**One-liner:** picking a dependency version, `search.maven.org`'s API reported Coil's newest release as **3.2.0**. The registry's own `maven-metadata.xml` said **3.5.0** — three minor versions newer and two months old. Pinning from the search result would have shipped a stale dependency that looked *deliberately chosen*, complete with a version number someone would defend in review. Search indexes are caches with their own refresh schedules; the registry has an authoritative metadata endpoint, it is one `curl` away, and it is the only thing that answers "what is the latest version" correctly.

## The failure shape

It is quiet, which is the problem:

1. You need the current version of a library.
2. You ask a search UI, a search API, an aggregator site, or a model.
3. You get **a** version. It is real, it exists, it resolves, it builds.
4. It is not the latest, and nothing anywhere will tell you.

A wrong-but-valid version produces no error. It produces a `libs.versions.toml` entry that reads as intentional forever, and you inherit months of fixed bugs you will rediscover yourself.

## Ask the registry directly

Every major registry publishes machine-readable metadata at a predictable URL. These are the source of truth the resolvers themselves use.

**Maven Central**

```bash
# group path with dots -> slashes
curl -s https://repo1.maven.org/maven2/dev/chrisbanes/haze/haze-android/maven-metadata.xml \
  | grep -E '<latest>|<release>|<lastUpdated>'
```

`<release>` is the newest non-SNAPSHOT. `<versioning><versions>` lists everything. `<lastUpdated>` timestamps the index itself, which tells you whether the *registry* is fresh, not just your reading of it.

**npm**

```bash
curl -s https://registry.npmjs.org/react | jq '."dist-tags"'
# {"latest":"...", "next":"...", ...}
```

**PyPI**

```bash
curl -s https://pypi.org/pypi/fonttools/json | jq -r '.info.version'
```

**crates.io**

```bash
curl -s https://crates.io/api/v1/crates/serde | jq -r '.crate.max_stable_version'
```

**Go** — the module proxy is the registry:

```bash
curl -s https://proxy.golang.org/github.com/gorilla/mux/@v/list
```

Or let your own toolchain ask, which is better still because it resolves through the exact repositories your build is configured with:

```bash
./gradlew dependencyUpdates      # ben-manes plugin
npm outdated
pip list --outdated
cargo upgrade --dry-run
```

## Read past the version number

Latest is not automatically correct. Two more checks, both cheap:

- **Stable vs pre-release.** The version list is chronological, so the newest entry is frequently an alpha. In the case this came from, the list ended `1.7.2, 2.0.0-alpha01 … alpha04` — the right pin was 1.7.2, and a naive "take the last one" would have shipped an alpha. `<release>` on Maven and `dist-tags.latest` on npm already exclude pre-releases; the raw version list does not.
- **Its own floor against your ceiling.** Fetch the POM / package manifest and check the dependency it demands versus what you resolve to:

  ```bash
  curl -s https://repo1.maven.org/maven2/dev/chrisbanes/haze/haze-android/1.7.2/haze-android-1.7.2.pom \
    | grep -A2 '<artifactId>ui</artifactId>'      # -> compose ui 1.10.0
  ```

  Ours resolved to 1.11.4, so the floor was satisfied and no version fight was coming. Thirty seconds, and it converts "I think this is compatible" into a fact before the dependency is added rather than after the build breaks.

## Why the index disagrees

Not a bug, exactly — a different job. Search endpoints run their own ingestion (Maven Central's is a Solr index), and ingestion lags, batches, and occasionally stalls on individual coordinates. There is no contract that the index reflects the registry within any window. The registry's metadata file, by contrast, *is* what the artifact publisher wrote.

The same gap exists for:

- **Mirrors and corporate proxies** (Artifactory, Nexus, internal npm) — a caching remote can serve a months-old view and looks identical to upstream.
- **Aggregator sites** — mvnrepository, libraries.io, "awesome" lists, badges.
- **LLMs, including this one.** A model's answer about "the latest version" is a statement about its training data, at best. This is the most common instance now and the least likely to be double-checked, because the answer arrives fluent and specific.

## The rule

**Resolve "what is the latest version" against the registry's authoritative metadata endpoint. Never a search UI, never an index API, never an aggregator, never from memory.**

And when you pin, put the evidence next to the pin:

```toml
# haze 1.7.2 — newest stable per repo1.maven.org maven-metadata.xml (2026-08-08);
# 2.0.0 is alpha. Needs compose-ui >= 1.10.0; we resolve 1.11.4.
haze = "1.7.2"
```

Two lines that stop the next person re-running the same investigation, and that date the claim so a future reader knows how stale it is.

## Related

- [[negative-control-before-trusting-a-probe]] — the same family: the thing that answered you was not the thing you thought you asked.
- [[chase-industry-stats-to-a-primary-source]] — the research-hygiene version of this rule, for numbers rather than versions: follow the citation chain to a primary source before the value becomes a constant.
- [[monorepo-stale-dist-zod-strip]] — staleness one boundary in: a committed artifact that is silently older than its source.
