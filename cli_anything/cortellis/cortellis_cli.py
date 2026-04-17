"""Cortellis CLI — Click command hierarchy with REPL entry point.

Entry point: cortellis
Root group: cortellis (with --json flag)

11 command groups:
  drugs, companies, deals, trials, regulations,
  conferences, literature, press-releases, ontology, analytics, ner
"""

import os
import sys

import click
from dotenv import load_dotenv

from cli_anything.cortellis import __version__
from cli_anything.cortellis.core.client import CortellisClient
from cli_anything.cortellis.utils.output import print_output

_BANNER = """
  ╔═════════════════════════════════════════════════════════════════════════════╗
  ║                                                                             ║
  ║    ██████╗ ██████╗ ██████╗ ████████╗███████╗██╗     ██╗     ██╗███████╗     ║
  ║   ██╔════╝██╔═══██╗██╔══██╗╚══██╔══╝██╔════╝██║     ██║     ██║██╔════╝     ║
  ║   ██║     ██║   ██║██████╔╝   ██║   █████╗  ██║     ██║     ██║███████╗     ║
  ║   ██║     ██║   ██║██╔══██╗   ██║   ██╔══╝  ██║     ██║     ██║╚════██║     ║
  ║   ╚██████╗╚██████╔╝██║  ██║   ██║   ███████╗███████╗███████╗██║███████║     ║
  ║    ╚═════╝ ╚═════╝ ╚═╝  ╚═╝   ╚═╝   ╚══════╝╚══════╝╚══════╝╚═╝╚══════╝     ║
  ║                                                                             ║
  ║            P h a r m a c e u t i c a l   I n t e l l i g e n c e            ║
  ║                              CLI  v{version:<6s}                                   ║
  ╚═════════════════════════════════════════════════════════════════════════════╝
""".format(version=__version__)

# Domain imports — populated by parallel workers
from cli_anything.cortellis.core import (
    drugs as _drugs,
    companies as _companies,
    deals as _deals,
    trials as _trials,
    regulatory as _regulatory,
    ontology as _ontology,
    analytics as _analytics,
    literature as _literature,
    conferences as _conferences,
    press_releases as _press_releases,
    ner as _ner,
    company_analytics as _company_analytics,
    deals_intelligence as _deals_intelligence,
    drug_design as _drug_design,
    targets as _targets,
)

load_dotenv()


# ---------------------------------------------------------------------------
# Root group
# ---------------------------------------------------------------------------

@click.group(invoke_without_command=True)
@click.option("--json", "json_mode", is_flag=True, default=False,
              help="Output raw JSON instead of formatted tables.")
@click.option("--debug", is_flag=True, default=False,
              help="Show API commands being executed in chat mode.")
@click.option("--engine", default="claude",
              type=click.Choice(["claude", "codex"], case_sensitive=False),
              help="AI engine for chat mode: 'claude' (Claude Code) or 'codex' (OpenAI Codex).")
@click.option("--no-flush", "no_flush", is_flag=True, default=False,
              help="Skip session memory flush on exit (useful for testing).")
@click.version_option(__version__, prog_name="cortellis")
@click.pass_context
def cli(ctx: click.Context, json_mode: bool, debug: bool, engine: str, no_flush: bool) -> None:
    """Cortellis pharmaceutical intelligence CLI."""
    ctx.ensure_object(dict)
    ctx.obj["json"] = json_mode
    ctx.obj["client"] = CortellisClient()

    if ctx.invoked_subcommand is None:
        # No subcommand — launch AI chat mode
        ctx.invoke(chat_cmd, debug=debug, engine=engine, no_flush=no_flush)


def _client(ctx: click.Context) -> CortellisClient:
    return ctx.obj["client"]


# ---------------------------------------------------------------------------
# config — interactive credential setup
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# drugs
# ---------------------------------------------------------------------------

@cli.group()
@click.pass_context
def drugs(ctx: click.Context) -> None:
    """Drug intelligence commands."""


@drugs.command("search")
@click.option("--query", default=None, help="Raw Cortellis query string.")
@click.option("--company", default=None)
@click.option("--indication", default=None)
@click.option("--action", default=None)
@click.option("--phase", default=None, help="Development phase (e.g. L, 1, 2, 3).")
@click.option("--technology", default=None)
@click.option("--drug-name", default=None)
@click.option("--country", default=None)
@click.option("--offset", default=0, show_default=True)
@click.option("--hits", default=10, show_default=True)
@click.option("--sort-by", default=None)
@click.option("--historic", is_flag=True, default=False,
              help="Use historic development status fields.")
@click.option("--status-date", default=None, help="Filter by status date (YYYY-MM-DD).")
@click.option("--phase-terminated", default=None, help="Filter by terminated phase.")
@click.option("--phase-highest", is_flag=True, default=False,
              help="Use phaseHighest field instead of LINKED phase (matches drugs where this IS the highest phase).")
@click.option("--return-filter-count", is_flag=True, default=False, help="Return filter counts in the response.")
@click.pass_context
def drugs_search(ctx, query, company, indication, action, phase, technology,
                 drug_name, country, offset, hits, sort_by, historic, status_date,
                 phase_terminated, phase_highest, return_filter_count):
    """Search the drug database."""
    data = _drugs.search(
        _client(ctx),
        query=query,
        company=company,
        indication=indication,
        action=action,
        phase=phase,
        technology=technology,
        drug_name=drug_name,
        country=country,
        offset=offset,
        hits=hits,
        sort_by=sort_by,
        historic=historic,
        status_date=status_date,
        phase_terminated=phase_terminated,
        phase_highest=phase_highest,
        return_filter_count=return_filter_count if return_filter_count else None,
    )
    print_output(ctx, data)


@drugs.command("get")
@click.argument("drug_id")
@click.option("--category", default=None,
              type=click.Choice(["report", "swot", "financial"]),
              help="Report category to fetch.")
@click.option("--include-sources", is_flag=True, default=False, help="Include source documents.")
@click.pass_context
def drugs_get(ctx, drug_id, category, include_sources):
    """Get a drug record by ID."""
    data = _drugs.get(_client(ctx), drug_id, category=category, include_sources=include_sources)
    print_output(ctx, data)


@drugs.command("records")
@click.argument("ids", nargs=-1, required=True)
@click.pass_context
def drugs_records(ctx, ids):
    """Batch get multiple drug records by ID."""
    data = _drugs.records(_client(ctx), list(ids))
    print_output(ctx, data)


@drugs.command("history")
@click.argument("drug_id")
@click.pass_context
def drugs_history(ctx, drug_id):
    """Get development status change history for a drug."""
    data = _drugs.change_history(_client(ctx), drug_id)
    print_output(ctx, data)


@drugs.command("autocomplete")
@click.argument("query")
@click.option("--hits", default=10, show_default=True,
              help="Number of suggestions to return.")
@click.pass_context
def drugs_autocomplete(ctx, query, hits):
    """Typeahead autocomplete suggestions for drug names."""
    data = _drugs.autocomplete(_client(ctx), query, hits=hits)
    print_output(ctx, data)


@drugs.command("ci-matrix")
@click.option("--query", required=True, help="Query for CI matrix.")
@click.option("--offset", default=0, show_default=True)
@click.option("--hits", default=20, show_default=True)
@click.pass_context
def drugs_ci_matrix(ctx, query, offset, hits):
    """Fetch competitive intelligence matrix for drugs."""
    data = _drugs.ci_matrix(_client(ctx), query, offset=offset, hits=hits)
    print_output(ctx, data)


@drugs.command("molfile")
@click.argument("drug_id")
@click.pass_context
def drugs_molfile(ctx, drug_id):
    """Get MOL file (chemical structure) for a drug."""
    text = _drugs.get_molfile(_client(ctx), drug_id)
    click.echo(text)


@drugs.command("structure-image")
@click.argument("drug_id")
@click.option("--format", "fmt", default="png", type=click.Choice(["png", "svg"]), show_default=True)
@click.option("--width", default=300, show_default=True)
@click.option("--height", default=300, show_default=True)
@click.option("--output", "output_file", default=None, help="Output file path (default: <drug_id>.<format>).")
@click.pass_context
def drugs_structure_image(ctx, drug_id, fmt, width, height, output_file):
    """Download structure image for a drug."""
    data = _drugs.get_structure_image(_client(ctx), drug_id, fmt=fmt, width=width, height=height)
    if not output_file:
        output_file = f"{drug_id}.{fmt}"
    with open(output_file, "wb") as f:
        f.write(data)
    click.echo(f"Saved to {output_file} ({len(data)} bytes)")


@drugs.command("structure-search")
@click.option("--smiles", required=True, help="SMILES string for structure search.")
@click.option("--type", "search_type", default="substructure", type=click.Choice(["substructure", "similarity", "exact"]), show_default=True)
@click.option("--offset", default=0, show_default=True)
@click.option("--hits", default=20, show_default=True)
@click.pass_context
def drugs_structure_search(ctx, smiles, search_type, offset, hits):
    """Search drugs by chemical structure (SMILES)."""
    data = _drugs.structure_search(_client(ctx), smiles=smiles, search_type=search_type, offset=offset, hits=hits)
    print_output(ctx, data)


@drugs.command("sources")
@click.argument("drug_id")
@click.pass_context
def drugs_sources(ctx, drug_id):
    """Get source documents for a drug."""
    data = _drugs.sources(_client(ctx), drug_id)
    print_output(ctx, data)


@drugs.command("batch-sources")
@click.argument("ids", nargs=-1, required=True)
@click.pass_context
def drugs_batch_sources(ctx, ids):
    """Batch get source documents for multiple drugs."""
    data = _drugs.batch_sources(_client(ctx), list(ids))
    print_output(ctx, data)


@drugs.command("financials")
@click.argument("drug_id")
@click.option("--csv", "as_csv", is_flag=True, default=False, help="Output as CSV instead of JSON.")
@click.pass_context
def drugs_financials(ctx, drug_id, as_csv):
    """Get financial data (sales & forecasts) for a drug."""
    if as_csv:
        text = _drugs.financials_csv(_client(ctx), drug_id)
        click.echo(text)
    else:
        data = _drugs.financials(_client(ctx), drug_id)
        print_output(ctx, data)


@drugs.command("swots")
@click.argument("drug_id")
@click.pass_context
def drugs_swots(ctx, drug_id):
    """Get SWOT analysis for a drug."""
    data = _drugs.swots(_client(ctx), drug_id)
    print_output(ctx, data)


@drugs.command("companies-by-taxonomy")
@click.option("--type", "taxonomy_type", required=True,
              type=click.Choice(["indication", "action", "technology", "all_action"]))
@click.option("--tree-code", required=True, help="Taxonomy tree code (e.g. CAR- for cardiovascular).")
@click.pass_context
def drugs_companies_by_taxonomy(ctx, taxonomy_type, tree_code):
    """Get companies linked to a taxonomy term."""
    data = _drugs.companies_linked_to_taxonomy(_client(ctx), taxonomy_type, tree_code)
    print_output(ctx, data)


# ---------------------------------------------------------------------------
# companies
# ---------------------------------------------------------------------------

@cli.group()
@click.pass_context
def companies(ctx: click.Context) -> None:
    """Company intelligence commands."""


@companies.command("search")
@click.option("--query", default=None)
@click.option("--name", default=None)
@click.option("--country", default=None)
@click.option("--size", default=None)
@click.option("--deals-count", default=None)
@click.option("--indications", default=None)
@click.option("--actions", default=None)
@click.option("--technologies", default=None)
@click.option("--status", default=None)
@click.option("--offset", default=0, show_default=True)
@click.option("--hits", default=10, show_default=True)
@click.option("--sort-by", default=None)
@click.pass_context
def companies_search(ctx, query, name, country, size, deals_count, indications,
                     actions, technologies, status, offset, hits, sort_by):
    """Search companies."""
    data = _companies.search(
        _client(ctx),
        query=query,
        name=name,
        country=country,
        size=size,
        deals_count=deals_count,
        indications=indications,
        actions=actions,
        technologies=technologies,
        status=status,
        offset=offset,
        hits=hits,
        sort_by=sort_by,
    )
    print_output(ctx, data)


@companies.command("get")
@click.argument("company_id")
@click.pass_context
def companies_get(ctx, company_id):
    """Get a company record by ID."""
    data = _companies.get(_client(ctx), company_id)
    print_output(ctx, data)


@companies.command("records")
@click.argument("ids", nargs=-1, required=True)
@click.pass_context
def companies_records(ctx, ids):
    """Batch get multiple company records by ID."""
    data = _companies.records(_client(ctx), list(ids))
    print_output(ctx, data)


