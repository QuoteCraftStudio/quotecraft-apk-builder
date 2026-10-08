# QuoteCraft APK Builder

HTML-to-APK builder with a Windows desktop control window and an Android phone browser interface. See START-HERE.md for the Android toolchain setup and supported app features.

## Windows executable packaging

This repository includes a packaging-only GitHub Actions workflow. It does not run tests.

After source files and `.github/workflows/package-windows.yml` are uploaded to the main branch, GitHub uses a Windows runner to produce `QuoteCraft-APK-Builder.exe`. When that build succeeds, its Actions page has a **QuoteCraft-APK-Builder-Windows** download containing the EXE and instructions. The artifact is retained for 14 days.

Alternatively, double-click **Build-Windows.cmd** on a Windows computer with Python installed. It installs a pinned PyInstaller version into an isolated environment and produces the EXE under **dist**. No application tests are run by this script.

The packaged EXE contains Python, so users do not need Python installed to run it. They still need the Android SDK, Java and Gradle to compile APKs. The Android builder interface runs in Chrome and uses the Windows computer for compilation.

The packaging files have been prepared; this source package does not contain a compiled EXE until a Windows packaging run succeeds.
