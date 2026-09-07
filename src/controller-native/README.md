# The native controller module

`K1NativeJoystick.cpp` supplies KOTOR with the one thing its retained console
input system lacks -- a joystick device -- so that the engine's own handlers
drive movement, buttons, screen cycling and the camera. The reverse engineering
is in `reverse-engineering/retained-xbox-gui-events.md`; the architecture and
the full mapping are in `docs/controller-native-path.md`.

## This is a preservation copy, and that is a problem to fix

**The build does not compile these files.** It compiles the copies in
`build/research/KPM-Xbox-Controls-K1/`, which is a clone of a third-party
repository (Saul0097's KPM Xbox Controls) and is ignored by this repository's
`.gitignore`.

That means the module's source was, until now, tracked by nothing: untracked in
the vendor clone and unreachable from the parent repository, one `git clean -xfd`
away from being lost. These copies exist so that cannot happen.

Two copies of a source file will diverge. Before any further work on the module,
one of these should happen, and it is a decision for a person:

1. Point the build at `src/controller-native/` and delete the vendor-clone
   copies, keeping the clone for Saul's own files only. This is the tidy answer.
2. Keep building from the clone and delete this directory, accepting that the
   module lives in a vendor tree.

Option 1 is the recommendation. It was not done unilaterally because it changes
the build.

`kotor1.hooks.toml` is copied for the same reason: it carries the four native
hook entries and is modified from the upstream file.