@companies.command("sources")
@click.argument("company_id")
@click.pass_context
def companies_sources(ctx, company_id):
    """Get source documents for a company."""
    data = _companies.sources(_client(ctx), company_id)
    print_output(ctx, data)


# ---------------------------------------------------------------------------
# deals
# ---------------------------------------------------------------------------

@cli.group()
@click.pass_context
def deals(ctx: click.Context) -> None:
    """Deal intelligence commands."""


@deals.command("search")
@click.option("--query", default=None)
@click.option("--drug", default=None)
@click.option("--indication", default=None)
@click.option("--type", "--deal-type", "deal_type", default=None)
@click.option("--status", default=None)
@click.option("--principal", default=None)
@click.option("--partner", default=None)
@click.option("--action", default=None)
@click.option("--date-start", default=None, help="Deal date range start (YYYY-MM-DD).")
@click.option("--date-end", default=None, help="Deal date range end (YYYY-MM-DD).")
@click.option("--offset", default=0, show_default=True)
@click.option("--hits", default=10, show_default=True)
@click.option("--sort-by", default=None)
@click.option("--indication-partner-company", default=None)
@click.option("--phase-start", default=None)
@click.option("--phase-now", default=None)
@click.option("--deal-status", default=None)
@click.option("--summary", default=None)
@click.option("--title-summary", default=None)
@click.option("--technology", default=None)
@click.option("--title", default=None)
@click.option("--actions-primary", default=None)
@click.option("--principal-hq", default=None)
@click.option("--territories-included", default=None)
@click.option("--territories-excluded", default=None)
@click.option("--date-most-recent", default=None)
@click.option("--max-value-paid-to-partner", default=None)
@click.option("--total-projected-current-amount", default=None)
@click.option("--min-value-paid-to-partner", default=None)
@click.option("--total-paid-amount", default=None)
@click.option("--disclosure-status", default=None)
@click.pass_context
def deals_search(ctx, query, drug, indication, deal_type, status, principal,
                 partner, action, date_start, date_end, offset, hits, sort_by,
                 indication_partner_company, phase_start, phase_now, deal_status,
                 summary, title_summary, technology, title, actions_primary,
                 principal_hq, territories_included, territories_excluded,
                 date_most_recent, max_value_paid_to_partner,
                 total_projected_current_amount, min_value_paid_to_partner,
                 total_paid_amount, disclosure_status):
    """Search deals."""
    data = _deals.search(
        _client(ctx),
        query=query,
        drug=drug,
        indication=indication,
        deal_type=deal_type,
        status=status,
        principal=principal,
        partner=partner,
        action=action,
        date_start=date_start,
        date_end=date_end,
        offset=offset,
        hits=hits,
        sort_by=sort_by,
        indication_partner_company=indication_partner_company,
        phase_start=phase_start,
        phase_now=phase_now,
        deal_status=deal_status,
        summary=summary,
        title_summary=title_summary,
        technology=technology,
        title=title,
        actions_primary=actions_primary,
        principal_hq=principal_hq,
        territories_included=territories_included,
        territories_excluded=territories_excluded,
        date_most_recent=date_most_recent,
        max_value_paid_to_partner=max_value_paid_to_partner,
        total_projected_current_amount=total_projected_current_amount,
        min_value_paid_to_partner=min_value_paid_to_partner,
        total_paid_amount=total_paid_amount,
        disclosure_status=disclosure_status,
    )
    print_output(ctx, data)


@deals.command("get")
@click.argument("deal_id")
@click.option("--category", default=None,
              type=click.Choice(["basic", "expanded"]))
@click.pass_context
def deals_get(ctx, deal_id, category):
    """Get a deal record by ID."""
    data = _deals.get(_client(ctx), deal_id, category=category)
    print_output(ctx, data)


@deals.command("records")
@click.argument("ids", nargs=-1, required=True)
@click.pass_context
def deals_records(ctx, ids):
    """Batch get multiple deal records by ID."""
    data = _deals.records(_client(ctx), list(ids))
    print_output(ctx, data)


@deals.command("sources")
@click.argument("deal_id")
@click.pass_context
def deals_sources(ctx, deal_id):
    """Get source documents for a deal."""
    data = _deals.sources(_client(ctx), deal_id)
    print_output(ctx, data)


# ---------------------------------------------------------------------------
# trials
# ---------------------------------------------------------------------------

@cli.group()
@click.pass_context
def trials(ctx: click.Context) -> None:
    """Clinical trial commands."""


@trials.command("search")
@click.option("--query", default=None)
@click.option("--indication", default=None)
@click.option("--phase", default=None)
@click.option("--recruitment-status", default=None, help="Recruitment status filter.")
@click.option("--status", default=None, help="Alias for --recruitment-status (backward compat).")
@click.option("--sponsor", default=None)
@click.option("--funder-type", default=None)
@click.option("--enrollment", default=None)
@click.option("--date-start", default=None)
@click.option("--date-end", default=None)
@click.option("--identifier", default=None)
@click.option("--title", default=None, help="Trial title filter.")
@click.option("--offset", default=0, show_default=True)
@click.option("--hits", default=10, show_default=True)
@click.option("--sort-by", default=None)
@click.pass_context
def trials_search(ctx, query, indication, phase, recruitment_status, status,
                  sponsor, funder_type, enrollment, date_start, date_end,
                  identifier, title, offset, hits, sort_by):
    """Search clinical trials."""
    data = _trials.search(
        _client(ctx),
        query=query,
        indication=indication,
        phase=phase,
        recruitment_status=recruitment_status,
        status=status,
        sponsor=sponsor,
        funder_type=funder_type,
        enrollment=enrollment,
        date_start=date_start,
        date_end=date_end,
        identifier=identifier,
        title=title,
        offset=offset,
        hits=hits,
        sort_by=sort_by,
    )
    print_output(ctx, data)


@trials.command("get")
@click.argument("trial_id")
@click.option("--category", default=None,
              type=click.Choice(["report", "sites"]))
@click.pass_context
def trials_get(ctx, trial_id, category):
    """Get a clinical trial by ID."""
    data = _trials.get(_client(ctx), trial_id, category=category)
    print_output(ctx, data)


@trials.command("records")
@click.argument("ids", nargs=-1, required=True)
@click.pass_context
def trials_records(ctx, ids):
    """Batch get multiple trial records by ID."""
    data = _trials.records(_client(ctx), list(ids))
    print_output(ctx, data)


@trials.command("sources")
@click.argument("trial_id")
@click.pass_context
def trials_sources(ctx, trial_id):
    """Get source documents for a clinical trial."""
    data = _trials.sources(_client(ctx), trial_id)
    print_output(ctx, data)


@trials.command("id-mappings")
@click.option("--entity-type", required=True, help="Entity type (e.g. Disease, Drug).")
@click.option("--id-type", required=True, help="Source ID type (e.g. ICD9, ICD10, MeSH).")
@click.option("--ids", required=True, help="Comma-separated IDs to map.")
@click.pass_context
def trials_id_mappings(ctx, entity_type, id_type, ids):
    """Fetch ID mappings for a trial entity type."""
    data = _trials.id_mappings(_client(ctx), entity_type=entity_type, id_type=id_type, ids=ids)
    print_output(ctx, data)


# ---------------------------------------------------------------------------
# regulations
# ---------------------------------------------------------------------------

@cli.group()
@click.pass_context
def regulations(ctx: click.Context) -> None:
    """Regulatory document commands."""


@regulations.command("search")
@click.option("--query", default=None)
@click.option("--region", default=None)
@click.option("--doc-category", default=None)
@click.option("--doc-type", default=None)
@click.option("--language", default=None)
@click.option("--product-category", default=None, help="Product category filter.")
@click.option("--include-outdated", is_flag=True, default=False,
              help="Include outdated/superseded documents.")
@click.option("--filters-enabled", is_flag=True, default=False,
              help="Enable facet filters in response.")
@click.option("--filter-count", is_flag=True, default=False,
              help="Return filter counts in response.")
@click.option("--offset", default=0, show_default=True)
@click.option("--hits", default=10, show_default=True)
@click.option("--sort-by", default=None)
@click.pass_context
def regulations_search(ctx, query, region, doc_category, doc_type, language,
                       product_category, include_outdated, filters_enabled,
                       filter_count, offset, hits, sort_by):
    """Search regulatory documents."""
    data = _regulatory.search(
        _client(ctx),
        query=query,
        region=region,
        doc_category=doc_category,
        doc_type=doc_type,
        language=language,
        prod_category=product_category,
        include_outdated=include_outdated,
        filters_enabled=filters_enabled,
        filter_count=filter_count,
        offset=offset,
        hits=hits,
        sort_by=sort_by,
    )
    print_output(ctx, data)


@regulations.command("get")
@click.argument("regulation_id")
@click.option("--category", default=None,
              type=click.Choice(["metadata", "source"]))
@click.pass_context
def regulations_get(ctx, regulation_id, category):
    """Get a regulatory document by ID."""
    data = _regulatory.get(_client(ctx), regulation_id, category=category)
    print_output(ctx, data)


@regulations.command("snapshot")
@click.argument("regulation_id")
@click.pass_context
def regulations_snapshot(ctx, regulation_id):
    """Get a snapshot of a regulatory document."""
    data = _regulatory.snapshot(_client(ctx), regulation_id)
    print_output(ctx, data)


@regulations.command("cited-documents")
@click.argument("regulation_id")
@click.pass_context
def regulations_cited_documents(ctx, regulation_id):
    """Get documents cited by a regulatory document."""
    data = _regulatory.cited_documents(_client(ctx), regulation_id)
    print_output(ctx, data)


@regulations.command("cited-by")
@click.argument("regulation_id")
@click.pass_context
def regulations_cited_by(ctx, regulation_id):
    """Get documents that cite a regulatory document."""
    data = _regulatory.cited_by(_client(ctx), regulation_id)
    print_output(ctx, data)


@regulations.command("grc-reports")
@click.pass_context
def regulations_grc_reports(ctx):
    """List available Global Regulatory Comparison reports."""
    data = _regulatory.grc_reports(_client(ctx))
    print_output(ctx, data)


@regulations.command("grc")
@click.argument("report_id")
@click.option("--fmt", default="json", type=click.Choice(["json", "csv"]), show_default=True)
@click.pass_context
def regulations_grc(ctx, report_id, fmt):
    """Get a specific Global Regulatory Comparison report."""
    data = _regulatory.grc(_client(ctx), report_id, fmt=fmt)
    print_output(ctx, data)


@regulations.command("grc-list")
@click.argument("report_id")
@click.pass_context
def regulations_grc_list(ctx, report_id):
    """Get list of items in a GRC report."""
    data = _regulatory.grc_list(_client(ctx), report_id)
    print_output(ctx, data)


@regulations.command("regions-entitled")
@click.pass_context
def regulations_regions_entitled(ctx):
    """Get regions the user is entitled to access."""
    data = _regulatory.regions_entitled(_client(ctx))
    print_output(ctx, data)


@regulations.command("db-rir")
@click.pass_context
def regulations_db_rir(ctx):
    """List Regulatory Intelligence Reports hierarchy (Drugs & Biologics)."""
    data = _regulatory.db_rir(_client(ctx))
    print_output(ctx, data)


@regulations.command("db-rs")
@click.pass_context
def regulations_db_rs(ctx):
    """List Regulatory Summaries hierarchy (Drugs & Biologics)."""
    data = _regulatory.db_rs(_client(ctx))
    print_output(ctx, data)


# ---------------------------------------------------------------------------
# conferences
# ---------------------------------------------------------------------------

@cli.group()
@click.pass_context
def conferences(ctx: click.Context) -> None:
    """Conference commands."""


@conferences.command("search")
@click.option("--query", default=None)
@click.option("--offset", default=0, show_default=True)
@click.option("--hits", default=10, show_default=True)
@click.option("--sort-by", default=None)
@click.option("--filters-enabled", is_flag=True, default=False,
              help="Enable facet filters in response.")
@click.option("--filter-count", is_flag=True, default=False,
              help="Return filter counts in response.")
@click.pass_context
def conferences_search(ctx, query, offset, hits, sort_by, filters_enabled, filter_count):
    """Search conferences."""
    data = _conferences.search(
        _client(ctx), query=query, offset=offset, hits=hits, sort_by=sort_by,
        filters_enabled=filters_enabled, filter_count=filter_count,
    )
    print_output(ctx, data)


@conferences.command("get")
@click.argument("conference_id")
@click.pass_context
def conferences_get(ctx, conference_id):
    """Get a conference by ID."""
    data = _conferences.get(_client(ctx), conference_id)
    print_output(ctx, data)


