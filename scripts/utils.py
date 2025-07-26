import logging
import uuid
import os


def get_unique_logger(log_level = "INFO"):
    """
    # Create a unique logger instance with a name based on UUID import uuid
    """
    # Get globally unique logger name
    logger_name = f"Logger_{uuid.uuid4()}"
    logger = logging.getLogger(logger_name)
    
    # Set the logger to debug level initially for its internal setup messages.
    # The effective level will also be governed by the root logger's level.
    level_map = {
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARNING": logging.WARNING,
        "ERROR": logging.ERROR,
        "CRITICAL": logging.CRITICAL
    }
    logger.setLevel(level_map.get(log_level, logging.NOTSET)) # Use .get with default for robustness
    return logger



def create_test_data(path: str, files: list[str] | str):
    """
    Create files relative to path
    """

    if isinstance(files, str):
        file_list = [f"{files}"]
    else:
        file_list = files

    for filename in file_list:
        filename = filename.lstrip("/\\")
        filepath = os.path.join(path, filename)
        head = os.path.dirname(filepath)
        try:
            os.makedirs(head, exist_ok=True)
        except OSError as e:
            sys.exit(1)

        try:
            with open(filepath, 'w') as f:
                f.write(f"Test data for {filepath}\n")
        except Exception as e:
            sys.exit(1)

    return filepath


def delete_test_data(path: str, files: list[str] | str):
    """
    Delete files relative to path
    """

    if isinstance(files, str):
        file_list = [f"{files}"]
    else:
        file_list = files

    for filename in file_list:
        try:
            filename = filename.lstrip("/\\")
            filepath = os.path.join(path, filename)
            os.remove(filepath)
        except Exception as e:
            continue
    
    return filepath


def get_destination_path(path, base_path, root_destination_path):
    path = path.replace("\\", "/")
    # Return part after base_path
    # Or entire path if base_path not found
    try:
        index = path.index(base_path)
        return_path = path[index + len(base_path):]
    except ValueError:
        return_path = path

    if return_path.startswith("/"):
        return f"{root_destination_path}{return_path}"
    else:
        return f"{root_destination_path}/{return_path}"

