//! KMRP Save Editor's core: the game file formats, finding the games and their saves,
//! and reading, changing and writing a save. No user interface here; `main.rs` and
//! `ui/` hold that.

pub mod area;
pub mod catalog;
pub mod globals;
pub mod creature;
pub mod formats;
pub mod gamedata;
pub mod map;
pub mod quests;
pub mod questdb;
pub mod games;
pub mod save;
pub mod text;
