from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import urllib.error
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path


class UpdateError(RuntimeError):
    pass


@dataclass(frozen=True)
class UpdateInfo:
    version: str
    download_url: str
    checksum_url: str
    asset_name: str


def _version_tuple(value: str) -> tuple[int, ...]:
    numbers = re.findall(r"\d+", value)
    return tuple(int(item) for item in numbers[:4]) or (0,)


def normalize_repo(value: str) -> str:
    value = value.strip().rstrip("/")
    value = re.sub(r"^https?://github\.com/", "", value, flags=re.I)
    value = re.sub(r"\.git$", "", value, flags=re.I)
    if value and not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", value):
        raise UpdateError("Địa chỉ GitHub phải có dạng ten-tai-khoan/ten-kho.")
    return value


def check_for_update(repo: str, current_version: str) -> UpdateInfo | None:
    repo = normalize_repo(repo)
    if not repo:
        raise UpdateError("Chưa cấu hình nguồn cập nhật GitHub.")
    request = urllib.request.Request(
        f"https://api.github.com/repos/{repo}/releases/latest",
        headers={"Accept": "application/vnd.github+json", "User-Agent": "AmazonMailReader"},
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            release = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise UpdateError(f"GitHub trả lỗi HTTP {exc.code}.") from exc
    except OSError as exc:
        raise UpdateError(f"Không kết nối được GitHub: {exc}") from exc
    version = str(release.get("tag_name") or release.get("name") or "0")
    if _version_tuple(version) <= _version_tuple(current_version):
        return None
    assets = release.get("assets") or []
    package = next((item for item in assets if str(item.get("name", "")).lower().endswith("win64.zip")), None)
    if package is None:
        package = next((item for item in assets if str(item.get("name", "")).lower().endswith(".zip")), None)
    if package is None:
        raise UpdateError("B?n ph�t h�nh chua c� g�i ZIP d�nh cho Windows.")
    package_name = str(package["name"])
    checksum = next(
        (item for item in assets if str(item.get("name", "")).lower() in {f"{package_name}.sha256".lower(), "sha256sums.txt"}),
        None,
    )
    if checksum is None:
        raise UpdateError("B?n ph�t h�nh thi?u file SHA-256 n�n app kh�ng t?i d? b?o d?m an to�n.")
    return UpdateInfo(version, str(package["browser_download_url"]), str(checksum["browser_download_url"]), package_name)


def download_update(info: UpdateInfo, data_dir: Path) -> Path:
    update_dir = data_dir / "updates"
    update_dir.mkdir(parents=True, exist_ok=True)
    package_path = update_dir / info.asset_name
    try:
        with urllib.request.urlopen(info.download_url, timeout=120) as response:
            package_data = response.read()
        with urllib.request.urlopen(info.checksum_url, timeout=30) as response:
            checksum_text = response.read().decode("utf-8", errors="replace")
    except OSError as exc:
        raise UpdateError(f"Tải bản cập nhật thất bại: {exc}") from exc
    matching_line = next((line for line in checksum_text.splitlines() if info.asset_name.lower() in line.lower()), checksum_text)
    expected_match = re.search(r"\b([a-fA-F0-9]{64})\b", matching_line)
    if not expected_match:
        raise UpdateError("Không đọc được mã SHA-256 của bản cập nhật.")
    actual = hashlib.sha256(package_data).hexdigest()
    if actual.lower() != expected_match.group(1).lower():
        raise UpdateError("Mã SHA-256 không khớp. File cập nhật đã bị từ chối.")
    package_path.write_bytes(package_data)
    try:
        with zipfile.ZipFile(package_path) as archive:
            names = archive.namelist()
            for name in names:
                normalized = name.replace("\\", "/")
                if normalized.startswith("/") or ".." in Path(normalized).parts:
                    raise UpdateError("Gói cập nhật chứa đường dẫn không an toàn.")
            if not any(Path(name).name.lower() == "run_app.bat" for name in names):
                raise UpdateError("Gói cập nhật thiếu file chạy ứng dụng.")
    except zipfile.BadZipFile as exc:
        raise UpdateError("Gói cập nhật không phải file ZIP hợp lệ.") from exc
    return package_path


def launch_update(package_path: Path, program_dir: Path, launcher_name: str, parent_pid: int) -> None:
    def ps_quote(value: str) -> str:
        return "'" + value.replace("'", "''") + "'"

    script_path = package_path.parent / "apply-update.ps1"
    backup = program_dir.with_name(program_dir.name + ".backup")
    script = f"""
$ErrorActionPreference = 'Stop'
Wait-Process -Id {parent_pid} -ErrorAction SilentlyContinue
$program = {ps_quote(str(program_dir))}
$backup = {ps_quote(str(backup))}
$package = {ps_quote(str(package_path))}
if (Test-Path -LiteralPath $backup) {{ Remove-Item -LiteralPath $backup -Recurse -Force }}
if (Test-Path -LiteralPath $program) {{ Move-Item -LiteralPath $program -Destination $backup }}
try {{
    New-Item -ItemType Directory -Path $program -Force | Out-Null
    Expand-Archive -LiteralPath $package -DestinationPath $program -Force
    $launcher = Join-Path $program {ps_quote(launcher_name)}
    if (-not (Test-Path -LiteralPath $launcher)) {{ throw 'Gói cập nhật thiếu file chạy ứng dụng.' }}
    Start-Process -FilePath $launcher -WindowStyle Hidden
}} catch {{
    if (Test-Path -LiteralPath $program) {{ Remove-Item -LiteralPath $program -Recurse -Force }}
    if (Test-Path -LiteralPath $backup) {{ Move-Item -LiteralPath $backup -Destination $program }}
    $oldLauncher = Join-Path $program {ps_quote(launcher_name)}
    if (Test-Path -LiteralPath $oldLauncher) {{ Start-Process -FilePath $oldLauncher -WindowStyle Hidden }}
    $_ | Out-File -LiteralPath (Join-Path (Split-Path $package) 'update-error.txt') -Encoding utf8
}}
""".strip()
    script_path.write_text(script, encoding="utf-8-sig")
    subprocess.Popen(
        ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script_path)],
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        close_fds=True,
    )
