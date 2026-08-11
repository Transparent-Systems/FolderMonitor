import logging
from re import S

from .base_handler import BaseHandler
from .rclone_handler import RcloneHandler
from .s3_handler import S3Handler


class BaseHandlerFactory:
    """
    Factory class for creating BaseHandler instances.
    """

    @classmethod
    def get_handler(
        cls, 
        logger: logging.Logger, 
        source_path: str, 
        remote_path: str,
        profile_type: str 
        ) -> BaseHandler | None:
        """
        Returns an BaseHandler instance based on the profile_type
        """

        # We need to instantiate a remote handler based on the profile_type
        # A profile can be a native profile or imported from Rclone
        profile_type = profile_type.strip()
        handler = None
        if profile_type == "s3":
            # Instantiate S3Handler
            handler = S3Handler(
                logger=logger,
                base_source_path=source_path,
                base_remote_path=remote_path,
                profile_type=profile_type    
                )
        else:
            # Instantiate RcloneHandler
            handler = RcloneHandler(
                logger=logger,
                base_source_path=source_path,
                base_remote_path=remote_path,
                profile_name=profile_type    
                )
    
        return handler
  
