"""Cortellis targets domain API functions."""



_BASE = "targets-v2"


def search(client, query, offset=0, hits=20, sort_by=None, sort_direction=None, filters_enabled=False):
    """Search targets. Example query: targetSynonyms:erbb"""
    params = {"query": query, "offset": offset, "hits": hits, "fmt": "json"}
    if sort_by:
        params["sortBy"] = sort_by
    if sort_direction:
        params["sortDirection"] = sort_direction
    if filters_enabled:
        params["filtersEnabled"] = "true"
    return client.get(f"{_BASE}/target/search", params=params)


def get_records(client, target_ids):
    """Batch get target records (up to 50 IDs)."""
    ids_str = ",".join(target_ids)
    return client.get(f"{_BASE}/targets", params={"idList": ids_str, "fmt": "json"})


def interactions(client, target_ids):
    """Get interactions for targets."""
    ids_str = ",".join(target_ids)
    return client.get(f"{_BASE}/target/interactions", params={"idList": ids_str, "fmt": "json"})


def sequences(client, target_ids):
    """Get sequences for targets."""
    ids_str = ",".join(target_ids)
    return client.get(f"{_BASE}/target/sequences", params={"idList": ids_str, "fmt": "json"})


def condition_drug_associations(client, target_ids):
    """Get drug-condition associations for targets."""
    ids_str = ",".join(target_ids)
    return client.get(f"{_BASE}/target/conditionDrugAssociations", params={"idList": ids_str, "fmt": "json"})


def condition_gene_associations(client, target_ids):
    """Get gene-condition associations for targets."""
    ids_str = ",".join(target_ids)
    return client.get(f"{_BASE}/target/conditionGeneAssociations", params={"idList": ids_str, "fmt": "json"})


def condition_gene_variant_associations(client, target_ids):
    """Get gene variant-condition associations for targets."""
    ids_str = ",".join(target_ids)
    return client.get(f"{_BASE}/target/conditionGeneVariantAssociations", params={"idList": ids_str, "fmt": "json"})


def get_drugs(client, drug_ids):
    """Get drug records in targets context (up to 25)."""
    ids_str = ",".join(drug_ids)
    return client.get(f"{_BASE}/drugs", params={"idList": ids_str, "fmt": "json"})


def get_trials(client, trial_ids):
    """Get trial records in targets context (up to 25)."""
    ids_str = ",".join(trial_ids)
    return client.get(f"{_BASE}/trials", params={"idList": ids_str, "fmt": "json"})


def get_patents(client, patent_ids):
    """Get patent records in targets context (up to 25)."""
    ids_str = ",".join(patent_ids)
    return client.get(f"{_BASE}/patents", params={"idList": ids_str, "fmt": "json"})


def get_references(client, reference_ids):
    """Get reference records in targets context (up to 25)."""
    ids_str = ",".join(reference_ids)
    return client.get(f"{_BASE}/references", params={"idList": ids_str, "fmt": "json"})