# ---------------------------------------------------------------------------
# literature
# ---------------------------------------------------------------------------

@cli.group()
@click.pass_context
def literature(ctx: click.Context) -> None:
    """Literature commands."""


@literature.command("search")
@click.option("--query", default=None)
@click.option("--offset", default=0, show_default=True)
@click.option("--hits", default=10, show_default=True)
@click.option("--sort-by", default=None)
@click.option("--filters-enabled", is_flag=True, default=False,
              help="Enable facet filters in response.")
@click.option("--filter-count", is_flag=True, default=False,
              help="Return filter counts in response.")
@click.pass_context
def literature_search(ctx, query, offset, hits, sort_by, filters_enabled, filter_count):
    """Search literature."""
    data = _literature.search(
        _client(ctx), query=query, offset=offset, hits=hits, sort_by=sort_by,
        filters_enabled=filters_enabled, filter_count=filter_count,
    )
    print_output(ctx, data)


@literature.command("get")
@click.argument("literature_id")
@click.pass_context
def literature_get(ctx, literature_id):
    """Get a literature record by ID."""
    data = _literature.get(_client(ctx), literature_id)
    print_output(ctx, data)


@literature.command("records")
@click.argument("ids", nargs=-1, required=True)
@click.pass_context
def literature_records(ctx, ids):
    """Batch get multiple literature records by ID."""
    data = _literature.records(_client(ctx), list(ids))
    print_output(ctx, data)


@literature.command("molfile")
@click.argument("literature_id")
@click.pass_context
def literature_molfile(ctx, literature_id):
    """Get MOL file (chemical structure) for a literature record."""
    text = _literature.get_molfile(_client(ctx), literature_id)
    click.echo(text)


@literature.command("structure-image")
@click.argument("literature_id")
@click.option("--format", "fmt", default="png", type=click.Choice(["png", "svg"]), show_default=True)
@click.option("--width", default=300, show_default=True)
@click.option("--height", default=300, show_default=True)
@click.option("--output", "output_file", default=None, help="Output file path (default: <id>.<format>).")
@click.pass_context
def literature_structure_image(ctx, literature_id, fmt, width, height, output_file):
    """Download structure image for a literature record."""
    data = _literature.get_structure_image(_client(ctx), literature_id, fmt=fmt, width=width, height=height)
    if not output_file:
        output_file = f"{literature_id}.{fmt}"
    with open(output_file, "wb") as f:
        f.write(data)
    click.echo(f"Saved to {output_file} ({len(data)} bytes)")


@literature.command("structure-search")
@click.option("--smiles", required=True, help="SMILES string for structure search.")
@click.option("--type", "search_type", default="substructure", type=click.Choice(["substructure", "similarity", "exact"]), show_default=True)
@click.option("--offset", default=0, show_default=True)
@click.option("--hits", default=20, show_default=True)
@click.pass_context
def literature_structure_search(ctx, smiles, search_type, offset, hits):
    """Search literature by chemical structure (SMILES)."""
    data = _literature.structure_search(_client(ctx), smiles=smiles, search_type=search_type, offset=offset, hits=hits)
    print_output(ctx, data)


# ---------------------------------------------------------------------------
# press-releases
# ---------------------------------------------------------------------------

@cli.group(name="press-releases")
@click.pass_context
def press_releases(ctx: click.Context) -> None:
    """Press release commands."""


@press_releases.command("search")
@click.option("--query", default=None)
@click.option("--offset", default=0, show_default=True)
@click.option("--hits", default=10, show_default=True)
@click.option("--sort-by", default=None)
@click.option("--filters-enabled", is_flag=True, default=False,
              help="Enable facet filters in response.")
@click.option("--filter-count", is_flag=True, default=False,
              help="Return filter counts in response.")
@click.pass_context
def press_releases_search(ctx, query, offset, hits, sort_by, filters_enabled, filter_count):
    """Search press releases."""
    data = _press_releases.search(
        _client(ctx), query=query, offset=offset, hits=hits, sort_by=sort_by,
        filters_enabled=filters_enabled, filter_count=filter_count,
    )
    print_output(ctx, data)


@press_releases.command("get")
@click.argument("id_list", nargs=-1, required=True)
@click.pass_context
def press_releases_get(ctx, id_list):
    """Get press releases by ID list."""
    data = _press_releases.get(_client(ctx), list(id_list))
    print_output(ctx, data)


# ---------------------------------------------------------------------------
# ontology
# ---------------------------------------------------------------------------

@cli.group()
@click.pass_context
def ontology(ctx: click.Context) -> None:
    """Ontology commands."""


@ontology.command("search")
@click.option("--term", required=True, help="Search term (e.g. 'obesity').")
@click.option("--category", required=True, help="Ontology category (e.g. indication, action, technology).")
@click.pass_context
def ontology_search(ctx, term, category):
    """Search the taxonomy for a term within a category."""
    data = _ontology.search(_client(ctx), category=category, term=term)
    print_output(ctx, data)


@ontology.command("top-level")
@click.option("--category", default=None)
@click.option("--counts", is_flag=True, default=False)
@click.option("--dataset", default=None)
@click.pass_context
def ontology_top_level(ctx, category, counts, dataset):
    """List top-level ontology nodes."""
    data = _ontology.top_level(_client(ctx), category=category, counts=counts, dataset=dataset)
    print_output(ctx, data)


@ontology.command("children")
@click.option("--category", required=True)
@click.option("--tree-code", required=True)
@click.option("--counts", is_flag=True, default=False)
@click.option("--dataset", default=None)
@click.pass_context
def ontology_children(ctx, category, tree_code, counts, dataset):
    """List child nodes for a tree code."""
    data = _ontology.children(
        _client(ctx), category=category, tree_code=tree_code, counts=counts, dataset=dataset
    )
    print_output(ctx, data)


@ontology.command("parents")
@click.option("--category", required=True)
@click.option("--tree-code", required=True)
@click.pass_context
def ontology_parents(ctx, category, tree_code):
    """List parent nodes for a tree code."""
    data = _ontology.parents(_client(ctx), category=category, tree_code=tree_code)
    print_output(ctx, data)


@ontology.command("synonyms")
@click.option("--category", required=True, help="Ontology category (e.g. indication).")
@click.option("--term", required=True, help="Term to look up synonyms for.")
@click.pass_context
def ontology_synonyms(ctx, category, term):
    """Fetch synonyms for a term in a taxonomy category."""
    data = _ontology.synonyms(_client(ctx), category=category, term=term)
    print_output(ctx, data)


@ontology.command("synonyms-by-id")
@click.option("--category", required=True, help="Ontology category (e.g. drug, action, indication).")
@click.option("--id", "node_id", required=True, help="Taxonomy node numeric identifier.")
@click.option("--id-type", default="idapi", show_default=True, help="ID type system (e.g. idapi, ddapi).")
@click.pass_context
def ontology_synonyms_by_id(ctx, category, node_id, id_type):
    """Fetch synonyms for a taxonomy node by numeric ID."""
    data = _ontology.synonyms_by_id(_client(ctx), category=category, id=node_id, id_type=id_type)
    print_output(ctx, data)


@ontology.command("id-map")
@click.option("--entity-type", required=True, help="Entity type (e.g. drug, company, disease, target, action).")
@click.option("--id-type", required=True, help="Source ID type (e.g. idapi, ddapi, companyId, ciIndication).")
@click.option("--ids", required=True, help="Comma-separated IDs to map.")
@click.pass_context
def ontology_id_map(ctx, entity_type, id_type, ids):
    """Map IDs for a given entity type between ID systems."""
    data = _ontology.id_map(_client(ctx), entity_type=entity_type, id_type=id_type, ids=ids)
    print_output(ctx, data)


@ontology.command("summary")
@click.option("--type", "summary_type", required=True,
              type=click.Choice([
                  "drug", "company", "indication", "action", "trial", "deal",
                  "patent", "journal", "meeting", "regulatory", "diseaseBriefing",
                  "patentFamily", "source", "eventTranscript",
              ]),
              help="Entity type.")
@click.option("--id", "entity_id", required=True, help="Entity identifier.")
@click.pass_context
def ontology_summary(ctx, summary_type, entity_id):
    """Fetch an ontology summary for an entity."""
    data = _ontology.summary(_client(ctx), summary_type=summary_type, id=entity_id)
    print_output(ctx, data)


# ---------------------------------------------------------------------------
# targets
# ---------------------------------------------------------------------------

@cli.group()
@click.pass_context
def targets(ctx):
    """Target intelligence commands."""


@targets.command("search")
@click.option("--query", required=True)
@click.option("--offset", default=0, show_default=True)
@click.option("--hits", default=20, show_default=True)
@click.option("--sort-by", default=None)
@click.option("--sort-direction", default=None, type=click.Choice(["ascending", "descending"]))
@click.option("--filters-enabled", is_flag=True, default=False)
@click.pass_context
def targets_search(ctx, query, offset, hits, sort_by, sort_direction, filters_enabled):
    """Search targets."""
    data = _targets.search(_client(ctx), query, offset=offset, hits=hits, sort_by=sort_by, sort_direction=sort_direction, filters_enabled=filters_enabled)
    print_output(ctx, data)


@targets.command("records")
@click.argument("ids", nargs=-1, required=True)
@click.pass_context
def targets_records(ctx, ids):
    """Batch get target records (up to 50 IDs)."""
    data = _targets.get_records(_client(ctx), list(ids))
    print_output(ctx, data)


@targets.command("interactions")
@click.argument("ids", nargs=-1, required=True)
@click.pass_context
def targets_interactions(ctx, ids):
    """Get interactions for targets."""
    data = _targets.interactions(_client(ctx), list(ids))
    print_output(ctx, data)


@targets.command("sequences")
@click.argument("ids", nargs=-1, required=True)
@click.pass_context
def targets_sequences(ctx, ids):
    """Get sequences for targets."""
    data = _targets.sequences(_client(ctx), list(ids))
    print_output(ctx, data)


@targets.command("condition-drugs")
@click.argument("ids", nargs=-1, required=True)
@click.pass_context
def targets_condition_drugs(ctx, ids):
    """Get drug-condition associations for targets."""
    data = _targets.condition_drug_associations(_client(ctx), list(ids))
    print_output(ctx, data)


@targets.command("condition-genes")
@click.argument("ids", nargs=-1, required=True)
@click.pass_context
def targets_condition_genes(ctx, ids):
    """Get gene-condition associations for targets."""
    data = _targets.condition_gene_associations(_client(ctx), list(ids))
    print_output(ctx, data)


@targets.command("condition-variants")
@click.argument("ids", nargs=-1, required=True)
@click.pass_context
def targets_condition_variants(ctx, ids):
    """Get gene variant-condition associations for targets."""
    data = _targets.condition_gene_variant_associations(_client(ctx), list(ids))
    print_output(ctx, data)


@targets.command("drugs")
@click.argument("ids", nargs=-1, required=True)
@click.pass_context
def targets_drugs(ctx, ids):
    """Get drug records in targets context (up to 25)."""
    data = _targets.get_drugs(_client(ctx), list(ids))
    print_output(ctx, data)


@targets.command("trials")
@click.argument("ids", nargs=-1, required=True)
@click.pass_context
def targets_trials(ctx, ids):
    """Get trial records in targets context (up to 25)."""
    data = _targets.get_trials(_client(ctx), list(ids))
    print_output(ctx, data)


@targets.command("patents")
@click.argument("ids", nargs=-1, required=True)
@click.pass_context
def targets_patents(ctx, ids):
    """Get patent records in targets context (up to 25)."""
    data = _targets.get_patents(_client(ctx), list(ids))
    print_output(ctx, data)


@targets.command("references")
@click.argument("ids", nargs=-1, required=True)
@click.pass_context
def targets_references(ctx, ids):
    """Get reference records in targets context (up to 25)."""
    data = _targets.get_references(_client(ctx), list(ids))
    print_output(ctx, data)


# ---------------------------------------------------------------------------
# analytics
# ---------------------------------------------------------------------------

@cli.group()
@click.pass_context
def analytics(ctx: click.Context) -> None:
    """Analytics query commands."""


