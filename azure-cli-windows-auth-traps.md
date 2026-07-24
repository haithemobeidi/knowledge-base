---
stack: [windows, azure, azure-cli, trusted-signing, entra-id]
kind: gotcha
last_verified: 2026-07-22
---

# Azure CLI auth on Windows: three stacked traps that break "just sign in again"

Any project that signs Windows builds with **Azure Trusted Signing** (or uses
`az` for anything) will eventually hit an expired token mid-pipeline and need to
re-authenticate. On Windows in 2026 that simple act hides **three independent
traps that stack**, and each one produces a misleading symptom. This article is
the ten-minute path through what cost a release evening of dead ends.

Context that makes it worse: the token expiry usually surfaces **inside a build
pipeline** (a signtool dlib waiting silently), so the first symptom isn't an
auth error — it's a build that hangs forever at the `Signing …` step.

## Trap 1 — the sign-in prompt is not in any browser

`az login` on modern Windows defaults to the **WAM broker** (Web Account
Manager): a *native Windows dialog*, not a browser page. Users hunt for a
browser tab that does not exist, or find the little native box and mistake it
for something else entirely ("why did a Windows thing pop up?").

Worse: while the broker is active, **the `BROWSER` environment variable does
nothing** — there is no browser launch to redirect. If you've been trying to
steer the login into a specific browser/profile and "nothing opens," this is
why. The CLI meanwhile prints `Select the account you want to log in with`
as if everything is fine.

**Fix:**

```
az config set core.enable_broker_on_windows=false
```

Now `az login` opens a real browser page (localhost-redirect flow). `BROWSER`
pointed at a chrome.exe works from here — the tab opens in the last-active
profile. And because it's a plain web login, it can be completed in ANY
browser on the machine; the localhost redirect doesn't care which browser
finishes it.

## Trap 2 — device-code flow is blocked on new tenants (AADSTS530035)

The classic workaround for browser confusion is `az login --use-device-code`
(user opens microsoft.com/devicelogin anywhere, types a code). On a **new Entra
tenant this fails** with:

> AADSTS530035: Access has been blocked by security defaults.

Microsoft **auto-enables "security defaults" on new tenants days after
creation** — device-code flow is a phishing vector, so it gets blocked. The
nasty part is the timeline: device-code login *worked* during initial setup
(day 0), then silently stopped (day ~2+) with no action on your part. "It
worked two days ago" is true and useless.

Do NOT disable security defaults to unblock it — they're what's protecting the
account that signs your releases. Use the browser flow from Trap 1.

## Trap 3 — the account picker offers the wrong account, with a misleading error

Personal machines are signed into a personal Microsoft account (Windows itself,
consumer services). The picker (WAM or web) **pre-offers that personal
account**; picking it against a work tenant yields:

> Selected user account does not exist in tenant '…' and cannot access the
> application '04b07795-8ddb-461a-bbee-02f9e1bf7b46' in that tenant. The
> account needs to be added as an external user in the tenant first.

That "needs to be added as an external user" instruction reads like a broken
setup requiring admin surgery. It isn't — it just means **you clicked the wrong
account**. (`04b07795-…` is the Azure CLI's own well-known app id, another
red-herring detail.) Click "Use another account" and enter the org account.

## The one-command resolution

After disabling the broker (Trap 1), pin BOTH the tenant and the scope so the
login can't wander into the wrong tenant and mints a token the signing dlib can
use immediately:

```
az login --tenant <TENANT_ID> --scope "https://codesigning.azure.net/.default"
```

Verify non-interactively (this is also the right *pre-flight check* before any
release build — a 2-second command that would have flagged the expiry before
the pipeline hung):

```
az account get-access-token --scope "https://codesigning.azure.net/.default" --query expiresOn -o tsv
```

If that prints a timestamp with no prompt, the signing step will run silently.
If it prints "run az login…", fix auth BEFORE starting the build.

## Symptom → trap map

| Symptom | Trap |
|---|---|
| Build hangs forever at `Signing …` | expired token → dlib waiting on an interactive prompt somewhere |
| "Nothing opened" after `az login` | 1 — the prompt is a native Windows dialog, not a browser |
| `BROWSER` env var ignored | 1 — broker active, no browser launch exists |
| AADSTS530035 on device-code | 2 — security defaults auto-enabled on the new tenant |
| "account does not exist in tenant / add as external user" | 3 — wrong account picked; not a setup problem |
