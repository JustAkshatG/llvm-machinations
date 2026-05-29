# C Source → IR → Reconstructed C — Tasks

- [x] New module
  - [x] `c_reconstructor.py` — IR→pseudo-C translator
- [x] Example files
  - [x] `examples/sample1.c` — inline + SCCP + CFG + DCE demo
  - [x] `examples/sample2.c` — multi-function call chain demo
  - [x] Remove old `examples/sample1.ll` and `examples/sample2.ll`
- [x] Modified modules
  - [x] `pipeline.py` — C→IR compilation, reconstructed_c field, save .c files
  - [x] `file_manager.py` — validate .c files, updated report
  - [x] `app.py` — three-panel layout, `c` keybinding, presentation mode update
- [x] Meta
  - [x] `README.md` — updated for C input
- [x] Verification
  - [x] Reconstructor smoke test
  - [x] Full pipeline with .c input
  - [x] TUI launches correctly