@analytics.command("run")
@click.argument("query_name")
@click.option("--drug-id", default=None)
@click.option("--indication-id", default=None)
@click.option("--action-id", default=None)
@click.option("--company-id", default=None)
@click.option("--trial-id", default=None)
@click.option("--id", "generic_id", default=None)
@click.option("--id-list", multiple=True, help="One or more IDs (repeat flag).")
@click.option("--fmt", default=None, help="Output format requested from the API.")
@click.pass_context
def analytics_run(ctx, query_name, drug_id, indication_id, action_id,
                  company_id, trial_id, generic_id, id_list, fmt):
    """Execute a named analytics query."""
    data = _analytics.run(
        _client(ctx),
        query_name=query_name,
        drug_id=drug_id,
        indication_id=indication_id,
        action_id=action_id,
        company_id=company_id,
        trial_id=trial_id,
        id=generic_id,
        id_list=list(id_list) if id_list else None,
        fmt=fmt,
    )
    print_output(ctx, data)


# ---------------------------------------------------------------------------
# ner
# ---------------------------------------------------------------------------

@cli.group()
@click.pass_context
def ner(ctx: click.Context) -> None:
    """Named entity recognition commands."""


@ner.command("match")
@click.argument("text")
@click.option("--urls/--no-urls", default=False, help="Include URLs in NER response.")
@click.pass_context
def ner_match(ctx, text, urls):
    """Match named entities in free text."""
    data = _ner.match(_client(ctx), text=text, include_urls=urls)
    print_output(ctx, data)


# ---------------------------------------------------------------------------
# company-analytics
# ---------------------------------------------------------------------------

@cli.group("company-analytics")
@click.pass_context
def company_analytics(ctx: click.Context) -> None:
    """Company analytics commands."""


@company_analytics.command("query-drugs")
@click.argument("query_name")
@click.option("--id-list", required=True, help="Comma-separated list of IDs.")
@click.pass_context
def company_analytics_query_drugs(ctx, query_name, id_list):
    """Run a drug analytics query (drugSalesActualAndForecast, drugPatentProductExpiry, drugPatentExpiryDetail)."""
    data = _company_analytics.query_drugs(_client(ctx), query_name, id_list.split(","))
    print_output(ctx, data)


@company_analytics.command("query-companies")
@click.argument("query_name")
@click.option("--id-list", required=True, help="Comma-separated list of IDs.")
@click.pass_context
def company_analytics_query_companies(ctx, query_name, id_list):
    """Run a company KPI query (companyPipelineSuccess, companyDrugFirstClass, etc.)."""
    data = _company_analytics.query_companies(_client(ctx), query_name, id_list.split(","))
    print_output(ctx, data)


@company_analytics.command("company-model")
@click.argument("company_id")
@click.pass_context
def company_analytics_company_model(ctx, company_id):
    """Get peer finder model for a company."""
    data = _company_analytics.get_company_model(_client(ctx), company_id)
    print_output(ctx, data)


@company_analytics.command("search-model")
@click.option("--query", required=True, help="Search query string.")
@click.pass_context
def company_analytics_search_model(ctx, query):
    """Search peer finder models."""
    data = _company_analytics.search_company_model(_client(ctx), query)
    print_output(ctx, data)


@company_analytics.command("similar-companies")
@click.argument("company_id")
@click.option("--hits", default=10, show_default=True, help="Number of similar companies to return.")
@click.pass_context
def company_analytics_similar_companies(ctx, company_id, hits):
    """Find similar companies using peer finder."""
    data = _company_analytics.get_similar_companies(_client(ctx), company_id, hits=hits)
    print_output(ctx, data)


@company_analytics.command("search-companies")
@click.option("--query", required=True, help="Search query string.")
@click.option("--offset", default=0, show_default=True)
@click.option("--hits", default=20, show_default=True)
@click.option("--sort-by", default=None)
@click.pass_context
def company_analytics_search_companies(ctx, query, offset, hits, sort_by):
    """Search companies in analytics context."""
    data = _company_analytics.search_companies(_client(ctx), query, offset=offset, hits=hits, sort_by=sort_by)
    print_output(ctx, data)


@company_analytics.command("get-company")
@click.argument("company_id")
@click.pass_context
def company_analytics_get_company(ctx, company_id):
    """Get company record in analytics context."""
    data = _company_analytics.get_company(_client(ctx), company_id)
    print_output(ctx, data)


@company_analytics.command("get-companies")
@click.argument("ids", nargs=-1, required=True)
@click.pass_context
def company_analytics_get_companies(ctx, ids):
    """Batch get companies."""
    data = _company_analytics.get_companies(_client(ctx), list(ids))
    print_output(ctx, data)


@company_analytics.command("search-drugs")
@click.option("--query", required=True, help="Search query string.")
@click.option("--offset", default=0, show_default=True)
@click.option("--hits", default=20, show_default=True)
@click.pass_context
def company_analytics_search_drugs(ctx, query, offset, hits):
    """Search drugs in analytics context."""
    data = _company_analytics.search_drugs(_client(ctx), query, offset=offset, hits=hits)
    print_output(ctx, data)


@company_analytics.command("search-deals")
@click.option("--query", required=True, help="Search query string.")
@click.option("--offset", default=0, show_default=True)
@click.option("--hits", default=20, show_default=True)
@click.pass_context
def company_analytics_search_deals(ctx, query, offset, hits):
    """Search deals in analytics context."""
    data = _company_analytics.search_deals(_client(ctx), query, offset=offset, hits=hits)
    print_output(ctx, data)


@company_analytics.command("search-patents")
@click.option("--query", required=True, help="Search query string.")
@click.option("--offset", default=0, show_default=True)
@click.option("--hits", default=20, show_default=True)
@click.pass_context
def company_analytics_search_patents(ctx, query, offset, hits):
    """Search patents in analytics context."""
    data = _company_analytics.search_patents(_client(ctx), query, offset=offset, hits=hits)
    print_output(ctx, data)


@company_analytics.command("id-map")
@click.argument("source_id")
@click.pass_context
def company_analytics_id_map(ctx, source_id):
    """Map IDs between CI and SI."""
    data = _company_analytics.id_map(_client(ctx), source_id)
    print_output(ctx, data)


# ---------------------------------------------------------------------------
# deals-intelligence
# ---------------------------------------------------------------------------

@cli.group("deals-intelligence")
@click.pass_context
def deals_intelligence(ctx: click.Context) -> None:
    """Deals intelligence commands (expanded deal records)."""


@deals_intelligence.command("search")
@click.option("--query", required=True, help="Search query string.")
@click.option("--offset", default=0, show_default=True)
@click.option("--hits", default=20, show_default=True)
@click.option("--sort-by", default=None)
@click.option("--filters-enabled", is_flag=True, default=False,
              help="Enable facet filters in response.")
@click.pass_context
def deals_intelligence_search(ctx, query, offset, hits, sort_by, filters_enabled):
    """Search expanded deal records."""
    data = _deals_intelligence.search_expanded(
        _client(ctx), query, offset=offset, hits=hits, sort_by=sort_by,
        filters_enabled=filters_enabled,
    )
    print_output(ctx, data)


@deals_intelligence.command("get")
@click.argument("deal_id")
@click.pass_context
def deals_intelligence_get(ctx, deal_id):
    """Get expanded deal record with full financials."""
    data = _deals_intelligence.get_expanded(_client(ctx), deal_id)
    print_output(ctx, data)


@deals_intelligence.command("records")
@click.argument("ids", nargs=-1, required=True)
@click.pass_context
def deals_intelligence_records(ctx, ids):
    """Batch get expanded deal records (up to 30)."""
    data = _deals_intelligence.get_expanded_batch(_client(ctx), list(ids))
    print_output(ctx, data)


@deals_intelligence.command("contracts")
@click.argument("deal_id")
@click.pass_context
def deals_intelligence_contracts(ctx, deal_id):
    """Get deal contract documents."""
    data = _deals_intelligence.get_contracts(_client(ctx), deal_id)
    print_output(ctx, data)


@deals_intelligence.command("contract-document")
@click.argument("deal_id")
@click.argument("contract_id")
@click.option("--fmt", default="pdf", type=click.Choice(["pdf", "txt"]), show_default=True,
              help="Output format.")
@click.option("--output", "output_file", default=None,
              help="Output file path (default: <contract_id>.<fmt>).")
@click.pass_context
def deals_intelligence_contract_document(ctx, deal_id, contract_id, fmt, output_file):
    """Get contract document as PDF or TXT."""
    result = _deals_intelligence.get_contract_document(_client(ctx), deal_id, contract_id, fmt=fmt)
    if fmt == "pdf":
        if not output_file:
            output_file = f"{contract_id}.pdf"
        with open(output_file, "wb") as f:
            f.write(result)
        click.echo(f"Saved to {output_file} ({len(result)} bytes)")
    else:
        if output_file:
            with open(output_file, "w") as f:
                f.write(result)
            click.echo(f"Saved to {output_file}")
        else:
            click.echo(result)


# ---------------------------------------------------------------------------
# drug-design
# ---------------------------------------------------------------------------

@cli.group("drug-design")
@click.pass_context
def drug_design(ctx: click.Context) -> None:
    """Drug design commands."""


@drug_design.command("pharmacology")
@click.option("--query", required=True, help="Search query string.")
@click.option("--offset", default=0, show_default=True)
@click.option("--hits", default=20, show_default=True)
@click.option("--sort-by", default=None)
@click.pass_context
def drug_design_pharmacology(ctx, query, offset, hits, sort_by):
    """Search pharmacology data."""
    data = _drug_design.search_pharmacology(_client(ctx), query, offset=offset, hits=hits, sort_by=sort_by)
    print_output(ctx, data)


@drug_design.command("pharmacokinetics")
@click.option("--query", required=True, help="Search query string.")
@click.option("--offset", default=0, show_default=True)
@click.option("--hits", default=20, show_default=True)
@click.option("--sort-by", default=None)
@click.pass_context
def drug_design_pharmacokinetics(ctx, query, offset, hits, sort_by):
    """Search pharmacokinetics data."""
    data = _drug_design.search_pharmacokinetics(_client(ctx), query, offset=offset, hits=hits, sort_by=sort_by)
    print_output(ctx, data)


@drug_design.command("search-drugs")
@click.option("--query", required=True, help="Search query string.")
@click.option("--offset", default=0, show_default=True)
@click.option("--hits", default=20, show_default=True)
@click.option("--sort-by", default=None)
@click.pass_context
def drug_design_search_drugs(ctx, query, offset, hits, sort_by):
    """Search drugs in SI domain."""
    data = _drug_design.search_drugs(_client(ctx), query, offset=offset, hits=hits, sort_by=sort_by)
    print_output(ctx, data)


@drug_design.command("get-drugs")
@click.argument("ids", nargs=-1, required=True)
@click.pass_context
def drug_design_get_drugs(ctx, ids):
    """Batch get drug records (up to 25 IDs)."""
    data = _drug_design.get_drugs(_client(ctx), list(ids))
    print_output(ctx, data)


@drug_design.command("molfile")
@click.argument("drug_id")
@click.pass_context
def drug_design_molfile(ctx, drug_id):
    """Get MOL file for a drug structure."""
    text = _drug_design.get_molfile(_client(ctx), drug_id)
    click.echo(text)


@drug_design.command("structure-image")
@click.argument("drug_id")
@click.option("--size", default="full", type=click.Choice(["tb", "full"]), show_default=True,
              help="Image size: tb (thumbnail) or full.")
@click.option("--output", "output_file", default=None,
              help="Output file path (default: <drug_id>_structure.<size>.png).")
@click.pass_context
def drug_design_structure_image(ctx, drug_id, size, output_file):
    """Get structure image for a drug."""
    data = _drug_design.get_structure_image(_client(ctx), drug_id, size=size)
    if not output_file:
        output_file = f"{drug_id}_structure_{size}.png"
    with open(output_file, "wb") as f:
        f.write(data)
    click.echo(f"Saved to {output_file} ({len(data)} bytes)")


@drug_design.command("references")
@click.argument("ids", nargs=-1, required=True)
@click.pass_context
def drug_design_references(ctx, ids):
    """Batch get reference records (up to 25)."""
    data = _drug_design.get_references(_client(ctx), list(ids))
    print_output(ctx, data)


@drug_design.command("patents")
@click.argument("ids", nargs=-1, required=True)
@click.pass_context
def drug_design_patents(ctx, ids):
    """Batch get patent records (up to 25)."""
    data = _drug_design.get_patents(_client(ctx), list(ids))
    print_output(ctx, data)


@drug_design.command("disease-briefings-search")
@click.option("--query", required=True, help="Search query string.")
@click.option("--offset", default=0, show_default=True)
@click.option("--hits", default=20, show_default=True)
@click.pass_context
def drug_design_disease_briefings_search(ctx, query, offset, hits):
    """Search disease briefings."""
    data = _drug_design.search_disease_briefings(_client(ctx), query, offset=offset, hits=hits)
    print_output(ctx, data)


