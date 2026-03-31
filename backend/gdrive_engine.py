"""Google Drive backup integration using OAuth 2.0.

Flow:
1. User places their OAuth client credentials JSON (from Google Cloud Console)
   into data/gdrive_credentials.json
2. On first use, the app opens a browser for OAuth consent
3. Token is cached in data/gdrive_token.json for subsequent use
4. Files are uploaded to a 'MeetingMate' folder in the user's Drive

Supported OAuth client types:
  - "Desktop app" (recommended): uses loopback redirect (http://localhost)
  - "Web app": needs http://localhost:8090/ in authorized redirect URIs
"""

import logging
import json
import mimetypes
from pathlib import Path
from typing import Optional

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

from config import (
    load_settings,
    GDRIVE_CREDENTIALS_PATH,
    GDRIVE_TOKEN_PATH,
)

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/drive.file"]

# Port for OAuth redirect — keep consistent
OAUTH_PORT = 8090


def _read_client_type() -> str:
    """Read the OAuth client type from credentials JSON."""
    try:
        data = json.loads(GDRIVE_CREDENTIALS_PATH.read_text(encoding="utf-8"))
        if "installed" in data:
            return "desktop"
        elif "web" in data:
            return "web"
    except Exception:
        pass
    return "unknown"


def _get_credentials() -> Optional[Credentials]:
    """Load or refresh OAuth credentials."""
    creds = None

    # 1. Try loading existing token
    if GDRIVE_TOKEN_PATH.exists():
        try:
            creds = Credentials.from_authorized_user_file(str(GDRIVE_TOKEN_PATH), SCOPES)
        except Exception as e:
            logger.warning(f"Failed to load existing token: {e}")
            creds = None

    # 2. Refresh if expired
    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            GDRIVE_TOKEN_PATH.write_text(creds.to_json())
            return creds
        except Exception as e:
            logger.warning(f"Token refresh failed: {e}")
            creds = None

    # 3. Return if still valid
    if creds and creds.valid:
        return creds

    # 4. Need new authorization
    if not GDRIVE_CREDENTIALS_PATH.exists():
        logger.warning(
            "No Google Drive credentials file found. "
            "Place your OAuth client JSON at %s",
            GDRIVE_CREDENTIALS_PATH,
        )
        return None

    creds = _run_oauth_flow()
    return creds


def _run_oauth_flow() -> Optional[Credentials]:
    """Run the OAuth 2.0 authorization flow.

    Handles both 'Desktop app' and 'Web app' client types.
    For Desktop app: uses run_local_server (loopback redirect, no URI config needed).
    For Web app: uses run_local_server with explicit port.
    """
    client_type = _read_client_type()
    logger.info(f"OAuth client type detected: {client_type}")

    try:
        flow = InstalledAppFlow.from_client_secrets_file(
            str(GDRIVE_CREDENTIALS_PATH), SCOPES
        )

        # run_local_server works for both Desktop and Web clients.
        # For Desktop: Google allows any loopback redirect automatically.
        # For Web: the user must add http://localhost:{port}/ to redirect URIs.
        creds = flow.run_local_server(
            host="localhost",
            port=OAUTH_PORT,
            open_browser=True,
            success_message=(
                "授權成功！你可以關閉此視窗並回到 MeetingMate。"
            ),
        )

        GDRIVE_TOKEN_PATH.write_text(creds.to_json())
        logger.info("Google Drive OAuth authorization successful.")
        return creds

    except Exception as e:
        error_msg = str(e)
        logger.error(f"OAuth flow failed: {error_msg}", exc_info=True)

        # Provide helpful guidance based on error type
        if "redirect_uri_mismatch" in error_msg.lower() or "redirect" in error_msg.lower():
            logger.error(
                "\n"
                "========================================================\n"
                " redirect_uri_mismatch 修復步驟:\n"
                "========================================================\n"
                " 方法 A（推薦）: 使用「桌面應用程式」類型的 OAuth 用戶端\n"
                "   1. 前往 Google Cloud Console > API 和服務 > 憑證\n"
                "   2. 刪除現有的 OAuth 用戶端 ID\n"
                "   3. 建立新的 OAuth 2.0 用戶端 ID\n"
                "   4. 應用程式類型選擇「桌面應用程式」\n"
                "   5. 下載 JSON 並存為 data/gdrive_credentials.json\n"
                "\n"
                " 方法 B: 如果堅持使用「網頁應用程式」類型\n"
                "   1. 在 OAuth 用戶端的「已授權的重新導向 URI」中加入:\n"
                f"      http://localhost:{OAUTH_PORT}/\n"
                "   注意：結尾的 / 斜線不能少！\n"
                "========================================================"
            )
        raise


def _get_service():
    """Build Google Drive API service."""
    creds = _get_credentials()
    if not creds:
        raise RuntimeError(
            "Google Drive 尚未授權。請先到設定頁面完成 Google Drive 授權。\n"
            "步驟：1) 在 Google Cloud Console 建立「桌面應用程式」類型的 OAuth 用戶端 "
            "2) 下載 JSON 存為 data/gdrive_credentials.json "
            "3) 點擊設定頁的授權按鈕"
        )
    return build("drive", "v3", credentials=creds)


