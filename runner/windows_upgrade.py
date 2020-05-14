import os
import requests
import sys
from packaging.version import parse


from tqdm import tqdm


def relative_dir():
    def is_pyinstall_bundled():
        if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
            return True
        return False

    if is_pyinstall_bundled():
        # This is a pyinstaller package on Windows; the `cwd` is
        # likely to be anything (e.g. the Github desktop AppData
        # space); `__file__` is some kind of temporary location
        # resulting from an internal unzip.
        relative_dir = os.path.dirname(os.path.realpath(sys.executable))
    else:
        relative_dir = os.getcwd()
    return relative_dir


def local_version():
    with open(os.path.join(os.path.dirname(__file__), "VERSION")) as version_file:
        version = version_file.read().strip()
    return version


def check_for_updates():
    """Return required version as a string, or None if no updates are required
    """
    with open(
        os.path.join(relative_dir(), "runner", "required_version.txt")
    ) as version_file:
        required_version = parse(version_file.read().strip())
    supplied_version = parse(local_version())
    if required_version > supplied_version:
        return str(required_version)


if __name__ == "__main__":
    required_version = check_for_updates()

    if required_version:
        url = f"https://github.com/ebmdatalab/opensafely-research-template/releases/download/v{required_version}/windows_run.exe"
        response = requests.get(url, stream=True)
        response.raise_for_status()
        t = tqdm(desc="Downloading new version...", unit="bytes", unit_scale=True)
        with open("windows_run.exe.tmp", "wb") as f:
            chunk_size = 2 ** 18  # 256k
            for data in response.iter_content(chunk_size=chunk_size):
                f.write(data)
                t.update(len(data))
        os.replace("windows_run.exe.tmp", "windows_run.exe")
        print("Upgraded!")
    else:
        print("No upgrade needed")
