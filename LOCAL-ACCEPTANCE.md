# Local native/web acceptance composition

This branch is a disposable integration experiment, not an official downstream sync pin, release, install, or authorization to change the live app.

Sources:

- Desktop main: ace641c32eb8692b26a2839643fc99a8c445c45b
- Native preference successor: 6a836f1e8693f9698c27f521649475ce8d24ba4b
- Native confirmation successor: 8c832adb02fca2e28dcde90a35d37d9e63fa90af
- Canonical web preference consumer: a81f2f0fa127fbcde73d3a739af575d6c04cfced
- Pending canonical cached-provider retry: d32b6d2f624cd1a562c3ec2919afbc53b4535bb8
- Pending canonical Exopet: d911b390e989d1bbb33bc7c3fce3e2094f9ff5a9

The local merges preserve desktop picker-generation cleanup, pet detach/state synchronization and the canonical native-reading restoration guards together. Test fixture module lists include both optional modules. Canonical minimum-positive session-list validation was retained.

Run the composed native acceptance on a Mac graphical session with an existing test Python environment:

```sh
EXO_BUS_URL=http://127.0.0.1:9 python clients/desktop/macos/Tests/test_native_workspace_acceptance.py
```

It compiles the production native delegate, calls its real HTTP verification/document-start injection path, uses the actual web assets/API with a synthetic core source, and drives a real WKWebView. It checks Appearance, route, thread, layout, reading fraction and companion Full/Off choices through a page reload and a second executable process at a different loopback port. Homes and preference suites are disposable; no app is installed, provider activated, model invoked, or live core contacted. Pet XP is explicitly synthetic fixture data, not evidence of ledger verification. The core pet verification tests remain separate.

The local web regression subset (desktop preferences, pet, recovery, shell, chat, chat-view and model-command files) passed 80 tests. The full exo-command suite then passed 480 tests in 151.96 seconds on `a1d6b16a186cf8f834f759df00973276f0305f9e`; the native helper-discovery/doc successor `3289e235b45af30057066cd9c0127f97661d49c3` retained identical web source and test subtrees. The later #932 composition adds only the cached-provider retry source path and its two browser cases; provider checks and composed native acceptance are rerun on that final tree. Successful fixture teardown can still emit pending `WebServer._client` task warnings. Native dialog acceptance separately dispatches Return/Escape to the temporary sheet and checks stale-context refusal. VoiceOver acceptance remains unperformed.
