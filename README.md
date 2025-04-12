# Wayland OBS Director (KDE Plasma)

A Python script for OBS Studio that automatically switches the active program scene based on the monitor where the mouse cursor is located. Designed specifically for **KDE Plasma 6** running on **Wayland**.

**Author:** [MullyCap2004]
**Version:** 2.0
**License:** MIT License (See LICENSE file)
**Repository:** [https://github.com/MullyCap2004/obs-kde-plasma-wayland-director.git]

---

## Description

This script monitors the active output (monitor) reported by KWin (KDE's Window Manager) via D-Bus and switches the OBS scene accordingly. This allows your main OBS output ("Program") to seamlessly follow your focus across multiple displays.

It uses `qdbus6` to interact with KWin and includes features like automatic monitor detection (preferring PyQt6 if available in OBS's Python environment, falling back to `kscreen-doctor`), a graphical configuration interface within OBS, and optional automatic activation on startup.

## Features

*   Automatic scene switching based on mouse cursor location across monitors.
*   Designed for KDE Plasma 6 on Wayland.
*   Uses KWin D-Bus via `qdbus6` for reliable active monitor detection.
*   Automatic monitor detection (tries PyQt6, falls back to `kscreen-doctor`).
*   Graphical configuration panel within OBS Scripts settings.
*   Option to activate automatically when OBS starts.
*   Dependency checks for `qdbus6`.

## Requirements

*   **OBS Studio:** Version 28+. Ensure Python scripting is enabled.
*   **Operating System:** Linux with **KDE Plasma 6** running a **Wayland** session.
*   **Multiple Monitors:** Configured and working in KDE.
*   **`qt6-tools`:** Essential dependency providing the `qdbus6` command.
    *   On Arch Linux: `sudo pacman -S qt6-tools`
    *   On Debian/Ubuntu-based systems (like Kubuntu): `sudo apt install qt6-tools` (Package name might vary slightly)
    *   On Fedora: `sudo dnf install qt6-qttools` (Package name might vary)
*   **`kscreen`:** Provides `kscreen-doctor`, used as a fallback for monitor detection. Usually installed by default with Plasma.
    *   On Arch Linux: `sudo pacman -S kscreen`
*   **(Recommended) `PyQt6`:** For the best monitor detection results. OBS *might* bundle this, or it might need to be available in the Python environment OBS is configured to use. The script will function without it but might rely solely on `kscreen-doctor`.

## Installation

1.  **Download:** Get the `wayland_obs_director.py` file from this repository (e.g., from the [Releases](link-to-releases-if-you-create-them) page or by cloning the repo).
2.  **Configure OBS Python:**
    *   Open OBS Studio.
    *   Go to `Tools` -> `Scripts`.
    *   Select the `Python Settings` tab.
    *   Ensure a valid Python installation path is configured. OBS often bundles Python, but you might need to point it to your system's Python 3 installation if you encounter issues or want to use globally installed packages like PyQt6.
3.  **Add the Script:**
    *   Go back to the `Scripts` tab.
    *   Click the `+` button (bottom left).
    *   Navigate to and select the downloaded `wayland_obs_director.py` file.
    *   The script "Wayland OBS Director" should now appear in the list.

## Usage

1.  **Select the Script:** Click on "Wayland OBS Director" in the Scripts list. Its description and options will appear on the right.
2.  **Enable:** Check the `Enable Script` box to activate the automatic scene switching.
3.  **(Optional) Activate on Startup:** Check `Activate on OBS Startup` if you want the script to be automatically enabled every time you launch OBS.
4.  **Refresh:** Click `Refresh Monitors && Scenes`. This will:
    *   Detect your connected monitors (using PyQt6 or `kscreen-doctor`).
    *   Get the list of your current OBS scenes.
    *   Populate the "Monitor -> Scene Mapping" section below.
5.  **Map Monitors to Scenes:** For each detected monitor (e.g., `DP-1`, `HDMI-A-0`), use the dropdown list next to it to select the OBS scene you want to activate when the mouse is on that monitor.
    *   Selecting `<Do Nothing>` means no scene change will occur for that specific monitor.
6.  **Done:** The script will now poll KWin periodically (`~350ms` by default) and switch scenes automatically when you move your mouse between mapped monitors.

## How it Works (Technical Details)

*   **Polling:** The script sets up a timer within OBS (`obs.timer_add`) that runs the `poll_kwin` function every `POLL_INTERVAL_MS` milliseconds.
*   **Active Monitor Detection:** `poll_kwin` calls `get_kwin_active_output_name_subprocess`, which executes the command `qdbus6 org.kde.KWin /KWin org.kde.KWin.activeOutputName`. This D-Bus call asks KWin directly which monitor output currently contains the mouse pointer.
*   **Monitor Name Detection (for UI):** The `detect_outputs` function (triggered by `Refresh` or script load) tries to get monitor names:
    *   **Attempt 1 (PyQt6):** It tries to import `PyQt6.QtGui.QGuiApplication` and use `QGuiApplication.screens()` to get `screen.name()`. This often provides the most accurate names matching KWin's output names (`DP-1`, etc.). Requires `PyQt6` to be available to OBS's Python environment.
    *   **Attempt 2 (kscreen-doctor):** If PyQt6 fails, it runs `kscreen-doctor -o` and parses the output to find lines like `Output: DP-1 enabled`.
*   **Scene Switching:** If the detected active monitor name changes and it's mapped to a scene in the UI settings, the script uses `obs.obs_frontend_set_current_scene` to switch to the target scene source.

## Troubleshooting

*   **Script Not Working:**
    *   Ensure the `Enable Script` checkbox is checked.
    *   Verify you are running **KDE Plasma 6** on a **Wayland** session (`echo $XDG_SESSION_TYPE` in terminal should output `wayland`).
    *   Confirm `qt6-tools` is installed and `qdbus6` is executable (`which qdbus6` should show a path, try running `qdbus6 org.kde.KWin /KWin org.kde.KWin.activeOutputName` in your terminal - it should output your current monitor name like `DP-1`).
    *   Check the OBS Log for errors: `Help` -> `Log Files` -> `View Current Log`. Look for lines containing `OBSDirector` or Python errors.
*   **Monitors Not Detected Correctly / Mapping UI Empty:**
    *   Click the `Refresh Monitors && Scenes` button.
    *   Ensure `kscreen` is installed (`which kscreen-doctor`).
    *   For best results, try installing `PyQt6` in a way that OBS's Python environment can see it (this can be tricky depending on how OBS handles Python).
    *   Check the OBS Log for errors during detection.
*   **Scenes Don't Switch:**
    *   Double-check the mapping in the script UI. Are the correct monitors mapped to the *exact* scene names in OBS? Scene names are case-sensitive.
    *   Make sure the scenes you mapped actually exist in your OBS Scene Collection.
*   **"WARNING: 'qdbus6' not found..." in Script UI:** `qt6-tools` is likely not installed correctly or `qdbus6` isn't in the system's PATH accessible by OBS.

## Contributions

Contributions are welcome! Feel free to open an Issue to report bugs or suggest features, or open a Pull Request with improvements.

1.  Fork the repository.
2.  Create a feature branch (`git checkout -b feature/AmazingFeature`).
3.  Commit your changes (`git commit -m 'Add some AmazingFeature'`).
4.  Push to the branch (`git push origin feature/AmazingFeature`).
5.  Open a Pull Request.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Credits and Attribution

**Script created by MullyCap2004 ([https://github.com/MullyCap2004]).**

If you use this script, adapt it, or include it in your own projects, **please provide attribution** by mentioning the original author and linking back to this repository. Thank you!

*(Example: "Uses the Wayland OBS Director script by [MullyCap2004] - [https://github.com/MullyCap2004/obs-kde-plasma-wayland-director.git]")*
