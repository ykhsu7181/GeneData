import os


def datafile_download_url(file_id):
    if not file_id:
        return None
    return f"/gd/api/files/data-files/{file_id}/download/"


def adapt_annotation_file(service_file):
    file_path = service_file.get("file_path")
    is_new_relation = service_file.get("source") == "new_relation"
    download_url = datafile_download_url(service_file.get("file_id")) if is_new_relation else None
    return {
        "id": service_file.get("file_id"),
        "name": service_file.get("file_name"),
        "file_path": file_path,
        "category": service_file.get("file_role"),
        "file_size": service_file.get("file_size"),
        "source": service_file.get("source"),
        "datafile_download_url": download_url,
        "download_url": download_url,
    }


def adapt_overview_file(service_file):
    file_size = service_file.get("file_size")
    is_new_relation = service_file.get("source") == "new_relation"
    download_url = datafile_download_url(service_file.get("file_id")) if is_new_relation else None
    return {
        "id": service_file.get("file_id"),
        "name": service_file.get("file_name"),
        "file_path": service_file.get("file_path"),
        "category": service_file.get("file_role"),
        "size": file_size,
        "file_size": file_size,
        "created_at": None,
        "source": service_file.get("source"),
        "file_code": service_file.get("file_code"),
        "md5": service_file.get("md5"),
        "datafile_download_url": download_url,
        "download_url": download_url,
    }


def has_path_traversal(file_path):
    path_parts = file_path.replace("\\", os.sep).replace("/", os.sep).split(os.sep)
    return any(part == ".." for part in path_parts)
