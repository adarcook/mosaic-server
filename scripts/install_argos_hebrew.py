from __future__ import annotations

import argostranslate.package
import argostranslate.translate


def main() -> None:
    installed = argostranslate.translate.get_installed_languages()
    source = next((language for language in installed if language.code == "en"), None)
    target = next((language for language in installed if language.code == "he"), None)
    if source is not None and target is not None:
        try:
            source.get_translation(target)
            print("Argos English-to-Hebrew model is already installed.")
            return
        except Exception:
            pass

    print("Updating the Argos package index...")
    argostranslate.package.update_package_index()
    packages = argostranslate.package.get_available_packages()
    package = next(
        (
            candidate
            for candidate in packages
            if candidate.from_code == "en" and candidate.to_code == "he"
        ),
        None,
    )
    if package is None:
        raise SystemExit("No Argos English-to-Hebrew package was found in the package index.")

    print(f"Downloading {package}...")
    download_path = package.download()
    argostranslate.package.install_from_path(download_path)
    print("Argos English-to-Hebrew model installed successfully.")


if __name__ == "__main__":
    main()