def _get_or_create_folder(service, folder_name: str, parent_id: Optional[str] = None) -> str:
    """Find or create a folder in Google Drive."""
    query = f"name='{folder_name}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
    if parent_id:
        query += f" and '{parent_id}' in parents"

    results = service.files().list(q=query, spaces="drive", fields="files(id, name)").execute()
    files = results.get("files", [])

    if files:
        return files[0]["id"]

    # Create folder
    metadata = {
        "name": folder_name,
        "mimeType": "application/vnd.google-apps.folder",
    }
    if parent_id:
        metadata["parents"] = [parent_id]

    folder = service.files().create(body=metadata, fields="id").execute()
    logger.info(f"Created Google Drive folder: {folder_name} ({folder['id']})")
    return folder["id"]


def _resolve_nested_folder(service, folder_path: str) -> str:
    """Resolve a nested folder path like 'Temp/MeetingMinute', creating folders as needed."""
    parts = [p.strip() for p in folder_path.split("/") if p.strip()]
    parent_id = None
    for part in parts:
        parent_id = _get_or_create_folder(service, part, parent_id)
    return parent_id


def upload_file(local_path: str, subfolder: str = "", filename: Optional[str] = None) -> str:
    """Upload a file to Google Drive under <gdrive_folder_name>/<subfolder>/."""
    settings = load_settings()
    service = _get_service()

    # Supports nested paths like "Temp/MeetingMinute"
    root_folder_id = _resolve_nested_folder(service, settings.gdrive_folder_name)
    parent_id = root_folder_id
    if subfolder:
        parent_id = _get_or_create_folder(service, subfolder, root_folder_id)

    path = Path(local_path)
    upload_name = filename or path.name
    mime_type = mimetypes.guess_type(str(path))[0] or "application/octet-stream"

    metadata = {
        "name": upload_name,
        "parents": [parent_id],
    }
    media = MediaFileUpload(str(path), mimetype=mime_type, resumable=True)
    file = service.files().create(body=metadata, media_body=media, fields="id").execute()

    logger.info(f"Uploaded to Drive: {upload_name} -> {file['id']}")
    return file["id"]


def check_auth_status() -> dict:
    """Check if Google Drive is authorized (non-interactive, won't trigger OAuth flow)."""
    try:
        if not GDRIVE_TOKEN_PATH.exists():
            return {"authorized": False, "email": ""}

        creds = Credentials.from_authorized_user_file(str(GDRIVE_TOKEN_PATH), SCOPES)

        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
            GDRIVE_TOKEN_PATH.write_text(creds.to_json())

        if creds and creds.valid:
            service = build("drive", "v3", credentials=creds)
            about = service.about().get(fields="user").execute()
            email = about.get("user", {}).get("emailAddress", "unknown")
            return {"authorized": True, "email": email}
    except Exception as e:
        logger.error(f"GDrive auth check failed: {e}")

    return {"authorized": False, "email": ""}


def start_auth_flow() -> dict:
    """Start OAuth authorization flow (opens browser). Returns result."""
    if not GDRIVE_CREDENTIALS_PATH.exists():
        return {
            "success": False,
            "error": (
                "找不到 OAuth 憑證檔案。請先完成以下步驟：\n"
                "1. 前往 Google Cloud Console > API 和服務 > 憑證\n"
                "2. 建立 OAuth 2.0 用戶端 ID（類型選「桌面應用程式」）\n"
                "3. 下載 JSON 檔，重新命名為 gdrive_credentials.json\n"
                f"4. 放入 {GDRIVE_CREDENTIALS_PATH.parent}/ 目錄"
            ),
        }

    try:
        creds = _run_oauth_flow()
        if creds and creds.valid:
            service = build("drive", "v3", credentials=creds)
            about = service.about().get(fields="user").execute()
            email = about.get("user", {}).get("emailAddress", "unknown")
            return {"success": True, "email": email}
        return {"success": False, "error": "授權失敗，請重試。"}
    except Exception as e:
        error_msg = str(e)
        if "redirect_uri_mismatch" in error_msg.lower() or "redirect" in error_msg.lower():
            return {
                "success": False,
                "error": (
                    "redirect_uri_mismatch 錯誤！\n\n"
                    "最簡單的修復方式：\n"
                    "1. 前往 Google Cloud Console > 憑證\n"
                    "2. 刪除目前的 OAuth 用戶端 ID\n"
                    "3. 重新建立，應用程式類型選「桌面應用程式」(Desktop app)\n"
                    "4. 下載新的 JSON 覆蓋 data/gdrive_credentials.json\n"
                    "5. 再次點擊授權按鈕\n\n"
                    "「桌面應用程式」類型不需要設定 redirect URI，不會有此問題。"
                ),
            }
        return {"success": False, "error": f"授權失敗：{error_msg}"}
