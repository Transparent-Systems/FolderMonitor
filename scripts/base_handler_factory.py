import logging

try:
    from scripts.base_handler import BaseHandler
except ModuleNotFoundError:
    from base_handler import BaseHandler

try:
    from scripts.profile_handler import ProfileHandler
except ModuleNotFoundError:
    from profile_handler import ProfileHandler

try:
    from scripts.rclone_handler import RcloneHandler
except ModuleNotFoundError:
    from rclone_handler import RcloneHandler

try:
    from scripts.s3_handler import S3Handler
except ModuleNotFoundError: 
    from s3_handler import S3Handler



class BaseHandlerFactory:
    """
    Factory class for creating BaseHandler instances.
    """

    _profile_handlers: dict[str, ProfileHandler] = {}

    @classmethod
    def get_handler(
        cls, 
        logger: logging.Logger, 
        source_path: str, 
        remote_path: str,
        remote_profile: str 
        ) -> BaseHandler | None:
        """
        Returns an BaseHandler instance based on the remote_profile.
        """

        # Populate profile_handlers if empty
        # Create ProfileHandlers
        if not cls._profile_handlers:
            app_names = ["foldermonitor", "rclone"]
            for app_name in app_names:
                cls._profile_handlers[app_name] = ProfileHandler(
                    logger=logger,
                    app_name=app_name
                )

        # We need to instantiate a remote handler based on the remote_profile
        # If remote_profile is a foldermonitor profile, then instantiate S3Handler
        # If remote_profile is a rclone profile, then instantiate RcloneHandler
        # Otherwise return None
        remote_profile = remote_profile.strip()
        handler = None

        foldermonitor_profile = cls._profile_handlers["foldermonitor"].get_profile(profile_name=remote_profile)
        if (foldermonitor_profile):
            if (foldermonitor_profile.get("type") == "s3"):
                # Instantiate S3Handler
                handler = S3Handler(
                    logger=logger,
                    base_source_path=source_path,
                    base_remote_path=remote_path,
                    remote_profile=remote_profile    
                    )
            else:
                # Instantiate RcloneHandler
                handler = RcloneHandler(
                    logger=logger,
                    base_source_path=source_path,
                    base_remote_path=remote_path,
                    remote_profile=remote_profile    
                    )
        elif (cls._profile_handlers["rclone"].get_profile(profile_name=remote_profile)):
            # Instantiate RcloneHandler
            handler = RcloneHandler(
                logger=logger,
                base_source_path=source_path,
                base_remote_path=remote_path,
                remote_profile=remote_profile    
                )
        elif (remote_profile == ""):
            # Instantiate RcloneHandler
            handler = RcloneHandler(
                logger=logger,
                base_source_path=source_path,
                base_remote_path=remote_path,
                remote_profile=remote_profile    
                )
        else:
            logger.error(f"Remote profile {remote_profile} not present in either foldermonitor or rclone configuration")

        return handler

    
