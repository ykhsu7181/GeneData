import json
import os
from collections import OrderedDict

from django.db.models import Q

from files.models import Accession, DataFile, FileRelation, Sample, Species
from files.services.data_overview_service import format_size


RAW_ROLE_TOKENS = ("raw", "reads", "fastq", "fq", "hifi", "ont", "hic")


def _params_get(params, key, default=""):
    value = params.get(key, default)
    return value.strip() if isinstance(value, str) else value


def _page_params(params):
    page = int(params.get("page", 1) or 1)
    page_size = int(params.get("page_size", 20) or 20)
    return max(page, 1), max(page_size, 1)


def _safe_json(raw):
    if not raw:
        return {}
    try:
        payload = json.loads(raw)
    except (TypeError, ValueError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _raw_meta(data_file):
    payload = _safe_json(data_file.description)
    raw_data = payload.get("raw_data", {})
    return raw_data if isinstance(raw_data, dict) else {}


def _is_raw_relation(relation):
    role = (relation.file_role or "").lower()
    name = (relation.file.file_name or "").lower()
    path = (relation.file.file_path or "").lower()
    return any(token in role or token in name or token in path for token in RAW_ROLE_TOKENS)


def _short_md5(md5):
    if not md5:
        return "-"
    if len(md5) <= 18:
        return md5
    return f"{md5[:8]}...{md5[-6:]}"


def _species_name(species):
    if not species:
        return "-"
    return species.chinese_name or species.common_name or species.scientific_name or species.species_code or "-"


def _latin_name(species):
    if not species:
        return "-"
    return species.scientific_name or species.common_name or species.species_code or "-"


def _infer_raw_data_type(data_file, meta, file_role):
    explicit = meta.get("raw_data_type")
    if explicit:
        return explicit
    value = " ".join([file_role or "", data_file.file_name or "", data_file.file_path or ""]).lower()
    if "rna" in value:
        return "RNA-seq"
    if "hifi" in value:
        return "HiFi"
    if "ont" in value:
        return "ONT"
    if "hic" in value or "hi-c" in value:
        return "Hi-C"
    if "wgs" in value or "resequencing" in value or "re-sequencing" in value:
        return "WGS"
    return "-"


def _infer_platform(meta, data_file):
    explicit = meta.get("sequencing_platform")
    if explicit:
        return explicit
    value = " ".join([data_file.file_name or "", data_file.file_path or ""]).lower()
    if "pacbio" in value or "hifi" in value:
        return "PacBio"
    if "nanopore" in value or "ont" in value:
        return "Nanopore"
    if "illumina" in value or "r1" in value or "r2" in value:
        return "Illumina"
    return "-"


def _infer_cluster(meta, file_path):
    explicit = meta.get("cluster_name")
    if explicit:
        return explicit
    lowered = (file_path or "").lower()
    for cluster in ("cluster01", "cluster02", "cluster03"):
        if cluster in lowered:
            return cluster
    return "-"


def _check_status(meta, data_file):
    explicit = meta.get("check_status")
    if explicit:
        return explicit
    if data_file.md5:
        return "verified"
    return "unchecked"


def _format_datetime(value):
    return value.strftime("%Y-%m-%d %H:%M") if value else "-"


def _row_from_bucket(file_id, bucket):
    data_file = bucket["file"]
    meta = _raw_meta(data_file)
    accession = bucket.get("accession") or (bucket.get("sample").accession if bucket.get("sample") else None)
    sample = bucket.get("sample")
    file_role = bucket.get("file_role") or "-"
    raw_data_type = _infer_raw_data_type(data_file, meta, file_role)
    sequencing_platform = _infer_platform(meta, data_file)
    cluster_name = _infer_cluster(meta, data_file.file_path)
    check_status = _check_status(meta, data_file)
    sample_code = meta.get("sample_code") or (sample.sample_code if sample else "-")
    species = accession.species if accession and accession.species else (sample.species if sample else None)

    return {
        "file_id": file_id,
        "accession": accession.accession if accession else "-",
        "accession_id": accession.id if accession else None,
        "sample_id": sample_code or "-",
        "species_id": species.id if species else None,
        "species_name": _species_name(species),
        "latin_name": _latin_name(species),
        "raw_data_type": raw_data_type,
        "sequencing_platform": sequencing_platform,
        "file_name": data_file.file_name or os.path.basename(data_file.file_path or "") or "-",
        "file_role": file_role,
        "cluster_name": cluster_name,
        "file_path": data_file.file_path or "-",
        "file_size": data_file.file_size,
        "file_size_display": format_size(data_file.file_size),
        "md5": data_file.md5 or "-",
        "md5_display": _short_md5(data_file.md5),
        "check_status": check_status,
        "updated_at": _format_datetime(data_file.updated_at),
        "created_at": _format_datetime(data_file.created_at),
        "remark": meta.get("remark") or "-",
    }


def _collect_rows():
    relations = (
        FileRelation.objects.select_related("file")
        .filter(file__isnull=False)
        .order_by("file_id", "related_type", "id")
    )
    buckets = OrderedDict()
    accession_ids = set()
    sample_ids = set()
    raw_relations = []

    for relation in relations:
        if not _is_raw_relation(relation):
            continue
        raw_relations.append(relation)
        bucket = buckets.setdefault(
            relation.file_id,
            {"file": relation.file, "relations": [], "file_role": relation.file_role},
        )
        bucket["relations"].append(relation)
        if relation.related_type == "accession":
            accession_ids.add(relation.related_id)
        elif relation.related_type == "sample":
            sample_ids.add(relation.related_id)

    accessions = {
        str(accession.id): accession
        for accession in Accession.objects.select_related("species").filter(id__in=accession_ids)
    }
    samples = {
        str(sample.id): sample
        for sample in Sample.objects.select_related("species", "accession", "accession__species").filter(id__in=sample_ids)
    }

    for bucket in buckets.values():
        for relation in bucket["relations"]:
            if relation.related_type == "accession" and relation.related_id in accessions:
                bucket["accession"] = accessions[relation.related_id]
            if relation.related_type == "sample" and relation.related_id in samples:
                bucket["sample"] = samples[relation.related_id]

    return [_row_from_bucket(file_id, bucket) for file_id, bucket in buckets.items()]


def _matches_keyword(row, keyword):
    if not keyword:
        return True
    haystack = " ".join(
        str(row.get(key) or "")
        for key in (
            "accession",
            "sample_id",
            "species_name",
            "latin_name",
            "raw_data_type",
            "sequencing_platform",
            "file_name",
            "file_role",
            "cluster_name",
            "file_path",
            "md5",
        )
    ).lower()
    return keyword.lower() in haystack


def _apply_filters(rows, params):
    keyword = _params_get(params, "keyword") or _params_get(params, "search")
    raw_data_type = _params_get(params, "raw_data_type")
    sequencing_platform = _params_get(params, "sequencing_platform")
    cluster = _params_get(params, "cluster")
    check_status = _params_get(params, "check_status")
    accession_id = _params_get(params, "accession_id")
    sample_id = _params_get(params, "sample_id")
    species_id = _params_get(params, "species_id")

    filtered = []
    for row in rows:
        if not _matches_keyword(row, keyword):
            continue
        if raw_data_type and row["raw_data_type"] != raw_data_type:
            continue
        if sequencing_platform and row["sequencing_platform"] != sequencing_platform:
            continue
        if cluster and row["cluster_name"] != cluster:
            continue
        if check_status and row["check_status"] != check_status:
            continue
        if accession_id and str(row.get("accession_id") or "") != str(accession_id):
            continue
        if sample_id and row.get("sample_id") != sample_id:
            continue
        if species_id and str(row.get("species_id") or "") != str(species_id):
            continue
        filtered.append(row)
    return filtered


def _summary(rows):
    accession_values = {row["accession"] for row in rows if row["accession"] and row["accession"] != "-"}
    sample_values = {row["sample_id"] for row in rows if row["sample_id"] and row["sample_id"] != "-"}
    cluster_values = {row["cluster_name"] for row in rows if row["cluster_name"] and row["cluster_name"] != "-"}
    total_size = sum(int(row["file_size"] or 0) for row in rows)
    latest = max((row["updated_at"] for row in rows if row["updated_at"] and row["updated_at"] != "-"), default="-")
    return {
        "accession_count": len(accession_values),
        "sample_count": len(sample_values),
        "datafile_count": len(rows),
        "raw_file_count": len(rows),
        "total_size": total_size,
        "total_size_display": format_size(total_size),
        "cluster_count": len(cluster_values),
        "latest_update": latest.split(" ")[0] if latest != "-" else "-",
    }


def _filters(rows):
    def unique_values(key):
        return sorted({row[key] for row in rows if row.get(key) and row[key] != "-"})

    return {
        "species": [
            {
                "key": species.id,
                "label": _species_name(species),
                "latin_name": _latin_name(species),
            }
            for species in Species.objects.order_by("species_code")
        ],
        "raw_data_types": unique_values("raw_data_type"),
        "sequencing_platforms": unique_values("sequencing_platform"),
        "clusters": unique_values("cluster_name"),
        "check_statuses": unique_values("check_status"),
    }


def build_raw_data_payload(params):
    page, page_size = _page_params(params)
    all_rows = _collect_rows()
    rows = _apply_filters(all_rows, params)
    total = len(rows)
    start = (page - 1) * page_size
    end = start + page_size
    return {
        "summary": _summary(rows),
        "filters": _filters(all_rows),
        "results": rows[start:end],
        "pagination": {
            "total": total,
            "page": page,
            "page_size": page_size,
            "next": f"?page={page + 1}&page_size={page_size}" if end < total else None,
            "previous": f"?page={page - 1}&page_size={page_size}" if page > 1 else None,
        },
    }
