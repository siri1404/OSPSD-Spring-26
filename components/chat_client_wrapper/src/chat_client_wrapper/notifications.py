"""Message formatters for storage and AI events."""

from __future__ import annotations


class NotificationMessages:
    """Message formatters for various storage and AI events."""

    @staticmethod
    def file_uploaded(container: str, object_name: str, size_bytes: int | None = None) -> str:
        """Format notification for file upload event.

        Args:
            container: Container/bucket name.
            object_name: Uploaded object name/path.
            size_bytes: Optional file size in bytes.

        Returns:
            Formatted notification message.
        """
        size_info = f" ({size_bytes} bytes)" if size_bytes is not None else ""
        return f"📤 File uploaded: `{object_name}` in container `{container}`{size_info}"

    @staticmethod
    def file_deleted(container: str, object_name: str) -> str:
        """Format notification for file deletion event.

        Args:
            container: Container/bucket name.
            object_name: Deleted object name/path.

        Returns:
            Formatted notification message.
        """
        return f"🗑️ File deleted: `{object_name}` from container `{container}`"

    @staticmethod
    def ai_action_performed(
        action: str,
        container: str | None = None,
        object_name: str | None = None,
        result: str | None = None,
    ) -> str:
        """Format notification for AI action event.

        Args:
            action: The action performed (e.g., "list_files", "delete_file").
            container: Optional container name involved in the action.
            object_name: Optional object name involved in the action.
            result: Optional brief result summary.

        Returns:
            Formatted notification message.
        """
        msg = f"🤖 AI performed action: `{action}`"

        if container:
            msg += f" on container `{container}`"
        if object_name:
            msg += f" targeting `{object_name}`"
        if result:
            msg += f"\n   Result: {result}"

        return msg

    @staticmethod
    def error_occurred(error_type: str, message: str, context: str | None = None) -> str:
        """Format notification for error event.

        Args:
            error_type: Type of error (e.g., "AuthenticationError", "FileNotFound").
            message: Error message.
            context: Optional context about what was being attempted.

        Returns:
            Formatted notification message.
        """
        msg = f"⚠️ Error occurred: {error_type} - {message}"
        if context:
            msg += f"\n   Context: {context}"
        return msg
