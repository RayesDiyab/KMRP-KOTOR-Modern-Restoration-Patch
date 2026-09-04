// Identity shown in Explorer's Properties -> Details for the patcher executable.
//
// csc synthesises a VERSIONINFO resource from these attributes. Without them the
// build shipped a blank FileDescription and 0.0.0.0 for both versions, so the
// file looked unsigned and unattributed next to the game's own executable.
//
// Attribution is deliberately split: KMRP is the product, but the game it patches
// is not ours, so the copyright names both and claims only the patch. The
// bundled high-resolution menu artwork is GPL-3.0 (see the licence resource
// compiled in beside it), which is why that is stated here rather than only in
// the About box.

using System.Reflection;
using System.Runtime.InteropServices;

[assembly: AssemblyTitle("KMRP - KOTOR Modern Restoration Patch")]
[assembly: AssemblyDescription("Resolution-aware interface patch for Star Wars: Knights of the Old Republic")]
[assembly: AssemblyProduct("KMRP - KOTOR Modern Restoration Patch")]
[assembly: AssemblyCompany("KMRP")]
[assembly: AssemblyCopyright("KMRP is a community patch, licensed under GPL-3.0. "
    + "Star Wars: Knights of the Old Republic (c) 2003 BioWare Corp. / LucasArts.")]
[assembly: AssemblyTrademark("Star Wars and related properties are trademarks of Lucasfilm Ltd. "
    + "BioWare and the BioWare Odyssey Engine are trademarks of BioWare Corp.")]

// Keep in step with GoldPatch.PatchVersion in KmrpPatcher.cs.
//
// This drifted once and shipped. PatchVersion reached 2.10.0-mapnotes while these
// stayed at 2.7.0.0, so the v2.10.0 release reported 2.7.0 under Properties ->
// Details -- which is exactly where SECURITY.md tells people to read the version
// from when filing a report. Nothing in the patcher compares these numbers, so the
// drift was invisible to the code and wrong only to the person reading it, which
// is why it survived four releases. AssemblyInformationalVersion carries the full
// string so the pre-release suffix has somewhere to live and cannot drift again.
[assembly: AssemblyVersion("2.10.0.0")]
[assembly: AssemblyFileVersion("2.10.0.0")]
[assembly: AssemblyInformationalVersion("2.10.0-mapnotes")]

[assembly: ComVisible(false)]
