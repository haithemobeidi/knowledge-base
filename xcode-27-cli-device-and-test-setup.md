---
stack: [ios, xcode, swift, testing, tooling]
kind: gotcha
last_verified: 2026-10-13
---

# Xcode 27 from the command line: devices without Simulator.app, wireless pairing, XcodeGen, and XCUITest under Swift 6

**One-liner:** Xcode 27 ships no Simulator.app (the simulator shows through **DeviceHub**), a wireless iPad pairs via a prompt found under Settings → Developer, and a CLI-only workflow needs a handful of exact commands. Testing from the CLI has four traps: XCUITest targets must be `nonisolated` by default under a MainActor-default app; a computed `XCUIApplication` property drops launch arguments; iOS 26's search bar says "Close", not "Cancel"; `simctl spawn defaults write` outlives the app's own UserDefaults reset.

*Playmoir iOS, M5 MacBook Air + iPad Pro M4, 2026-09-29 to 2026-10-13. Xcode 27.0, Swift 6.4, XcodeGen 2.46.*

## Devices

- **No Simulator.app:** open `Xcode.app/Contents/Applications/DeviceHub.app` to see simulators. `xcrun simctl` still works for everything else.
- **Wireless iPad:** "Pair Nearby Device" from DeviceHub; the code prompt on the iPad is under **Settings → Developer**, not Privacy & Security → Developer Mode. Accept the Program License Agreement on the developer site first or signing fails.
- **Build + install, no Xcode UI:**

```bash
xcodebuild -project App.xcodeproj -scheme App -destination 'id=<UDID>' \
  -allowProvisioningUpdates -allowProvisioningDeviceRegistration build
xcrun devicectl device install app --device <UDID> build/Build/Products/Debug-iphoneos/App.app
xcrun devicectl list devices      # if the iPad vanishes, re-pair from DeviceHub
```

- **XcodeGen:** the binary loses its presets when run through a symlink; call it from where it was installed (or a wrapper that `cd`s there). Valid `SWIFT_VERSION` values are 4, 4.2, 5, 6: "6.2" is rejected (the compiler is 6.4; the language mode is 6).

## Swift 6 settings that work

```yaml
SWIFT_VERSION: "6.0"
SWIFT_DEFAULT_ACTOR_ISOLATION: MainActor
SWIFT_UPCOMING_FEATURE_NONISOLATED_NONSENDING_BY_DEFAULT: YES
SWIFT_UPCOMING_FEATURE_INFER_ISOLATED_CONFORMANCES: YES
SWIFT_UPCOMING_FEATURE_MEMBER_IMPORT_VISIBILITY: YES
```

`SWIFT_APPROACHABLE_CONCURRENCY` does nothing in Swift 6 mode (Xcode's template uses Swift 5 + that flag). With MainActor default, types used inside an `actor` (Codable DTOs, value caches) need `nonisolated struct`; member-import visibility means `import AuthenticationServices` / `import Nuke` where a member is used, not just where the type is.

## Testing from the CLI

- **Unit tests:** Swift Testing (`import Testing`, `@Test`, `#expect`) in a `bundle.unit-test` target that depends on the app; XcodeGen sets `TEST_HOST` so `@testable import` works.
- **UI tests:** a `bundle.ui-testing` target with `SWIFT_DEFAULT_ACTOR_ISOLATION: nonisolated`. Under a MainActor default, `XCTestCase`'s initialisers and `setUp` can't be overridden (they're nonisolated); mark test methods `@MainActor` instead.
- **One `XCUIApplication` per test, stored:** `private var app: XCUIApplication { XCUIApplication() }` builds a new handle per use, so `app.launchArguments = [...]` and `app.launch()` hit different objects and the arguments never arrive. Store it (`nonisolated(unsafe) private var app: XCUIApplication!`, set in a `@MainActor` launch helper).
- **iOS 26 search bar:** the dismiss control is an ✕ labelled **"Close"**; query `label IN {'Close','Cancel'}`.
- **System prompts** (e.g. ASWebAuthenticationSession's "wants to use … to sign in") belong to SpringBoard: `XCUIApplication(bundleIdentifier: "com.apple.springboard").alerts`.
- **Reset hooks:** a `-uiTestReset` launch argument that clears the app's UserDefaults domain, Keychain item and files gives each test a fresh install. But a value written from outside with `xcrun simctl spawn <dev> defaults write <bundle> key …` survives `removePersistentDomain`; delete it with `simctl spawn … defaults delete <bundle>` after manual experiments.
- **Errors you'll see:** `xcodebuild … test` output is huge; grep `Test Case.*(passed|failed)|error:|TEST ` and export screenshots with `xcrun xcresulttool export attachments --path <xcresult> --output-path <dir>`.

## Related

- `verify-motion-frame-by-frame.md` (recording + slow motion), `wireless-adb-refused-means-unpaired.md` (the Android pairing equivalent).
