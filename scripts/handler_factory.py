class HandlerFactory:
    @staticmethod
    def get_handler(remote_string: str):
        """
        Takes "profile:path" and returns the appropriate Handler instance.
        """
        # 1. Parse the profile name (e.g., 'e2')
        profile_name = remote_string.split(':', 1)[0]
        
        # 2. Load the secrets config (logic from our previous discussion)
        # For this example, assume we have a helper to get the section
        config_section = load_config_section(profile_name) 
        backend_type = config_section.get('type', 's3').lower()

        # 3. Return the specific implementation
        if backend_type == 's3':
            from handlers.s3_handler import S3Handler
            return S3Handler(remote_string)
            
        elif backend_type == 'ftp':
            from handlers.ftp_handler import FTPHandler
            return FTPHandler(remote_string)
            
        elif backend_type == 'onedrive':
            from handlers.onedrive_handler import OneDriveHandler
            return OneDriveHandler(remote_string)
            
        else:
            raise ValueError(f"Unsupported backend type: {backend_type}")
        