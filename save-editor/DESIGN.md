---
name: KMRP Save Editor
description: A KotOR 1 and 2 save editor shaped like the game's own Load screen and in-game menu, in the KMRP family colours.
colors:
  navy-window: "#0a1220"
  navy-glow: "#16243a"
  navy-panel: "#0d1626"
  navy-panel-edge: "#1c2b42"
  navy-field: "#060b14"
  navy-edge: "#2a3b55"
  navy-row-line: "#16233a"
  navy-selected: "#0b1c2c"
  navy-hover: "#111f33"
  holo-cyan: "#2ac6ef"
  holo-cyan-fill-top: "#2fd0f5"
  holo-cyan-fill-bottom: "#1ab3e3"
  holo-cyan-fill-hover: "#58def8"
  holo-cyan-light: "#0a7fb0"
  holo-ink: "#06121e"
  tsl-teal: "#2fcf9b"
  tsl-teal-fill-top: "#46dcac"
  tsl-teal-fill-bottom: "#1fb486"
  tsl-teal-fill-hover: "#66e8bf"
  tsl-teal-light: "#0f8a63"
  tsl-ink: "#04140e"
  text: "#ecf3f8"
  muted: "#b1c3d0"
  soft: "#8fa3b5"
  faint: "#7a8a9a"
  crest-gold: "#e2c35c"
  unsaved-orange: "#ff9a3c"
  saved-green: "#7ee0ab"
  danger-red: "#ff6b6b"
  revert-grey-top: "#566272"
  revert-grey-bottom: "#424d5c"
  scrim: "#03060cbc"
typography:
  display:
    fontFamily: "KMRP Original HD Menu, system-ui"
    fontSize: "46px"
    letterSpacing: "1px"
  headline:
    fontFamily: "KMRP Original HD Menu, system-ui"
    fontSize: "30px"
  title:
    fontFamily: "KMRP Original HD Menu Medium, system-ui"
    fontSize: "20px"
  list:
    fontFamily: "KMRP Original HD Menu Medium, system-ui"
    fontSize: "19px"
  label:
    fontFamily: "KMRP Original HD Menu Small B, system-ui"
    fontSize: "15px"
    letterSpacing: "4px"
  body:
    fontFamily: "KMRP Original HD Descriptions, system-ui"
    fontSize: "14.5px"
  note:
    fontFamily: "KMRP Original HD Descriptions, system-ui"
    fontSize: "13.5px"
rounded:
  thumb: "3px"
  control: "5px"
  row: "6px"
  panel: "10px"
  dialog: "12px"
  pill: "13px"
spacing:
  row-gap: "4px"
  inline: "12px"
  panel-inset: "22px"
  gutter: "24px"
  column-gap: "34px"
  page-margin: "60px"
components:
  button-primary:
    backgroundColor: "{colors.holo-cyan-fill-top}"
    textColor: "{colors.holo-ink}"
    typography: "{typography.title}"
    rounded: "{rounded.control}"
    height: "50px"
  button-primary-hover:
    backgroundColor: "{colors.holo-cyan-fill-hover}"
  button-primary-disabled:
    backgroundColor: "{colors.navy-selected}"
    textColor: "{colors.faint}"
  button-outline:
    backgroundColor: "{colors.navy-field}"
    textColor: "{colors.text}"
    typography: "{typography.title}"
    rounded: "{rounded.control}"
    height: "50px"
  button-outline-hover:
    backgroundColor: "{colors.navy-hover}"
  button-small:
    backgroundColor: "{colors.navy-field}"
    textColor: "{colors.text}"
    rounded: "{rounded.control}"
    height: "38px"
    padding: "0 16px"
  button-revert:
    backgroundColor: "{colors.revert-grey-top}"
    textColor: "{colors.text}"
    rounded: "{rounded.control}"
    height: "50px"
  field:
    backgroundColor: "{colors.navy-field}"
    textColor: "{colors.text}"
    typography: "{typography.list}"
    rounded: "{rounded.control}"
    height: "40px"
    padding: "0 12px"
  stepper:
    backgroundColor: "{colors.navy-field}"
    textColor: "{colors.text}"
    rounded: "{rounded.control}"
    height: "40px"
    width: "140px"
  switch:
    backgroundColor: "{colors.navy-field}"
    rounded: "{rounded.pill}"
    height: "26px"
    width: "50px"
  switch-on:
    backgroundColor: "{colors.holo-cyan}"
  panel:
    backgroundColor: "{colors.navy-panel}"
    rounded: "{rounded.panel}"
    padding: "22px"
  list-row-selected:
    backgroundColor: "{colors.navy-selected}"
    textColor: "{colors.crest-gold}"
    rounded: "{rounded.row}"
  tab:
    textColor: "{colors.soft}"
    typography: "{typography.title}"
    height: "48px"
  tab-active:
    textColor: "{colors.text}"