@drug_design.command("disease-briefings")
@click.argument("ids", nargs=-1, required=True)
@click.pass_context
def drug_design_disease_briefings(ctx, ids):
    """Batch get disease briefing records (up to 10)."""
    data = _drug_design.get_disease_briefings(_client(ctx), list(ids))
    print_output(ctx, data)


@drug_design.command("disease-briefing-text")
@click.argument("briefing_id")
@click.argument("section_id")
@click.pass_context
def drug_design_disease_briefing_text(ctx, briefing_id, section_id):
    """Get disease briefing section text."""
    data = _drug_design.get_disease_briefing_text(_client(ctx), briefing_id, section_id)
    print_output(ctx, data)


@drug_design.command("disease-briefing-media")
@click.argument("filename")
@click.option("--output", "output_file", default=None,
              help="Output file path (default: <filename>).")
@click.pass_context
def drug_design_disease_briefing_media(ctx, filename, output_file):
    """Get embedded media from a disease briefing."""
    data = _drug_design.get_disease_briefing_multimedia(_client(ctx), filename)
    if not output_file:
        output_file = filename
    with open(output_file, "wb") as f:
        f.write(data)
    click.echo(f"Saved to {output_file} ({len(data)} bytes)")


# ---------------------------------------------------------------------------
# config
# ---------------------------------------------------------------------------

@cli.command("config")
@click.option("--env-file", default=".env", show_default=True,
              help="Path to the .env file to write credentials into.")
def config_cmd(env_file: str) -> None:
    """Interactively set Cortellis API credentials and save to a .env file.

    Prompts for CORTELLIS_USERNAME and CORTELLIS_PASSWORD, then writes
    (or updates) the given .env file so subsequent commands pick them up
    automatically.
    """
    import os
    import re

    click.echo("Cortellis credential setup")
    click.echo(f"Credentials will be written to: {os.path.abspath(env_file)}\n")

    username = click.prompt("CORTELLIS_USERNAME", default=os.environ.get("CORTELLIS_USERNAME", ""))
    password = click.prompt("CORTELLIS_PASSWORD", hide_input=True,
                            default=os.environ.get("CORTELLIS_PASSWORD", ""))

    # Read existing .env content (if any) so we can update in place
    existing_lines: list[str] = []
    if os.path.exists(env_file):
        with open(env_file) as fh:
            existing_lines = fh.readlines()

    def _upsert(lines: list[str], key: str, value: str) -> list[str]:
        """Replace an existing KEY=... line or append a new one."""
        pattern = re.compile(rf"^{re.escape(key)}\s*=")
        updated = False
        result = []
        for line in lines:
            if pattern.match(line):
                result.append(f"{key}={value}\n")
                updated = True
            else:
                result.append(line)
        if not updated:
            result.append(f"{key}={value}\n")
        return result

    existing_lines = _upsert(existing_lines, "CORTELLIS_USERNAME", username)
    existing_lines = _upsert(existing_lines, "CORTELLIS_PASSWORD", password)

    with open(env_file, "w") as fh:
        fh.writelines(existing_lines)
    os.chmod(env_file, 0o600)

    click.echo(f"\nCredentials saved to {os.path.abspath(env_file)}")
    click.echo("Run any cortellis command — credentials will be loaded automatically.")


# ---------------------------------------------------------------------------
# setup — full onboarding for new users
# ---------------------------------------------------------------------------

@cli.command("setup")
def setup_cmd() -> None:
    """First-time setup wizard for new users.

    Walks through: credentials, API connectivity test, AI engine check, and web UI build.
    """
    import os
    import shutil
    from pathlib import Path

    click.echo(_BANNER)
    click.echo("  Welcome to Cortellis CLI Setup!\n")

    # Step 1: Credentials
    click.echo("  Step 1/4: Cortellis API Credentials")
    click.echo("  " + "-" * 40)

    env_path = Path.cwd() / ".env"
    existing = {}
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                existing[k.strip()] = v.strip()

    current_user = existing.get("CORTELLIS_USERNAME", os.environ.get("CORTELLIS_USERNAME", ""))
    if current_user:
        click.echo(f"  Current username: {current_user}")
        if not click.confirm("  Update credentials?", default=False):
            username = current_user
            password = existing.get("CORTELLIS_PASSWORD", os.environ.get("CORTELLIS_PASSWORD", ""))
        else:
            username = click.prompt("  Username", default=current_user)
            password = click.prompt("  Password", hide_input=True)
    else:
        username = click.prompt("  Username")
        password = click.prompt("  Password", hide_input=True)

    existing["CORTELLIS_USERNAME"] = username
    existing["CORTELLIS_PASSWORD"] = password
    env_path.write_text("\n".join(f"{k}={v}" for k, v in existing.items()) + "\n")
    os.chmod(env_path, 0o600)
    click.echo(f"  Saved to {env_path}\n")

    # Step 2: Test API connectivity
    click.echo("  Step 2/4: Testing API Connection")
    click.echo("  " + "-" * 40)
    try:
        from cli_anything.cortellis.core.client import CortellisClient as _TestClient
        c = _TestClient(username=username, password=password)
        result = c.get("drugs-v2/drug/search", params={"query": "*", "hits": "1", "fmt": "json"})
        total = result.get("drugResultsOutput", {}).get("@totalResults", "?")
        click.echo(f"  Connected! ({total} drugs in database)")
        c.close()
    except Exception as e:
        click.echo(f"  Connection failed: {e}")
        click.echo("  Check your credentials and try again with: cortellis config")
    click.echo()

    # Step 3: AI engine check (for chat mode)
    click.echo("  Step 3/4: AI Chat Engine (for AI Chat Mode)")
    click.echo("  " + "-" * 40)
    import subprocess as _sp
    claude_bin = shutil.which("claude")
    codex_bin = shutil.which("codex")

    if claude_bin:
        click.echo("  Claude Code CLI found!")
        try:
            check = _sp.run([claude_bin, "--print", "-p", "say ok", "--max-turns", "1"],
                            capture_output=True, text=True, timeout=15)
            if check.returncode == 0:
                click.echo("  Authenticated! 'cortellis chat' is ready.")
            else:
                err = check.stderr.strip()
                if "login" in err.lower() or "auth" in err.lower() or "not logged" in err.lower():
                    click.echo("  Not logged in yet. Run this to authenticate:")
                    click.echo("    claude login")
                else:
                    click.echo("  'cortellis chat' should be ready.")
        except _sp.TimeoutExpired:
            click.echo("  Auth check timed out — 'cortellis chat' should still work.")
        except Exception:
            click.echo("  Could not verify auth — try 'cortellis chat' to test.")
    else:
        click.echo("  Claude Code CLI not found.")
        click.echo("  To enable AI chat mode with Claude, install Claude Code:")
        click.echo("    npm install -g @anthropic-ai/claude-code")
        click.echo("    claude login")

    if codex_bin:
        click.echo("  OpenAI Codex CLI found!")
        try:
            codex_check = _sp.run([codex_bin, "login", "status"],
                                  capture_output=True, text=True, timeout=10)
            if codex_check.returncode == 0:
                click.echo(f"  Authenticated! ({codex_check.stdout.strip()})")
                click.echo("  'cortellis --engine codex' is ready.")
            else:
                click.echo("  Not logged in yet. Run this to authenticate:")
                click.echo("    codex login --device-auth")
        except Exception:
            click.echo("  Could not verify auth — try: codex login --device-auth")
    else:
        click.echo("  OpenAI Codex CLI not found.")
        click.echo("  To enable AI chat mode with Codex, install it:")
        click.echo("    npm install -g @openai/codex")
        click.echo("    codex login --device-auth")

    if not claude_bin and not codex_bin:
        click.echo("  (Optional — all other commands work without an AI engine)")
    click.echo()

    # Step 4: Build web UI
    click.echo("  Step 4/4: Web UI")
    click.echo("  " + "-" * 40)
    try:
        import uvicorn  # noqa
        import fastapi  # noqa
    except ImportError:
        import sys as _sys
        in_venv = _sys.prefix != _sys.base_prefix
        if in_venv:
            click.echo("  Web dependencies missing — installing now…")
            result = _sp.run(
                [_sys.executable, "-m", "pip", "install", "fastapi>=0.115", "uvicorn[standard]>=0.30"],
                check=False,
            )
            if result.returncode != 0:
                click.echo("  Install failed. Run manually: pip install fastapi 'uvicorn[standard]'")
                return
        else:
            click.echo("  Web dependencies missing. Re-install cortellis-cli to pick them up:")
            click.echo("    pip install --upgrade git+https://github.com/uh-joan/cortellis-cli.git")
            return
    from pathlib import Path as _Path
    ui_dir = _Path(__file__).resolve().parents[2] / "web" / "ui"
    dist_dir = ui_dir / "dist"
    if dist_dir.exists():
        click.echo("  Web UI already built. Run: cortellis web")
    elif not shutil.which("npm"):
        click.echo("  node/npm not found — skipping web UI build.")
        click.echo("  Install Node.js from https://nodejs.org/ then run: cortellis web")
    else:
        click.echo("  Building web UI (takes ~30s)…")
        if not (ui_dir / "node_modules").exists():
            click.echo("  Installing UI dependencies…")
            _sp.run(["npm", "install"], cwd=str(ui_dir), check=True)
        result = _sp.run(["npm", "run", "build"], cwd=str(ui_dir))
        if result.returncode == 0:
            click.echo("  Web UI built. Run: cortellis web")
        else:
            click.echo("  Build failed. Try manually: cd web/ui && npm run build")
    click.echo()

    # Summary
    click.echo("  " + "=" * 50)
    click.echo("  Setup Complete!")
    click.echo("  " + "=" * 50)
    click.echo()
    click.echo("  Quick start:")
    click.echo("    cortellis drugs search --phase L --hits 5")
    click.echo("    cortellis --json companies search --query \"Pfizer\"")
    click.echo("    cortellis ontology search --term \"obesity\" --category indication")
    if claude_bin:
        click.echo("    cortellis chat                       # AI chat via Claude Code")
    if codex_bin:
        click.echo("    cortellis --engine codex chat        # AI chat via OpenAI Codex")
    click.echo()
    click.echo("  Run 'cortellis --help' to see all 17 command groups.")


# ---------------------------------------------------------------------------
# run-skill — harness mode: enforced step sequencing for skill workflows
# ---------------------------------------------------------------------------

@cli.group(name="run-skill")
def run_skill() -> None:
    """Run a skill workflow with enforced step sequencing (harness mode).

    Unlike invoking skills via the AI chat, this executes recipe scripts in
    guaranteed order and exits 1 on any step failure — no silent data gaps.
    """


@run_skill.command(name="landscape")
@click.argument("indication")
@click.option("--force-refresh", is_flag=True, help="Re-fetch even if wiki article is fresh")
@click.option("--review", is_flag=True, help="Pause for analyst approval before wiki compilation")
@click.option("--dry-run", is_flag=True, help="Print wave schedule without executing")
def run_skill_landscape(indication: str, force_refresh: bool, review: bool, dry_run: bool) -> None:
    """Run the full landscape pipeline for INDICATION with enforced step order.

    Example: cortellis run-skill landscape obesity
             cortellis run-skill landscape obesity --review
             cortellis run-skill landscape obesity --dry-run
    """
    import re
    from pathlib import Path
    from cli_anything.cortellis.core.harness_runner import HarnessRunner, REPO_ROOT

    workflow_yaml = Path(__file__).resolve().parent / "skills/landscape/workflow.yaml"
    runner = HarnessRunner(workflow_yaml)

    if dry_run:
        runner.dry_run()
        return

    slug = re.sub(r"[^a-z0-9]+", "-", indication.lower()).strip("-")
    output_dir = REPO_ROOT / "raw" / slug

    exit_code = runner.execute(
        indication,
        output_dir,
        dry_run=False,
        force_refresh=force_refresh,
        review=review,
    )
    if exit_code != 0:
        raise SystemExit(exit_code)


