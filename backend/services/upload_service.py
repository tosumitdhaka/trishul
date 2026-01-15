"""
Upload Service - Manages temporary file uploads and cleanup
"""

import shutil
import tarfile
import uuid
import zipfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional, Tuple

from fastapi import HTTPException, UploadFile

from services.config_service import Config
from utils.logger import get_logger

logger = get_logger(__name__)


class UploadService:
    """
    Manages file uploads to temporary session directories
    """

    def __init__(self, base_upload_dir: str = None):

        self.config = Config()

        self.base_upload_dir = Path(base_upload_dir or self.config.upload.upload_dir)
        self.base_upload_dir.mkdir(exist_ok=True)

        # Archive settings from config
        self.max_size = self.config.upload.max_size_mb * 1024 * 1024
        self.max_archive_size = self.config.upload.max_archive_size_mb * 1024 * 1024
        self.max_archive_entries = self.config.upload.max_archive_entries

        # Supported file extensions from config
        self.supported_extensions = set(self.config.upload.supported_extensions)

    def create_session(self) -> str:
        """
        Create a new upload session with UUID

        Returns:
            session_id: UUID string
        """
        session_id = str(uuid.uuid4())
        session_dir = self.base_upload_dir / session_id
        session_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"Created upload session: {session_id}")
        return session_id

    def get_session_dir(self, session_id: str) -> Path:
        """
        Get session directory path

        Args:
            session_id: Session UUID

        Returns:
            Path to session directory
        """
        session_dir = self.base_upload_dir / session_id
        if not session_dir.exists():
            raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")
        return session_dir

    async def upload_file(self, session_id: str, file: UploadFile) -> Tuple[str, int]:
        """
        Upload a single file to session directory

        Args:
            session_id: Session UUID
            file: Uploaded file

        Returns:
            Tuple of (file_path, file_size)
        """
        session_dir = self.get_session_dir(session_id)

        if not session_dir.exists():
            raise ValueError(f"Session not found: {session_id}")

        # ✅ Extract just the filename (ignore directory structure)
        filename = Path(file.filename).name

        # ✅ Save to session directory root (flat structure)
        file_path = session_dir / filename

        # Read and save file
        content = await file.read()

        with open(file_path, "wb") as f:
            f.write(content)

        file_size = len(content)

        # ✅ ADD: Validate file size
        if file_size > self.max_size:
            raise HTTPException(
                status_code=413,
                detail=f"File too large: {file_size / (1024*1024):.1f}MB (max: {self.config.upload.max_size_mb}MB)"
            )

        logger.info(f"✅ Uploaded {filename} ({file_size} bytes) to session {session_id}")

        return str(file_path), file_size

    async def upload_files(self, session_id: str, files: List[UploadFile]) -> List[dict]:
        """
        Upload multiple files to session directory

        Args:
            session_id: Session UUID
            files: List of uploaded files

        Returns:
            List of file info dicts
        """
        results = []

        for file in files:
            try:
                file_path, file_size = await self.upload_file(session_id, file)

                results.append(
                    {
                        "filename": Path(file.filename).name,  # ✅ Use clean filename
                        "original_path": file.filename,  # Keep original for reference
                        "path": file_path,
                        "size": file_size,
                        "status": "success",
                    }
                )

            except Exception as e:
                logger.error(f"Failed to upload {file.filename}: {e}")
                results.append({"filename": file.filename, "status": "failed", "error": str(e)})

        return results

    def extract_archive(self, session_id: str, archive_path: Path) -> dict:
        """
        Extract archive to session directory
        """
        session_dir = self.get_session_dir(session_id)
        extract_dir = session_dir

        try:

            # ✅ ADD: Validate archive size
            archive_size = archive_path.stat().st_size
            if archive_size > self.max_archive_size:
                raise ValueError(
                    f"Archive too large: {archive_size / (1024*1024):.1f}MB "
                    f"(max: {self.config.upload.max_archive_size_mb}MB)"
                )

            total_files = 0
            supported_files_list = []  # ✅ Track filenames
            ignored_files_list = []  # ✅ Track filenames
            total_size = 0

            if archive_path.suffix == ".zip":
                with zipfile.ZipFile(archive_path, "r") as zip_ref:
                    file_list = zip_ref.namelist()

                    if len(file_list) > self.max_archive_entries:
                        raise ValueError(f"Archive contains too many files: {len(file_list)}")

                    for file_info in zip_ref.infolist():
                        if file_info.is_dir():
                            continue

                        filename = Path(file_info.filename).name
                        target_path = extract_dir / filename

                        with zip_ref.open(file_info) as source:
                            with open(target_path, "wb") as target:
                                shutil.copyfileobj(source, target)

                        total_files += 1
                        file_size = target_path.stat().st_size
                        total_size += file_size

                        # ✅ Track by filename
                        if target_path.suffix.lower() in self.supported_extensions:
                            supported_files_list.append(filename)
                        else:
                            ignored_files_list.append(filename)

            elif archive_path.suffix in [".tar", ".gz", ".tgz"]:
                with tarfile.open(archive_path, "r:*") as tar_ref:
                    members = tar_ref.getmembers()

                    if len(members) > self.max_archive_entries:
                        raise ValueError(f"Archive contains too many files: {len(members)}")

                    for member in members:
                        if member.isdir():
                            continue

                        filename = Path(member.name).name
                        target_path = extract_dir / filename

                        with tar_ref.extractfile(member) as source:
                            with open(target_path, "wb") as target:
                                shutil.copyfileobj(source, target)

                        total_files += 1
                        file_size = target_path.stat().st_size
                        total_size += file_size

                        # ✅ Track by filename
                        if target_path.suffix.lower() in self.supported_extensions:
                            supported_files_list.append(filename)
                        else:
                            ignored_files_list.append(filename)

            else:
                raise ValueError(f"Unsupported archive format: {archive_path.suffix}")

            # Delete the original archive file
            archive_path.unlink()

            logger.info(
                f"Extracted {total_files} files "
                f"({len(supported_files_list)} supported, {len(ignored_files_list)} ignored)"
            )

            return {
                "success": True,
                "total_files": total_files,
                "supported_files": supported_files_list,  # ✅ Return list
                "ignored_files": ignored_files_list,  # ✅ Return list
                "extract_dir": str(extract_dir),
                "total_size": total_size,
            }

        except Exception as e:
            logger.error(f"Archive extraction failed: {e}", exc_info=True)
            raise

    def filter_supported_files(self, session_id: str) -> List[dict]:
        """
        Get list of supported files in session directory

        Args:
            session_id: Session UUID

        Returns:
            List of supported file info dicts
        """
        session_dir = self.get_session_dir(session_id)
        supported_files = []

        for file_path in session_dir.rglob("*"):
            if file_path.is_file() and file_path.suffix.lower() in self.supported_extensions:
                supported_files.append(
                    {
                        "filename": file_path.name,
                        "path": str(file_path),
                        "size": file_path.stat().st_size,
                        "relative_path": str(file_path.relative_to(session_dir)),
                    }
                )

        return supported_files

    def cleanup_session(self, session_id: str) -> bool:
        """
        Delete session directory and all contents

        Args:
            session_id: Session UUID

        Returns:
            True if successful
        """
        try:
            session_dir = self.base_upload_dir / session_id
            if session_dir.exists():
                shutil.rmtree(session_dir)
                logger.info(f"Cleaned up session: {session_id}")
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to cleanup session {session_id}: {e}")
            return False

    def cleanup_old_sessions(self, max_age_hours: Optional[int] = None) -> int:
        """
        Cleanup sessions older than max_age_hours

        Args:
            max_age_hours: Maximum age in hours

        Returns:
            Number of sessions cleaned up
        """

        # ✅ Use config if not provided
        if max_age_hours is None:
            max_age_hours = self.config.upload.session_timeout_hours

        cleaned = 0
        cutoff_time = datetime.now() - timedelta(hours=max_age_hours)

        try:
            for session_dir in self.base_upload_dir.iterdir():
                if not session_dir.is_dir():
                    continue

                # Check directory modification time
                mtime = datetime.fromtimestamp(session_dir.stat().st_mtime)
                if mtime < cutoff_time:
                    try:
                        shutil.rmtree(session_dir)
                        cleaned += 1
                        logger.info(f"Cleaned up old session: {session_dir.name}")
                    except Exception as e:
                        logger.error(f"Failed to cleanup {session_dir.name}: {e}")

            logger.info(f"Cleaned up {cleaned} old sessions")
            return cleaned

        except Exception as e:
            logger.error(f"Cleanup old sessions failed: {e}")
            return cleaned

    def get_session_info(self, session_id: str) -> dict:
        """
        Get information about a session

        Args:
            session_id: Session UUID

        Returns:
            Session info dict
        """
        session_dir = self.get_session_dir(session_id)

        # Count files and calculate total size
        file_count = 0
        total_size = 0
        supported_count = 0

        for file_path in session_dir.rglob("*"):
            if file_path.is_file():
                file_count += 1
                total_size += file_path.stat().st_size

                if file_path.suffix.lower() in self.supported_extensions:
                    supported_count += 1

        return {
            "session_id": session_id,
            "path": str(session_dir),
            "file_count": file_count,
            "supported_count": supported_count,
            "total_size": total_size,
            "created": datetime.fromtimestamp(session_dir.stat().st_ctime).isoformat(),
        }