---

# Design System: KMRP Save Editor

## Overview

**Creative North Star: "The Ebon Hawk's Console"**

The editor is a piece of the game's own interface brought to the desktop. The first screen reads like KotOR's Load screen: a list of saves with their screenshots on the left, the chosen save's picture, party and Open button on the right. The editor reads like the in-game menu: tabs across the top, the party down the left, and every value changed in the place it is shown. It belongs to the KMRP family and carries the KMRP Font Converter's crest header, colours and type unchanged.

The world is dark navy glass lit by holo cyan for KotOR, and the same structure in teal-green for KotOR II (the sequel's own GUI text colour). Each game has a dark and a light mode; switching games switches the whole palette. Surfaces are hairline-edged panels on a deep window with one soft radial glow behind the header. Density is high but calm: rows separated by single hairlines, no cards inside cards, no tiles, nothing animated.

The one loud colour is orange, and it means one thing: changed and not yet saved. Gold marks who or what is current. Cyan (or teal) is the only action and focus colour.

**Key Characteristics:**
- Game-shaped structure: Load-screen list, in-game-menu tabs, party rail on the left.
- One accent per game (holo cyan or TSL teal), four modes from one set of roles.
- KMRP's Original HD Font throughout, in four cuts with fixed jobs.
- Hairline panels, 5px controls, flat surfaces, no shadows.
- Orange is reserved for unsaved changes.
- Static: no transitions, no motion of any kind.

## Colors

Deep navy (or deep green-black for KotOR II) with a single holo accent, gold for the current selection, and orange held back for unsaved edits. Every colour is a role in `ui/theme.slint` with four values (KotOR dark, KotOR light, KotOR II dark, KotOR II light); the frontmatter records KotOR dark, the default, and the sidecar carries the other three modes.

### Primary
- **Holo Cyan** (KotOR accent): section labels, the active tab underline, focus borders, hover borders, scroll thumbs, plus and minus signs, links, switches that are on. Darkens to the light-mode cyan on pale surfaces so it keeps contrast.
- **Holo Cyan Fill** (top, bottom, hover): the vertical gradient of the one main action on a screen (Open This Save, Save Changes, OK) and the active half of the game switch. Text on it is always the near-black Holo Ink, never white.

### Secondary
- **TSL Teal** (KotOR II accent) with its own fill gradient and ink: replaces Holo Cyan in every role when a KotOR II save is shown. It is a second world, not a second accent; the two never appear together.

### Tertiary
- **Crest Gold**: the selected save's name, the selected party member's name, the player's portrait border, the border of party members in the party, the current portrait in the look picker, and the moon and sun of the theme toggle. Gold says "this one".
- **Unsaved Orange**: a changed value's text and border, the dot beside a tab that holds changes, the change count, a changed party member's name, and warnings about a save. Nothing else.
- **Saved Green**: the "SAVED" status label after a write.
- **Danger Red**: "COULD NOT SAVE", the status box border on failure, and a remove cross on hover.

### Neutral
- **Navy Window**: the window background, under the header glow.
- **Navy Glow**: the centre of the radial glow behind the crest header (220px tall, fading to the window by 70%).
- **Navy Panel** with **Panel Edge**: the large content panels (saves list, preview, tab body, dialogs).
- **Navy Field**: the inside of every input, stepper, outline button, thumbnail well and status box; darker than the panel so controls read as recessed.
- **Edge**: control borders and the hairline under the tab bar.
- **Row Line**: the 1px hairline under every list row.
- **Selected** and **Hover**: row backgrounds for the chosen and pointed-at row.
- **Text, Muted, Soft, Faint**: four text steps. Text for values and names, Muted for area lines and secondary values, Soft for inactive tabs and switch knobs, Faint for notes, dates, placeholders and disabled labels.
- **Revert Grey** (top, bottom): the gradient of the Revert button only.
- **Scrim**: the translucent cover behind a dialog.

### Named Rules
**The Orange Means Unsaved Rule.** Orange appears only on something changed since the last save (or a warning about the save itself). If nothing is pending, no orange is on screen.

**The One World Per Game Rule.** A screen is all cyan (KotOR) or all teal (KotOR II). Accent, fills and ink switch together with the game; the structure never changes.

**The Ink On Fill Rule.** Text on a cyan or teal fill uses the game's ink colour, never white.

## Typography

**Display Font:** KMRP Original HD Menu (falls back to the system font when the game's files are missing at build time)
**List Font:** KMRP Original HD Menu Medium (the game's save list font)
**Label Font:** KMRP Original HD Menu Small B
**Body Font:** KMRP Original HD Descriptions

**Character:** the Menu cuts are the game's own small-capital menu lettering, wide and engraved; the Descriptions cut is a plain, slightly spaced reading face for anything longer than a name.

### Hierarchy
- **Display** (Menu, 46px, 1px tracking): "Save Editor" beside the crest. Once per window.
- **Headline** (Menu, 24 to 30px): dialog titles, the previewed save's name, the change count, empty-state titles.
- **Title** (Menu Medium, 20px): main tabs and button captions (18px on All Saves, 16px on small buttons and story sub-tabs).
- **List** (Menu Medium, 17 to 21px): save names (21px), field labels and stat names (19px), party names and picker rows (17 to 18px).
- **Label** (Menu Small B, 15px, 4px tracking, capitals, accent colour): the name over each section of content (WHO, ATTRIBUTES, KOTOR SAVES). At 11px with 2px tracking it labels the status box and a save's tag.
- **Body** (Descriptions, 14 to 16px): area lines, preview details, context line, footer.
- **Note** (Descriptions, 12 to 13.5px, Faint): explanations under values and sections, word-wrapped.

### Named Rules
**The Four Cuts Rule.** Each cut has one job: Menu for titles and numbers, Menu Medium for names and controls, Small B for spaced section labels, Descriptions for sentences. Do not swap them.

**The Section Label Rule.** Spaced capital labels only name the block of content directly beneath them. They never sit above a headline as decoration.

## Layout

A fixed desktop canvas: preferred 1600 by 900, minimum 1280 by 780. Everything hangs from a 60px page margin on left and right. The crest header occupies the top 170px (crest 110px tall at 60px from the left, 44px from the top); a top-right slot holds the game switch on the saves screen, Revert and Save Changes in the editor (with a status line under them), and the square settings button (the KMRP installer's gear) at the top right of both screens. A footer line sits 46px above the bottom edge on the saves screen only: version and dot-separated links on the left, the credit on the right; in the editor the tabs reach the bottom and the backups, version and credit are in Settings. Dark or light and the text size are in Settings (2026-10-22); the round theme toggle is gone.

Saves screen: two panels from y 200px, the list taking 47% of the width, a 24px gutter, the preview taking the rest. The preview stacks the screenshot (half its width tall), name and details, party portraits, and an action row pinned 22px from the bottom.

Editor: tab bar at y 170px; a 262px party rail on the left; the tab panel from x 342px to the right margin; a bottom bar 64px tall holding the change count, the backup status box, Revert (170px) and Save Changes (330px). Inside the tab panel, content falls into three equal columns with 34px gaps, each led by a section label, with rows on hairlines.

Rhythm: rows are 44 to 60px tall with a 1px hairline beneath; controls inside a row are 12px apart; list items are 4 to 6px apart; panel content is inset 22 to 26px.

## Elevation & Depth

Flat. There are no shadows anywhere. Depth comes from tone: the window is darkest, panels sit one step lighter behind a hairline edge, and fields drop back to the darkest tone so they read as recessed wells. The only light source is the header's radial glow. A dialog separates from the page with the scrim alone.

### Named Rules
**The Tone Not Shadow Rule.** Separate layers by a tonal step and a 1px edge, never by a drop shadow.

## Shapes

Small, consistent rounding that grows with the size of the surface: 3px on save and portrait thumbnails, 5px on every control and small picture well, 6 to 7px on selectable list rows and the status box, 10px on content panels, 12px on dialogs. Switches and the theme toggle are full pills and circles. Every container is a 1px hairline; thicker borders mean state (2px for a changed portrait or hovered look, 3px for the current look). Icons (plus, minus, cross, moon, sun) are drawn as 2px stroked paths, not font glyphs.

## Components

### Buttons
Engraved-caption buttons in the Menu Medium cut, never animated.
- **Shape:** 5px corners, 50px tall (38px for small buttons), width from the caption plus 48px (32px small).
- **Primary:** cyan (or teal) vertical gradient, ink caption. One per screen: Open This Save, Save Changes, OK.
- **Outline:** field background with a 1px edge, text caption; hover lifts to the hover tone with an accent border. Used for secondary actions and in-panel actions such as Change Look and To Next Level (small).
- **Revert:** grey vertical gradient, no border; sits beside Save Changes only.
- **Disabled:** primary drops to the selected tone, others to the field tone; caption goes Faint, pointer becomes the default arrow.

### Segmented controls
- **Game switch:** two halves in a 6px-cornered frame; the active half takes the primary fill and ink, the other is a field with Soft text.
- **Story sub-tabs:** separate 5px chips; the active one has the selected background and accent border, the rest the field background and Soft text.

### Inputs / Fields
- **Field:** 40px, field background, 1px edge, 5px corners, 12px side padding. Focus turns the border accent; a changed value turns text and border orange. Placeholder in Descriptions 14px, Faint.
- **Stepper:** a field with drawn minus and plus at each end (accent, Faint at the limit) and the number in Menu, centred. Typing a number also works. Changed turns it orange.
- **Switch:** 50 by 26 pill with an 18px knob; on is accent with an ink knob, changed and on is orange, off is a field with a Soft knob.
- **Alignment bar:** a 14px rounded track from dark-side red through grey to light-side blue, with a 4px marker that turns orange when changed.

### Navigation
- **Tabs:** Menu Medium 20px captions, Soft at rest, Muted on hover, Text when active with a 3px accent underline; a 7px orange dot follows any tab holding unsaved changes. A context line (area and game) sits right-aligned on the same rail, Faint.
- **Party rail:** 66px rows with a 52px portrait; the chosen member gets the selected background, an accent border and a gold name.

### Lists
- **Save row:** 92px with a 96px screenshot, name in Menu Medium 21px, area in Muted, time and date right-aligned in Faint. Selected: accent border, selected background, gold name. Double-click opens.
- **Data rows:** label left, control right, hairline beneath, optional Faint note under the label.
- **Scroller:** a 4px accent thumb at the right edge, shown only when the content overflows.

### Panels and Dialogs
- **Panel:** panel tone, 1px panel edge, 10px corners, content inset 22 to 26px.
- **Dialog:** centred on the scrim, panel tone, 1px edge, 12px corners, 32px by 28px inset; headline title, note, content, and right-aligned buttons.

### Signature: the save bar
The editor's bottom bar is the system's promise made visible: the change count (orange number, Menu 24px), a field-toned status box whose spaced label reads "A BACKUP IS MADE BEFORE SAVING" over the backup path (then SAVED in green or COULD NOT SAVE in red), then Revert and Save Changes. Both buttons stay disabled until something has changed.

## Do's and Don'ts

### Do:
- **Do** take every colour from `Theme`, so all four modes follow.
- **Do** show any edited value in Unsaved Orange until it is saved, and mark its tab with the orange dot.
- **Do** keep one primary (cyan or teal fill) button per screen.
- **Do** separate rows with a 1px Row Line and layers with a tonal step and a 1px edge.
- **Do** draw small symbols (plus, minus, cross, sun, moon) as 2px stroked paths; the KMRP fonts lack them.
- **Do** keep the 60px page margin and the crest header in the same place on every screen.

### Don't:
- **Don't** use orange for emphasis, branding or hover; it means unsaved.
- **Don't** add shadows, blur or glows beyond the single header glow.
- **Don't** animate anything: no transitions, fades or sliding panels.
- **Don't** lay the editor out as tiles or a dashboard grid; it is tabs, a party rail and rows.
- **Don't** use white text on a cyan or teal fill; use the game's ink.
- **Don't** mix KotOR cyan and KotOR II teal on one screen.