@run_skill.command(name="pipeline")
@click.argument("company")
@click.option("--force-refresh", is_flag=True, help="Re-fetch even if wiki article is fresh")
@click.option("--review", is_flag=True, help="Pause for analyst approval before wiki compilation")
@click.option("--dry-run", is_flag=True, help="Print wave schedule without executing")
def run_skill_pipeline(company: str, force_refresh: bool, review: bool, dry_run: bool) -> None:
    """Run the full pipeline workflow for COMPANY with enforced step order.

    Example: cortellis run-skill pipeline Pfizer
             cortellis run-skill pipeline Pfizer --review
             cortellis run-skill pipeline Pfizer --dry-run
    """
    import re
    from pathlib import Path
    from cli_anything.cortellis.core.harness_runner import HarnessRunner, REPO_ROOT

    workflow_yaml = Path(__file__).resolve().parent / "skills/pipeline/workflow.yaml"
    runner = HarnessRunner(workflow_yaml)

    if dry_run:
        runner.dry_run()
        return

    slug = re.sub(r"[^a-z0-9]+", "-", company.lower()).strip("-")
    output_dir = REPO_ROOT / "raw" / slug

    exit_code = runner.execute(
        company,
        output_dir,
        dry_run=False,
        force_refresh=force_refresh,
        review=review,
    )
    if exit_code != 0:
        raise SystemExit(exit_code)


@run_skill.command(name="drug-profile")
@click.argument("drug")
@click.option("--review", is_flag=True, help="Pause for analyst approval before wiki compilation")
@click.option("--dry-run", is_flag=True, help="Print wave schedule without executing")
def run_skill_drug_profile(drug: str, review: bool, dry_run: bool) -> None:
    """Run the full drug-profile pipeline for DRUG with enforced step order.

    Example: cortellis run-skill drug-profile semaglutide
             cortellis run-skill drug-profile tirzepatide --review
             cortellis run-skill drug-profile semaglutide --dry-run
    """
    import re
    from pathlib import Path
    from cli_anything.cortellis.core.harness_runner import HarnessRunner, REPO_ROOT

    workflow_yaml = Path(__file__).resolve().parent / "skills/drug-profile/workflow.yaml"
    runner = HarnessRunner(workflow_yaml)

    if dry_run:
        runner.dry_run()
        return

    slug = re.sub(r"[^a-z0-9]+", "-", drug.lower()).strip("-")
    output_dir = REPO_ROOT / "raw" / "drugs" / slug

    exit_code = runner.execute(drug, output_dir, review=review)
    if exit_code != 0:
        raise SystemExit(exit_code)


@run_skill.command(name="target-profile")
@click.argument("target")
@click.option("--review", is_flag=True, help="Pause for analyst approval before wiki compilation")
@click.option("--dry-run", is_flag=True, help="Print wave schedule without executing")
def run_skill_target_profile(target: str, review: bool, dry_run: bool) -> None:
    """Run the full target-profile pipeline for TARGET with enforced step order.

    Example: cortellis run-skill target-profile GLP-1
             cortellis run-skill target-profile EGFR --review
             cortellis run-skill target-profile PD-L1 --dry-run
    """
    import re
    from pathlib import Path
    from cli_anything.cortellis.core.harness_runner import HarnessRunner, REPO_ROOT

    workflow_yaml = Path(__file__).resolve().parent / "skills/target-profile/workflow.yaml"
    runner = HarnessRunner(workflow_yaml)

    if dry_run:
        runner.dry_run()
        return

    slug = re.sub(r"[^a-z0-9]+", "-", target.lower()).strip("-")
    output_dir = REPO_ROOT / "raw" / "targets" / slug

    exit_code = runner.execute(target, output_dir, review=review)
    if exit_code != 0:
        raise SystemExit(exit_code)


@run_skill.command(name="drug-comparison")
@click.argument("query")
@click.option("--dry-run", is_flag=True, help="Print wave schedule without executing")
def run_skill_drug_comparison(query: str, dry_run: bool) -> None:
    """Run the drug-comparison pipeline for QUERY (e.g. "tirzepatide vs semaglutide").

    Example: cortellis run-skill drug-comparison "tirzepatide vs semaglutide"
             cortellis run-skill drug-comparison "ozempic versus wegovy versus mounjaro"
             cortellis run-skill drug-comparison "tirzepatide vs semaglutide" --dry-run
    """
    import re
    from pathlib import Path
    from cli_anything.cortellis.core.harness_runner import HarnessRunner, REPO_ROOT

    workflow_yaml = Path(__file__).resolve().parent / "skills/drug-comparison/workflow.yaml"
    runner = HarnessRunner(workflow_yaml)

    if dry_run:
        runner.dry_run()
        return

    slug = re.sub(r"[^a-z0-9]+", "-", query.lower()).strip("-")
    output_dir = REPO_ROOT / "raw" / "comparisons" / slug

    exit_code = runner.execute(query, output_dir)
    if exit_code != 0:
        raise SystemExit(exit_code)


@run_skill.command(name="conference-intel")
@click.argument("query")
@click.option("--review", is_flag=True, help="Pause for analyst approval before wiki compilation")
@click.option("--dry-run", is_flag=True, help="Print wave schedule without executing")
def run_skill_conference_intel(query: str, review: bool, dry_run: bool) -> None:
    """Run the conference-intel pipeline for QUERY.

    Example: cortellis run-skill conference-intel "ASCO 2026"
             cortellis run-skill conference-intel "obesity conferences"
             cortellis run-skill conference-intel "ASCO 2026" --dry-run
    """
    import re
    from pathlib import Path
    from cli_anything.cortellis.core.harness_runner import HarnessRunner, REPO_ROOT

    workflow_yaml = Path(__file__).resolve().parent / "skills/conference-intel/workflow.yaml"
    runner = HarnessRunner(workflow_yaml)

    if dry_run:
        runner.dry_run()
        return

    slug = re.sub(r"[^a-z0-9]+", "-", query.lower()).strip("-")
    output_dir = REPO_ROOT / "raw" / "conferences" / slug

    exit_code = runner.execute(query, output_dir, review=review)
    if exit_code != 0:
        raise SystemExit(exit_code)


@run_skill.command(name="changelog")
@click.argument("indication")
@click.option("--dry-run", is_flag=True, help="Print wave schedule without executing")
def run_skill_changelog(indication: str, dry_run: bool) -> None:
    """Show competitive landscape history for INDICATION.

    Example: cortellis run-skill changelog obesity
             cortellis run-skill changelog MASH --dry-run
    """
    import re
    from pathlib import Path
    from cli_anything.cortellis.core.harness_runner import HarnessRunner, REPO_ROOT

    workflow_yaml = Path(__file__).resolve().parent / "skills/changelog/workflow.yaml"
    runner = HarnessRunner(workflow_yaml)

    if dry_run:
        runner.dry_run()
        return

    slug = re.sub(r"[^a-z0-9]+", "-", indication.lower()).strip("-")
    output_dir = REPO_ROOT / "raw" / slug

    exit_code = runner.execute(indication, output_dir)
    if exit_code != 0:
        raise SystemExit(exit_code)


@run_skill.command(name="ingest")
@click.argument("file_path")
@click.option("--dry-run", is_flag=True, help="Print wave schedule without executing")
def run_skill_ingest(file_path: str, dry_run: bool) -> None:
    """Ingest an internal document into the wiki.

    Example: cortellis run-skill ingest raw/internal/deal_memo.md
             cortellis run-skill ingest path/to/report.pdf --dry-run
    """
    import re
    from pathlib import Path
    from cli_anything.cortellis.core.harness_runner import HarnessRunner, REPO_ROOT

    workflow_yaml = Path(__file__).resolve().parent / "skills/ingest/workflow.yaml"
    runner = HarnessRunner(workflow_yaml)

    if dry_run:
        runner.dry_run()
        return

    slug = re.sub(r"[^a-z0-9]+", "-", Path(file_path).stem.lower()).strip("-")
    output_dir = REPO_ROOT / "raw" / "internal" / slug

    exit_code = runner.execute(file_path, output_dir)
    if exit_code != 0:
        raise SystemExit(exit_code)


# repl — interactive command REPL
# ---------------------------------------------------------------------------

@cli.command("repl")
@click.pass_context
def repl_cmd(ctx) -> None:
    """Launch interactive command REPL."""
    click.echo(_BANNER)
    from cli_anything.cortellis.utils.repl_skin import run_repl
    run_repl(cli, ctx)


# ---------------------------------------------------------------------------
# wiki — knowledge base management
# ---------------------------------------------------------------------------

@cli.group("wiki")
def wiki_group() -> None:
    """Manage the compiled wiki knowledge base."""


@wiki_group.command("refresh")
@click.option(
    "--fetch", "tier", flag_value=2, default=1,
    help="Tier 2: re-fetch structured data from APIs + recompile (no LLM).",
)
@click.option(
    "--full", "tier", flag_value=3,
    help="Tier 3: full refresh including LLM synthesis via HarnessRunner.",
)
@click.option(
    "--type", "types",
    default=None,
    help="Comma-separated entity types to refresh: drug,target,company,indication,conference.",
)
@click.option("--dry-run", is_flag=True, help="Show what would be refreshed without making changes.")
@click.option("--verbose/--quiet", default=True, show_default=True)
def wiki_refresh_cmd(tier, types, dry_run, verbose) -> None:
    """Refresh the wiki knowledge base.

    \b
    Tier 1 (default)  — recompile from existing raw/ data. Fast, no API calls.
    Tier 2 (--fetch)  — re-fetch structured + external data, then recompile.
    Tier 3 (--full)   — full refresh including LLM synthesis via HarnessRunner.

    \b
    Examples:
      cortellis wiki refresh                        # compile-only (all types)
      cortellis wiki refresh --fetch --type drug    # re-fetch drugs only
      cortellis wiki refresh --dry-run              # preview what would run
    """
    import sys as _sys
    from cli_anything.cortellis.core.wiki_refresh import refresh_compile, refresh_data, refresh_full

    type_set = None
    if types:
        type_set = {t.strip().lower() for t in types.split(",") if t.strip()}

    base_dir = "."

    tier_label = {1: "compile-only", 2: "fetch+compile", 3: "full"}.get(tier, "?")
    scope = ", ".join(sorted(type_set)) if type_set else "all"
    click.echo(f"\nWiki refresh — tier {tier} ({tier_label}), types: {scope}")
    if dry_run:
        click.echo("  [dry-run mode — no changes will be written]\n")

    try:
        if tier == 1:
            results = refresh_compile(base_dir, types=type_set, verbose=verbose, dry_run=dry_run)
        elif tier == 2:
            results = refresh_data(base_dir, types=type_set, verbose=verbose, dry_run=dry_run)
        else:
            results = refresh_full(base_dir, types=type_set, verbose=verbose, dry_run=dry_run)
    except NotImplementedError as exc:
        click.echo(f"\nError: {exc}", err=True)
        _sys.exit(1)

    ok = len(results.get("ok", []))
    skipped = len(results.get("skipped", []))
    errors = len(results.get("error", []))
    click.echo(f"\nDone — {ok} refreshed, {skipped} skipped, {errors} errors.")

    if results.get("skipped") and verbose:
        click.echo("\nSkipped:")
        for slug, reason in results["skipped"]:
            click.echo(f"  {slug}: {reason}")

    if results.get("error"):
        click.echo("\nErrors:")
        for slug, reason in results["error"]:
            click.echo(f"  {slug}: {reason}", err=True)


# ---------------------------------------------------------------------------
# web — browser-based chat UI
# ---------------------------------------------------------------------------

@cli.command("web")
@click.option("--host", default="127.0.0.1", show_default=True, help="Bind host.")
@click.option("--port", default=7337, show_default=True, help="Bind port.")
@click.option("--dev", is_flag=True, help="Run Vite dev server alongside FastAPI (hot reload).")
def web_cmd(host, port, dev) -> None:
    """Start the Cortellis web UI in your browser.

    Launches a FastAPI server that exposes the same intelligence capabilities
    as the CLI chat, accessible from any browser at http://<host>:<port>.

    For production (serves built React app):
      cortellis web

    For development (hot-reload UI):
      cortellis web --dev
      # Then open http://localhost:5173 (Vite proxy → FastAPI on 7337)
    """
    import shutil as _shutil
    import subprocess as _sp
    import sys as _sys
    from pathlib import Path as _Path

    import uvicorn  # noqa

    ui_dir = _Path(__file__).resolve().parents[2] / "web" / "ui"

    if dev:
        if not _shutil.which("npm"):  # noqa: needed for --dev npm check
            click.echo("Error: node/npm is required for --dev mode.", err=True)
            raise SystemExit(1)
        if not (ui_dir / "node_modules").exists():
            click.echo("  Installing UI dependencies (first run)…")
            _sp.run(["npm", "install"], cwd=str(ui_dir), check=True)
        vite = _sp.Popen(["npm", "run", "dev"], cwd=str(ui_dir))
        click.echo(f"  Vite dev server starting at http://localhost:5173")
        click.echo(f"  FastAPI backend at http://{host}:{port}")
        click.echo("  Press Ctrl-C to stop both servers.\n")
        import sys as _sys
        _repo = str(_Path(__file__).resolve().parents[2])
        if _repo not in _sys.path:
            _sys.path.insert(0, _repo)
        from web.server.main import app as _app
        try:
            uvicorn.run(_app, host=host, port=port, reload=False, log_level="info")
        finally:
            vite.terminate()
    else:
        dist = ui_dir / "dist"
        if not dist.exists():
            click.echo("Error: web UI not built. Run: cortellis setup", err=True)
            raise SystemExit(1)

        url = f"http://{host}:{port}"
        click.echo(f"\n  Cortellis Web UI → {url}")
        click.echo("  Press Ctrl-C to stop.\n")

        import sys as _sys
        _repo = str(_Path(__file__).resolve().parents[2])
        if _repo not in _sys.path:
            _sys.path.insert(0, _repo)
        from web.server.main import app as _app

        import threading as _th
        import webbrowser as _wb
        _th.Timer(1.2, lambda: _wb.open(url)).start()

        uvicorn.run(_app, host=host, port=port, reload=False, log_level="warning")


