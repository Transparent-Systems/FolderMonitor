from abc import ABC, abstractmethod
from typing import Tuple

class BaseHandler(ABC):
    """
    Abstract Base Class that defines the contract for all storage backends.
    """

    @abstractmethod
    def get_remote_path(self, source_path: str) -> str:
        """
        Derives remote path from base source path and this source path.
        Returns a string path.
        """
        pass

    @abstractmethod
    def file_exists(self, remote_path: str) -> tuple[int, str]:
        """
        Check if remote path exists
        """
        pass

    def copy_file(self, source_path: str, remote_path: str | None = None) -> tuple[int, str]:
        """
        Copy source_path to remote_path.
        If remote_path is None, the remote_path is derived from the source_path
        Returns:
            (result_code, result_output)

        """
        pass

    @abstractmethod
    def copy_folder(self, source_path: str) -> Tuple[int, str]:
        """
        Copy the source path to the derived remote path.
        The remote path can usually be automatically derived from the source path.
        """
        pass


    @abstractmethod
    def delete_file(self, remote_path: str) -> Tuple[int, str]:
        """
        Delete file at remote_path.
        """
        pass

    @abstractmethod
    def delete_folder(self, remote_path: str) -> Tuple[int, str]:
        """
        Delete objects in remote_path
        """
        pass

    # @abstractmethod
    # def sync_folder(self, source_path: str) -> Tuple[int, str]:
    #     """
    #     Sync the source path to the derived remote path.
    #     """
    #     pass

    def normalize_path(self, path: str) -> str:
        """
        Shared utility: S3 and most cloud providers prefer forward slashes.
        """
        return path.replace('\\', '/').strip('/')
    
    