# ---------------------------------------------------------------------------
# chat — AI-powered natural language interface via Claude Code
# ---------------------------------------------------------------------------

def chat_cmd(debug, engine="claude", no_flush=False) -> None:
    """Start an AI chat session for querying Cortellis in natural language.

    Launches an AI engine (Claude Code or Codex) with Cortellis knowledge pre-loaded.
    Ask questions like "show me Phase 3 drugs for obesity" and get answers.
    Requires 'claude' (Claude Code) or 'codex' (OpenAI Codex) CLI.
    """
    import json as _json
    import shutil
    import subprocess
    from pathlib import Path

    engine = (engine or "claude").lower()
    if engine == "codex":
        ai_bin = shutil.which("codex")
        if not ai_bin:
            click.echo("Error: 'codex' CLI not found. Install OpenAI Codex:")
            click.echo("  npm install -g @openai/codex")
            click.echo("  export OPENAI_API_KEY=<your-key>")
            raise SystemExit(1)
        click.echo(_BANNER)
        click.echo("  Cortellis AI Chat — powered by Codex")
        click.echo("  Ask questions naturally. Type 'exit' or Ctrl-D to quit.\n")
    else:
        ai_bin = shutil.which("claude")
        if not ai_bin:
            click.echo("Error: 'claude' CLI not found. Install Claude Code first.")
            click.echo("  https://docs.anthropic.com/en/docs/claude-code")
            raise SystemExit(1)
        click.echo(_BANNER)
        click.echo("  Cortellis AI Chat — powered by Claude Code")
        click.echo("  Ask questions naturally. Type 'exit' or Ctrl-D to quit.\n")

    # Load all skills from skills/*/SKILL.md
    skills_dir = Path(__file__).parent / "skills"
    skill_parts = []
    for skill_dir in sorted(skills_dir.iterdir()):
        skill_file = skill_dir / "SKILL.md" if skill_dir.is_dir() else None
        if skill_file and skill_file.exists():
            skill_parts.append(skill_file.read_text())
    skill_content = "\n\n".join(skill_parts)

    # Inject wiki INDEX if available — enables cross-session knowledge
    wiki_index_path = os.path.join(os.getcwd(), "wiki", "INDEX.md")
    wiki_index_section = ""
    if os.path.exists(wiki_index_path):
        wiki_index_content = Path(wiki_index_path).read_text()
        wiki_index_section = (
            "\n\n## Available Compiled Knowledge\n\n"
            "CRITICAL RULE: ALWAYS check the wiki BEFORE making any API calls. "
            "If the answer exists in a compiled article, use it. "
            "Only call the Cortellis API when the wiki does not have the information "
            "or the user explicitly asks for a fresh analysis.\n\n"
            "Before fetching drug lists, company data, or landscape information from the API, "
            "first read the relevant wiki article. For example, if the user asks about "
            "approved drugs for obesity, read wiki/indications/obesity.md or raw/obesity/launched.csv "
            "instead of searching the API again.\n\n"
            "To read a compiled article: cat wiki/indications/<slug>.md\n"
            "To read a company profile: cat wiki/companies/<slug>.md\n"
            "To read raw drug lists: cat raw/<slug>/launched.csv (or phase3.csv, etc.)\n"
            "To compare indications: python3 $RECIPES/portfolio_report.py\n"
            "To check what changed: python3 $RECIPES/diff_landscape.py <slug>\n\n"
            f"{wiki_index_content}"
        )

    # Inject strategic signals if wiki has temporal data
    signals_section = ""
    try:
        from cli_anything.cortellis.utils.intelligence import extract_signals, format_signals_for_prompt
        wiki_path = os.path.join(os.getcwd(), "wiki")
        if os.path.isdir(wiki_path):
            signals = extract_signals(wiki_path)
            signals_section = format_signals_for_prompt(signals) if signals else ""
    except Exception:
        pass

    # Inject recent analysis insights
    insights_section = ""
    try:
        from cli_anything.cortellis.utils.insights_extractor import load_recent_insights, format_insights_for_prompt
        wiki_path = os.path.join(os.getcwd(), "wiki")
        if os.path.isdir(wiki_path):
            recent = load_recent_insights(wiki_path, max_age_days=30)
            insights_section = format_insights_for_prompt(recent) if recent else ""
    except Exception:
        pass

    # Inject daily session log — what happened in previous sessions
    daily_log_section = ""
    daily_dir = os.path.join(os.getcwd(), "daily")
    if os.path.isdir(daily_dir):
        from datetime import datetime as _dt, timedelta as _td, timezone as _tz
        now = _dt.now(_tz.utc)
        for offset in range(3):
            date_str = (now - _td(days=offset)).strftime("%Y-%m-%d")
            log_path = os.path.join(daily_dir, f"{date_str}.md")
            if os.path.exists(log_path):
                content = Path(log_path).read_text(encoding="utf-8")
                lines = content.strip().split("\n")
                if len(lines) > 40:
                    content = "\n".join(lines[-40:])
                daily_log_section = (
                    "\n\n## What Happened in Previous Sessions\n\n"
                    "You have a persistent knowledge base that accumulates across sessions. "
                    "The following is a log of recent conversations and analyses. "
                    "When the user asks what you discussed previously, refer to this — "
                    "it IS your memory from past sessions.\n\n"
                    f"{content}\n"
                )
                break

    # Build the system prompt
    venv_activate = str(Path(__file__).resolve().parents[2] / ".venv" / "bin" / "activate")
    # Prefix that activates venv + runs cortellis in one shot
    run = f"source {venv_activate} && cortellis --json"

    system_prompt = f"""You are a Cortellis pharmaceutical intelligence assistant.
You answer questions about drugs, companies, deals, clinical trials, regulatory events,
conferences, literature, press releases, ontology, and analytics using the Cortellis API.

CRITICAL RULE: Every Bash command MUST start with this exact prefix:
  {run}

Never try to run `cortellis` without this prefix. Never try to find or check the venv path. Just use the prefix above every single time.

{skill_content}
{wiki_index_section}
{signals_section}
{insights_section}
{daily_log_section}

WORKFLOW:
1. User asks a question
2. You run one or more Bash commands using the prefix above
3. You summarize the JSON results in clear, conversational language

EXAMPLES:
- "what drugs are in phase 3 for obesity?" →
  First: {run} ontology search --term "obesity" --category indication
  Then use the ID: {run} drugs search --phase C3 --indication 238 --hits 10

- "tell me about tirzepatide" →
  {run} drugs get 101964 --category report

- "show me Pfizer deals" →
  {run} deals search --principal "Pfizer" --hits 10

- "find launched drugs for diabetes in the US" →
  {run} ontology search --term "diabetes" --category indication
  Then: {run} drugs search --phase L --indication <ID> --country US --hits 20

IMPORTANT: Indication, company, and country filters use numeric IDs. Always look up IDs first with ontology search if the user gives you a name.

STRICT DATA RULES:
1. ONLY report data returned by cortellis. Never add drugs/companies/trials from your training data.
2. Give exact numbers. Never say "~8" or "6-7". If the query returned 8 results, say "8".
3. If data is missing from results, say "not in the Cortellis results". Do NOT fill gaps from memory.
4. Never mention drugs that did not appear in the query results.
5. Check wiki/ articles and compiled knowledge FIRST. Only call the CLI if the wiki doesn't have the answer or the user asks for fresh data.
6. ALWAYS list ALL items in tables. NEVER truncate with "+ N others" or summaries. Show every entry the API returned. A drug CAN appear in multiple phase tables — that's correct (e.g. semaglutide is Launched for T2D but Phase 3 for Alzheimer's). Show it in BOTH tables with the relevant indication for that phase.

SKILL AUTO-ROUTING (CRITICAL — follow these rules EVERY time):
You have workflow skills that produce comprehensive, structured analysis. Use them AUTOMATICALLY when the question matches:

| Question about... | Use skill | Examples |
|---|---|---|
| A company's drugs/pipeline/portfolio | /pipeline | "what's Pfizer's pipeline?", "show me Novo Nordisk drugs", "Aexon Labs portfolio" |
| An indication's competitive landscape | /landscape | "obesity landscape", "who's competing in NSCLC?", "breast cancer market overview" |
| A target/mechanism landscape | /landscape --target | "/landscape --target GLP-1 receptor", "landscape --target PD-L1", "EGFR competitive landscape" |
| Technology/modality landscape | /landscape --technology | "ADC landscape", "mRNA competitive landscape", "gene therapy market overview" |
| A specific drug in depth | /drug-profile | "deep dive on tirzepatide", "drug profile semaglutide", "full report on Keytruda" |

The user can also invoke skills explicitly with /pipeline, /landscape, etc.

When a skill applies (auto-detected or explicitly invoked), follow its Workflow section EXACTLY:
- Run EVERY step in the workflow. Do not skip any.
- Use the skill's recipes (Python scripts and bash scripts) as documented.
- If the question starts with [SKILL: Use the /X skill workflow], you MUST use that skill.

For SIMPLE factual questions that don't need a full workflow (e.g. "how many Phase 3 drugs for diabetes?", "what's drug ID 101964?"), just run the CLI directly.

CRITICAL: --company and --indication take NUMERIC IDs, not names. Always resolve IDs first via companies search or ontology search.

All skills and their workflows are included below in the system context."""

    turn_number = 0
    first_turn = True

    # In-session + cross-session 5-turn conversation history
    conversation_history: list[dict] = []
    try:
        import json as _jh
        from datetime import datetime as _dth, timezone as _tzh
        _hist_path = os.path.join(os.getcwd(), "daily",
                                  f"{_dth.now(_tzh.utc).strftime('%Y-%m-%d')}.json")
        if os.path.exists(_hist_path):
            conversation_history = _jh.loads(Path(_hist_path).read_text())[-5:]
    except Exception:
        pass

    while True:
        try:
            question = input("  you> ").strip()
        except (EOFError, KeyboardInterrupt):
            if not no_flush:
                try:
                    from cli_anything.cortellis.utils.session_memory import flush_session_memory
                    recompiled = flush_session_memory()
                    if recompiled:
                        click.echo(f"\n  Updated wiki for: {', '.join(recompiled)}")
                except Exception:
                    pass
            click.echo("\n  Goodbye!")
            break

        if not question:
            continue
        if question.lower() in ("exit", "quit", "/exit"):
            if not no_flush:
                try:
                    from cli_anything.cortellis.utils.session_memory import flush_session_memory
                    recompiled = flush_session_memory()
                    if recompiled:
                        click.echo(f"  Updated wiki for: {', '.join(recompiled)}")
                except Exception:
                    pass
            click.echo("  Goodbye!")
            break

        from cli_anything.cortellis.core.status_translator import translate_command
        from cli_anything.cortellis.core.skill_router import detect_skill
        from cli_anything.cortellis.core.context_detector import needs_context, detect_multi_entity

        # Detect context need BEFORE any rewriting (uses original question)
        turn_number += 1
        use_context = needs_context(question, turn_number)

        # Handle explicit /skill invocations — strip the / to prevent
        # Claude Code from interpreting it as a slash command
        CORTELLIS_SKILLS = {"pipeline", "landscape", "drug-profile", "drug-comparison", "conference-intel", "target-profile", "signals"}
        if question.startswith("/"):
            skill_name = question.split()[0][1:].lower()
            if skill_name in CORTELLIS_SKILLS:
                args = question[len(skill_name) + 1:].strip()
                question = f"[SKILL: Use the /{skill_name} skill workflow] {args}"
                use_context = False  # Explicit skill invocation always starts fresh

        # Auto-detect skill and prepend directive for natural language queries
        skill_directive = detect_skill(question)
        routed_question = f"{skill_directive}{question}" if skill_directive else question

        # Parallel dispatch hint: prepend when 2+ entities detected for the same skill
        multi = detect_multi_entity(question)
        if multi and len(multi['entities']) >= 2:
            entity_list = ', '.join(f'"{e}"' for e in multi['entities'])
            routed_question = (
                f"[PARALLEL DISPATCH: This query covers {len(multi['entities'])} entities "
                f"({entity_list}) for the /{multi['skill']} skill. "
                f"Run each as a separate Agent invocation with run_in_background=true "
                f"so they execute concurrently. Synthesize results after all complete.]\n"
                + routed_question
            )

        # Wiki fast-path: inject ANY matching wiki articles (indications, drugs, companies)
        from cli_anything.cortellis.core.skill_router import check_wiki_fast_path
        from cli_anything.cortellis.utils.wiki import read_article as _read_wiki

        wiki_context = ""

        # 1. Check landscape fast-path (existing)
        wiki_article_path = check_wiki_fast_path(question)
        if wiki_article_path:
            art = _read_wiki(wiki_article_path)
            if art:
                wiki_context = (
                    "\n\n--- COMPILED WIKI ARTICLE ---\n"
                    "A compiled article is available. "
                    "Use it to answer the question. Only call the API "
                    "if the user explicitly requests fresh data or asks "
                    "for something not in this article.\n\n"
                    f"Title: {art['meta'].get('title', 'Unknown')}\n"
                    f"Compiled: {art['meta'].get('compiled_at', 'Unknown')}\n\n"
                    f"{art['body']}\n"
                    "--- END COMPILED ARTICLE ---\n"
                )

        # 2. Scan wiki/drugs/ and wiki/companies/ for entity matches
        if not wiki_context:
            wiki_dir = os.path.join(os.getcwd(), "wiki")
            question_lower = question.lower()
            matched_articles = []
            for article_type in ("drugs", "companies"):
                type_dir = os.path.join(wiki_dir, article_type)
                if not os.path.isdir(type_dir):
                    continue
                for fname in os.listdir(type_dir):
                    if not fname.endswith(".md"):
                        continue
                    slug = fname[:-3]
                    # Check if slug words appear in question
                    slug_words = slug.replace("-", " ")
                    # Match if any significant slug word (>3 chars) appears in question
                    if any(w in question_lower for w in slug_words.split() if len(w) > 3):
                        art = _read_wiki(os.path.join(type_dir, fname))
                        if art and art["meta"]:
                            matched_articles.append(art)
                        if len(matched_articles) >= 3:  # cap at 3 to stay within context
                            break
                if len(matched_articles) >= 3:
                    break

            if matched_articles:
                parts = ["\n\n--- COMPILED WIKI ARTICLES ---\n"
                         "These wiki articles match your question. "
                         "Use them to answer. Only call the API if the information is missing.\n\n"]
                for art in matched_articles:
                    parts.append(f"### {art['meta'].get('title', 'Unknown')} "
                                 f"(compiled: {art['meta'].get('compiled_at', '?')[:10]})\n\n")
                    # Include body but cap per article to manage context
                    body = art["body"]
                    if len(body) > 5000:
                        body = body[:5000] + "\n\n_[Article truncated — read full: cat wiki/...]_\n"
                    parts.append(f"{body}\n\n")
                parts.append("--- END COMPILED ARTICLES ---\n")
                wiki_context = "".join(parts)

        history_block = ""
        if conversation_history:
            _hlines = ["\n\n## Recent Conversation\n\n"]
            for _t in conversation_history[-5:]:
                _a = _t["a"][:400] + ("..." if len(_t["a"]) > 400 else "")
                _hlines.append(f"**User:** {_t['q']}\n\n**Assistant:** {_a}\n\n---\n\n")
            history_block = "".join(_hlines)
        effective_prompt = system_prompt + wiki_context + history_block

        text = ""
        if engine == "codex":
            # codex exec: non-interactive mode with sandboxed auto-approval.
            # System context is prepended to the message (no --append-system-prompt equiv).
            # Final answer is written to a temp file via --output-last-message for clean capture.
            import tempfile as _tmpfile
            _codex_out = _tmpfile.mktemp(suffix=".txt")
            _has_session_memory = bool(daily_log_section or insights_section)
            _memory_rule = (
                "MEMORY RULE: Sections labeled 'What Happened in Previous Sessions' "
                "are your ONLY source of truth about past conversations. "
                "When asked what was discussed, report ONLY what appears in those sections — "
                "nothing more. Do NOT add context, code changes, PR numbers, test results, "
                "or anything else from your training data. If it is not in the memory sections, "
                "it did not happen as far as you are concerned."
                if _has_session_memory else
                "MEMORY RULE: No session memory is available for this workspace. "
                "If asked what was discussed previously, say exactly: "
                "'I have no memory of previous sessions in this workspace.' "
                "Do not fabricate any session history from training data."
            )
            full_message = f"{_memory_rule}\n\n{effective_prompt}\n\n---\n\n{routed_question}"
            cmd = [ai_bin, "exec", "--dangerously-bypass-approvals-and-sandbox", "--ephemeral",
                   "-C", os.getcwd(),
                   "--output-last-message", _codex_out,
                   full_message]
        else:
            cmd = [ai_bin, "--print", "-p", routed_question,
                   "--append-system-prompt", effective_prompt,
                   "--allowedTools", "Bash",
                   "--output-format", "stream-json", "--verbose"]
            if use_context and not first_turn:
                cmd.append("--continue")

        # Show spinner while waiting for output; in non-debug mode update status
        # dynamically as tool calls stream in, printing each status as a new line.
        import threading
        import itertools
        import time

        # [label, needs_newline]
        # needs_newline: True while spinner is actively overwriting the current line
        spinner_state = ["Querying Cortellis", False]
        stop_spinner = threading.Event()

        t_start = time.time()

        def spin():
            dots = itertools.cycle(["", ".", "..", "..."])
            while not stop_spinner.is_set():
                elapsed = int(time.time() - t_start)
                d = next(dots)
                label = spinner_state[0]
                line = f"  {label}{d:<3s}  ({elapsed}s)"
                sys.stdout.write(f"\r{line:<80s}")
                sys.stdout.flush()
                spinner_state[1] = True
                time.sleep(0.4)

        spinner_thread = threading.Thread(target=spin, daemon=True)
        spinner_thread.start()

        popen_kwargs = dict(stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        if engine == "codex":
            # Prevent codex from blocking on stdin
            popen_kwargs["stdin"] = subprocess.DEVNULL
        proc = subprocess.Popen(cmd, **popen_kwargs)
        first_output = True

        if engine == "codex":
            # Drain stdout (codex exec streams tool-call activity there) but
            # the clean final answer is in _codex_out written by --output-last-message.
            for _ in iter(proc.stdout.readline, b""):
                pass
            stop_spinner.set()
            spinner_thread.join()
            elapsed = int(time.time() - t_start)
            if spinner_state[1]:
                sys.stdout.write(f"\r  Answered in {elapsed}s" + " " * 40 + "\n\n")
            else:
                sys.stdout.write(f"  Answered in {elapsed}s\n\n")
            sys.stdout.flush()
            text = ""
            if os.path.exists(_codex_out):
                with open(_codex_out, encoding="utf-8") as _f:
                    text = _f.read().strip()
                os.unlink(_codex_out)
            if not text:
                text = "[No response from Codex]"
            sys.stdout.write(text)
            if not text.endswith("\n"):
                sys.stdout.write("\n")
            sys.stdout.flush()

            # Append turn log to daily/<date>.md so future sessions have memory.
            # Uses same file as Claude Code session hooks but with [Codex] marker —
            # both append, neither overwrites, no conflict.
            if not no_flush:
                try:
                    from datetime import datetime as _dt2, timezone as _tz2
                    _now = _dt2.now(_tz2.utc)
                    _daily_dir = os.path.join(os.getcwd(), "daily")
                    os.makedirs(_daily_dir, exist_ok=True)
                    _log_path = os.path.join(_daily_dir, f"{_now.strftime('%Y-%m-%d')}.md")
                    _entry = (
                        f"\n\n---\n\n"
                        f"### [Codex] Turn ({_now.strftime('%H:%M:%S')} UTC)\n\n"
                        f"**Q:** {routed_question[:300]}\n\n"
                        f"**A:** {text[:500]}{'...' if len(text) > 500 else ''}\n"
                    )
                    if not os.path.exists(_log_path):
                        with open(_log_path, "w", encoding="utf-8") as _lf:
                            _lf.write(f"# Daily Log — {_now.strftime('%Y-%m-%d')}\n")
                    with open(_log_path, "a", encoding="utf-8") as _lf:
                        _lf.write(_entry)
                except Exception:
                    pass
        else:
            # Parse stream-json to show tool calls + final answer
            for line in iter(proc.stdout.readline, b""):
                decoded = line.decode("utf-8", errors="replace").strip()
                if not decoded:
                    continue
                try:
                    event = _json.loads(decoded)
                except _json.JSONDecodeError:
                    continue

                etype = event.get("type", "")

                # Tool calls are inside assistant message content array
                if etype == "assistant" and "message" in event:
                    content = event["message"].get("content", [])
                    if isinstance(content, list):
                        for block in content:
                            if block.get("type") == "tool_use":
                                tool = block.get("name", "?")
                                inp = block.get("input", {})
                                if tool == "Bash" and "command" in inp:
                                    cmd_str = inp["command"]
                                    if debug:
                                        # Stop spinner and print raw command
                                        if first_output:
                                            stop_spinner.set()
                                            spinner_thread.join()
                                            if spinner_state[1]:
                                                sys.stdout.write("\n")
                                            first_output = False
                                        if "cortellis" in cmd_str:
                                            short = cmd_str.split("cortellis", 1)[1].strip()
                                            sys.stdout.write(f"  > cortellis {short}\n")
                                        else:
                                            sys.stdout.write(f"  > {cmd_str[:80]}\n")
                                        sys.stdout.flush()
                                    else:
                                        # Update spinner: commit current line, start new status
                                        new_status = translate_command(cmd_str)
                                        if new_status:
                                            if spinner_state[1]:
                                                elapsed = int(time.time() - t_start)
                                                line = f"  {spinner_state[0]}  ({elapsed}s)"
                                                sys.stdout.write(f"\r{line:<80s}\n")
                                                sys.stdout.flush()
                                                spinner_state[1] = False
                                            spinner_state[0] = new_status
                                elif debug:
                                    if first_output:
                                        stop_spinner.set()
                                        spinner_thread.join()
                                        if spinner_state[1]:
                                            sys.stdout.write("\n")
                                        first_output = False
                                    sys.stdout.write(f"  > {tool}\n")
                                    sys.stdout.flush()

                elif etype == "result":
                    # Stop spinner and print final answer
                    stop_spinner.set()
                    spinner_thread.join()
                    if spinner_state[1]:
                        elapsed = int(time.time() - t_start)
                        sys.stdout.write(f"\r  Answered in {elapsed}s" + " " * 40 + "\n\n")
                        sys.stdout.flush()
                    elif first_output:
                        elapsed = int(time.time() - t_start)
                        sys.stdout.write(f"  Answered in {elapsed}s\n\n")
                        sys.stdout.flush()
                    first_output = False
                    text = event.get("result", "")
                    sys.stdout.write(text)
                    if not text.endswith("\n"):
                        sys.stdout.write("\n")
                    sys.stdout.flush()

            if first_output or (not stop_spinner.is_set()):
                stop_spinner.set()
                spinner_thread.join()
                if spinner_state[1]:
                    elapsed = int(time.time() - t_start)
                    sys.stdout.write(f"\r  Answered in {elapsed}s" + " " * 40 + "\n\n")
                    sys.stdout.flush()

        proc.wait()
        click.echo()

        # Append Q&A to history and persist for cross-session recall
        if text:
            conversation_history.append({"q": question[:300], "a": text[:600]})
            if len(conversation_history) > 5:
                conversation_history = conversation_history[-5:]
            try:
                import json as _jsave
                from datetime import datetime as _dts, timezone as _tzs
                _hdir = os.path.join(os.getcwd(), "daily")
                os.makedirs(_hdir, exist_ok=True)
                _hpath = os.path.join(_hdir, f"{_dts.now(_tzs.utc).strftime('%Y-%m-%d')}.json")
                Path(_hpath).write_text(_jsave.dumps(conversation_history, indent=2))
            except Exception:
                pass

        first_turn = False
